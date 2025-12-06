"""
PCB File Parsers - Universal Multi-Format Support

Supported formats:
- KiCad (.kicad_pcb, .kicad_sch)
- Eagle (.brd, .sch) 
- Altium (.PcbDoc, .SchDoc)
- Gerber RS-274X/X2
- Excellon drill
- IPC-2581 XML
- BOM (CSV, Excel)
- Pick-and-Place (CSV, POS)

Usage:
    from parsers import UniversalParser, parse_pcb_project
    
    # Parse any format
    result = parse_pcb_project('/path/to/project.zip')
    print(f"Components: {len(result.pcb_data.components)}")
"""

# Base classes
from .base_parser import BaseParser, ParsedPCBData, BoardInfo, Component, Net, Track, Via, Zone

# Format detection
from .format_detector import (
    FormatDetector, 
    FileFormat, 
    EDAToolFamily,
    ProjectStructure,
    DetectedFile
)

# Native parsers
from .kicad_parser import KiCadParser
from .eagle_parser import EagleParser
from .altium_parser import AltiumParser
from .gerber_parser import GerberParser
from .ipc2581_parser import IPC2581Parser
from .hybrid_parser import HybridParser

# Manufacturing format parsers
from .odbpp_parser import ODBPPParser, parse_odbpp
from .cadence_parser import CadenceParser, parse_cadence

# Assembly data parsers
from .bom_parser import BOMParser, PickAndPlaceParser, BOMData, BOMItem

# Universal orchestrator
from .universal_parser import UniversalParser, ParseResult, parse_pcb_project

__all__ = [
    # Base
    "BaseParser",
    "ParsedPCBData",
    "BoardInfo",
    "Component", 
    "Net",
    "Track",
    "Via",
    "Zone",
    
    # Format detection
    "FormatDetector",
    "FileFormat",
    "EDAToolFamily",
    "ProjectStructure",
    "DetectedFile",
    
    # Native Parsers
    "KiCadParser",
    "EagleParser",
    "AltiumParser",
    "GerberParser",
    "IPC2581Parser",
    "HybridParser",
    
    # Manufacturing Parsers
    "ODBPPParser",
    "parse_odbpp",
    "CadenceParser",
    "parse_cadence",
    
    # Assembly Parsers
    "BOMParser",
    "PickAndPlaceParser",
    "BOMData",
    "BOMItem",
    
    # Universal
    "UniversalParser",
    "ParseResult",
    "parse_pcb_project",
]
