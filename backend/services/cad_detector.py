"""
CAD Tool Detection Service
Automatically detects which EDA tool was used based on file signatures
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class CADSignature:
    """Signature for detecting CAD tools"""
    name: str
    priority: int  # Higher = checked first
    required_files: List[str]  # File extensions or names that MUST exist
    optional_files: List[str]  # Files that strengthen the match
    magic_strings: Dict[str, str]  # filename -> string to find in file


class CADToolDetector:
    """Detect which CAD tool generated the project files"""
    
    # Define signatures for all major CAD tools
    SIGNATURES = [
        # KiCad (highest priority for open format)
        CADSignature(
            name="KiCad",
            priority=100,
            required_files=[".kicad_pro"],  # KiCad 6+
            optional_files=[".kicad_pcb", ".kicad_sch", ".kicad_mod"],
            magic_strings={}
        ),
        CADSignature(
            name="KiCad 5",
            priority=95,
            required_files=[".pro"],
            optional_files=[".kicad_pcb", ".sch"],
            magic_strings={".kicad_pcb": "(kicad_pcb"}
        ),
        
        # Altium
        CADSignature(
            name="Altium Designer",
            priority=90,
            required_files=[".PrjPcb"],
            optional_files=[".SchDoc", ".PcbDoc", ".OutJob"],
            magic_strings={}
        ),
        
        # OrCAD / Cadence Allegro
        CADSignature(
            name="OrCAD/Allegro",
            priority=85,
            required_files=[".opj"],
            optional_files=[".dsn", ".brd"],
            magic_strings={}
        ),
        CADSignature(
            name="Allegro",
            priority=84,
            required_files=[".brd"],
            optional_files=[".dra", ".psm"],
            magic_strings={".brd": "BOARD_FILE"}
        ),
        
        # EAGLE / Autodesk Fusion
        CADSignature(
            name="EAGLE",
            priority=80,
            required_files=[".brd", ".sch"],
            optional_files=[".lbr"],
            magic_strings={".brd": "<?xml version", ".sch": "<?xml version"}
        ),
        
        # PADS
        CADSignature(
            name="PADS",
            priority=75,
            required_files=[".asc"],
            optional_files=[".grp", ".cfg"],
            magic_strings={".asc": "*PADS*"}
        ),
        
        # Xpedition
        CADSignature(
            name="Xpedition",
            priority=70,
            required_files=[".pcb"],
            optional_files=[".prj", ".lmc"],
            magic_strings={}
        ),
        
        # EasyEDA / JLCEDA
        CADSignature(
            name="EasyEDA",
            priority=65,
            required_files=[".json"],
            optional_files=[],
            magic_strings={".json": '"head":{"docType":"1"'}  # EasyEDA JSON format
        ),
        
        # DipTrace
        CADSignature(
            name="DipTrace",
            priority=60,
            required_files=[".dip"],
            optional_files=[".eli"],
            magic_strings={}
        ),
        
        # Neutral formats (lowest priority)
        CADSignature(
            name="IPC-2581",
            priority=50,
            required_files=[".xml"],
            optional_files=[],
            magic_strings={".xml": "<IPC-2581"}
        ),
        CADSignature(
            name="ODB++",
            priority=49,
            required_files=["matrix/matrix"],  # ODB++ folder structure
            optional_files=["steps", "fonts"],
            magic_strings={}
        ),
        CADSignature(
            name="Gerber",
            priority=40,
            required_files=[".gbr", ".gtl", ".gbl"],  # Common gerber extensions
            optional_files=[".gto", ".gbo", ".drl"],
            magic_strings={}
        ),
    ]
    
    def __init__(self):
        """Initialize detector"""
        self.signatures = sorted(self.SIGNATURES, key=lambda x: x.priority, reverse=True)
    
    def detect(self, directory: Path) -> Dict:
        """
        Detect CAD tool from project directory
        
        Args:
            directory: Path to extracted project
            
        Returns:
            Detection result with tool info and confidence
        """
        logger.info(f"Detecting CAD tool in: {directory}")
        
        # Build file inventory
        inventory = self._scan_directory(directory)
        
        # Try each signature
        results = []
        for sig in self.signatures:
            confidence = self._match_signature(sig, inventory)
            if confidence > 0:
                results.append({
                    "tool": sig.name,
                    "confidence": confidence,
                    "priority": sig.priority
                })
        
        # Sort by confidence * priority
        results.sort(key=lambda x: x["confidence"] * x["priority"], reverse=True)
        
        # Detect neutral formats
        neutral_formats = self._detect_neutral_formats(inventory)
        
        # Build result
        if results:
            primary_tool = results[0]
            result = {
                "tool_family": primary_tool["tool"],
                "confidence": primary_tool["confidence"],
                "all_matches": results[:3],  # Top 3 matches
                "neutral_formats": neutral_formats,
                "file_inventory": {
                    "total_files": len(inventory["all_files"]),
                    "extensions": dict(inventory["extensions"].most_common(20)),
                },
                "has_gerbers": neutral_formats.get("gerber", False),
                "has_ipc2581": neutral_formats.get("ipc2581", False),
                "has_odbpp": neutral_formats.get("odbpp", False),
                "has_step": neutral_formats.get("step", False),
                "has_bom": neutral_formats.get("bom", False),
            }
        else:
            # Unknown format
            result = {
                "tool_family": "Unknown",
                "confidence": 0,
                "all_matches": [],
                "neutral_formats": neutral_formats,
                "file_inventory": {
                    "total_files": len(inventory["all_files"]),
                    "extensions": dict(inventory["extensions"].most_common(20)),
                },
                "has_gerbers": neutral_formats.get("gerber", False),
                "has_ipc2581": neutral_formats.get("ipc2581", False),
                "has_odbpp": neutral_formats.get("odbpp", False),
                "has_step": neutral_formats.get("step", False),
                "has_bom": neutral_formats.get("bom", False),
            }
        
        logger.info(f"Detection result: {result['tool_family']} (confidence: {result['confidence']})")
        return result
    
    def _scan_directory(self, directory: Path) -> Dict:
        """Scan directory and build file inventory"""
        all_files = []
        extensions = Counter()
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), directory)
                all_files.append(rel_path)
                
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    extensions[ext] += 1
        
        return {
            "all_files": all_files,
            "extensions": extensions,
            "directory": directory
        }
    
    def _match_signature(self, signature: CADSignature, inventory: Dict) -> float:
        """
        Match a signature against file inventory
        
        Returns:
            Confidence score 0-1
        """
        score = 0.0
        max_score = 0.0
        
        # Check required files (70% weight)
        max_score += 0.7
        required_matches = 0
        for req_file in signature.required_files:
            if self._has_file_pattern(req_file, inventory):
                required_matches += 1
        
        if signature.required_files:
            score += 0.7 * (required_matches / len(signature.required_files))
        
        # If no required matches, return 0
        if required_matches == 0:
            return 0.0
        
        # Check optional files (20% weight)
        if signature.optional_files:
            max_score += 0.2
            optional_matches = sum(
                1 for opt_file in signature.optional_files
                if self._has_file_pattern(opt_file, inventory)
            )
            score += 0.2 * (optional_matches / len(signature.optional_files))
        
        # Check magic strings (10% weight)
        if signature.magic_strings:
            max_score += 0.1
            magic_matches = self._check_magic_strings(signature, inventory)
            score += 0.1 * magic_matches
        
        return score
    
    def _has_file_pattern(self, pattern: str, inventory: Dict) -> bool:
        """Check if pattern matches any file"""
        if pattern.startswith("."):
            # Extension match
            return pattern.lower() in inventory["extensions"]
        else:
            # Filename match
            return any(pattern.lower() in f.lower() for f in inventory["all_files"])
    
    def _check_magic_strings(self, signature: CADSignature, inventory: Dict) -> float:
        """Check for magic strings in files"""
        if not signature.magic_strings:
            return 0.0
        
        matches = 0
        directory = inventory["directory"]
        
        for pattern, magic in signature.magic_strings.items():
            # Find matching files
            for file in inventory["all_files"]:
                if pattern in os.path.splitext(file)[1].lower():
                    try:
                        file_path = directory / file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(10000)  # Read first 10KB
                            if magic in content:
                                matches += 1
                                break  # Found one match for this pattern
                    except Exception:
                        continue
        
        return matches / len(signature.magic_strings) if signature.magic_strings else 0.0
    
    def _detect_neutral_formats(self, inventory: Dict) -> Dict:
        """Detect neutral manufacturing formats"""
        formats = {}
        
        # Gerber files
        gerber_exts = {'.gbr', '.gtl', '.gbl', '.gto', '.gbo', '.gts', '.gbs', 
                       '.gtp', '.gbp', '.gm1', '.gm2', '.gm3', '.gko', '.g1', 
                       '.g2', '.g3', '.g4', '.gp1', '.gp2'}
        formats["gerber"] = any(ext in inventory["extensions"] for ext in gerber_exts)
        
        # Drill files
        drill_exts = {'.drl', '.txt', '.xln', '.nc', '.ncd'}
        formats["drill"] = any(ext in inventory["extensions"] for ext in drill_exts)
        
        # IPC-2581
        formats["ipc2581"] = any(
            "ipc-2581" in f.lower() or ".xml" in f.lower()
            for f in inventory["all_files"]
        )
        
        # ODB++
        formats["odbpp"] = any("matrix" in f.lower() for f in inventory["all_files"])
        
        # STEP files
        step_exts = {'.step', '.stp'}
        formats["step"] = any(ext in inventory["extensions"] for ext in step_exts)
        
        # BOM
        bom_exts = {'.csv', '.xlsx', '.xls', '.txt'}
        formats["bom"] = any(
            ext in inventory["extensions"] and ("bom" in f.lower() or "parts" in f.lower())
            for f in inventory["all_files"]
            for ext in bom_exts
        )
        
        # Pick and place / centroid
        formats["centroid"] = any(
            "pos" in f.lower() or "centroid" in f.lower() or "xy" in f.lower() or "place" in f.lower()
            for f in inventory["all_files"]
        )
        
        return formats
