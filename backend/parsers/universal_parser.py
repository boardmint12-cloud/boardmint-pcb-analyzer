"""
Universal Parser Orchestrator
Routes files to appropriate parsers and merges results

This is the main entry point for parsing any PCB design file format.
Supports single files, ZIP archives, and project directories.
"""

import logging
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

from .format_detector import (
    FormatDetector, FileFormat, EDAToolFamily,
    ProjectStructure, DetectedFile
)
from .base_parser import ParsedPCBData, BoardInfo, Component, Net, Track, Via, Zone
from .kicad_parser import KiCadParser
from .eagle_parser import EagleParser
from .altium_parser import AltiumParser
from .gerber_parser import GerberParser
from .ipc2581_parser import IPC2581Parser
from .odbpp_parser import ODBPPParser
from .cadence_parser import CadenceParser
from .bom_parser import BOMParser, PickAndPlaceParser, BOMData
from .hybrid_parser import HybridParser

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Complete parse result from universal parser"""
    success: bool
    pcb_data: ParsedPCBData
    bom_data: Optional[BOMData] = None
    pnp_data: Optional[List[Dict]] = None
    project_structure: Optional[ProjectStructure] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Metadata
    detected_format: Optional[FileFormat] = None
    detected_eda: Optional[EDAToolFamily] = None
    files_parsed: List[str] = field(default_factory=list)


class UniversalParser:
    """
    Universal parser that handles any supported file format
    
    Supports:
    - Single files (.kicad_pcb, .brd, .PcbDoc, .xml, etc.)
    - ZIP archives containing project files
    - Project directories
    - Gerber file sets
    
    Parsing strategy:
    1. Detect format from file signature/extension
    2. Route to appropriate parser
    3. Merge data from multiple files (PCB + schematic + BOM)
    4. Validate and return unified result
    """
    
    def __init__(self):
        """Initialize parsers"""
        self.format_detector = FormatDetector()
        
        # Parser instances
        self.parsers = {
            EDAToolFamily.KICAD: HybridParser(),  # Use hybrid for KiCad (best quality)
            EDAToolFamily.EAGLE: EagleParser(),
            EDAToolFamily.ALTIUM: AltiumParser(),
            EDAToolFamily.GERBER: GerberParser(),
            EDAToolFamily.CADENCE_ORCAD: CadenceParser(),
            EDAToolFamily.CADENCE_ALLEGRO: CadenceParser(),
        }
        
        self.ipc_parser = IPC2581Parser()
        self.odbpp_parser = ODBPPParser()
        self.cadence_parser = CadenceParser()
        self.bom_parser = BOMParser()
        self.pnp_parser = PickAndPlaceParser()
    
    def parse(self, input_path: Union[str, Path]) -> ParseResult:
        """
        Parse any supported input (file, directory, or ZIP)
        
        Args:
            input_path: Path to file, directory, or ZIP archive
            
        Returns:
            ParseResult with parsed data and metadata
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            return ParseResult(
                success=False,
                pcb_data=self._empty_pcb_data(),
                errors=[f"Input not found: {input_path}"]
            )
        
        # Handle ZIP archives
        if input_path.is_file() and input_path.suffix.lower() == '.zip':
            return self._parse_zip(input_path)
        
        # Handle single files
        if input_path.is_file():
            return self._parse_single_file(input_path)
        
        # Handle directories
        return self._parse_directory(input_path)
    
    def _parse_zip(self, zip_path: Path) -> ParseResult:
        """Extract and parse ZIP archive"""
        logger.info(f"Extracting ZIP: {zip_path}")
        
        # Create temp directory for extraction
        temp_dir = tempfile.mkdtemp(prefix='pcb_parse_')
        
        try:
            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            # Parse extracted contents
            result = self._parse_directory(Path(temp_dir))
            result.files_parsed.append(str(zip_path))
            
            return result
            
        except zipfile.BadZipFile:
            return ParseResult(
                success=False,
                pcb_data=self._empty_pcb_data(),
                errors=["Invalid ZIP file"]
            )
        except Exception as e:
            return ParseResult(
                success=False,
                pcb_data=self._empty_pcb_data(),
                errors=[f"ZIP extraction failed: {e}"]
            )
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    def _parse_single_file(self, file_path: Path) -> ParseResult:
        """Parse a single file"""
        logger.info(f"Parsing single file: {file_path}")
        
        # Detect format
        detected = self.format_detector.detect_file(file_path)
        
        logger.info(f"Detected format: {detected.format.value}, "
                   f"confidence: {detected.confidence:.2f}")
        
        # Route to appropriate parser
        pcb_data = self._route_to_parser(detected, file_path)
        
        # Create project structure for single file
        project_structure = self.format_detector.detect_single_file(file_path)
        
        return ParseResult(
            success=len(pcb_data.components) > 0 or len(pcb_data.nets) > 0,
            pcb_data=pcb_data,
            project_structure=project_structure,
            detected_format=detected.format,
            detected_eda=detected.eda_tool,
            files_parsed=[str(file_path)],
            warnings=project_structure.warnings
        )
    
    def _parse_directory(self, dir_path: Path) -> ParseResult:
        """Parse a project directory"""
        logger.info(f"Parsing directory: {dir_path}")
        
        # Detect project structure
        project_structure = self.format_detector.detect_project(dir_path)
        
        logger.info(f"Detected EDA: {project_structure.eda_tool.value}, "
                   f"Files: {len(project_structure.all_files)}")
        
        warnings = list(project_structure.warnings)
        errors = []
        files_parsed = []
        
        # Parse main PCB file
        pcb_data = self._empty_pcb_data()
        
        if project_structure.main_pcb_file:
            main_file = project_structure.main_pcb_file
            pcb_data = self._route_to_parser(main_file, main_file.path)
            files_parsed.append(str(main_file.path))
            
            logger.info(f"Parsed main PCB: {len(pcb_data.components)} components, "
                       f"{len(pcb_data.nets)} nets")
        
        # If no main PCB but have Gerbers, use Gerber parser
        elif project_structure.gerber_files:
            pcb_data = self.parsers[EDAToolFamily.GERBER].parse(str(dir_path))
            files_parsed.extend([str(f.path) for f in project_structure.gerber_files])
        
        # Check for IPC-2581
        for other_file in project_structure.other_files:
            if other_file.format == FileFormat.IPC_2581:
                ipc_data = self.ipc_parser.parse(str(other_file.path))
                if ipc_data.components:
                    pcb_data = self._merge_pcb_data(pcb_data, ipc_data)
                    files_parsed.append(str(other_file.path))
        
        # Parse BOM files
        bom_data = None
        if project_structure.bom_files:
            bom_file = project_structure.bom_files[0]
            bom_data = self.bom_parser.parse(str(bom_file.path))
            files_parsed.append(str(bom_file.path))
            
            # Enhance components with BOM data
            pcb_data = self._enhance_with_bom(pcb_data, bom_data)
            
            logger.info(f"Parsed BOM: {bom_data.total_unique_parts} parts")
        
        # Parse PnP files
        pnp_data = None
        if project_structure.pnp_files:
            pnp_file = project_structure.pnp_files[0]
            pnp_data = self.pnp_parser.parse(str(pnp_file.path))
            files_parsed.append(str(pnp_file.path))
            
            # Enhance components with position data
            pcb_data = self._enhance_with_pnp(pcb_data, pnp_data)
            
            logger.info(f"Parsed PnP: {len(pnp_data)} placements")
        
        # Determine success
        success = (
            len(pcb_data.components) > 0 or 
            len(pcb_data.nets) > 0 or
            len(project_structure.gerber_files) > 0
        )
        
        if not success:
            errors.append("No design data could be extracted from the uploaded files")
        
        return ParseResult(
            success=success,
            pcb_data=pcb_data,
            bom_data=bom_data,
            pnp_data=pnp_data,
            project_structure=project_structure,
            detected_format=project_structure.main_pcb_file.format if project_structure.main_pcb_file else FileFormat.UNKNOWN,
            detected_eda=project_structure.eda_tool,
            files_parsed=files_parsed,
            warnings=warnings,
            errors=errors
        )
    
    def _route_to_parser(self, detected: DetectedFile, file_path: Path) -> ParsedPCBData:
        """Route file to appropriate parser based on format"""
        fmt = detected.format
        eda = detected.eda_tool
        
        # IPC-2581
        if fmt == FileFormat.IPC_2581:
            return self.ipc_parser.parse(str(file_path))
        
        # KiCad
        if fmt in (FileFormat.KICAD_PCB, FileFormat.KICAD_SCH, FileFormat.KICAD_PRO):
            return self.parsers[EDAToolFamily.KICAD].parse(file_path)
        
        # Eagle
        if fmt in (FileFormat.EAGLE_BRD, FileFormat.EAGLE_SCH):
            return self.parsers[EDAToolFamily.EAGLE].parse(str(file_path))
        
        # Altium
        if fmt in (FileFormat.ALTIUM_PCBDOC, FileFormat.ALTIUM_SCHDOC):
            return self.parsers[EDAToolFamily.ALTIUM].parse(str(file_path))
        
        # Gerber
        if fmt in (FileFormat.GERBER, FileFormat.GERBER_X2, FileFormat.EXCELLON):
            return self.parsers[EDAToolFamily.GERBER].parse(str(file_path.parent))
        
        # ODB++
        if fmt == FileFormat.ODB_PP:
            return self.odbpp_parser.parse(str(file_path))
        
        # Cadence
        if fmt in (FileFormat.CADENCE_BRD, FileFormat.CADENCE_DSN):
            logger.info("Parsing Cadence native format (partial support)")
            return self.cadence_parser.parse(str(file_path))
        
        # Unknown format
        logger.warning(f"Unknown format {fmt}, attempting generic parse")
        return self._attempt_generic_parse(file_path)
    
    def _parse_odb(self, path: Path) -> ParsedPCBData:
        """Parse ODB++ directory"""
        return self.odbpp_parser.parse(str(path))
    
    def _attempt_generic_parse(self, file_path: Path) -> ParsedPCBData:
        """Attempt to parse unknown format"""
        # Try reading as text and look for patterns
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read(10000)
            
            # Check for S-expression (KiCad-like)
            if content.strip().startswith('('):
                return self.parsers[EDAToolFamily.KICAD].parse(file_path)
            
            # Check for XML
            if content.strip().startswith('<?xml') or content.strip().startswith('<'):
                # Try Eagle
                if '<eagle' in content.lower():
                    return self.parsers[EDAToolFamily.EAGLE].parse(str(file_path))
                # Try IPC-2581
                if 'ipc' in content.lower():
                    return self.ipc_parser.parse(str(file_path))
            
        except:
            pass
        
        return self._empty_pcb_data()
    
    def _merge_pcb_data(self, primary: ParsedPCBData, secondary: ParsedPCBData) -> ParsedPCBData:
        """Merge two PCB data sets, primary takes precedence"""
        # Merge components
        primary_refs = {c.reference for c in primary.components}
        for comp in secondary.components:
            if comp.reference not in primary_refs:
                primary.components.append(comp)
        
        # Merge nets
        primary_nets = {n.name for n in primary.nets}
        for net in secondary.nets:
            if net.name not in primary_nets:
                primary.nets.append(net)
        
        # Extend tracks and vias
        primary.tracks.extend(secondary.tracks)
        primary.vias.extend(secondary.vias)
        primary.zones.extend(secondary.zones)
        
        # Update board info if missing
        if primary.board_info.size_x == 0 and secondary.board_info.size_x > 0:
            primary.board_info.size_x = secondary.board_info.size_x
            primary.board_info.size_y = secondary.board_info.size_y
        
        return primary
    
    def _enhance_with_bom(self, pcb_data: ParsedPCBData, bom_data: BOMData) -> ParsedPCBData:
        """Enhance PCB components with BOM data"""
        # Create lookup by reference
        bom_lookup = {}
        for item in bom_data.items:
            # Handle grouped references
            refs = item.extra_fields.get('all_references', item.reference).split(',')
            for ref in refs:
                bom_lookup[ref.strip()] = item
        
        # Enhance components
        for comp in pcb_data.components:
            bom_item = bom_lookup.get(comp.reference)
            if bom_item:
                if not comp.value and bom_item.value:
                    comp.value = bom_item.value
                if not comp.mpn and bom_item.mpn:
                    comp.mpn = bom_item.mpn
                if not comp.footprint and bom_item.footprint:
                    comp.footprint = bom_item.footprint
        
        return pcb_data
    
    def _enhance_with_pnp(self, pcb_data: ParsedPCBData, pnp_data: List[Dict]) -> ParsedPCBData:
        """Enhance PCB components with pick-and-place position data"""
        # Create lookup by reference
        pnp_lookup = {p['reference']: p for p in pnp_data}
        
        # Update component positions
        for comp in pcb_data.components:
            pnp = pnp_lookup.get(comp.reference)
            if pnp:
                if comp.x is None or comp.x == 0:
                    comp.x = pnp.get('x_mm', 0)
                    comp.y = pnp.get('y_mm', 0)
                if comp.rotation is None:
                    comp.rotation = pnp.get('rotation_deg', 0)
                if not comp.layer:
                    side = pnp.get('side', 'top')
                    comp.layer = 'B.Cu' if side == 'bottom' else 'F.Cu'
        
        return pcb_data
    
    def _empty_pcb_data(self) -> ParsedPCBData:
        """Return empty PCB data"""
        return ParsedPCBData(
            board_info=BoardInfo(size_x=0, size_y=0, layer_count=2),
            components=[],
            nets=[],
            tracks=[],
            vias=[],
            zones=[]
        )
    
    def _empty_pcb_data_with_warning(self, warning: str) -> ParsedPCBData:
        """Return empty PCB data with warning"""
        data = self._empty_pcb_data()
        data.raw_data = {'warning': warning}
        return data


# Convenience function
def parse_pcb_project(input_path: str) -> ParseResult:
    """
    Parse any PCB project file, directory, or ZIP
    
    Args:
        input_path: Path to input
        
    Returns:
        ParseResult with all parsed data
    """
    parser = UniversalParser()
    return parser.parse(input_path)
