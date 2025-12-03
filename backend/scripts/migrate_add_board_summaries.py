#!/usr/bin/env python3
"""
Migration Script: Regenerate Board Summaries
Fixes missing board_summary data for existing analysis jobs
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.analysis_job import AnalysisJob
from models.project import Project
from services.analysis_service import AnalysisService
from parsers.hybrid_parser import HybridParser
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_board_summaries(dry_run=False):
    """
    Regenerate board summaries for jobs missing them
    
    Args:
        dry_run: If True, only show what would be done
    """
    db = SessionLocal()
    
    try:
        # Find all completed jobs
        logger.info("Finding completed jobs...")
        jobs = db.query(AnalysisJob)\
                 .filter(AnalysisJob.status == "completed")\
                 .all()
        
        logger.info(f"Found {len(jobs)} completed jobs")
        
        # Check which ones are missing board_summary
        jobs_to_fix = []
        for job in jobs:
            if not job.raw_results or not job.raw_results.get("board_summary"):
                jobs_to_fix.append(job)
        
        logger.info(f"Jobs missing board_summary: {len(jobs_to_fix)}")
        
        if len(jobs_to_fix) == 0:
            logger.info("✅ All jobs already have board summaries!")
            return
        
        if dry_run:
            logger.info("DRY RUN - Would fix these jobs:")
            for job in jobs_to_fix[:10]:  # Show first 10
                logger.info(f"  - Job {job.id} (Project: {job.project_id})")
            if len(jobs_to_fix) > 10:
                logger.info(f"  ... and {len(jobs_to_fix) - 10} more")
            return
        
        # Create service instance
        service = AnalysisService()
        parser = HybridParser()
        
        # Process each job
        success_count = 0
        error_count = 0
        
        for i, job in enumerate(jobs_to_fix, 1):
            logger.info(f"[{i}/{len(jobs_to_fix)}] Processing job {job.id}...")
            
            try:
                # Get project
                project = db.query(Project).filter(Project.id == job.project_id).first()
                if not project:
                    logger.warning(f"  ⚠️ Project {job.project_id} not found, skipping")
                    error_count += 1
                    continue
                
                # Check if extracted path exists
                extracted_path = Path(project.extracted_path)
                if not extracted_path.exists():
                    logger.warning(f"  ⚠️ Extracted path not found: {extracted_path}")
                    error_count += 1
                    continue
                
                # Re-parse PCB
                logger.info(f"  Parsing PCB...")
                pcb_data = parser.parse(extracted_path)
                
                if len(pcb_data.components) == 0:
                    logger.warning(f"  ⚠️ No components found, using placeholder summary")
                    board_summary = {
                        "purpose": "Unable to determine (no components extracted)",
                        "description": "PCB parsing found no components.",
                        "key_features": [],
                        "main_components": [],
                        "design_notes": ""
                    }
                else:
                    # Generate summary
                    logger.info(f"  Generating AI summary ({len(pcb_data.components)} components)...")
                    board_summary = service._generate_board_summary(pcb_data, extracted_path)
                
                # Save with proper change detection
                updated_raw_results = dict(job.raw_results) if job.raw_results else {}
                updated_raw_results["board_summary"] = board_summary
                job.raw_results = updated_raw_results
                
                db.commit()
                
                logger.info(f"  ✅ Success: {board_summary.get('purpose', 'unknown')[:60]}...")
                success_count += 1
                
            except Exception as e:
                logger.error(f"  ❌ Failed: {e}")
                error_count += 1
                db.rollback()
                continue
        
        logger.info("=" * 60)
        logger.info(f"Migration complete!")
        logger.info(f"  ✅ Success: {success_count}")
        logger.info(f"  ❌ Errors:  {error_count}")
        logger.info(f"  📊 Total:   {len(jobs_to_fix)}")
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate board summaries for existing jobs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.force:
        print("⚠️  This will regenerate board summaries for all jobs missing them.")
        print("   This may take a while and consume OpenAI API credits.")
        response = input("   Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            sys.exit(0)
    
    migrate_board_summaries(dry_run=args.dry_run)
