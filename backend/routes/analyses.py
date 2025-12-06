"""
Multi-Tenant Analyses Routes
Handles PCB analysis with organization isolation

Features:
- Start/view/delete analyses
- Issue comments
- File purposes
- PDF report access
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from pathlib import Path
from supabase_client import get_supabase
from auth_middleware import verify_token, AuthContext
from services.file_analyzer import FileAnalyzer
from services.file_loader import FileLoader
from parsers.hybrid_parser import HybridParser
from services.ai_service import AIAnalysisService
from rules import (
    MainsSafetyRules,
    BusInterfaceRules,
    PowerSMPSRules,
    BOMValidationRules,
    HighSpeedInterfaceRules,
    ThermalAnalysisRules,
    BOMSanityRules,
    AssemblyTestRules,
    Issue
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analyses"])

# Initialize services
file_analyzer = FileAnalyzer()
file_loader = FileLoader()
hybrid_parser = HybridParser()


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


class IssueCommentRequest(BaseModel):
    comment: str
    status: Optional[str] = None  # open, acknowledged, resolved, wont_fix


class IssueCommentResponse(BaseModel):
    id: str
    analysis_id: str
    issue_id: str
    comment: str
    status: str
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================
# HELPER FUNCTIONS
# ============================================

async def run_pcb_analysis(
    analysis_id: str,
    project_id: str,
    organization_id: str,
    user_id: str
):
    """Run full PCB analysis in background - parses files, runs DRC, generates PDF"""
    supabase = get_supabase()
    
    def update_status(status: str, **kwargs):
        """Helper to update analysis status"""
        data = {"status": status}
        data.update(kwargs)
        supabase.table("analyses").update(data).eq("id", analysis_id).execute()
    
    try:
        # Update status to processing
        update_status("processing", started_at=datetime.utcnow().isoformat())
        
        # Get project info
        project = supabase.table("projects").select("*").eq("id", project_id).single().execute()
        if not project.data:
            raise Exception("Project not found")
        
        # Path to uploaded/extracted files
        project_path = Path(f"uploads/{project_id}")
        extracted_path = project_path / "extracted"
        analysis_path = extracted_path if extracted_path.exists() else project_path
        
        if not analysis_path.exists():
            raise Exception(f"Project files not found at {analysis_path}")
        
        logger.info(f"🔍 Running full PCB analysis on: {analysis_path}")
        
        # ===== STEP 1: File Analysis =====
        update_status("processing")
        file_infos, file_tree_node, project_structure = file_analyzer.analyze_project(analysis_path)
        file_purposes = file_analyzer.get_file_purposes_dict(file_infos)
        logger.info(f"📁 Found {len(file_infos)} files, type: {project_structure.project_type}")
        
        # ===== STEP 2: Parse PCB Files =====
        update_status("processing")
        
        pcb_data = None
        board_info = {}
        
        try:
            logger.info(f"🔧 Running HybridParser on: {analysis_path}")
            pcb_data = hybrid_parser.parse(analysis_path)
            
            if pcb_data and pcb_data.board_info:
                board_info = {
                    "size_x": pcb_data.board_info.size_x or 0,
                    "size_y": pcb_data.board_info.size_y or 0,
                    "layer_count": pcb_data.board_info.layer_count or 0,
                    "components_count": len(pcb_data.components),
                    "nets_count": len(pcb_data.nets),
                    "eda_tool": project.data.get("eda_tool", project_structure.project_type),
                    "parsing_method": "hybrid_parser"
                }
                logger.info(f"✅ Parsed: {board_info['size_x']}x{board_info['size_y']}mm, "
                           f"{board_info['layer_count']} layers, {board_info['components_count']} components")
            else:
                logger.warning("⚠️ HybridParser returned no board_info")
                board_info = {
                    "size_x": 0, "size_y": 0, "layer_count": 0,
                    "components_count": len(pcb_data.components) if pcb_data else 0,
                    "nets_count": len(pcb_data.nets) if pcb_data else 0,
                    "eda_tool": project_structure.project_type,
                    "parsing_method": "hybrid_parser_partial"
                }
        except Exception as parse_error:
            logger.error(f"❌ Parsing failed: {parse_error}")
            board_info = {
                "size_x": 0, "size_y": 0, "layer_count": 0,
                "components_count": 0, "nets_count": 0,
                "eda_tool": project_structure.project_type,
                "parsing_method": "failed",
                "parse_error": str(parse_error)
            }
        
        # ===== STEP 3: Run DRC Rule Engines =====
        update_status("processing")
        all_issues = []
        
        if pcb_data:
            try:
                # Initialize rule engines
                rule_engines = [
                    MainsSafetyRules(),
                    BusInterfaceRules(),
                    PowerSMPSRules(),
                    BOMValidationRules(),
                    HighSpeedInterfaceRules(),
                    ThermalAnalysisRules(),
                    BOMSanityRules(),
                    AssemblyTestRules()
                ]
                
                # Run each rule engine
                for engine in rule_engines:
                    try:
                        engine_issues = engine.analyze(pcb_data)
                        all_issues.extend(engine_issues)
                        logger.info(f"  {engine.__class__.__name__}: {len(engine_issues)} issues")
                    except Exception as rule_error:
                        logger.warning(f"  {engine.__class__.__name__} failed: {rule_error}")
                
                logger.info(f"🔍 DRC found {len(all_issues)} total issues")
            except Exception as drc_error:
                logger.error(f"❌ DRC failed: {drc_error}")
        
        # ===== STEP 4: AI Analysis =====
        update_status("processing")
        board_summary = {}
        ai_suggestions = []
        
        try:
            ai_service = AIAnalysisService()
            
            # Prepare data for AI
            parsed_data = {
                "board_info": board_info,
                "nets": [{"name": n.name, "connections": n.pads} for n in (pcb_data.nets if pcb_data else [])],
                "components": [{"reference": c.reference, "value": c.value, "footprint": c.footprint} 
                              for c in (pcb_data.components if pcb_data else [])]
            }
            
            # Get AI issues and suggestions
            ai_issues, ai_suggestions = ai_service.analyze_pcb(
                project_path=analysis_path,
                parsed_data=parsed_data,
                rule_engine_issues=all_issues,
                fab_profile="2l_cheap_proto"
            )
            all_issues.extend(ai_issues)
            logger.info(f"🤖 AI added {len(ai_issues)} issues, {len(ai_suggestions)} suggestions")
            
            # Generate board summary
            if pcb_data and len(pcb_data.components) > 0:
                component_refs = [c.reference for c in pcb_data.components[:20]]
                component_values = [c.value for c in pcb_data.components if c.value][:10]
                
                board_summary = {
                    "purpose": project_structure.description or "PCB design project",
                    "description": f"Board with {len(pcb_data.components)} components and {len(pcb_data.nets)} nets",
                    "key_features": list(set(component_values))[:5],
                    "main_components": component_refs[:5],
                    "design_notes": f"Detected as {project_structure.project_type} project"
                }
            else:
                board_summary = {
                    "purpose": project_structure.description or "PCB project",
                    "description": f"{project_structure.project_type} with {len(file_infos)} files",
                    "key_features": project_structure.key_components[:5] if project_structure.key_components else [],
                    "main_components": [],
                    "design_notes": "Limited parsing - check file format compatibility"
                }
        except Exception as ai_error:
            logger.error(f"❌ AI analysis failed: {ai_error}")
            board_summary = {
                "purpose": project_structure.description or "PCB project",
                "description": f"Analysis encountered issues: {str(ai_error)[:100]}",
                "key_features": [],
                "main_components": [],
                "design_notes": "AI analysis unavailable"
            }
        
        # ===== STEP 5: Calculate Summary =====
        critical_count = sum(1 for i in all_issues if getattr(i, 'severity', None) and i.severity.value == "critical")
        warning_count = sum(1 for i in all_issues if getattr(i, 'severity', None) and i.severity.value == "warning")
        info_count = sum(1 for i in all_issues if getattr(i, 'severity', None) and i.severity.value == "info")
        
        # Determine risk level
        if critical_count > 3:
            risk_level = "high"
        elif critical_count > 0 or warning_count > 5:
            risk_level = "moderate"
        else:
            risk_level = "low"
        
        # Convert issues to JSON-serializable format
        issues_json = []
        for issue in all_issues:
            try:
                issues_json.append({
                    "id": str(uuid.uuid4()),
                    "issue_code": getattr(issue, 'issue_code', 'UNKNOWN'),
                    "severity": issue.severity.value if hasattr(issue, 'severity') else "info",
                    "category": getattr(issue, 'category', 'general'),
                    "title": getattr(issue, 'title', str(issue)),
                    "description": getattr(issue, 'description', ''),
                    "suggested_fix": getattr(issue, 'suggested_fix', ''),
                    "affected_nets": getattr(issue, 'affected_nets', []),
                    "affected_components": getattr(issue, 'affected_components', []),
                    "location_x": getattr(issue, 'location_x', None),
                    "location_y": getattr(issue, 'location_y', None),
                    "layer": getattr(issue, 'layer', None)
                })
            except Exception as issue_err:
                logger.warning(f"Failed to serialize issue: {issue_err}")
        
        drc_results = {
            "summary": {
                "critical": critical_count,
                "warning": warning_count,
                "info": info_count
            },
            "risk_level": risk_level,
            "checks_run": ["file_analysis", "hybrid_parser", "drc_rules", "ai_analysis"],
            "ai_suggestions": ai_suggestions
        }
        
        # ===== STEP 6: Generate PDF =====
        pdf_path = None
        update_status("processing")
        
        try:
            from services.export_service import ExportService
            export_service = ExportService()
            
            # Create a minimal results dict for PDF generation
            pdf_results = {
                "job_id": analysis_id,
                "project_id": project_id,
                "board_info": board_info,
                "board_summary": board_summary,
                "issues": issues_json,
                "summary": drc_results["summary"],
                "risk_level": risk_level
            }
            
            # Try to generate PDF (this may fail if export_service expects different format)
            pdf_path = export_service.generate_pdf_for_supabase(analysis_id, pdf_results, organization_id)
            if pdf_path:
                logger.info(f"✅ PDF generated: {pdf_path}")
        except Exception as pdf_error:
            logger.warning(f"⚠️ PDF generation failed: {pdf_error}")
            pdf_path = None
        
        # ===== STEP 7: Save Results =====
        update_status(
            "completed",
            completed_at=datetime.utcnow().isoformat(),
            board_info=board_info,
            board_summary=board_summary,
            drc_results=drc_results,
            file_purposes=file_purposes,
            project_structure=project_structure.to_dict(),
            issues_json=issues_json,
            pdf_storage_path=pdf_path,
            raw_results={
                "file_count": len(file_infos),
                "project_type": project_structure.project_type,
                "components_parsed": board_info.get("components_count", 0),
                "nets_parsed": board_info.get("nets_count", 0),
                "issues_found": len(all_issues),
                "risk_level": risk_level
            }
        )
        
        logger.info(f"✅ Analysis {analysis_id} completed: {risk_level} risk, "
                   f"{critical_count} critical, {warning_count} warnings, {info_count} info")
        
    except Exception as e:
        logger.error(f"❌ Analysis {analysis_id} failed: {e}")
        import traceback
        traceback.print_exc()
        
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
            run_pcb_analysis,
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


# ============================================
# LEGACY RESULTS ENDPOINT (for DashboardPage compatibility)
# ============================================

@router.get("/results/{analysis_id}")
async def get_results_legacy(analysis_id: str):
    """
    Legacy results endpoint for backward compatibility with DashboardPage.
    Returns results in the old format expected by the frontend.
    """
    supabase = get_supabase()
    
    try:
        # Get analysis - no auth required for polling during analysis
        result = (
            supabase.table("analyses")
            .select("*")
            .eq("id", analysis_id)
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        analysis = result.data
        
        # Transform to legacy format (handle None values)
        drc_results = analysis.get("drc_results") or {}
        summary = drc_results.get("summary") or {"critical": 0, "warning": 0, "info": 0}
        
        # Determine risk level
        if summary.get("critical", 0) > 0:
            risk_level = "high"
        elif summary.get("warning", 0) > 2:
            risk_level = "moderate"
        else:
            risk_level = "low"
        
        # Group issues by category (handle None)
        issues_json = analysis.get("issues_json") or []
        issues_by_category = {}
        for issue in issues_json:
            category = issue.get("category", "general") if issue else "general"
            if category not in issues_by_category:
                issues_by_category[category] = []
            issues_by_category[category].append(issue)
        
        return {
            "job_id": analysis_id,
            "project_id": analysis.get("project_id"),
            "status": analysis.get("status") or "pending",
            "progress": "Analysis complete" if analysis.get("status") == "completed" else "Processing...",
            "risk_level": risk_level,
            "summary": summary,
            "board_info": analysis.get("board_info") or {},
            "board_summary": analysis.get("board_summary") or {},
            "issues_by_category": issues_by_category,
            "file_purposes": analysis.get("file_purposes") or {},
            "created_at": analysis.get("created_at"),
            "completed_at": analysis.get("completed_at"),
            "error_message": analysis.get("error_message")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")


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
            .select("pdf_storage_path, organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        pdf_path = result.data.get("pdf_storage_path")
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF not available yet")
        
        # Generate signed URL from analysis-reports bucket
        signed_url = supabase.storage.from_("analysis-reports").create_signed_url(
            pdf_path,
            60 * 60  # 1 hour expiry
        )
        
        return {"download_url": signed_url["signedURL"]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get PDF URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to get PDF URL")


# ============================================
# ISSUE COMMENTS ENDPOINTS
# ============================================

@router.get("/analyses/{analysis_id}/issues")
async def list_analysis_issues(
    analysis_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """
    List all issues from an analysis with their comments.
    Combines DRC results with user comments.
    """
    supabase = get_supabase()
    
    try:
        # Get analysis with org verification
        result = (
            supabase.table("analyses")
            .select("drc_results, issues_json, organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Get issues from DRC results
        drc_results = result.data.get("drc_results", {})
        issues_json = result.data.get("issues_json", [])
        
        # Get all comments for this analysis
        comments_result = (
            supabase.table("issue_comments")
            .select("*, users(full_name)")
            .eq("analysis_id", analysis_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        # Group comments by issue_id
        comments_by_issue = {}
        for comment in comments_result.data or []:
            issue_id = comment["issue_id"]
            if issue_id not in comments_by_issue:
                comments_by_issue[issue_id] = []
            comments_by_issue[issue_id].append({
                "id": comment["id"],
                "comment": comment["comment"],
                "status": comment["status"],
                "created_by": comment["created_by"],
                "created_by_name": comment.get("users", {}).get("full_name", "Unknown"),
                "created_at": comment["created_at"]
            })
        
        # Merge issues with comments
        issues_with_comments = []
        for issue in issues_json:
            issue_id = issue.get("id", "")
            issues_with_comments.append({
                **issue,
                "comments": comments_by_issue.get(issue_id, []),
                "comment_count": len(comments_by_issue.get(issue_id, []))
            })
        
        return {
            "analysis_id": analysis_id,
            "issues": issues_with_comments,
            "total_issues": len(issues_with_comments),
            "drc_summary": drc_results.get("summary", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list issues: {e}")
        raise HTTPException(status_code=500, detail="Failed to list issues")


@router.post("/analyses/{analysis_id}/issues/{issue_id}/comments", response_model=IssueCommentResponse)
async def add_issue_comment(
    analysis_id: str,
    issue_id: str,
    request: IssueCommentRequest,
    auth: AuthContext = Depends(verify_token)
):
    """Add a comment to an issue"""
    supabase = get_supabase()
    
    try:
        # Verify analysis access
        analysis = (
            supabase.table("analyses")
            .select("organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not analysis.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Create comment
        comment_data = {
            "id": str(uuid.uuid4()),
            "analysis_id": analysis_id,
            "issue_id": issue_id,
            "comment": request.comment,
            "status": request.status or "open",
            "created_by": auth.user_id
        }
        
        result = supabase.table("issue_comments").insert(comment_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create comment")
        
        logger.info(f"✓ Issue comment added to {issue_id} by {auth.email}")
        
        return {
            **result.data[0],
            "created_by_name": auth.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add issue comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to add issue comment")


@router.get("/analyses/{analysis_id}/issues/{issue_id}/comments")
async def get_issue_comments(
    analysis_id: str,
    issue_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Get all comments for a specific issue"""
    supabase = get_supabase()
    
    try:
        # Verify analysis access
        analysis = (
            supabase.table("analyses")
            .select("organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not analysis.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Get comments
        result = (
            supabase.table("issue_comments")
            .select("*, users(full_name)")
            .eq("analysis_id", analysis_id)
            .eq("issue_id", issue_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        comments = []
        for comment in result.data or []:
            comments.append({
                "id": comment["id"],
                "analysis_id": comment["analysis_id"],
                "issue_id": comment["issue_id"],
                "comment": comment["comment"],
                "status": comment["status"],
                "created_by": comment["created_by"],
                "created_by_name": comment.get("users", {}).get("full_name", "Unknown"),
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"]
            })
        
        return {"comments": comments}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get issue comments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get issue comments")


@router.patch("/analyses/{analysis_id}/issues/{issue_id}/status")
async def update_issue_status(
    analysis_id: str,
    issue_id: str,
    request: IssueCommentRequest,
    auth: AuthContext = Depends(verify_token)
):
    """Update issue status (acknowledged, resolved, wont_fix)"""
    supabase = get_supabase()
    
    try:
        # Verify analysis access
        analysis = (
            supabase.table("analyses")
            .select("organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not analysis.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        valid_statuses = ["open", "acknowledged", "resolved", "wont_fix"]
        if request.status and request.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        # Create a status change comment
        comment_data = {
            "id": str(uuid.uuid4()),
            "analysis_id": analysis_id,
            "issue_id": issue_id,
            "comment": request.comment or f"Status changed to {request.status}",
            "status": request.status or "open",
            "created_by": auth.user_id
        }
        
        result = supabase.table("issue_comments").insert(comment_data).execute()
        
        logger.info(f"✓ Issue {issue_id} status updated to {request.status} by {auth.email}")
        
        return {"message": "Issue status updated", "new_status": request.status}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update issue status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update issue status")


@router.delete("/analyses/{analysis_id}/comments/{comment_id}")
async def delete_issue_comment(
    analysis_id: str,
    comment_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """Delete an issue comment (owner only)"""
    supabase = get_supabase()
    
    try:
        # Get comment to verify ownership
        comment = (
            supabase.table("issue_comments")
            .select("created_by, analysis_id")
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
        supabase.table("issue_comments").delete().eq("id", comment_id).execute()
        
        logger.info(f"✓ Issue comment {comment_id} deleted by {auth.email}")
        return {"message": "Comment deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete issue comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete issue comment")


# ============================================
# FILE PURPOSES ENDPOINT
# ============================================

@router.get("/analyses/{analysis_id}/file-purposes")
async def get_analysis_file_purposes(
    analysis_id: str,
    auth: AuthContext = Depends(verify_token)
):
    """
    Get file purposes from an analysis.
    Shows what each file in the project does.
    """
    supabase = get_supabase()
    
    try:
        # Get analysis with project info
        analysis = (
            supabase.table("analyses")
            .select("project_id, file_purposes, organization_id")
            .eq("id", analysis_id)
            .eq("organization_id", auth.organization_id)
            .single()
            .execute()
        )
        
        if not analysis.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        file_purposes = analysis.data.get("file_purposes")
        
        if not file_purposes:
            # Generate file purposes if not available
            project_id = analysis.data["project_id"]
            local_path = Path(f"uploads/{project_id}/extracted")
            
            if local_path.exists():
                file_infos, _, project_structure = file_analyzer.analyze_project(local_path)
                file_purposes = file_analyzer.get_file_purposes_dict(file_infos)
                
                # Update analysis with file purposes
                supabase.table("analyses").update({
                    "file_purposes": file_purposes,
                    "project_structure": project_structure.to_dict()
                }).eq("id", analysis_id).execute()
            else:
                file_purposes = {}
        
        return {
            "analysis_id": analysis_id,
            "file_purposes": file_purposes,
            "file_count": len(file_purposes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file purposes: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file purposes")
