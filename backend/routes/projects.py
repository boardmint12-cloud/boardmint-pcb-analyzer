"""
Multi-Tenant Projects Routes
Handles PCB project uploads and management with organization isolation

Features:
- Project CRUD with organization isolation
- File tree browsing
- File comments
- Supabase Storage integration
- Download individual files or entire project
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import os
import shutil
import zipfile
import io
from pathlib import Path
from supabase_client import get_supabase
from auth_middleware import verify_token, AuthContext
from services.file_analyzer import FileAnalyzer
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])

# Initialize file analyzer
file_analyzer = FileAnalyzer()


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
    file_tree: Optional[dict] = None
    user_comment: Optional[str] = None
    eda_tool: Optional[str] = None
    extraction_status: Optional[str] = None


class FileTreeResponse(BaseModel):
    project_id: str
    file_tree: dict
    file_count: int
    total_size_bytes: int


class FileInfoResponse(BaseModel):
    path: str
    name: str
    file_type: str
    purpose: str
    description: str
    size_bytes: int
    connections: List[str]


class ProjectStructureResponse(BaseModel):
    project_type: str
    main_pcb_file: Optional[str]
    main_schematic_file: Optional[str]
    layer_count: Optional[int]
    has_bom: bool
    has_gerbers: bool
    has_3d_models: bool
    file_count: int
    total_size_bytes: int
    description: str
    key_components: List[str]


class FileCommentRequest(BaseModel):
    comment: str


class FileCommentResponse(BaseModel):
    id: str
    project_id: str
    file_path: str
    comment: str
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProjectCommentRequest(BaseModel):
    comment: str


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    user_comment: Optional[str] = None


# ============================================
# VERSION MODELS
# ============================================

class VersionResponse(BaseModel):
    id: str
    version_number: int
    version_name: Optional[str]
    description: Optional[str]
    original_filename: str
    file_size_bytes: Optional[int]
    eda_tool: Optional[str]
    uploaded_by: str
    uploaded_by_name: Optional[str]
    uploaded_by_avatar: Optional[str]
    created_at: datetime


class ContributorResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    avatar_url: Optional[str]
    role: str
    contribution_count: int


class ProjectWithVersionsResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    eda_tool: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    version_count: int
    contributors: List[ContributorResponse]
    created_by_name: Optional[str]


# ============================================
# ROUTES
# ============================================

@router.get("")
async def list_projects(auth: AuthContext = Depends(verify_token)):
    """List all projects in current organization with version count and contributors"""
    supabase = get_supabase()
    
    try:
        # Get projects with creator info, analysis count, and version count
        # Note: avatar_url is optional - migration may not have been run yet
        result = (
            supabase.table("projects")
            .select("*, users(full_name, email), analyses(count)")
            .eq("organization_id", auth.organization_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        projects = []
        for project in result.data or []:
            project_id = project["id"]
            
            # Get contributors for this project (if table exists)
            contributors = []
            try:
                contributors_result = (
                    supabase.table("project_contributors")
                    .select("*, users(full_name, email)")
                    .eq("project_id", project_id)
                    .order("contribution_count", desc=True)
                    .limit(5)
                    .execute()
                )
                
                for contrib in contributors_result.data or []:
                    user_data = contrib.get("users", {}) or {}
                    contributors.append({
                        "user_id": contrib["user_id"],
                        "full_name": user_data.get("full_name", "Unknown"),
                        "email": user_data.get("email", ""),
                        "avatar_url": None,  # Will be added after migration
                        "role": contrib.get("role", "contributor"),
                        "contribution_count": contrib.get("contribution_count", 1)
                    })
            except Exception:
                # Table might not exist yet - that's OK
                pass
            
            # If no contributors found, add the creator
            if not contributors:
                user_data = project.get("users", {}) or {}
                contributors.append({
                    "user_id": project["created_by"],
                    "full_name": user_data.get("full_name", "Unknown"),
                    "email": user_data.get("email", ""),
                    "avatar_url": None,  # Will be added after migration
                    "role": "owner",
                    "contribution_count": 1
                })
            
            projects.append({
                "id": project_id,
                "organization_id": project["organization_id"],
                "name": project["name"],
                "description": project.get("description"),
                "eda_tool": project.get("eda_tool"),
                "status": project.get("extraction_status", "uploaded"),
                "created_by": project["created_by"],
                "created_by_name": project.get("users", {}).get("full_name", "Unknown") if project.get("users") else "Unknown",
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "analysis_count": len(project.get("analyses", [])),
                "version_count": project.get("version_count", 1),
                "contributors": contributors
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
            "analysis_count": len(project.get("analyses", [])),
            "file_tree": project.get("file_tree"),
            "user_comment": project.get("user_comment"),
            "eda_tool": project.get("eda_tool"),
            "extraction_status": project.get("extraction_status")
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
    user_comment: Optional[str] = Form(None),
    auth: AuthContext = Depends(verify_token)
):
    """
    Upload PCB files and create new project.
    
    This will:
    1. Save file locally and extract if ZIP
    2. Analyze file tree and detect EDA tool
    3. Upload original file to Supabase Storage
    4. Create project record with file tree
    5. Return project ID (user can then choose to analyze)
    """
    supabase = get_supabase()
    upload_dir = None
    
    try:
        # Generate project ID
        project_id = str(uuid.uuid4())
        
        # Storage path: org_<id>/projects/project_<id>/
        storage_path = f"org_{auth.organization_id}/projects/{project_id}"
        
        # Save file locally first (for analysis)
        upload_dir = Path(f"uploads/{project_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        file_size = 0
        
        # Stream file to disk
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                buffer.write(chunk)
        
        logger.info(f"Saved {file_size / 1024 / 1024:.2f}MB to {file_path}")
        
        # Extract if ZIP
        extracted_path = upload_dir / "extracted"
        extracted_path.mkdir(parents=True, exist_ok=True)
        
        is_zip = file.filename.lower().endswith('.zip')
        
        if is_zip:
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extracted_path)
                logger.info(f"Extracted ZIP to {extracted_path}")
                extraction_status = "extracted"
            except zipfile.BadZipFile:
                logger.error("Invalid ZIP file")
                raise HTTPException(status_code=400, detail="Invalid ZIP file")
        else:
            # Single file - copy to extracted folder
            shutil.copy2(file_path, extracted_path / file.filename)
            extraction_status = "single_file"
        
        # Analyze file tree
        try:
            file_infos, file_tree_node, project_structure = file_analyzer.analyze_project(extracted_path)
            file_tree = file_tree_node.to_dict()
            eda_tool = project_structure.project_type
            logger.info(f"File analysis complete: {len(file_infos)} files, EDA: {eda_tool}")
        except Exception as e:
            logger.warning(f"File analysis failed: {e}")
            file_tree = None
            eda_tool = "unknown"
        
        # Upload original file to Supabase Storage
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
                
            storage_file_path = f"{storage_path}/{file.filename}"
            supabase.storage.from_("pcb-files").upload(
                storage_file_path,
                file_content,
                {"content-type": file.content_type or "application/octet-stream"}
            )
            logger.info(f"Uploaded to Supabase Storage: {storage_file_path}")
        except Exception as e:
            logger.warning(f"Supabase storage upload failed: {e}")
            # Continue without cloud storage - files still available locally
        
        # Create project record
        project_data = {
            "id": project_id,
            "organization_id": auth.organization_id,
            "created_by": auth.user_id,
            "name": name,
            "description": description,
            "user_comment": user_comment,
            "storage_path": storage_path,
            "original_filename": file.filename,
            "file_size_bytes": file_size,
            "eda_tool": eda_tool,
            "extraction_status": extraction_status,
            "file_tree": file_tree,
            "metadata": {
                "original_filename": file.filename,
                "file_size": file_size,
                "content_type": file.content_type,
                "is_zip": is_zip,
                "file_count": len(file_infos) if file_infos else 0
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
        logger.error(f"Failed to create project: {e}", exc_info=True)
        # Cleanup on failure
        if upload_dir and upload_dir.exists():
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


# ============================================
# FILE TREE & STRUCTURE ENDPOINTS
# ============================================

@router.get("/{project_id}/files", response_model=FileTreeResponse)
async def get_project_files(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """
    Get file tree for a project.
    Returns hierarchical file structure with purposes.
    """
    supabase = get_supabase()
    
    try:
        # Get project with file tree
        project = (
            supabase.table("projects")
            .select("file_tree, organization_id, metadata")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        file_tree = project.data.get("file_tree")
        
        if not file_tree:
            # Re-analyze if file tree not available
            local_path = Path(f"uploads/{project_id}/extracted")
            if local_path.exists():
                file_infos, file_tree_node, _ = file_analyzer.analyze_project(local_path)
                file_tree = file_tree_node.to_dict()
                
                # Update project with file tree
                supabase.table("projects").update({
                    "file_tree": file_tree
                }).eq("id", project_id).execute()
            else:
                file_tree = {"name": "Project", "is_directory": True, "children": []}
        
        metadata = project.data.get("metadata", {})
        
        return {
            "project_id": project_id,
            "file_tree": file_tree,
            "file_count": metadata.get("file_count", 0),
            "total_size_bytes": file_tree.get("size_bytes", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        # Handle Supabase "no rows" error as 404
        if "PGRST116" in error_str or "0 rows" in error_str:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.error(f"Failed to get file tree: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file tree")


@router.get("/{project_id}/files/{file_path:path}", response_model=FileInfoResponse)
async def get_file_info(
    project_id: str,
    file_path: str,
    auth: AuthContext = Depends(verify_token)
):
    """
    Get detailed info about a specific file.
    Includes purpose, description, and connections.
    """
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Analyze the specific file
        local_path = Path(f"uploads/{project_id}/extracted")
        if not local_path.exists():
            raise HTTPException(status_code=404, detail="Project files not found")
        
        full_file_path = local_path / file_path
        if not full_file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get file info
        file_infos, _, _ = file_analyzer.analyze_project(local_path)
        file_info = next((f for f in file_infos if f.path == file_path), None)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="File info not found")
        
        return {
            "path": file_info.path,
            "name": file_info.name,
            "file_type": file_info.file_type.value,
            "purpose": file_info.purpose,
            "description": file_info.description,
            "size_bytes": file_info.size_bytes,
            "connections": file_info.connections
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file info")


@router.get("/{project_id}/structure", response_model=ProjectStructureResponse)
async def get_project_structure(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """
    Get project structure overview.
    Shows how files connect together and key project info.
    """
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Analyze project structure
        local_path = Path(f"uploads/{project_id}/extracted")
        if not local_path.exists():
            raise HTTPException(status_code=404, detail="Project files not found")
        
        _, _, project_structure = file_analyzer.analyze_project(local_path)
        
        return project_structure.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "PGRST116" in error_str or "0 rows" in error_str:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.error(f"Failed to get project structure: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project structure")


# ============================================
# PROJECT UPDATE & COMMENTS
# ============================================

@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    auth: AuthContext = Depends(verify_token)
):
    """Update project details (name, description, comment)"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("created_by, organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Build update data
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.user_comment is not None:
            update_data["user_comment"] = request.user_comment
        
        if not update_data:
            return {"message": "No changes to apply"}
        
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        result = supabase.table("projects").update(update_data).eq("id", project_id).execute()
        
        logger.info(f"✓ Project {project_id} updated by {auth.email}")
        return {"message": "Project updated successfully", "project": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project")


# ============================================
# FILE COMMENTS ENDPOINTS
# ============================================

@router.get("/{project_id}/comments")
async def list_project_file_comments(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """List all file comments for a project"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get all comments
        result = (
            supabase.table("file_comments")
            .select("*, users(full_name)")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        comments = []
        for comment in result.data or []:
            comments.append({
                "id": comment["id"],
                "project_id": comment["project_id"],
                "file_path": comment["file_path"],
                "comment": comment["comment"],
                "created_by": comment["created_by"],
                "created_by_name": comment.get("users", {}).get("full_name", "Unknown"),
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"]
            })
        
        return {"comments": comments}
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "PGRST116" in error_str or "0 rows" in error_str:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.error(f"Failed to list file comments: {e}")
        raise HTTPException(status_code=500, detail="Failed to list file comments")


@router.post("/{project_id}/files/{file_path:path}/comments", response_model=FileCommentResponse)
async def add_file_comment(
    project_id: str,
    file_path: str,
    request: FileCommentRequest,
    auth: AuthContext = Depends(verify_token)
):
    """Add a comment to a specific file"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Create comment
        comment_data = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "file_path": file_path,
            "comment": request.comment,
            "created_by": auth.user_id
        }
        
        result = supabase.table("file_comments").insert(comment_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create comment")
        
        logger.info(f"✓ File comment added to {file_path} by {auth.email}")
        
        return {
            **result.data[0],
            "created_by_name": auth.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add file comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to add file comment")


@router.get("/{project_id}/files/{file_path:path}/comments")
async def get_file_comments(
    project_id: str,
    file_path: str,
    auth: AuthContext = Depends(verify_token)
):
    """Get all comments for a specific file"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get comments for file
        result = (
            supabase.table("file_comments")
            .select("*, users(full_name)")
            .eq("project_id", project_id)
            .eq("file_path", file_path)
            .order("created_at", desc=True)
            .execute()
        )
        
        comments = []
        for comment in result.data or []:
            comments.append({
                "id": comment["id"],
                "project_id": comment["project_id"],
                "file_path": comment["file_path"],
                "comment": comment["comment"],
                "created_by": comment["created_by"],
                "created_by_name": comment.get("users", {}).get("full_name", "Unknown"),
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"]
            })
        
        return {"comments": comments}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file comments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file comments")


@router.delete("/{project_id}/comments/{comment_id}")
async def delete_file_comment(
    project_id: str,
    comment_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Delete a file comment (owner only)"""
    supabase = get_supabase()
    
    try:
        # Get comment to verify ownership
        comment = (
            supabase.table("file_comments")
            .select("created_by, project_id")
            .eq("id", comment_id)
            .single()
            .execute()
        )
        
        if not comment.data:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        # Check ownership
        if comment.data["created_by"] != auth.user_id and not auth.is_admin():
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Delete comment
        supabase.table("file_comments").delete().eq("id", comment_id).execute()
        
        logger.info(f"✓ File comment {comment_id} deleted by {auth.email}")
        return {"message": "Comment deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file comment")


# ============================================
# DOWNLOAD ENDPOINTS
# ============================================

@router.get("/{project_id}/download")
async def download_project_zip(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """
    Download entire project as ZIP.
    Returns signed URL from Supabase Storage or streams from local.
    """
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("storage_path, organization_id, metadata")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        metadata = project.data.get("metadata", {})
        original_filename = metadata.get("original_filename", "project.zip")
        storage_path = project.data.get("storage_path")
        
        # Try to get from Supabase Storage first
        if storage_path:
            try:
                storage_file_path = f"{storage_path}/{original_filename}"
                signed_url = supabase.storage.from_("pcb-files").create_signed_url(
                    storage_file_path,
                    60 * 60  # 1 hour expiry
                )
                return {"download_url": signed_url["signedURL"], "filename": original_filename}
            except Exception as e:
                logger.warning(f"Could not get signed URL: {e}")
        
        # Fall back to local file
        local_path = Path(f"uploads/{project_id}/{original_filename}")
        if local_path.exists():
            def iter_file():
                with open(local_path, "rb") as f:
                    while chunk := f.read(1024 * 1024):
                        yield chunk
            
            return StreamingResponse(
                iter_file(),
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={original_filename}"}
            )
        
        raise HTTPException(status_code=404, detail="Project file not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download project: {e}")
        raise HTTPException(status_code=500, detail="Failed to download project")


# ============================================
# VERSION MANAGEMENT ENDPOINTS
# ============================================

@router.get("/{project_id}/versions", response_model=List[VersionResponse])
async def list_project_versions(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """List all versions of a project"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get all versions
        versions_result = (
            supabase.table("project_versions")
            .select("*, users(full_name, email, avatar_url)")
            .eq("project_id", project_id)
            .order("version_number", desc=True)
            .execute()
        )
        
        versions = []
        for v in versions_result.data or []:
            user_data = v.get("users", {}) or {}
            versions.append({
                "id": v["id"],
                "version_number": v["version_number"],
                "version_name": v.get("version_name"),
                "description": v.get("description"),
                "original_filename": v["original_filename"],
                "file_size_bytes": v.get("file_size_bytes"),
                "eda_tool": v.get("eda_tool"),
                "uploaded_by": v["uploaded_by"],
                "uploaded_by_name": user_data.get("full_name", "Unknown"),
                "uploaded_by_avatar": user_data.get("avatar_url"),
                "created_at": v["created_at"]
            })
        
        return versions
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "PGRST116" in error_str or "0 rows" in error_str:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.error(f"Failed to list versions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list versions")


@router.post("/{project_id}/versions", response_model=VersionResponse)
async def create_project_version(
    project_id: str,
    file: UploadFile = File(...),
    version_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    auth: AuthContext = Depends(verify_token)
):
    """Upload a new version of a project"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id, version_count, storage_path")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get next version number
        current_version = project.data.get("version_count", 1)
        next_version = current_version + 1
        
        # Generate version ID
        version_id = str(uuid.uuid4())
        
        # Storage path for this version
        storage_path = f"org_{auth.organization_id}/projects/{project_id}/versions/{version_id}"
        
        # Save file locally first
        upload_dir = Path(f"uploads/{project_id}/versions/{version_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        file_size = 0
        
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                buffer.write(chunk)
        
        # Extract if ZIP
        extracted_path = upload_dir / "extracted"
        extracted_path.mkdir(parents=True, exist_ok=True)
        
        is_zip = file.filename.lower().endswith('.zip')
        eda_tool = "unknown"
        file_tree = None
        
        if is_zip:
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extracted_path)
                
                # Analyze files
                try:
                    file_infos, file_tree_node, project_structure = file_analyzer.analyze_project(extracted_path)
                    file_tree = file_tree_node.to_dict()
                    eda_tool = project_structure.project_type
                except Exception as e:
                    logger.warning(f"File analysis failed: {e}")
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid ZIP file")
        else:
            shutil.copy2(file_path, extracted_path / file.filename)
        
        # Upload to Supabase Storage
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            storage_file_path = f"{storage_path}/{file.filename}"
            supabase.storage.from_("pcb-files").upload(
                storage_file_path,
                file_content,
                {"content-type": file.content_type or "application/octet-stream"}
            )
        except Exception as e:
            logger.warning(f"Supabase storage upload failed: {e}")
        
        # Create version record
        version_data = {
            "id": version_id,
            "project_id": project_id,
            "version_number": next_version,
            "version_name": version_name or f"v{next_version}.0",
            "description": description,
            "storage_path": storage_path,
            "original_filename": file.filename,
            "file_size_bytes": file_size,
            "file_tree": file_tree,
            "eda_tool": eda_tool,
            "uploaded_by": auth.user_id,
            "organization_id": auth.organization_id
        }
        
        result = supabase.table("project_versions").insert(version_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create version")
        
        # Update project version count
        supabase.table("projects").update({
            "version_count": next_version,
            "current_version_id": version_id
        }).eq("id", project_id).execute()
        
        # Update or create contributor record
        try:
            supabase.table("project_contributors").upsert({
                "project_id": project_id,
                "user_id": auth.user_id,
                "role": "contributor",
                "last_contribution_at": datetime.utcnow().isoformat(),
            }, on_conflict="project_id,user_id").execute()
        except Exception as e:
            logger.warning(f"Failed to update contributors: {e}")
        
        logger.info(f"✓ Version {next_version} created for project {project_id} by {auth.email}")
        
        return {
            "id": version_id,
            "version_number": next_version,
            "version_name": version_name or f"v{next_version}.0",
            "description": description,
            "original_filename": file.filename,
            "file_size_bytes": file_size,
            "eda_tool": eda_tool,
            "uploaded_by": auth.user_id,
            "uploaded_by_name": auth.email,
            "uploaded_by_avatar": None,
            "created_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "PGRST116" in error_str or "0 rows" in error_str:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.error(f"Failed to create version: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create version: {str(e)}")


@router.get("/{project_id}/contributors", response_model=List[ContributorResponse])
async def list_project_contributors(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """List all contributors to a project"""
    supabase = get_supabase()
    
    try:
        # Verify project access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get all contributors
        contributors_result = (
            supabase.table("project_contributors")
            .select("*, users(full_name, email, avatar_url)")
            .eq("project_id", project_id)
            .order("contribution_count", desc=True)
            .execute()
        )
        
        contributors = []
        for contrib in contributors_result.data or []:
            user_data = contrib.get("users", {}) or {}
            contributors.append({
                "user_id": contrib["user_id"],
                "full_name": user_data.get("full_name", "Unknown"),
                "email": user_data.get("email", ""),
                "avatar_url": user_data.get("avatar_url"),
                "role": contrib.get("role", "contributor"),
                "contribution_count": contrib.get("contribution_count", 1)
            })
        
        return contributors
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "PGRST116" in error_str or "0 rows" in error_str:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.error(f"Failed to list contributors: {e}")
        raise HTTPException(status_code=500, detail="Failed to list contributors")
