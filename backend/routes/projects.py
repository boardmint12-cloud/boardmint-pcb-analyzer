"""
Multi-Tenant Projects Routes
Handles PCB project uploads and management with organization isolation
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import os
import shutil
from pathlib import Path
from supabase_client import get_supabase
from auth_middleware import verify_token, AuthContext
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    analysis_count: int


class ProjectDetailResponse(ProjectResponse):
    storage_path: Optional[str]
    metadata: dict
    analyses: List[dict]


# ============================================
# ROUTES
# ============================================

@router.get("", response_model=List[ProjectResponse])
async def list_projects(auth: AuthContext = Depends(verify_token)):
    """List all projects in current organization"""
    supabase = get_supabase()
    
    try:
        # Get projects with creator info and analysis count
        result = (
            supabase.table("projects")
            .select("*, users(full_name, email), analyses(count)")
            .eq("organization_id", auth.organization_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        projects = []
        for project in result.data or []:
            projects.append({
                "id": project["id"],
                "organization_id": project["organization_id"],
                "name": project["name"],
                "description": project.get("description"),
                "created_by": project["created_by"],
                "created_by_name": project.get("users", {}).get("full_name", "Unknown"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "analysis_count": len(project.get("analyses", []))
            })
        
        return projects
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to list projects")


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: str, auth: AuthContext = Depends(verify_token)):
    """Get project details"""
    supabase = get_supabase()
    
    try:
        # Get project with analyses
        result = (
            supabase.table("projects")
            .select("*, users(full_name, email), analyses(*)")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)  # Security: org isolation
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = result.data
        
        return {
            "id": project["id"],
            "organization_id": project["organization_id"],
            "name": project["name"],
            "description": project.get("description"),
            "created_by": project["created_by"],
            "created_by_name": project.get("users", {}).get("full_name", "Unknown"),
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
            "storage_path": project.get("storage_path"),
            "metadata": project.get("metadata", {}),
            "analyses": project.get("analyses", []),
            "analysis_count": len(project.get("analyses", []))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project")


@router.post("", response_model=ProjectResponse)
async def create_project(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    auth: AuthContext = Depends(verify_token)
):
    """
    Upload PCB files and create new project.
    
    This will:
    1. Create project record
    2. Store files in Supabase Storage
    3. Return project ID for analysis
    """
    supabase = get_supabase()
    
    try:
        # Generate project ID
        project_id = str(uuid.uuid4())
        
        # Storage path: org_<id>/projects/project_<id>/
        storage_path = f"org_{auth.organization_id}/projects/{project_id}"
        
        # Save file locally first (for analysis)
        upload_dir = Path(f"uploads/{project_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Upload to Supabase Storage
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        storage_file_path = f"{storage_path}/{file.filename}"
        supabase.storage.from_("pcb-files").upload(
            storage_file_path,
            file_content,
            {"content-type": file.content_type or "application/octet-stream"}
        )
        
        # Create project record
        project_data = {
            "id": project_id,
            "organization_id": auth.organization_id,
            "created_by": auth.user_id,
            "name": name,
            "description": description,
            "storage_path": storage_path,
            "metadata": {
                "original_filename": file.filename,
                "file_size": os.path.getsize(file_path),
                "content_type": file.content_type
            }
        }
        
        result = supabase.table("projects").insert(project_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create project")
        
        logger.info(f"✓ Project {project_id} created by {auth.email}")
        
        return {
            **result.data[0],
            "created_by_name": auth.email,
            "analysis_count": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        # Cleanup on failure
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Delete project (creator or admin only)"""
    supabase = get_supabase()
    
    try:
        # Get project to verify ownership/org
        project = (
            supabase.table("projects")
            .select("created_by, organization_id, storage_path")
            .eq("id", project_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check permissions: creator or admin
        if project.data["created_by"] != auth.user_id and not auth.is_admin():
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Verify org isolation
        if project.data["organization_id"] != auth.organization_id:
            raise HTTPException(status_code=403, detail="Project not in your organization")
        
        # Delete from storage
        storage_path = project.data.get("storage_path")
        if storage_path:
            try:
                # List and delete all files in project folder
                files = supabase.storage.from_("pcb-files").list(storage_path)
                for file_obj in files:
                    supabase.storage.from_("pcb-files").remove([f"{storage_path}/{file_obj['name']}"])
            except Exception as e:
                logger.warning(f"Failed to delete storage files: {e}")
        
        # Delete local files
        local_path = Path(f"uploads/{project_id}")
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)
        
        # Delete project (cascade will delete analyses)
        supabase.table("projects").delete().eq("id", project_id).execute()
        
        logger.info(f"✓ Project {project_id} deleted by {auth.email}")
        return {"message": "Project deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project")


@router.get("/{project_id}/download/{filename}")
async def download_project_file(
    project_id: str,
    filename: str,
    auth: AuthContext = Depends(verify_token)
):
    """Download project file from storage"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("storage_path, organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get signed URL for file
        storage_path = f"{project.data['storage_path']}/{filename}"
        signed_url = supabase.storage.from_("pcb-files").create_signed_url(
            storage_path,
            60 * 60  # 1 hour expiry
        )
        
        return {"download_url": signed_url["signedURL"]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file")
