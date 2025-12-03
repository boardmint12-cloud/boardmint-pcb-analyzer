"""
Organization Management Routes
Handles organization CRUD, member management, and invites
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
from supabase_client import get_supabase
from auth_middleware import verify_token, verify_admin, AuthContext
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organizations", tags=["organizations"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    max_users: int
    max_projects: int
    created_at: datetime


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = None
    settings: Optional[dict] = None


class MemberResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    created_at: datetime
    last_login: Optional[datetime]


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "employee"  # employee, admin, viewer


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    invite_link: str
    expires_at: datetime


# ============================================
# ROUTES
# ============================================

@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(auth: AuthContext = Depends(verify_token)):
    """Get current user's organization details"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("organizations").select("*").eq("id", auth.organization_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        return result.data
        
    except Exception as e:
        logger.error(f"Failed to fetch organization: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch organization")


@router.put("/current", response_model=OrganizationResponse)
async def update_organization(
    update: UpdateOrganizationRequest,
    auth: AuthContext = Depends(verify_admin)
):
    """Update organization (admin only)"""
    supabase = get_supabase()
    
    try:
        # Build update payload
        update_data = {}
        if update.name:
            update_data["name"] = update.name
        if update.settings is not None:
            update_data["settings"] = update.settings
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        result = supabase.table("organizations").update(update_data).eq("id", auth.organization_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        logger.info(f"✓ Organization {auth.organization_id} updated by {auth.email}")
        return result.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update organization: {e}")
        raise HTTPException(status_code=500, detail="Failed to update organization")


@router.get("/members", response_model=List[MemberResponse])
async def list_organization_members(auth: AuthContext = Depends(verify_token)):
    """List all members of current organization"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("users").select("*").eq("organization_id", auth.organization_id).execute()
        
        return result.data or []
        
    except Exception as e:
        logger.error(f"Failed to list members: {e}")
        raise HTTPException(status_code=500, detail="Failed to list members")


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    auth: AuthContext = Depends(verify_admin)
):
    """Remove member from organization (admin only)"""
    supabase = get_supabase()
    
    try:
        # Can't remove yourself
        if user_id == auth.user_id:
            raise HTTPException(status_code=400, detail="Cannot remove yourself")
        
        # Verify user is in same org
        user_result = supabase.table("users").select("organization_id").eq("id", user_id).single().execute()
        
        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user_result.data["organization_id"] != auth.organization_id:
            raise HTTPException(status_code=403, detail="User not in your organization")
        
        # Delete user from auth.users (cascade will handle users table)
        supabase.auth.admin.delete_user(user_id)
        
        logger.info(f"✓ User {user_id} removed from organization by {auth.email}")
        return {"message": "Member removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove member: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove member")


@router.post("/invite", response_model=InviteResponse)
async def invite_member(
    invite: InviteRequest,
    auth: AuthContext = Depends(verify_admin)
):
    """Invite new member to organization (admin only)"""
    supabase = get_supabase()
    
    try:
        # Check if email already in organization
        existing = supabase.table("users").select("email").eq("email", invite.email).execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="User already exists in an organization")
        
        # Check if already invited
        existing_invite = (
            supabase.table("organization_invites")
            .select("*")
            .eq("email", invite.email)
            .eq("organization_id", auth.organization_id)
            .is_("accepted_at", "null")
            .execute()
        )
        
        if existing_invite.data:
            raise HTTPException(status_code=400, detail="User already invited")
        
        # Generate invite token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 days to accept
        
        # Create invite
        invite_data = {
            "organization_id": auth.organization_id,
            "email": invite.email,
            "role": invite.role,
            "invited_by": auth.user_id,
            "token": token,
            "expires_at": expires_at.isoformat()
        }
        
        result = supabase.table("organization_invites").insert(invite_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create invite")
        
        invite_record = result.data[0]
        
        # Generate invite link
        frontend_url = "http://localhost:5173"  # TODO: Get from env
        invite_link = f"{frontend_url}/invite/{token}"
        
        # TODO: Send email with invite link
        # await send_invite_email(invite.email, invite_link, auth.organization_id)
        
        logger.info(f"✓ Invite sent to {invite.email} by {auth.email}")
        
        return {
            **invite_record,
            "invite_link": invite_link
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create invite: {e}")
        raise HTTPException(status_code=500, detail="Failed to create invite")


@router.get("/invites", response_model=List[InviteResponse])
async def list_invites(auth: AuthContext = Depends(verify_admin)):
    """List pending invites (admin only)"""
    supabase = get_supabase()
    
    try:
        result = (
            supabase.table("organization_invites")
            .select("*")
            .eq("organization_id", auth.organization_id)
            .is_("accepted_at", "null")
            .execute()
        )
        
        frontend_url = "http://localhost:5173"  # TODO: Get from env
        
        invites = []
        for invite in result.data or []:
            invites.append({
                **invite,
                "invite_link": f"{frontend_url}/invite/{invite['token']}"
            })
        
        return invites
        
    except Exception as e:
        logger.error(f"Failed to list invites: {e}")
        raise HTTPException(status_code=500, detail="Failed to list invites")


@router.delete("/invites/{invite_id}")
async def cancel_invite(
    invite_id: str,
    auth: AuthContext = Depends(verify_admin)
):
    """Cancel pending invite (admin only)"""
    supabase = get_supabase()
    
    try:
        # Verify invite belongs to org
        invite = (
            supabase.table("organization_invites")
            .select("organization_id")
            .eq("id", invite_id)
            .single()
            .execute()
        )
        
        if not invite.data:
            raise HTTPException(status_code=404, detail="Invite not found")
        
        if invite.data["organization_id"] != auth.organization_id:
            raise HTTPException(status_code=403, detail="Invite not in your organization")
        
        # Delete invite
        supabase.table("organization_invites").delete().eq("id", invite_id).execute()
        
        logger.info(f"✓ Invite {invite_id} cancelled by {auth.email}")
        return {"message": "Invite cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel invite: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel invite")


@router.get("/stats")
async def get_organization_stats(auth: AuthContext = Depends(verify_token)):
    """Get organization statistics"""
    supabase = get_supabase()
    
    try:
        # Count members
        members_result = supabase.table("users").select("id", count="exact").eq("organization_id", auth.organization_id).execute()
        member_count = members_result.count or 0
        
        # Count projects
        projects_result = supabase.table("projects").select("id", count="exact").eq("organization_id", auth.organization_id).execute()
        project_count = projects_result.count or 0
        
        # Count analyses
        analyses_result = supabase.table("analyses").select("id", count="exact").eq("organization_id", auth.organization_id).execute()
        analysis_count = analyses_result.count or 0
        
        # Get recent analyses
        recent_analyses = (
            supabase.table("analyses")
            .select("id, status, created_at")
            .eq("organization_id", auth.organization_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        
        return {
            "member_count": member_count,
            "project_count": project_count,
            "analysis_count": analysis_count,
            "recent_analyses": recent_analyses.data or []
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")
