"""
Upload service - handles file uploads and storage

Supports:
- ZIP archives containing project files
- Single PCB files (.kicad_pcb, .brd, .PcbDoc, etc.)
- Single Gerber files
- BOM/PnP files
"""
import os
import uuid
import zipfile
import logging
import shutil
import json
from typing import Optional, List, Tuple
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models.project import Project
from config import get_settings, ensure_upload_dir
from services.file_loader import FileLoader
from services.cad_detector import CADToolDetector
from parsers.format_detector import FormatDetector, FileFormat, EDAToolFamily

logger = logging.getLogger(__name__)


# Supported single file extensions
SUPPORTED_SINGLE_FILE_EXTENSIONS = {
    # PCB Native
    '.kicad_pcb', '.kicad_sch', '.kicad_pro',
    '.brd', '.sch',  # Eagle
    '.pcbdoc', '.schdoc', '.prjpcb',  # Altium
    '.dsn', '.opj',  # OrCAD
    # Manufacturing
    '.gbr', '.ger', '.gtl', '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gko',
    '.drl', '.xln', '.exc',
    '.xml',  # IPC-2581
    # Assembly
    '.csv', '.xlsx', '.xls', '.pos', '.xy', '.mnt',
    # MCAD
    '.step', '.stp', '.emn', '.emp',
}


class UploadService:
    """Handle PCB project uploads - ZIP or single files"""
    
    def __init__(self):
        self.settings = get_settings()
        self.upload_dir = ensure_upload_dir()
        self.file_loader = FileLoader()
        self.cad_detector = CADToolDetector()
        self.format_detector = FormatDetector()
    
    def _is_supported_single_file(self, filename: str) -> bool:
        """Check if file extension is supported for single-file upload"""
        ext = Path(filename).suffix.lower()
        return ext in SUPPORTED_SINGLE_FILE_EXTENSIONS
    
    async def upload_project(
        self,
        file: UploadFile,
        project_name: Optional[str] = None,
        eda_tool: str = "auto",
        db: Session = None
    ) -> Project:
        """
        Handle project upload (ZIP or single file)
        
        Args:
            file: Uploaded file (ZIP or single PCB file)
            project_name: Optional project name
            eda_tool: EDA tool type or "auto" for detection
            
        Returns:
            Project object
        """
        filename = file.filename or "unknown"
        is_zip = filename.lower().endswith('.zip')
        is_single = self._is_supported_single_file(filename)
        
        # Validate file type
        if not is_zip and not is_single:
            supported = ", ".join(sorted(SUPPORTED_SINGLE_FILE_EXTENSIONS)[:10]) + "..."
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Upload a ZIP archive or single PCB file ({supported})"
            )
        
        # Generate project ID
        project_id = str(uuid.uuid4())
        
        # Create project directory
        project_dir = self.upload_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Stream file to disk (never load full file into memory)
        uploaded_path = project_dir / filename
        total_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        
        try:
            with open(uploaded_path, 'wb') as f:
                while chunk := await file.read(chunk_size):
                    total_size += len(chunk)
                    f.write(chunk)
            
            logger.info(f"✅ Streamed {total_size / 1024 / 1024:.2f}MB to {uploaded_path}")
            
        except Exception as e:
            # Clean up on error
            if uploaded_path.exists():
                uploaded_path.unlink()
            if project_dir.exists():
                shutil.rmtree(project_dir)
            logger.error(f"Upload stream failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Upload failed")
        
        # Handle extraction based on file type
        extracted_path = project_dir / "extracted"
        extracted_path.mkdir(parents=True, exist_ok=True)
        
        warnings = []
        
        if is_zip:
            # Extract ZIP archive
            try:
                organized_files = self.file_loader.extract_and_flatten(uploaded_path, extracted_path)
                logger.info(f"Extracted ZIP: {[(k, len(v)) for k, v in organized_files.items()]}")
            except Exception as e:
                logger.error(f"Failed to extract ZIP: {e}", exc_info=True)
                shutil.rmtree(project_dir)
                raise HTTPException(status_code=400, detail="Invalid ZIP file")
        else:
            # Single file - copy to extracted folder
            dest_path = extracted_path / filename
            shutil.copy2(uploaded_path, dest_path)
            
            # Detect format and generate warning if incomplete
            detected = self.format_detector.detect_file(dest_path)
            
            if detected.format in (FileFormat.GERBER, FileFormat.GERBER_X2):
                warnings.append("⚠️ Single Gerber file uploaded. For complete analysis, upload full Gerber set in ZIP.")
            elif detected.format == FileFormat.EXCELLON:
                warnings.append("⚠️ Drill file only. For complete analysis, upload with Gerber files.")
            elif detected.format in (FileFormat.BOM_CSV, FileFormat.BOM_XLSX):
                warnings.append("ℹ️ BOM file uploaded. For DRC analysis, also upload PCB layout file.")
            elif detected.format == FileFormat.PICK_AND_PLACE:
                warnings.append("ℹ️ Pick-and-place file uploaded. For full analysis, also upload PCB layout.")
            
            # Auto-detect EDA tool from format
            if eda_tool == "auto" and detected.eda_tool:
                eda_tool = detected.eda_tool.value
            
            organized_files = {'single_file': [str(dest_path)]}
            logger.info(f"Single file upload: {filename} -> {detected.format.value}")
        
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
        
        # Handle default eda_tool
        if eda_tool == "auto":
            eda_tool = "unknown"
        
        try:
            # Clean up project name
            clean_name = project_name or filename
            for ext in ['.zip', '.kicad_pcb', '.brd', '.PcbDoc', '.pcbdoc']:
                clean_name = clean_name.replace(ext, '')
            
            project = Project(
                id=project_id,
                name=clean_name,
                eda_tool=eda_tool,
                zip_path=str(uploaded_path),
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
