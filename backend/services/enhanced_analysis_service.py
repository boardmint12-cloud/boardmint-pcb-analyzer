"""
Enhanced Analysis Service
Uses canonical model + high-performance DRC engine
"""
import logging
import json
import time
from pathlib import Path
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor

from database import SessionLocal
from models.project import Project
from models.analysis_job import AnalysisJob
from services.parser_bridge import ParserBridge
from services.drc_engine import DRCEngine
from services.rule_profiles import RuleProfileLibrary
from config import get_settings

logger = logging.getLogger(__name__)


class EnhancedAnalysisService:
    """
    Enhanced analysis service with multi-CAD support and parallel DRC
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.parser_bridge = ParserBridge()
        self.drc_engine = DRCEngine(max_workers=self.settings.max_workers)
        self.profile_library = RuleProfileLibrary()
        
        logger.info(f"Enhanced Analysis Service initialized (workers: {self.settings.max_workers})")
    
    def analyze_project(
        self,
        project_id: str,
        profile_id: str = "2l_cheap_proto",
        enable_ai: bool = False
    ) -> Dict:
        """
        Analyze project with canonical model + DRC engine
        
        Args:
            project_id: Project UUID
            profile_id: Rule profile to use
            enable_ai: Enable AI-powered analysis
            
        Returns:
            Analysis results dictionary
        """
        start_time = time.time()
        
        logger.info(f"Starting enhanced analysis for project: {project_id}")
        
        # Get project from database
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            
            # Load CAD detection results
            project_dir = Path(project.extracted_path).parent
            detection_file = project_dir / "cad_detection.json"
            
            if detection_file.exists():
                with open(detection_file, 'r') as f:
                    detection_result = json.load(f)
                    tool_family = detection_result.get('tool_family', 'Unknown')
            else:
                tool_family = project.eda_tool
            
            logger.info(f"Detected tool: {tool_family}")
            
            # STEP 1: Parse to canonical model
            parse_start = time.time()
            board = self.parser_bridge.parse_to_canonical(
                project.extracted_path,
                tool_family
            )
            parse_time = time.time() - parse_start
            
            logger.info(f"✓ Parsing completed in {parse_time:.2f}s")
            logger.info(f"  - Components: {board.component_count()}")
            logger.info(f"  - Nets: {board.net_count()}")
            logger.info(f"  - Layers: {board.layer_count()}")
            
            # STEP 2: Recommend profile if needed
            if profile_id == "auto":
                profile_id = self._recommend_profile(board)
                logger.info(f"Auto-selected profile: {profile_id}")
            
            # STEP 3: Run DRC checks (parallel)
            drc_start = time.time()
            violations = self.drc_engine.run_checks(board, profile_id)
            drc_time = time.time() - drc_start
            
            logger.info(f"✓ DRC completed in {drc_time:.2f}s")
            logger.info(f"  - Violations: {len(violations)}")
            
            # STEP 4: Generate report
            report = self.drc_engine.generate_report(violations, board, profile_id)
            
            # STEP 5: Optional AI analysis
            if enable_ai and self.settings.enable_ai_analysis:
                ai_start = time.time()
                ai_insights = self._run_ai_analysis(board, violations)
                ai_time = time.time() - ai_start
                report['ai_insights'] = ai_insights
                logger.info(f"✓ AI analysis completed in {ai_time:.2f}s")
            
            total_time = time.time() - start_time
            
            # Add timing info
            report['performance'] = {
                "total_time": round(total_time, 2),
                "parse_time": round(parse_time, 2),
                "drc_time": round(drc_time, 2),
                "violations_per_second": round(len(violations) / drc_time if drc_time > 0 else 0, 2)
            }
            
            # Save report
            report_file = project_dir / "drc_report.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"✅ Analysis completed in {total_time:.2f}s - Status: {report['status']}")
            
            return report
            
        finally:
            db.close()
    
    def _recommend_profile(self, board) -> str:
        """Recommend profile based on board characteristics"""
        layer_count = board.layer_count()
        
        # Check for high voltage
        hv_nets = board.get_high_voltage_nets(threshold=100)
        if hv_nets:
            return "hv_power"
        
        # By layer count
        if layer_count == 2:
            return "2l_cheap_proto"
        elif layer_count == 4:
            return "4l_iot"
        elif layer_count >= 6:
            return "6l_hdi"
        
        return "ipc2221_generic"
    
    def _run_ai_analysis(self, board, violations) -> Dict:
        """
        Run AI-powered analysis for additional insights
        This is a placeholder for future AI integration
        """
        try:
            # Future: OpenAI/GPT analysis of violations
            # For now, return basic insights
            
            insights = {
                "enabled": True,
                "summary": f"Analyzed {board.component_count()} components and found {len(violations)} issues.",
                "suggestions": []
            }
            
            # Add context-aware suggestions
            if any(v.category.value == "high_voltage" for v in violations):
                insights["suggestions"].append({
                    "type": "high_voltage",
                    "message": "Consider adding conformal coating for high-voltage sections",
                    "priority": "high"
                })
            
            if board.layer_count() == 2 and board.component_count() > 50:
                insights["suggestions"].append({
                    "type": "design",
                    "message": "Complex 2-layer design - consider 4-layer for better routing",
                    "priority": "medium"
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {"enabled": False, "error": str(e)}
    
    def batch_analyze(self, project_ids: list, profile_id: str = "2l_cheap_proto") -> Dict:
        """
        Analyze multiple projects in parallel
        
        Args:
            project_ids: List of project UUIDs
            profile_id: Rule profile to use
            
        Returns:
            Batch results
        """
        logger.info(f"Starting batch analysis of {len(project_ids)} projects")
        
        results = {}
        failed = []
        
        # Use ThreadPoolExecutor for parallel analysis
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            future_to_project = {
                executor.submit(self.analyze_project, pid, profile_id): pid
                for pid in project_ids
            }
            
            for future in future_to_project:
                project_id = future_to_project[future]
                try:
                    result = future.result()
                    results[project_id] = {
                        "status": "success",
                        "report": result
                    }
                except Exception as e:
                    logger.error(f"Project {project_id} analysis failed: {e}")
                    failed.append(project_id)
                    results[project_id] = {
                        "status": "failed",
                        "error": str(e)
                    }
        
        return {
            "total": len(project_ids),
            "successful": len(project_ids) - len(failed),
            "failed": len(failed),
            "failed_projects": failed,
            "results": results
        }
