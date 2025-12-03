"""
Authentication Middleware
Validates Supabase JWT tokens and extracts user context
"""
import os
import jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase_client import get_supabase
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


class AuthContext:
    """User authentication context"""
    
    def __init__(self, user_id: str, email: str, organization_id: str, role: str):
        self.user_id = user_id
        self.email = email
        self.organization_id = organization_id
        self.role = role
    
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role == "admin"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "organization_id": self.organization_id,
            "role": self.role
        }


async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> AuthContext:
    """
    Verify JWT token from Supabase and return user context.
    
    Usage in routes:
        @app.get("/protected")
        async def protected_route(auth: AuthContext = Depends(verify_token)):
            # auth.user_id, auth.organization_id, etc.
    """
    token = credentials.credentials
    
    try:
        # Decode JWT token
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            raise ValueError("SUPABASE_JWT_SECRET not configured")
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated"
        )
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user_id")
        
        # Fetch user's organization and role from database
        supabase = get_supabase()
        
        result = supabase.table("users").select("organization_id, role, email").eq("id", user_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=401, detail="User not found in database")
        
        user_data = result.data
        
        auth_context = AuthContext(
            user_id=user_id,
            email=email or user_data.get("email", ""),
            organization_id=user_data.get("organization_id"),
            role=user_data.get("role", "employee")
        )
        
        logger.debug(f"✓ Authenticated user: {email} (org: {auth_context.organization_id}, role: {auth_context.role})")
        
        return auth_context
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def verify_admin(auth: AuthContext = Depends(verify_token)) -> AuthContext:
    """
    Verify user is admin.
    
    Usage:
        @app.delete("/admin-only")
        async def admin_route(auth: AuthContext = Depends(verify_admin)):
            # Only admins can access this
    """
    if not auth.is_admin():
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    return auth


# Optional auth (for public endpoints that want to know if user is logged in)
async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security)
) -> Optional[AuthContext]:
    """
    Optional authentication - doesn't fail if no token provided.
    
    Usage:
        @app.get("/public-or-private")
        async def mixed_route(auth: Optional[AuthContext] = Depends(optional_auth)):
            if auth:
                # User is logged in
            else:
                # Anonymous user
    """
    if credentials is None:
        return None
    
    try:
        return await verify_token(credentials)
    except HTTPException:
        return None
