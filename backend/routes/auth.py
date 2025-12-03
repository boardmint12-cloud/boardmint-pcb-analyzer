"""
Authentication Routes
Handles signup, login, and user profile
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from supabase_client import get_supabase
from auth_middleware import verify_token, optional_auth, AuthContext
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization_name: Optional[str] = None
    invite_token: Optional[str] = None


class SignupResponse(BaseModel):
    user_id: str
    email: str
    organization_id: str
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    organization_id: str
    organization_name: str
    created_at: str


class AcceptInviteRequest(BaseModel):
    token: str
    email: EmailStr
    password: str
    full_name: str


# ============================================
# ROUTES
# ============================================

@router.post("/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    """
    Sign up new user.
    
    Two modes:
    1. New organization (no invite_token) - Creates org + user as admin
    2. Join existing org (with invite_token) - Joins org as employee
    """
    supabase = get_supabase()
    
    try:
        # Check if user already exists
        existing = supabase.table("users").select("email").eq("email", request.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Mode 1: Accepting invite (join existing org)
        if request.invite_token:
            # Verify invite
            invite = (
                supabase.table("organization_invites")
                .select("*")
                .eq("token", request.invite_token)
                .eq("email", request.email)
                .is_("accepted_at", "null")
                .single()
                .execute()
            )
            
            if not invite.data:
                raise HTTPException(status_code=400, detail="Invalid or expired invite")
            
            invite_data = invite.data
            
            # Check if expired
            from datetime import datetime
            if datetime.fromisoformat(invite_data["expires_at"].replace("Z", "+00:00")) < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Invite has expired")
            
            # Create user with organization context
            user_metadata = {
                "full_name": request.full_name,
                "organization_id": invite_data["organization_id"],
                "role": invite_data["role"]
            }
            
            auth_result = supabase.auth.sign_up({
                "email": request.email,
                "password": request.password,
                "options": {
                    "data": user_metadata
                }
            })
            
            # Mark invite as accepted
            supabase.table("organization_invites").update({
                "accepted_at": datetime.utcnow().isoformat()
            }).eq("id", invite_data["id"]).execute()
            
            logger.info(f"✓ User {request.email} joined organization via invite")
            
            return {
                "user_id": auth_result.user.id,
                "email": request.email,
                "organization_id": invite_data["organization_id"],
                "message": "Successfully joined organization"
            }
        
        # Mode 2: New organization (no invite)
        else:
            org_name = request.organization_name or f"{request.full_name}'s Organization"
            org_slug = org_name.lower().replace(" ", "-").replace("'", "")
            
            user_metadata = {
                "full_name": request.full_name,
                "organization_name": org_name,
                "organization_slug": org_slug
            }
            
            auth_result = supabase.auth.sign_up({
                "email": request.email,
                "password": request.password,
                "options": {
                    "data": user_metadata
                }
            })
            
            # Get the created organization ID
            user_record = supabase.table("users").select("organization_id").eq("id", auth_result.user.id).single().execute()
            
            logger.info(f"✓ New user {request.email} created organization {org_name}")
            
            return {
                "user_id": auth_result.user.id,
                "email": request.email,
                "organization_id": user_record.data["organization_id"],
                "message": "Account created successfully"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login existing user"""
    supabase = get_supabase()
    
    try:
        # Authenticate with Supabase
        auth_result = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        # Update last login
        supabase.table("users").update({
            "last_login": auth_result.user.last_sign_in_at
        }).eq("id", auth_result.user.id).execute()
        
        logger.info(f"✓ User {request.email} logged in")
        
        return {
            "access_token": auth_result.session.access_token,
            "refresh_token": auth_result.session.refresh_token,
            "user": {
                "id": auth_result.user.id,
                "email": auth_result.user.email,
                "last_sign_in_at": auth_result.user.last_sign_in_at
            }
        }
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
async def logout(auth: AuthContext = Depends(verify_token)):
    """Logout current user"""
    supabase = get_supabase()
    
    try:
        supabase.auth.sign_out()
        logger.info(f"✓ User {auth.email} logged out")
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user(auth: AuthContext = Depends(verify_token)):
    """Get current user profile"""
    supabase = get_supabase()
    
    try:
        # Get user with organization info
        result = (
            supabase.table("users")
            .select("*, organizations(name)")
            .eq("id", auth.user_id)
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = result.data
        
        return {
            "id": user_data["id"],
            "email": user_data["email"],
            "full_name": user_data.get("full_name"),
            "role": user_data["role"],
            "organization_id": user_data["organization_id"],
            "organization_name": user_data["organizations"]["name"],
            "created_at": user_data["created_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")


@router.get("/verify-invite/{token}")
async def verify_invite(token: str):
    """Verify invite token is valid"""
    supabase = get_supabase()
    
    try:
        invite = (
            supabase.table("organization_invites")
            .select("*, organizations(name)")
            .eq("token", token)
            .is_("accepted_at", "null")
            .single()
            .execute()
        )
        
        if not invite.data:
            raise HTTPException(status_code=404, detail="Invalid or already accepted invite")
        
        # Check if expired
        from datetime import datetime
        expires_at = datetime.fromisoformat(invite.data["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Invite has expired")
        
        return {
            "valid": True,
            "email": invite.data["email"],
            "organization_name": invite.data["organizations"]["name"],
            "role": invite.data["role"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify invite: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify invite")


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    supabase = get_supabase()
    
    try:
        auth_result = supabase.auth.refresh_session(refresh_token)
        
        return {
            "access_token": auth_result.session.access_token,
            "refresh_token": auth_result.session.refresh_token
        }
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
