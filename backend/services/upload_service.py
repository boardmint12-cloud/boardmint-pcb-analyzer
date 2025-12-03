"""
Upload service - handles file uploads and storage
"""
import os
import uuid
import zipfile
import logging
import shutil
import json
from typing import Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models.project import Project
from config import get_settings, ensure_upload_dir
from services.file_loader import FileLoader
from services.cad_detector import CADToolDetector

logger = logging.getLogger(__name__)


class UploadService:
    """Handle PCB project uploads"""
    
    def __init__(self):
        self.settings = get_settings()
        self.upload_dir = ensure_upload_dir()
        self.file_loader = FileLoader()
        self.cad_detector = CADToolDetector()
    
    async def upload_project(
        self,
        file: UploadFile,
        project_name: Optional[str] = None,
        eda_tool: str = "kicad",
        db: Session = None
    ) -> Project:
        """
        Handle project ZIP upload
        
        Args:
            file: Uploaded ZIP file
            project_name: Optional project name
            eda_tool: EDA tool type (kicad, altium, easyleda, gerber)
            
        Returns:
            Project object
        """
        # Validate file
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only ZIP files are supported")
        
        # Generate project ID
        project_id = str(uuid.uuid4())
        
        # Create project directory
        project_dir = self.upload_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Stream file to disk (never load full file into memory)
        zip_path = project_dir / file.filename
        total_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        
        try:
            with open(zip_path, 'wb') as f:
                while chunk := await file.read(chunk_size):
                    # Check size limit as we stream
                    total_size += len(chunk)
                    if total_size > self.settings.max_upload_size:
                        # Clean up and raise error
                        f.close()
                        zip_path.unlink()
                        shutil.rmtree(project_dir)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large. Max size: {self.settings.max_upload_size / 1024 / 1024}MB"
                        )
                    f.write(chunk)
            
            logger.info(f"✅ Streamed {total_size / 1024 / 1024:.2f}MB to {zip_path}")
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Clean up on error
            if zip_path.exists():
                zip_path.unlink()
            if project_dir.exists():
                shutil.rmtree(project_dir)
            logger.error(f"Upload stream failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Upload failed")
        
        # Extract and organize ZIP with FileLoader
        extracted_path = project_dir / "extracted"
        try:
            # Use FileLoader for smart extraction and organization
            organized_files = self.file_loader.extract_and_flatten(zip_path, extracted_path)
            logger.info(f"Extracted and organized ZIP: {[(k, len(v)) for k, v in organized_files.items()]}")
        except Exception as e:
            logger.error(f"Failed to extract ZIP: {e}", exc_info=True)
            shutil.rmtree(project_dir)
            raise HTTPException(status_code=400, detail="Invalid ZIP file")
        
        # Detect CAD tool
        try:
            detection_result = self.cad_detector.detect(extracted_path)
            logger.info(f"CAD detection: {detection_result['tool_family']} (confidence: {detection_result['confidence']})")
            
            # Save detection result
            detection_file = project_dir / "cad_detection.json"
            with open(detection_file, 'w') as f:
                json.dump(detection_result, f, indent=2)
            
            # Override eda_tool if we detected something with high confidence
            if detection_result['confidence'] > 0.7:
                eda_tool = detection_result['tool_family']
        except Exception as e:
            logger.error(f"CAD detection failed: {e}", exc_info=True)
            detection_result = {"tool_family": "Unknown", "confidence": 0}
        
        # Validate contents
        if not self._validate_contents(extracted_path, eda_tool):
            logger.warning(f"ZIP validation warnings for {project_id}")
        
        # Create database entry
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        
        try:
            project = Project(
                id=project_id,
                name=project_name or file.filename.replace('.zip', ''),
                eda_tool=eda_tool,
                zip_path=str(zip_path),
                extracted_path=str(extracted_path),
                status="uploaded"
            )
            
            db.add(project)
            db.commit()
            db.refresh(project)
            
            logger.info(f"Created project {project_id}")
            return project
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        finally:
            if should_close:
                db.close()
    
    def _validate_contents(self, extracted_path: Path, eda_tool: str) -> bool:
        """
        Validate extracted contents
        
        Args:
            extracted_path: Path to extracted files
            eda_tool: Expected EDA tool type
            
        Returns:
            True if validation passes
        """
        files = list(extracted_path.rglob('*'))
        
        if eda_tool == "kicad":
            # Check for .kicad_pcb or .kicad_sch
            has_pcb = any(f.suffix == '.kicad_pcb' for f in files)
            has_sch = any(f.suffix in ['.kicad_sch', '.sch'] for f in files)
            
            if not (has_pcb or has_sch):
                logger.warning("KiCad project missing .kicad_pcb or schematic files")
                return False
        
        elif eda_tool == "gerber":
            # Check for gerber-like files
            gerber_exts = ['.gbr', '.pho', '.art', '.ger']
            has_gerber = any(f.suffix in gerber_exts for f in files)
            
            if not has_gerber:
                logger.warning("Gerber project missing gerber files")
                return False
        
        return True
