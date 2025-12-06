"""
PCB Analyzer - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path
import logging

from config import get_settings, ensure_upload_dir
from database import engine, Base, get_db
from sqlalchemy.orm import Session
from models.project import Project
from models.analysis_job import AnalysisJob
from services.upload_service import UploadService
from services.analysis_service import AnalysisService
from services.export_service import ExportService
from services.rule_profiles import RuleProfileLibrary, ProfileType
from services.enhanced_analysis_service import EnhancedAnalysisService
from services.cost_estimator import CostEstimator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting PCB Analyzer API...")
    ensure_upload_dir()
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down PCB Analyzer API...")


# Initialize FastAPI app
app = FastAPI(
    title="PCB Analyzer API",
    description="Building Automation PCB Analysis Platform",
    version="1.0.0",
    lifespan=lifespan
)

settings = get_settings()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "healthy",
        "service": "PCB Analyzer API",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "upload_dir": str(ensure_upload_dir()),
    }


# Project endpoints
@app.post("/api/upload")
async def upload_project(
    file: UploadFile = File(...),
    project_name: str = None,
    eda_tool: str = "auto"
):
    """
    Upload a PCB project (ZIP archive or single file)
    
    Supported formats:
    - ZIP archives containing project files
    - Single PCB files: .kicad_pcb, .brd, .PcbDoc, .dsn
    - Gerber files: .gbr, .gtl, .gbl, etc.
    - Manufacturing: IPC-2581 .xml, drill files
    - Assembly: BOM (.csv, .xlsx), Pick-and-place (.pos, .csv)
    
    Args:
        file: ZIP or single PCB/Gerber file
        project_name: Optional project name (defaults to filename)
        eda_tool: "auto" for auto-detection, or specific tool
    
    Returns:
        Project details with ID
    """
    try:
        upload_service = UploadService()
        project = await upload_service.upload_project(
            file=file,
            project_name=project_name,
            eda_tool=eda_tool
        )
        
        return {
            "success": True,
            "project": {
                "id": project.id,
                "name": project.name,
                "eda_tool": project.eda_tool,
                "status": project.status,
                "created_at": project.created_at.isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/{project_id}")
async def start_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    fab_profile: str = "cheap_cn_8mil"
):
    """
    Start analysis for a project
    
    Args:
        project_id: Project UUID
        fab_profile: Fabrication profile (cheap_cn_8mil, local_fab_8mil, hdi_4mil)
    
    Returns:
        Analysis job details
    """
    try:
        analysis_service = AnalysisService()
        
        # Create analysis job
        job = await analysis_service.create_job(project_id, fab_profile)
        
        # Run analysis in background
        background_tasks.add_task(
            analysis_service.run_analysis,
            job.id,
            project_id
        )
        
        return {
            "success": True,
            "job": {
                "id": job.id,
                "project_id": project_id,
                "status": job.status,
                "created_at": job.created_at.isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"Analysis start failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: Legacy endpoint disabled - using Supabase-backed route in routes/analyses.py
# @app.get("/api/results/{job_id}")
# async def get_analysis_results(job_id: str):
#     """Get analysis results for a job (LEGACY - uses SQLite)"""
#     try:
#         analysis_service = AnalysisService()
#         results = await analysis_service.get_results(job_id)
#         if not results:
#             raise HTTPException(status_code=404, detail="Job not found")
#         return results
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Failed to get results: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint removed - use multi-tenant routes/projects.py instead
# @app.get("/api/projects")
# async def list_projects(...)


@app.get("/api/export/{job_id}/pdf")
async def export_pdf_report(job_id: str, db: Session = Depends(get_db)):
    """
    Export analysis report as PDF (uses pre-generated PDF if available)
    
    Args:
        job_id: Analysis job UUID
        db: Database session (injected)
    
    Returns:
        PDF file download
    """
    try:
        # Check if PDF was pre-generated
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job and job.raw_results and job.raw_results.get("pdf_path"):
            pdf_path = job.raw_results["pdf_path"]
            logger.info(f"Using pre-generated PDF: {pdf_path}")
            
            if Path(pdf_path).exists():
                return FileResponse(
                    pdf_path,
                    media_type="application/pdf",
                    filename=f"pcb_analysis_{job_id}.pdf"
                )
            else:
                logger.warning(f"Pre-generated PDF not found at {pdf_path}, regenerating...")
        
        # Generate PDF on-demand if not pre-generated or file missing
        logger.info(f"Generating PDF on-demand for job {job_id}")
        export_service = ExportService()
        pdf_path = await export_service.generate_pdf(job_id)
        
        if not pdf_path or not Path(pdf_path).exists():
            raise HTTPException(status_code=404, detail="Report generation failed. Analysis may not be complete.")
        
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"pcb_analysis_{job_id}.pdf"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF export error: {str(e)}")


@app.get("/api/cost/{job_id}")
async def estimate_cost(job_id: str, db: Session = Depends(get_db)):
    """
    Estimate project cost (PCB + components + assembly)
    
    Args:
        job_id: Analysis job UUID
    
    Returns:
        Cost breakdown estimate
    """
    try:
        from services.parser_bridge import ParserBridge
        from parsers.hybrid_parser import HybridParser
        from pathlib import Path
        
        # Get job and project
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        project = db.query(Project).filter(Project.id == job.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Parse PCB to get canonical board model
        hybrid_parser = HybridParser()
        parsed_data = hybrid_parser.parse(Path(project.extracted_path))
        
        # Convert to canonical model
        bridge = ParserBridge()
        board = bridge.parse_to_canonical(parsed_data, project.extracted_path, project.eda_tool)
        
        # Estimate costs
        estimator = CostEstimator()
        cost_breakdown = estimator.estimate(board)
        
        return {
            "success": True,
            "job_id": job_id,
            "project_id": project.id,
            "cost_breakdown": {
                "pcb_cost": cost_breakdown.pcb_cost,
                "component_cost": cost_breakdown.component_cost,
                "assembly_cost": cost_breakdown.assembly_cost,
                "total_cost": cost_breakdown.total_cost,
                "currency": cost_breakdown.currency,
                "notes": cost_breakdown.notes
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cost estimation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{project_id}")
async def get_project_history(project_id: str, db: Session = Depends(get_db)):
    """
    Get analysis history for a project
    
    Shows trend over time: improving, stable, or regressing
    
    Args:
        project_id: Project UUID
    
    Returns:
        List of historical analysis results
    """
    try:
        # Get all completed jobs for this project
        jobs = db.query(AnalysisJob)\
                 .filter(AnalysisJob.project_id == project_id)\
                 .filter(AnalysisJob.status == "completed")\
                 .order_by(AnalysisJob.completed_at.desc())\
                 .all()
        
        if not jobs:
            return {
                "success": True,
                "project_id": project_id,
                "history": [],
                "trend": "no_data"
            }
        
        # Build history list
        history = []
        for job in jobs:
            history.append({
                "job_id": job.id,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "risk_level": job.risk_level,
                "critical_count": int(job.critical_count) if job.critical_count else 0,
                "warning_count": int(job.warning_count) if job.warning_count else 0,
                "info_count": int(job.info_count) if job.info_count else 0,
                "fab_profile": job.fab_profile
            })
        
        # Determine trend (comparing last 2 analyses)
        trend = "no_data"
        if len(history) >= 2:
            latest = history[0]
            previous = history[1]
            
            latest_critical = latest["critical_count"]
            prev_critical = previous["critical_count"]
            
            if latest_critical < prev_critical:
                trend = "improving"
            elif latest_critical > prev_critical:
                trend = "regressing"
            else:
                trend = "stable"
        
        return {
            "success": True,
            "project_id": project_id,
            "history": history,
            "trend": trend,
            "total_analyses": len(history)
        }
    
    except Exception as e:
        logger.error(f"Failed to get project history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Rule Profiles endpoints
@app.get("/api/profiles")
async def list_rule_profiles(profile_type: Optional[str] = None):
    """
    List available rule profiles
    
    Args:
        profile_type: Optional filter by type (board_tech, standard, manufacturer)
    
    Returns:
        List of rule profiles
    """
    try:
        library = RuleProfileLibrary()
        
        if profile_type:
            try:
                ptype = ProfileType(profile_type)
                profiles = library.list_profiles(ptype)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid profile type: {profile_type}")
        else:
            profiles = library.list_profiles()
        
        # Return summaries
        return {
            "success": True,
            "count": len(profiles),
            "profiles": [library.profile_summary(p.id) for p in profiles]
        }
    
    except Exception as e:
        logger.error(f"Failed to list profiles: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles/{profile_id}")
async def get_rule_profile(profile_id: str):
    """
    Get detailed rule profile
    
    Args:
        profile_id: Profile identifier
    
    Returns:
        Detailed profile information
    """
    try:
        library = RuleProfileLibrary()
        profile = library.get_profile(profile_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
        
        return {
            "success": True,
            "profile": library.profile_summary(profile_id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Enhanced Analysis endpoint (NEW - High Performance)
@app.post("/api/analyze/enhanced/{project_id}")
async def enhanced_analysis(
    project_id: str,
    profile_id: str = "auto",
    enable_ai: bool = False,
    background_tasks: BackgroundTasks = None
):
    """
    🚀 Enhanced high-performance analysis with canonical model + parallel DRC
    
    Args:
        project_id: Project UUID
        profile_id: Rule profile ID (or "auto" for automatic selection)
        enable_ai: Enable AI-powered insights
    
    Returns:
        Comprehensive DRC report with violations
    """
    try:
        logger.info(f"🚀 Enhanced analysis started for project: {project_id}")
        
        enhanced_service = EnhancedAnalysisService()
        
        # Run analysis
        report = enhanced_service.analyze_project(
            project_id=project_id,
            profile_id=profile_id,
            enable_ai=enable_ai
        )
        
        return {
            "success": True,
            "project_id": project_id,
            "report": report
        }
    
    except Exception as e:
        logger.error(f"Enhanced analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/batch")
async def batch_analysis(
    project_ids: List[str],
    profile_id: str = "auto"
):
    """
    🚀 Batch analysis of multiple projects in parallel
    
    Args:
        project_ids: List of project UUIDs
        profile_id: Rule profile to use
    
    Returns:
        Batch analysis results
    """
    try:
        logger.info(f"🚀 Batch analysis started for {len(project_ids)} projects")
        
        enhanced_service = EnhancedAnalysisService()
        
        results = enhanced_service.batch_analyze(
            project_ids=project_ids,
            profile_id=profile_id
        )
        
        return {
            "success": True,
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Batch analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# MULTI-TENANT ROUTES (Production SaaS)
# ============================================

# Import multi-tenant route modules
try:
    from routes import auth, organizations, projects, analyses, quotes
    
    # Register multi-tenant routes
    app.include_router(auth.router)
    app.include_router(organizations.router)
    app.include_router(projects.router)
    app.include_router(analyses.router)
    app.include_router(quotes.router)
    
    logger.info("✓ Multi-tenant routes registered")
except ImportError as e:
    logger.warning(f"Multi-tenant routes not available: {e}")
    logger.warning("Running in legacy mode without multi-tenancy")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.python_env == "development",
        workers=4 if settings.python_env == "production" else 1,  # Multi-worker in production
        limit_concurrency=1000,  # Handle more concurrent connections
        limit_max_requests=10000,  # Restart workers after N requests (memory management)
        timeout_keep_alive=65,  # Keep connections alive longer
        log_level="info"
    )
