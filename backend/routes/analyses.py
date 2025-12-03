"""
Multi-Tenant Analyses Routes
Handles PCB analysis with organization isolation
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from pathlib import Path
from supabase_client import get_supabase
from auth_middleware import verify_token, AuthContext
from services.analysis_service import AnalysisService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analyses"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class AnalysisResponse(BaseModel):
    id: str
    project_id: str
    organization_id: str
    status: str
    created_by: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]


class AnalysisDetailResponse(AnalysisResponse):
    board_info: Optional[dict]
    board_summary: Optional[dict]
    drc_results: Optional[dict]
    cost_estimate: Optional[dict]
    pdf_path: Optional[str]


class StartAnalysisRequest(BaseModel):
    project_id: str


# ============================================
# HELPER FUNCTIONS
# ============================================

async def run_analysis_background(
    analysis_id: str,
    project_id: str,
    organization_id: str,
    user_id: str
):
    """Run PCB analysis in background"""
    supabase = get_supabase()
    
    try:
        # Update status to processing
        supabase.table("analyses").update({
            "status": "processing",
            "started_at": datetime.utcnow().isoformat()
        }).eq("id", analysis_id).execute()
        
        # Get project path
        project = supabase.table("projects").select("*").eq("id", project_id).single().execute()
        
        if not project.data:
            raise Exception("Project not found")
        
        # Run analysis using existing AnalysisService
        analysis_service = AnalysisService()
        
        # Path to uploaded files
        project_path = Path(f"uploads/{project_id}")
        
        if not project_path.exists():
            raise Exception(f"Project files not found at {project_path}")
        
        # Run the analysis (this uses your existing analysis engine!)
        results = await analysis_service.analyze_project_async(str(project_path))
        
        # Extract results
        board_info = results.get("board_info", {})
        board_summary = results.get("board_summary", {})
        drc_results = results.get("drc_results", {})
        cost_estimate = results.get("cost_estimate", {})
        pdf_path = results.get("pdf_path")
        
        # Update analysis with results
        supabase.table("analyses").update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "board_info": board_info,
            "board_summary": board_summary,
            "drc_results": drc_results,
            "cost_estimate": cost_estimate,
            "pdf_path": pdf_path,
            "raw_results": results
        }).eq("id", analysis_id).execute()
        
        logger.info(f"✓ Analysis {analysis_id} completed successfully")
        
    except Exception as e:
        logger.error(f"✗ Analysis {analysis_id} failed: {e}")
        
        # Update with error
        supabase.table("analyses").update({
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error_message": str(e)
        }).eq("id", analysis_id).execute()


# ============================================
# ROUTES
# ============================================

@router.post("/projects/{project_id}/analyze", response_model=AnalysisResponse)
async def start_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(verify_token)
):
    """Start PCB analysis for a project"""
    supabase = get_supabase()
    
    try:
        # Verify project exists and user has access
        project = (
            supabase.table("projects")
            .select("organization_id")
            .eq("id", project_id)
            .eq("organization_id", auth.organization_id)  # Security: org isolation
            .single()
            .execute()
        )
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Create analysis record
        analysis_id = str(uuid.uuid4())
        
        analysis_data = {
            "id": analysis_id,
            "project_id": project_id,
            "organization_id": auth.organization_id,
            "created_by": auth.user_id,
            "status": "pending"
        }
        
        result = supabase.table("analyses").insert(analysis_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create analysis")
        
        # Start analysis in background
        background_tasks.add_task(
            run_analysis_background,
            analysis_id,
            project_id,
            auth.organization_id,
            auth.user_id
        )
        
        logger.info(f"✓ Analysis {analysis_id} started for project {project_id} by {auth.email}")
        
        return result.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/projects/{project_id}/analyses", response_model=List[AnalysisResponse])
async def list_project_analyses(
    project_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """List all analyses for a project"""
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
        
        # Get analyses
        result = (
            supabase.table("analyses")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        return result.data or []
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail="Failed to list analyses")


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis(
    analysis_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Get analysis details"""
    supabase = get_supabase()
    
    try:
        # Get analysis with org verification
        result = (
            supabase.table("analyses")
            .select("*")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)  # Security: org isolation
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return result.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analysis")


@router.get("/analyses", response_model=List[AnalysisResponse])
async def list_organization_analyses(
    auth: AuthContext = Depends(verify_token),
    limit: int = 50,
    status: Optional[str] = None
):
    """List all analyses for current organization"""
    supabase = get_supabase()
    
    try:
        query = (
            supabase.table("analyses")
            .select("*")
            .eq("organization_id", auth.organization_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        
        if status:
            query = query.eq("status", status)
        
        result = query.execute()
        
        return result.data or []
        
    except Exception as e:
        logger.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail="Failed to list analyses")


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Delete analysis (creator or admin only)"""
    supabase = get_supabase()
    
    try:
        # Get analysis to verify ownership/org
        analysis = (
            supabase.table("analyses")
            .select("created_by, organization_id")
            .eq("id", analysis_id)
            .single()
            .execute()
        )
        
        if not analysis.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Check permissions
        if analysis.data["created_by"] != auth.user_id and not auth.is_admin():
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Verify org isolation
        if analysis.data["organization_id"] != auth.organization_id:
            raise HTTPException(status_code=403, detail="Analysis not in your organization")
        
        # Delete analysis
        supabase.table("analyses").delete().eq("id", analysis_id).execute()
        
        logger.info(f"✓ Analysis {analysis_id} deleted by {auth.email}")
        return {"message": "Analysis deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete analysis")


@router.get("/analyses/{analysis_id}/pdf")
async def download_analysis_pdf(
    analysis_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Get PDF download URL for analysis"""
    supabase = get_supabase()
    
    try:
        # Get analysis with org verification
        result = (
            supabase.table("analyses")
            .select("pdf_path, organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        pdf_path = result.data.get("pdf_path")
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF not available yet")
        
        # Generate signed URL
        signed_url = supabase.storage.from_("pcb-files").create_signed_url(
            pdf_path,
            60 * 60  # 1 hour expiry
        )
        
        return {"download_url": signed_url["signedURL"]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get PDF URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to get PDF URL")
