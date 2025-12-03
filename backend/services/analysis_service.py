"""
Analysis service - runs PCB analysis pipeline with GPT-5.1 extraction
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from database import SessionLocal
from sqlalchemy.orm import Session
from models.project import Project
from models.analysis_job import AnalysisJob
from models.issue import Issue as IssueModel
from parsers import KiCadParser, GerberParser
from parsers.hybrid_parser import HybridParser
from rules import (
    MainsSafetyRules,
    BusInterfaceRules,
    PowerSMPSRules,
    BOMSanityRules,
    AssemblyTestRules,
    Issue
)
from services.ai_service import AIAnalysisService
from services.file_loader import FileLoader
from services.gpt_extractor import GPTExtractor
from services.cache_service import get_cache

logger = logging.getLogger(__name__)


class AnalysisService:
    """Handle PCB analysis workflows"""
    
    async def create_job(self, project_id: str, fab_profile: str = "cheap_cn_8mil", db: Session = None):
        """
        Create a new analysis job
        
        Args:
            project_id: Project UUID
            fab_profile: Fabrication profile
            db: Database session (optional, creates new if not provided)
            
        Returns:
            AnalysisJob object
        """
        # Support both injection and manual creation for backward compatibility
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        
        try:
            # Verify project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Create job
            job = AnalysisJob(
                project_id=project_id,
                fab_profile=fab_profile,
                status="pending"
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
            logger.info(f"Created analysis job {job.id} for project {project_id}")
            return job
        
        finally:
            if should_close:
                db.close()
    
    async def run_analysis(self, job_id: str, project_id: str, db: Session = None):
        """
        Run full analysis pipeline (background task)
        
        Args:
            job_id: Analysis job UUID
            project_id: Project UUID
            db: Database session (optional, creates new if not provided)
        """
        # Support both injection and manual creation
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        
        try:
            # Get job and project
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not job or not project:
                logger.error(f"Job or project not found: {job_id}, {project_id}")
                return
            
            # Check cache first
            cache = get_cache()
            file_hash = cache.compute_file_hash(project.zip_path)
            cache_key = cache.get_cache_key(project_id, file_hash, job.fab_profile or "auto")
            
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"🎯 Using cached analysis for project {project_id}")
                # Restore job from cached data
                job.status = "completed"
                job.started_at = datetime.utcnow()
                job.completed_at = datetime.utcnow()
                job.progress = "Restored from cache"
                job.raw_results = cached_result.get('raw_results', {})
                job.risk_level = cached_result.get('risk_level')
                job.critical_count = cached_result.get('critical_count', 0)
                job.warning_count = cached_result.get('warning_count', 0)
                job.info_count = cached_result.get('info_count', 0)
                db.commit()
                
                # Restore issues
                for issue_data in cached_result.get('issues', []):
                    issue = IssueModel(**issue_data)
                    issue.job_id = job_id
                    db.add(issue)
                db.commit()
                
                logger.info(f"✅ Cache restore complete: {job.critical_count} critical, {job.warning_count} warnings")
                return
            
            # Update status
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.progress = "Parsing project files..."
            db.commit()
            
            logger.info(f"Starting GPT-5.1 powered analysis for job {job_id}")
            
            # Step 1: Load and organize files
            job.progress = "Loading project files..."
            db.commit()
            
            file_loader = FileLoader()
            organized_files = file_loader.extract_and_flatten(
                Path(project.zip_path),
                Path(project.extracted_path)
            )
            
            # Step 2: Use HybridParser (Deterministic + AI semantic classification)
            job.progress = "Parsing PCB with hybrid deterministic+AI method..."
            db.commit()
            
            hybrid_parser = HybridParser()
            try:
                logger.info(f"Starting HybridParser on: {project.extracted_path}")
                pcb_data = hybrid_parser.parse(Path(project.extracted_path))
                logger.info(f"✅ HybridParser success: {len(pcb_data.components)} components, {len(pcb_data.nets)} nets, board_info: {pcb_data.board_info}")
                
                # Update raw results with deterministic geometry
                job.raw_results = {
                    "board_info": {
                        "size_x": pcb_data.board_info.size_x if pcb_data.board_info else 0,
                        "size_y": pcb_data.board_info.size_y if pcb_data.board_info else 0,
                        "layer_count": pcb_data.board_info.layer_count if pcb_data.board_info else 0,
                    },
                    "nets_count": len(pcb_data.nets),
                    "components_count": len(pcb_data.components),
                    "parsing_method": "hybrid_deterministic_ai",
                    "files_found": {
                        "pcb": len(organized_files.get('pcb', [])) > 0,
                        "schematic": len(organized_files.get('schematic', [])) > 0,
                        "netlist": len(organized_files.get('netlist', [])) > 0,
                        "bom": len(organized_files.get('bom', [])) > 0
                    }
                }
                db.commit()
                
            except Exception as e:
                logger.error(f"❌ HybridParser failed: {e}", exc_info=True)
                logger.info("Falling back to GPT extraction...")
                # Fallback to old method if hybrid fails
                try:
                    extracted_data = self._gpt_extract_project(organized_files, file_loader)
                    logger.info(f"GPT extraction: {len(extracted_data.get('components', []))} components")
                    pcb_data = self._convert_gpt_to_parsed_data(extracted_data)
                    job.raw_results = {
                        "board_info": extracted_data.get("board_info", {}),
                        "nets_count": len(extracted_data.get("nets", [])),
                        "components_count": len(extracted_data.get("components", [])),
                        "parsing_method": "gpt_fallback",
                    }
                    db.commit()
                except Exception as fallback_error:
                    logger.error(f"❌ GPT fallback also failed: {fallback_error}", exc_info=True)
                    # Create empty pcb_data to continue analysis
                    from parsers import ParsedPCBData, Component, Net, BoardInfo
                    pcb_data = ParsedPCBData(
                        board_info=None,
                        components=[],
                        nets=[]
                    )
                    job.raw_results = {
                        "board_info": {},
                        "nets_count": 0,
                        "components_count": 0,
                        "parsing_method": "failed_both",
                        "error": str(fallback_error)
                    }
                    db.commit()
            
            # Step 3: Generate board summary (what does this board do?)
            job.progress = "Analyzing board purpose and functionality..."
            db.commit()
            
            try:
                if len(pcb_data.components) > 0:
                    board_summary = self._generate_board_summary(pcb_data, Path(project.extracted_path))
                else:
                    logger.warning("No components found, skipping board summary")
                    board_summary = {
                        "purpose": "Unable to determine (no components extracted)",
                        "description": "PCB parsing found no components. The file may be empty, corrupted, or in an unsupported format.",
                        "key_features": [],
                        "main_components": [],
                        "design_notes": "Please verify the uploaded file is a valid KiCad PCB file."
                    }
                
                # CRITICAL: Must reassign the whole dict to trigger SQLAlchemy change detection
                if not job.raw_results:
                    job.raw_results = {}
                
                updated_raw_results = dict(job.raw_results)  # Create a copy
                updated_raw_results["board_summary"] = board_summary
                job.raw_results = updated_raw_results  # Reassign to trigger change detection
                
                db.commit()
                logger.info(f"Generated board summary: {board_summary.get('purpose', 'unknown')}")
            except Exception as summary_error:
                logger.error(f"Board summary generation failed: {summary_error}", exc_info=True)
                # CRITICAL: Must reassign to trigger SQLAlchemy change detection
                updated_raw_results = dict(job.raw_results) if job.raw_results else {}
                updated_raw_results["board_summary"] = {
                    "purpose": "Summary generation failed",
                    "description": str(summary_error),
                    "key_features": [],
                    "main_components": [],
                    "design_notes": ""
                }
                job.raw_results = updated_raw_results
                db.commit()
            
            # Step 4: Run rule engines (OLD + NEW DRC)
            job.progress = "Running analysis rules..."
            db.commit()
            
            all_issues = self._run_rule_engines(pcb_data, job.fab_profile)
            
            # Step 4b: Run NEW enhanced DRC engine in parallel
            job.progress = "Running enhanced DRC checks..."
            db.commit()
            
            try:
                logger.info("Running enhanced DRC engine...")
                enhanced_issues = self._run_enhanced_drc(pcb_data, str(project.extracted_path), job.fab_profile, project.eda_tool)
                all_issues.extend(enhanced_issues)
                logger.info(f"✅ Enhanced DRC found {len(enhanced_issues)} additional issues")
            except Exception as drc_error:
                logger.error(f"❌ Enhanced DRC failed: {drc_error}", exc_info=True)
            
            # Step 5: AI-enhanced analysis for additional insights
            job.progress = "Running AI insights (GPT-5.1)..."
            db.commit()
            
            ai_service = AIAnalysisService()
            ai_issues, ai_suggestions = ai_service.analyze_pcb(
                project_path=Path(project.extracted_path),
                parsed_data={
                    "board_info": job.raw_results.get("board_info", {}),
                    "nets": [{"name": n.name, "connections": n.pads} for n in pcb_data.nets],
                    "components": [{"reference": c.reference, "value": c.value} for c in pcb_data.components]
                },
                rule_engine_issues=all_issues,
                fab_profile=job.fab_profile
            )
            
            # Combine rule engine + AI issues
            all_issues.extend(ai_issues)
            logger.info(f"Total issues: {len(all_issues)} (AI added {len(ai_issues)} issues + {len(ai_suggestions)} suggestions)")
            
            # Store suggestions in job.raw_results for display
            if not job.raw_results:
                job.raw_results = {}
            job.raw_results["ai_suggestions"] = ai_suggestions
            
            # Step 6: Store issues
            job.progress = "Storing results..."
            db.commit()
            
            self._store_issues(job_id, all_issues, db)
            
            # Step 7: Calculate summary
            critical_count = sum(1 for i in all_issues if i.severity.value == "critical")
            warning_count = sum(1 for i in all_issues if i.severity.value == "warning")
            info_count = sum(1 for i in all_issues if i.severity.value == "info")
            
            # Determine risk level
            if critical_count > 3:
                risk_level = "high"
            elif critical_count > 0 or warning_count > 5:
                risk_level = "moderate"
            else:
                risk_level = "low"
            
            # Update job
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.risk_level = risk_level
            job.critical_count = str(critical_count)
            job.warning_count = str(warning_count)
            job.info_count = str(info_count)
            job.progress = "Complete"
            
            # Update project status
            project.status = "completed"
            if pcb_data.board_info:
                project.layer_count = pcb_data.board_info.layer_count
                project.board_size_x = int(pcb_data.board_info.size_x) if pcb_data.board_info.size_x else 0
                project.board_size_y = int(pcb_data.board_info.size_y) if pcb_data.board_info.size_y else 0
            else:
                logger.warning("board_info is None, using default values")
                project.layer_count = 0
                project.board_size_x = 0
                project.board_size_y = 0
            
            db.commit()
            
            # Store in cache for future use
            cache_data = {
                'raw_results': job.raw_results,
                'risk_level': risk_level,
                'critical_count': critical_count,
                'warning_count': warning_count,
                'info_count': info_count,
                'issues': [
                    {
                        'issue_code': issue.issue_code,
                        'severity': issue.severity,
                        'category': issue.category,
                        'title': issue.title,
                        'description': issue.description,
                        'suggested_fix': issue.suggested_fix,
                        'affected_nets': issue.affected_nets,
                        'affected_components': issue.affected_components,
                        'location_x': issue.location_x,
                        'location_y': issue.location_y,
                        'layer': issue.layer
                    }
                    for issue in all_issues
                ]
            }
            cache.set(cache_key, cache_data)
            
            logger.info(f"Analysis complete for job {job_id}: {risk_level} risk, "
                       f"{critical_count} critical, {warning_count} warnings")
            logger.info(f"💾 Cached results for future analyses")
            
            # Step 8: Pre-generate PDF report for instant download
            job.progress = "Generating PDF report..."
            db.commit()
            
            try:
                from services.export_service import ExportService
                export_service = ExportService()
                logger.info(f"Starting PDF generation for job {job_id}")
                pdf_path = export_service.generate_pdf_sync(job_id)  # Synchronous version
                if pdf_path:
                    # CRITICAL: Must reassign to trigger SQLAlchemy change detection
                    updated_raw_results = dict(job.raw_results) if job.raw_results else {}
                    updated_raw_results["pdf_path"] = pdf_path
                    job.raw_results = updated_raw_results
                    db.commit()
                    logger.info(f"✅ PDF pre-generated at: {pdf_path}")
                else:
                    logger.warning("⚠️ PDF pre-generation returned None, will generate on-demand")
            except Exception as pdf_error:
                logger.error(f"❌ PDF pre-generation failed: {pdf_error}", exc_info=True)
                logger.warning("PDF will be generated on-demand when requested")
            
            job.progress = "Complete"
            db.commit()
            
        except Exception as e:
            logger.error(f"Analysis failed for job {job_id}: {e}", exc_info=True)
            
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
        
        finally:
            if should_close:
                db.close()
    
    def _generate_board_summary(self, pcb_data, project_path: Path) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of what the board does and how it works.
        
        CRITICAL FIX: Now uses deterministic component classification to prevent
        AI from misidentifying components (e.g., NRF24L01 as MCU instead of ATmega328P).
        
        Returns:
            Dict with keys: purpose, description, key_features, main_components, design_notes, main_mcu
        """
        try:
            from openai import OpenAI
            from config import get_settings
            from services.component_classifier import ComponentClassifier
            import json
            
            settings = get_settings()
            if not settings.openai_api_key:
                logger.warning("OpenAI API key not configured, skipping board summary")
                return {"purpose": "Unknown (AI not configured)", "description": "", "key_features": []}
            
            client = OpenAI(api_key=settings.openai_api_key)
            classifier = ComponentClassifier()
            
            # CRITICAL: Classify components BEFORE sending to AI
            # This provides ground truth that AI MUST respect
            classified_components = classifier.classify_all(pcb_data.components)
            
            # Find main MCU deterministically (don't let AI guess)
            main_mcu = classifier.find_main_mcu(classified_components)
            
            # Group components by type for structured prompt
            grouped = classifier.group_by_type(classified_components)
            
            # Build structured component lists
            mcu_list = []
            for comp in grouped.get('MCU', [])[:5]:
                mcu_list.append(f"  - {comp['ref']}: {comp['value']} (MAIN MICROCONTROLLER)")
            
            wireless_list = []
            for comp in grouped.get('WIRELESS_MODULE', [])[:5]:
                wireless_list.append(f"  - {comp['ref']}: {comp['value']} (WIRELESS/RADIO MODULE - NOT a CPU)")
            
            power_list = []
            for comp in grouped.get('VOLTAGE_REGULATOR', [])[:5]:
                power_list.append(f"  - {comp['ref']}: {comp['value']} (VOLTAGE REGULATOR)")
            
            sensor_list = []
            for comp in grouped.get('SENSOR', [])[:5]:
                sensor_list.append(f"  - {comp['ref']}: {comp['value']} (SENSOR)")
            
            comm_list = []
            for comp in grouped.get('COMMUNICATION', [])[:5]:
                comm_list.append(f"  - {comp['ref']}: {comp['value']} (COMMUNICATION INTERFACE)")
            
            other_ics = []
            for comp in grouped.get('OTHER', [])[:10]:
                if comp['ref'].upper().startswith('U'):  # Only ICs
                    other_ics.append(f"  - {comp['ref']}: {comp['value']}")
            
            # Build constraint-heavy prompt
            system_msg = """You are an expert embedded systems and PCB design engineer.

CRITICAL RULES - DO NOT VIOLATE THESE:
1. Components are PRE-CLASSIFIED with a 'class' field. This classification is GROUND TRUTH.
2. NEVER contradict the component classification.
3. Components labeled "MAIN MICROCONTROLLER" are the main CPU.
4. Components labeled "WIRELESS/RADIO MODULE - NOT a CPU" are NOT the main microcontroller.
5. Components labeled "VOLTAGE REGULATOR" are power supplies, not processors.
6. If you see exactly ONE microcontroller, that MUST be the main MCU in your analysis.
7. Do not guess or speculate beyond what the components definitively show."""

            user_prompt = f"""Analyze this PCB design and provide a comprehensive summary.

**BOARD INFORMATION:**
- Dimensions: {pcb_data.board_info.size_x if pcb_data.board_info else 'unknown'}mm x {pcb_data.board_info.size_y if pcb_data.board_info else 'unknown'}mm
- Layers: {pcb_data.board_info.layer_count if pcb_data.board_info else 'unknown'}
- Total Components: {len(pcb_data.components)}
- Nets: {len(pcb_data.nets)}

**MICROCONTROLLERS (Main CPU):**
{chr(10).join(mcu_list) if mcu_list else "  - None detected"}

**WIRELESS/COMMUNICATION MODULES:**
{chr(10).join(wireless_list) if wireless_list else "  - None detected"}

**POWER MANAGEMENT:**
{chr(10).join(power_list) if power_list else "  - None detected"}

**SENSORS:**
{chr(10).join(sensor_list) if sensor_list else "  - None detected"}

**COMMUNICATION INTERFACES:**
{chr(10).join(comm_list) if comm_list else "  - None detected"}

**OTHER ICs:**
{chr(10).join(other_ics[:5]) if other_ics else "  - None detected"}

**KEY NETS:**
{', '.join([net.name for net in pcb_data.nets[:20]])}

INSTRUCTIONS:
Based on the CLASSIFIED components above, provide a summary.
The MAIN MICROCONTROLLER is: {main_mcu['ref'] + ' (' + main_mcu['value'] + ')' if main_mcu else 'None detected'}

Return STRICTLY valid JSON with this structure:
{{
  "purpose": "What this board is designed to do (1-2 sentences)",
  "description": "How it works and main functional blocks (2-3 sentences)",
  "key_features": ["Feature 1", "Feature 2", "Feature 3"],
  "main_mcu": {{
    "ref": "{main_mcu['ref'] if main_mcu else 'None'}",
    "value": "{main_mcu['value'] if main_mcu else 'None'}"
  }},
  "main_components": ["Component role 1", "Component role 2", "Component role 3"],
  "design_notes": "Notable design aspects"
}}

Be specific and factual. Do not speculate beyond what components show.
Do NOT output any text outside the JSON. No commentary, no markdown."""

            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Lower temperature for more deterministic output
                max_tokens=1000
            )
            
            summary = json.loads(response.choices[0].message.content)
            
            # CRITICAL: Override main_mcu with our deterministic result
            # Even if AI says something different, we use ground truth
            if main_mcu:
                summary['main_mcu'] = {
                    'ref': main_mcu['ref'],
                    'value': main_mcu['value']
                }
            
            logger.info(f"✓ Generated board summary: {summary.get('purpose', 'unknown')[:60]}...")
            logger.info(f"✓ Main MCU (deterministic): {main_mcu['ref'] if main_mcu else 'None'}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate board summary: {e}", exc_info=True)
            return {
                "purpose": "Analysis board (summary generation failed)",
                "description": "Could not determine board functionality",
                "key_features": [],
                "main_components": [],
                "design_notes": ""
            }
    
    def _gpt_extract_project(self, organized_files: Dict, file_loader: FileLoader) -> Dict[str, Any]:
        """
        Use GPT-5.1 to extract structured data from PCB files
        
        Args:
            organized_files: Files organized by type
            file_loader: FileLoader instance
            
        Returns:
            Extracted structured data
        """
        logger.info("Starting GPT-powered extraction")
        
        gpt_extractor = GPTExtractor()
        
        # Prepare file contents
        prepared = file_loader.prepare_for_gpt(organized_files)
        
        # Extract from PCB file
        board_data = {}
        if prepared['pcb_files']:
            pcb_file = prepared['pcb_files'][0]
            board_data = gpt_extractor.extract_board_data(
                pcb_file['content'],
                pcb_file['filename']
            )
        
        # Extract from schematic
        schematic_data = {}
        if prepared['schematic_files']:
            sch_file = prepared['schematic_files'][0]
            schematic_data = gpt_extractor.extract_schematic_data(
                sch_file['content'],
                sch_file['filename']
            )
        
        # Extract from netlist
        netlist_data = {}
        if prepared['netlist_files']:
            net_file = prepared['netlist_files'][0]
            netlist_data = gpt_extractor.extract_netlist_data(
                net_file['content']
            )
        
        # Merge all data sources
        merged_data = gpt_extractor.merge_data_sources(
            board_data,
            schematic_data,
            netlist_data
        )
        
        logger.info(f"GPT extraction complete: {len(merged_data.get('components', []))} components")
        
        return merged_data
    
    def _convert_gpt_to_parsed_data(self, gpt_data: Dict) -> Any:
        """
        Convert GPT extracted data to ParsedPCBData format for rule engines
        
        Args:
            gpt_data: Data from GPT extraction
            
        Returns:
            ParsedPCBData object compatible with rule engines
        """
        from parsers.base_parser import ParsedPCBData, BoardInfo, Net, Component
        
        # Convert board info
        board_info_dict = gpt_data.get('board_info', {})
        board_info = BoardInfo(
            size_x=board_info_dict.get('size_x_mm', 0),
            size_y=board_info_dict.get('size_y_mm', 0),
            layer_count=board_info_dict.get('layer_count', 2)
        )
        
        # Convert components
        components = []
        for comp_dict in gpt_data.get('components', []):
            comp = Component(
                reference=comp_dict.get('reference', '?'),
                value=comp_dict.get('value', ''),
                footprint=comp_dict.get('footprint', ''),
                x=comp_dict.get('x_mm', 0),
                y=comp_dict.get('y_mm', 0),
                rotation=comp_dict.get('rotation_deg', 0),
                layer=comp_dict.get('layer', 'Top')
            )
            components.append(comp)
        
        # Convert nets
        nets = []
        for net_dict in gpt_data.get('nets', []):
            net = Net(
                name=net_dict.get('name', ''),
                is_power=net_dict.get('is_power', False),
                is_ground=net_dict.get('is_ground', False),
                is_mains=net_dict.get('is_mains', False)
            )
            # Add pad connections if available
            net.pads = net_dict.get('connections', [])
            nets.append(net)
        
        return ParsedPCBData(
            board_info=board_info,
            nets=nets,
            components=components,
            files_found={
                'pcb': True,
                'schematic': len(gpt_data.get('components', [])) > 0,
                'bom': False,
                'position': False
            },
            raw_data=gpt_data
        )
    
    def _parse_project(self, project: Project, job: AnalysisJob):
        """Parse project files based on EDA tool"""
        try:
            if project.eda_tool == "kicad":
                parser = KiCadParser()
            else:
                parser = GerberParser()
            
            pcb_data = parser.parse(project.extracted_path)
            logger.info(f"Parsed project: {len(pcb_data.components)} components, {len(pcb_data.nets)} nets")
            
            return pcb_data
            
        except Exception as e:
            logger.error(f"Parse failed: {e}", exc_info=True)
            return None
    
    def _run_rule_engines(self, pcb_data, fab_profile: str) -> List[Issue]:
        """Run all rule engines"""
        all_issues = []
        
        # Instantiate rule engines
        engines = [
            MainsSafetyRules(fab_profile),
            BusInterfaceRules(fab_profile),
            PowerSMPSRules(fab_profile),
            BOMSanityRules(fab_profile),
            AssemblyTestRules(fab_profile),
        ]
        
        # Run each engine
        for engine in engines:
            try:
                engine_name = engine.__class__.__name__
                logger.info(f"Running {engine_name}...")
                
                issues = engine.analyze(pcb_data)
                all_issues.extend(issues)
                
                logger.info(f"{engine_name}: {len(issues)} issues found")
                
            except Exception as e:
                logger.error(f"Rule engine {engine.__class__.__name__} failed: {e}", exc_info=True)
        
        return all_issues
    
    def _run_enhanced_drc(self, pcb_data, extracted_path: str, fab_profile: str, eda_tool: str = "kicad") -> List[Issue]:
        """
        Run enhanced DRC engine and convert results to old Issue format
        
        Args:
            pcb_data: Parsed PCB data
            extracted_path: Path to extracted project
            fab_profile: Fabrication profile
            eda_tool: EDA tool name
            
        Returns:
            List of Issue objects
        """
        try:
            from services.parser_bridge import ParserBridge
            from services.drc_engine import DRCEngine
            from rules import Issue, IssueSeverity
            
            # Convert to canonical model
            bridge = ParserBridge()
            board = bridge._convert_to_canonical(pcb_data, extracted_path, eda_tool)
            
            # Select profile based on fab_profile
            profile_map = {
                "cheap_cn_8mil": "2l_cheap_proto",
                "local_fab_8mil": "4l_iot",
                "hdi_4mil": "6l_hdi"
            }
            profile_id = profile_map.get(fab_profile, "2l_cheap_proto")
            
            # Run DRC
            drc_engine = DRCEngine(max_workers=8)  # Use 8 workers for background task
            violations = drc_engine.run_checks(board, profile_id)
            
            # Convert violations to old Issue format
            issues = []
            for violation in violations:
                # Map severity
                if violation.severity.value == "critical":
                    severity = IssueSeverity.CRITICAL
                elif violation.severity.value == "error":
                    severity = IssueSeverity.CRITICAL  # Map ERROR to CRITICAL
                elif violation.severity.value == "warning":
                    severity = IssueSeverity.WARNING
                else:
                    severity = IssueSeverity.INFO
                
                # Build suggested fix
                suggested_fix = violation.description
                if violation.required and violation.actual:
                    suggested_fix += f" | Actual: {violation.actual}mm, Required: {violation.required}mm"
                elif violation.required:
                    suggested_fix += f" | Required: {violation.required}mm"
                
                issue = Issue(
                    issue_code=f"DRC_{violation.category.value.upper()}",
                    severity=severity,
                    category=violation.category.value,
                    title=violation.description[:100],  # Shorter title
                    description=violation.description,
                    suggested_fix=suggested_fix,
                    affected_nets=[violation.net1, violation.net2] if violation.net1 else [],
                    affected_components=[violation.component] if violation.component else [],
                    location_x=violation.x,
                    location_y=violation.y,
                    layer=violation.layer
                )
                issues.append(issue)
            
            return issues
            
        except Exception as e:
            logger.error(f"Enhanced DRC failed: {e}", exc_info=True)
            return []
    
    def _store_issues(self, job_id: str, issues: List[Issue], db):
        """Store issues in database"""
        for issue in issues:
            issue_model = IssueModel(
                job_id=job_id,
                issue_code=issue.issue_code,
                severity=issue.severity.value,
                category=issue.category,
                title=issue.title,
                description=issue.description,
                suggested_fix=issue.suggested_fix,
                affected_nets=issue.affected_nets,
                affected_components=issue.affected_components,
                location_x=issue.location_x,
                location_y=issue.location_y,
                layer=issue.layer
            )
            db.add(issue_model)
        
        db.commit()
        logger.info(f"Stored {len(issues)} issues for job {job_id}")
    
    async def get_results(self, job_id: str, db: Session = None):
        """
        Get analysis results for a job
        
        Args:
            job_id: Analysis job UUID
            db: Database session (optional)
            
        Returns:
            Results dictionary
        """
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            
            if not job:
                return None
            
            # Get issues
            issues = db.query(IssueModel).filter(IssueModel.job_id == job_id).all()
            
            # Group issues by category
            issues_by_category = {}
            for issue in issues:
                if issue.category not in issues_by_category:
                    issues_by_category[issue.category] = []
                
                issues_by_category[issue.category].append({
                    "id": issue.id,
                    "issue_code": issue.issue_code,
                    "severity": issue.severity,
                    "title": issue.title,
                    "description": issue.description,
                    "suggested_fix": issue.suggested_fix,
                    "affected_nets": issue.affected_nets,
                    "affected_components": issue.affected_components,
                    "location_x": issue.location_x,
                    "location_y": issue.location_y,
                    "layer": issue.layer
                })
            
            return {
                "job_id": job.id,
                "project_id": job.project_id,
                "status": job.status,
                "progress": job.progress,
                "risk_level": job.risk_level,
                "summary": {
                    "critical": int(job.critical_count) if job.critical_count else 0,
                    "warning": int(job.warning_count) if job.warning_count else 0,
                    "info": int(job.info_count) if job.info_count else 0,
                },
                "board_info": job.raw_results.get("board_info") if job.raw_results else None,
                "board_summary": job.raw_results.get("board_summary") if job.raw_results else None,
                "issues_by_category": issues_by_category,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
            
        finally:
            if should_close:
                db.close()
