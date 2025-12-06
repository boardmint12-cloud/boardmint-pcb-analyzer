"""
Universal PCB Format Detector
Identifies file formats from content signatures and extensions

Supports:
- PCB Native: KiCad, Eagle, Altium, Cadence, PADS
- Manufacturing: Gerber, Excellon, ODB++, IPC-2581
- Assembly: Pick-and-place, BOM
- MCAD: STEP, IDF
- Semiconductor: GDSII, LEF/DEF
"""

import os
import re
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FileFormat(str, Enum):
    """Supported file formats"""
    # PCB Native
    KICAD_PCB = "kicad_pcb"
    KICAD_SCH = "kicad_sch"
    KICAD_PRO = "kicad_pro"
    EAGLE_BRD = "eagle_brd"
    EAGLE_SCH = "eagle_sch"
    ALTIUM_PCBDOC = "altium_pcbdoc"
    ALTIUM_SCHDOC = "altium_schdoc"
    ALTIUM_PRJPCB = "altium_prjpcb"
    CADENCE_BRD = "cadence_brd"
    CADENCE_DSN = "cadence_dsn"
    PADS_PCB = "pads_pcb"
    PADS_SCH = "pads_sch"
    
    # Manufacturing
    GERBER = "gerber"
    GERBER_X2 = "gerber_x2"
    EXCELLON = "excellon"
    ODB_PP = "odb_pp"
    IPC_2581 = "ipc_2581"
    IPC_D356 = "ipc_d356"
    
    # Assembly
    PICK_AND_PLACE = "pick_and_place"
    BOM_CSV = "bom_csv"
    BOM_XLSX = "bom_xlsx"
    
    # MCAD Exchange
    STEP = "step"
    IDF_BOARD = "idf_board"
    IDF_LIBRARY = "idf_library"
    
    # Semiconductor
    GDSII = "gdsii"
    LEF = "lef"
    DEF = "def"
    LIBERTY = "liberty"
    SPICE = "spice"
    
    # Other
    NETLIST = "netlist"
    UNKNOWN = "unknown"


class EDAToolFamily(str, Enum):
    """EDA tool families"""
    KICAD = "kicad"
    EAGLE = "eagle"
    ALTIUM = "altium"
    CADENCE_ORCAD = "cadence_orcad"
    CADENCE_ALLEGRO = "cadence_allegro"
    PADS = "pads"
    XPEDITION = "xpedition"
    GERBER = "gerber"
    MANUFACTURING = "manufacturing"
    UNKNOWN = "unknown"


@dataclass
class DetectedFile:
    """A detected file with its format information"""
    path: Path
    format: FileFormat
    confidence: float  # 0.0 - 1.0
    eda_tool: Optional[EDAToolFamily] = None
    layer_type: Optional[str] = None  # For Gerber: "copper_top", "soldermask", etc.
    metadata: Dict = field(default_factory=dict)


@dataclass 
class ProjectStructure:
    """Detected project structure"""
    root_path: Path
    eda_tool: EDAToolFamily
    main_pcb_file: Optional[DetectedFile] = None
    schematic_files: List[DetectedFile] = field(default_factory=list)
    gerber_files: List[DetectedFile] = field(default_factory=list)
    drill_files: List[DetectedFile] = field(default_factory=list)
    bom_files: List[DetectedFile] = field(default_factory=list)
    pnp_files: List[DetectedFile] = field(default_factory=list)
    netlist_files: List[DetectedFile] = field(default_factory=list)
    library_files: List[DetectedFile] = field(default_factory=list)
    mcad_files: List[DetectedFile] = field(default_factory=list)
    other_files: List[DetectedFile] = field(default_factory=list)
    
    # Warnings for missing/incomplete data
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_complete(self) -> bool:
        """Check if project has minimum required files"""
        return self.main_pcb_file is not None or len(self.gerber_files) >= 2
    
    @property
    def all_files(self) -> List[DetectedFile]:
        """Get all detected files"""
        files = []
        if self.main_pcb_file:
            files.append(self.main_pcb_file)
        files.extend(self.schematic_files)
        files.extend(self.gerber_files)
        files.extend(self.drill_files)
        files.extend(self.bom_files)
        files.extend(self.pnp_files)
        files.extend(self.netlist_files)
        files.extend(self.library_files)
        files.extend(self.mcad_files)
        files.extend(self.other_files)
        return files


class FormatDetector:
    """
    Universal format detector for PCB design files
    
    Detection strategy:
    1. Extension-based detection (fast)
    2. Content signature detection (accurate)
    3. Structure analysis for archives (ODB++, project folders)
    """
    
    # Extension mappings (extension -> (format, eda_tool, confidence))
    EXTENSION_MAP = {
        # KiCad
        '.kicad_pcb': (FileFormat.KICAD_PCB, EDAToolFamily.KICAD, 0.95),
        '.kicad_sch': (FileFormat.KICAD_SCH, EDAToolFamily.KICAD, 0.95),
        '.kicad_pro': (FileFormat.KICAD_PRO, EDAToolFamily.KICAD, 0.95),
        '.kicad_mod': (FileFormat.KICAD_PCB, EDAToolFamily.KICAD, 0.90),  # Footprint
        '.kicad_sym': (FileFormat.KICAD_SCH, EDAToolFamily.KICAD, 0.90),  # Symbol
        
        # Eagle
        '.brd': (FileFormat.EAGLE_BRD, EDAToolFamily.EAGLE, 0.70),  # Could also be Allegro
        '.sch': (FileFormat.EAGLE_SCH, EDAToolFamily.EAGLE, 0.60),  # Generic
        '.lbr': (FileFormat.EAGLE_BRD, EDAToolFamily.EAGLE, 0.90),  # Eagle library
        
        # Altium
        '.pcbdoc': (FileFormat.ALTIUM_PCBDOC, EDAToolFamily.ALTIUM, 0.95),
        '.schdoc': (FileFormat.ALTIUM_SCHDOC, EDAToolFamily.ALTIUM, 0.95),
        '.prjpcb': (FileFormat.ALTIUM_PRJPCB, EDAToolFamily.ALTIUM, 0.95),
        '.schlib': (FileFormat.ALTIUM_SCHDOC, EDAToolFamily.ALTIUM, 0.90),
        '.pcblib': (FileFormat.ALTIUM_PCBDOC, EDAToolFamily.ALTIUM, 0.90),
        
        # Cadence
        '.dsn': (FileFormat.CADENCE_DSN, EDAToolFamily.CADENCE_ORCAD, 0.80),
        '.opj': (FileFormat.CADENCE_DSN, EDAToolFamily.CADENCE_ORCAD, 0.90),
        
        # PADS
        '.pcb': (FileFormat.PADS_PCB, EDAToolFamily.PADS, 0.50),  # Very generic
        '.asc': (FileFormat.NETLIST, EDAToolFamily.PADS, 0.60),
        
        # Manufacturing
        '.gbr': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.90),
        '.ger': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.90),
        '.pho': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.85),
        '.gtl': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Top copper
        '.gbl': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Bottom copper
        '.gts': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Top soldermask
        '.gbs': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Bottom soldermask
        '.gto': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Top silkscreen
        '.gbo': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Bottom silkscreen
        '.gtp': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Top paste
        '.gbp': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.95),  # Bottom paste
        '.gm1': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.90),  # Mechanical
        '.gko': (FileFormat.GERBER, EDAToolFamily.GERBER, 0.90),  # Board outline
        '.drl': (FileFormat.EXCELLON, EDAToolFamily.GERBER, 0.95),
        '.xln': (FileFormat.EXCELLON, EDAToolFamily.GERBER, 0.90),
        '.exc': (FileFormat.EXCELLON, EDAToolFamily.GERBER, 0.90),
        
        # IPC formats
        '.ipc': (FileFormat.IPC_D356, EDAToolFamily.MANUFACTURING, 0.80),
        '.d356': (FileFormat.IPC_D356, EDAToolFamily.MANUFACTURING, 0.95),
        
        # Assembly
        '.csv': (FileFormat.BOM_CSV, EDAToolFamily.MANUFACTURING, 0.50),  # Need content check
        '.xlsx': (FileFormat.BOM_XLSX, EDAToolFamily.MANUFACTURING, 0.60),
        '.xls': (FileFormat.BOM_XLSX, EDAToolFamily.MANUFACTURING, 0.60),
        '.xy': (FileFormat.PICK_AND_PLACE, EDAToolFamily.MANUFACTURING, 0.80),
        '.pos': (FileFormat.PICK_AND_PLACE, EDAToolFamily.MANUFACTURING, 0.80),
        '.mnt': (FileFormat.PICK_AND_PLACE, EDAToolFamily.MANUFACTURING, 0.80),
        
        # MCAD
        '.step': (FileFormat.STEP, EDAToolFamily.UNKNOWN, 0.95),
        '.stp': (FileFormat.STEP, EDAToolFamily.UNKNOWN, 0.95),
        '.emn': (FileFormat.IDF_BOARD, EDAToolFamily.UNKNOWN, 0.95),
        '.emp': (FileFormat.IDF_LIBRARY, EDAToolFamily.UNKNOWN, 0.95),
        
        # Semiconductor
        '.gds': (FileFormat.GDSII, EDAToolFamily.UNKNOWN, 0.95),
        '.gds2': (FileFormat.GDSII, EDAToolFamily.UNKNOWN, 0.95),
        '.lef': (FileFormat.LEF, EDAToolFamily.UNKNOWN, 0.95),
        '.def': (FileFormat.DEF, EDAToolFamily.UNKNOWN, 0.95),
        '.lib': (FileFormat.LIBERTY, EDAToolFamily.UNKNOWN, 0.70),  # Could be many things
        '.sp': (FileFormat.SPICE, EDAToolFamily.UNKNOWN, 0.80),
        '.spice': (FileFormat.SPICE, EDAToolFamily.UNKNOWN, 0.95),
        '.cir': (FileFormat.SPICE, EDAToolFamily.UNKNOWN, 0.90),
        
        # Netlists
        '.net': (FileFormat.NETLIST, EDAToolFamily.UNKNOWN, 0.70),
    }
    
    # Gerber layer type detection from filename
    GERBER_LAYER_PATTERNS = {
        r'\.gtl$|top.*copper|copper.*top|f\.cu': 'copper_top',
        r'\.gbl$|bottom.*copper|copper.*bottom|b\.cu': 'copper_bottom',
        r'\.g[2-9]l?$|inner|in[0-9]': 'copper_inner',
        r'\.gts$|top.*mask|mask.*top|f\.mask': 'soldermask_top',
        r'\.gbs$|bottom.*mask|mask.*bottom|b\.mask': 'soldermask_bottom',
        r'\.gto$|top.*silk|silk.*top|f\.silk': 'silkscreen_top',
        r'\.gbo$|bottom.*silk|silk.*bottom|b\.silk': 'silkscreen_bottom',
        r'\.gtp$|top.*paste|paste.*top|f\.paste': 'paste_top',
        r'\.gbp$|bottom.*paste|paste.*bottom|b\.paste': 'paste_bottom',
        r'\.gko$|\.gm1$|outline|edge|board': 'board_outline',
        r'\.drl$|\.xln$|drill|plated': 'drill',
    }
    
    # Content signatures for format detection
    CONTENT_SIGNATURES = {
        FileFormat.KICAD_PCB: [
            (b'(kicad_pcb', 0.98),
            (b'(module', 0.70),
            (b'(footprint', 0.80),
        ],
        FileFormat.KICAD_SCH: [
            (b'(kicad_sch', 0.98),
            (b'(symbol', 0.70),
        ],
        FileFormat.EAGLE_BRD: [
            (b'<!DOCTYPE eagle', 0.98),
            (b'<eagle version', 0.95),
            (b'<board>', 0.80),
        ],
        FileFormat.EAGLE_SCH: [
            (b'<!DOCTYPE eagle', 0.90),
            (b'<schematic>', 0.85),
        ],
        FileFormat.ALTIUM_PCBDOC: [
            (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1', 0.60),  # OLE compound
            (b'|COMPONENT|', 0.80),
        ],
        FileFormat.GERBER: [
            (b'%FSLAX', 0.95),  # RS-274X format spec
            (b'%MOMM*%', 0.90),  # Metric mode
            (b'%MOIN*%', 0.90),  # Imperial mode
            (b'G04', 0.70),     # Comment
            (b'D01*', 0.60),    # Draw command
            (b'D02*', 0.60),    # Move command
            (b'D03*', 0.60),    # Flash command
        ],
        FileFormat.GERBER_X2: [
            (b'%TF.GenerationSoftware', 0.95),
            (b'%TF.FileFunction', 0.95),
            (b'%TF.Part', 0.90),
        ],
        FileFormat.EXCELLON: [
            (b'M48', 0.90),     # Header start
            (b'INCH', 0.70),
            (b'METRIC', 0.70),
            (b'T01C', 0.80),    # Tool definition
            (b'%', 0.40),       # Common but not definitive
        ],
        FileFormat.IPC_2581: [
            (b'<?xml', 0.30),
            (b'<IPC-2581', 0.98),
            (b'IPC-2581', 0.90),
        ],
        FileFormat.ODB_PP: [
            (b'matrix', 0.70),
            (b'steps', 0.70),
        ],
        FileFormat.STEP: [
            (b'ISO-10303-21', 0.98),
            (b'STEP', 0.60),
        ],
        FileFormat.GDSII: [
            (b'\x00\x06\x00\x02', 0.90),  # GDSII header
        ],
        FileFormat.LEF: [
            (b'VERSION', 0.50),
            (b'MACRO', 0.80),
            (b'LAYER', 0.60),
        ],
        FileFormat.DEF: [
            (b'VERSION', 0.50),
            (b'DESIGN', 0.80),
            (b'COMPONENTS', 0.70),
        ],
        FileFormat.SPICE: [
            (b'.subckt', 0.90),
            (b'.model', 0.80),
            (b'.param', 0.70),
            (b'.include', 0.60),
        ],
    }
    
    def __init__(self):
        """Initialize format detector"""
        pass
    
    def detect_file(self, file_path: Path) -> DetectedFile:
        """
        Detect format of a single file
        
        Args:
            file_path: Path to file
            
        Returns:
            DetectedFile with format information
        """
        if not file_path.exists():
            return DetectedFile(
                path=file_path,
                format=FileFormat.UNKNOWN,
                confidence=0.0
            )
        
        # Step 1: Extension-based detection
        ext = file_path.suffix.lower()
        ext_result = self.EXTENSION_MAP.get(ext)
        
        initial_format = FileFormat.UNKNOWN
        initial_eda = EDAToolFamily.UNKNOWN
        initial_confidence = 0.0
        
        if ext_result:
            initial_format, initial_eda, initial_confidence = ext_result
        
        # Step 2: Content-based detection (improves confidence)
        content_format, content_confidence = self._detect_from_content(file_path)
        
        # Choose best result
        if content_confidence > initial_confidence:
            final_format = content_format
            final_confidence = content_confidence
        else:
            final_format = initial_format
            final_confidence = initial_confidence
        
        # Step 3: Detect Gerber layer type
        layer_type = None
        if final_format in (FileFormat.GERBER, FileFormat.GERBER_X2, FileFormat.EXCELLON):
            layer_type = self._detect_gerber_layer(file_path)
        
        # Step 4: Detect CSV type (BOM vs PnP)
        if final_format == FileFormat.BOM_CSV:
            csv_type, csv_confidence = self._detect_csv_type(file_path)
            final_format = csv_type
            final_confidence = max(final_confidence, csv_confidence)
        
        return DetectedFile(
            path=file_path,
            format=final_format,
            confidence=final_confidence,
            eda_tool=initial_eda,
            layer_type=layer_type
        )
    
    def _detect_from_content(self, file_path: Path) -> Tuple[FileFormat, float]:
        """Detect format from file content signatures"""
        try:
            # Read first 8KB for signature detection
            with open(file_path, 'rb') as f:
                content = f.read(8192)
            
            best_format = FileFormat.UNKNOWN
            best_confidence = 0.0
            
            for fmt, signatures in self.CONTENT_SIGNATURES.items():
                for signature, confidence in signatures:
                    if signature in content:
                        if confidence > best_confidence:
                            best_format = fmt
                            best_confidence = confidence
            
            return best_format, best_confidence
            
        except Exception as e:
            logger.warning(f"Content detection failed for {file_path}: {e}")
            return FileFormat.UNKNOWN, 0.0
    
    def _detect_gerber_layer(self, file_path: Path) -> Optional[str]:
        """Detect Gerber layer type from filename and content"""
        filename = file_path.name.lower()
        
        for pattern, layer_type in self.GERBER_LAYER_PATTERNS.items():
            if re.search(pattern, filename, re.IGNORECASE):
                return layer_type
        
        # Try to detect from X2 attributes in content
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read(2000)
            
            # X2 FileFunction attribute
            match = re.search(r'%TF\.FileFunction,(\w+)', content)
            if match:
                func = match.group(1).lower()
                if 'copper' in func:
                    return 'copper_top' if 'top' in func else 'copper_bottom'
                elif 'soldermask' in func:
                    return 'soldermask_top' if 'top' in func else 'soldermask_bottom'
                elif 'legend' in func or 'silk' in func:
                    return 'silkscreen_top' if 'top' in func else 'silkscreen_bottom'
                elif 'paste' in func:
                    return 'paste_top' if 'top' in func else 'paste_bottom'
                elif 'profile' in func or 'outline' in func:
                    return 'board_outline'
        except:
            pass
        
        return None
    
    def _detect_csv_type(self, file_path: Path) -> Tuple[FileFormat, float]:
        """Detect if CSV is BOM or Pick-and-place"""
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read(2000).lower()
            
            # PnP indicators
            pnp_keywords = ['centroid', 'mid x', 'mid y', 'ref x', 'ref y', 
                          'rotation', 'side', 'designator', 'footprint']
            pnp_score = sum(1 for kw in pnp_keywords if kw in content)
            
            # BOM indicators  
            bom_keywords = ['quantity', 'qty', 'part number', 'mpn', 'manufacturer',
                          'description', 'value', 'price', 'supplier']
            bom_score = sum(1 for kw in bom_keywords if kw in content)
            
            if pnp_score > bom_score:
                return FileFormat.PICK_AND_PLACE, 0.70 + (pnp_score * 0.05)
            else:
                return FileFormat.BOM_CSV, 0.60 + (bom_score * 0.05)
                
        except:
            return FileFormat.BOM_CSV, 0.50
    
    def detect_project(self, project_path: Path) -> ProjectStructure:
        """
        Analyze a project directory and categorize all files
        
        Args:
            project_path: Path to project directory
            
        Returns:
            ProjectStructure with categorized files
        """
        logger.info(f"Detecting project structure: {project_path}")
        
        structure = ProjectStructure(
            root_path=project_path,
            eda_tool=EDAToolFamily.UNKNOWN
        )
        
        # Check for ODB++ structure first
        if self._is_odb_structure(project_path):
            structure.eda_tool = EDAToolFamily.MANUFACTURING
            structure.main_pcb_file = DetectedFile(
                path=project_path,
                format=FileFormat.ODB_PP,
                confidence=0.95,
                eda_tool=EDAToolFamily.MANUFACTURING
            )
            return structure
        
        # Scan all files
        eda_votes: Dict[EDAToolFamily, int] = {}
        
        for file_path in project_path.rglob('*'):
            if file_path.is_dir():
                continue
            
            # Skip hidden files and common non-design files
            if file_path.name.startswith('.') or file_path.name.startswith('__'):
                continue
            if file_path.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.md', '.json']:
                continue
            
            detected = self.detect_file(file_path)
            
            if detected.eda_tool and detected.eda_tool != EDAToolFamily.UNKNOWN:
                eda_votes[detected.eda_tool] = eda_votes.get(detected.eda_tool, 0) + 1
            
            # Categorize file
            self._categorize_file(detected, structure)
        
        # Determine primary EDA tool
        if eda_votes:
            structure.eda_tool = max(eda_votes, key=eda_votes.get)
        
        # Generate warnings for incomplete projects
        self._generate_warnings(structure)
        
        logger.info(f"Detected {len(structure.all_files)} files, EDA: {structure.eda_tool.value}")
        
        return structure
    
    def _is_odb_structure(self, path: Path) -> bool:
        """Check if directory is ODB++ structure"""
        # ODB++ has specific directories: matrix, steps, symbols, etc.
        odb_markers = ['matrix', 'steps', 'symbols', 'fonts']
        found = sum(1 for m in odb_markers if (path / m).exists())
        return found >= 2
    
    def _categorize_file(self, detected: DetectedFile, structure: ProjectStructure):
        """Categorize a detected file into the project structure"""
        fmt = detected.format
        
        # PCB files
        if fmt in (FileFormat.KICAD_PCB, FileFormat.EAGLE_BRD, FileFormat.ALTIUM_PCBDOC,
                   FileFormat.CADENCE_BRD, FileFormat.PADS_PCB):
            if structure.main_pcb_file is None or detected.confidence > structure.main_pcb_file.confidence:
                structure.main_pcb_file = detected
        
        # Schematic files
        elif fmt in (FileFormat.KICAD_SCH, FileFormat.EAGLE_SCH, FileFormat.ALTIUM_SCHDOC,
                     FileFormat.CADENCE_DSN, FileFormat.PADS_SCH):
            structure.schematic_files.append(detected)
        
        # Gerber files
        elif fmt in (FileFormat.GERBER, FileFormat.GERBER_X2):
            structure.gerber_files.append(detected)
        
        # Drill files
        elif fmt == FileFormat.EXCELLON:
            structure.drill_files.append(detected)
        
        # BOM files
        elif fmt in (FileFormat.BOM_CSV, FileFormat.BOM_XLSX):
            structure.bom_files.append(detected)
        
        # Pick and place
        elif fmt == FileFormat.PICK_AND_PLACE:
            structure.pnp_files.append(detected)
        
        # Netlists
        elif fmt in (FileFormat.NETLIST, FileFormat.IPC_D356):
            structure.netlist_files.append(detected)
        
        # MCAD
        elif fmt in (FileFormat.STEP, FileFormat.IDF_BOARD, FileFormat.IDF_LIBRARY):
            structure.mcad_files.append(detected)
        
        # Other known formats
        elif fmt != FileFormat.UNKNOWN:
            structure.other_files.append(detected)
    
    def _generate_warnings(self, structure: ProjectStructure):
        """Generate warnings for incomplete or problematic projects"""
        warnings = []
        
        # No PCB file and no Gerbers
        if not structure.main_pcb_file and not structure.gerber_files:
            warnings.append("⚠️ No PCB layout file or Gerber files found. Analysis will be limited.")
        
        # Gerbers without drill
        if structure.gerber_files and not structure.drill_files:
            warnings.append("⚠️ Gerber files found but no drill file (.drl). Drill analysis unavailable.")
        
        # No schematic
        if not structure.schematic_files:
            warnings.append("ℹ️ No schematic files found. Net voltage analysis may be incomplete.")
        
        # No BOM
        if not structure.bom_files:
            warnings.append("ℹ️ No BOM file found. Component validation will use footprint data only.")
        
        # Altium/Cadence native without export
        if structure.eda_tool in (EDAToolFamily.ALTIUM, EDAToolFamily.CADENCE_ALLEGRO, 
                                   EDAToolFamily.CADENCE_ORCAD):
            if not structure.gerber_files:
                warnings.append(
                    f"⚠️ {structure.eda_tool.value} native files detected. "
                    "For best results, also include Gerber/ODB++ export."
                )
        
        structure.warnings = warnings
    
    def detect_single_file(self, file_path: Path) -> ProjectStructure:
        """
        Create project structure from a single file
        
        Args:
            file_path: Path to single file
            
        Returns:
            ProjectStructure with the single file categorized
        """
        detected = self.detect_file(file_path)
        
        structure = ProjectStructure(
            root_path=file_path.parent,
            eda_tool=detected.eda_tool or EDAToolFamily.UNKNOWN
        )
        
        self._categorize_file(detected, structure)
        self._generate_warnings(structure)
        
        return structure
