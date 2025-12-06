"""
File Analyzer Service - AI-powered file purpose detection
Analyzes each file in a PCB project to determine its purpose and how it connects to other files

Features:
- Detects file type and purpose
- Generates human-readable descriptions
- Maps file connections/dependencies
- Builds project structure overview
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from openai import OpenAI
from config import get_settings

logger = logging.getLogger(__name__)


class FileType(str, Enum):
    """PCB project file types"""
    PCB_LAYOUT = "pcb_layout"
    SCHEMATIC = "schematic"
    GERBER = "gerber"
    DRILL = "drill"
    BOM = "bom"
    PICK_AND_PLACE = "pick_and_place"
    NETLIST = "netlist"
    FOOTPRINT = "footprint"
    SYMBOL = "symbol"
    MODEL_3D = "model_3d"
    DOCUMENTATION = "documentation"
    PROJECT = "project"
    LIBRARY = "library"
    RULES = "rules"
    OUTPUT = "output"
    OTHER = "other"


@dataclass
class FileInfo:
    """Information about a single file"""
    path: str
    name: str
    extension: str
    size_bytes: int
    file_type: FileType
    purpose: str
    description: str
    connections: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "name": self.name,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "file_type": self.file_type.value,
            "purpose": self.purpose,
            "description": self.description,
            "connections": self.connections,
            "metadata": self.metadata
        }


@dataclass
class FileTreeNode:
    """Node in the file tree"""
    name: str
    path: str
    is_directory: bool
    file_type: Optional[FileType] = None
    purpose: Optional[str] = None
    size_bytes: int = 0
    children: List['FileTreeNode'] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        result = {
            "name": self.name,
            "path": self.path,
            "is_directory": self.is_directory,
            "size_bytes": self.size_bytes
        }
        if self.file_type:
            result["file_type"] = self.file_type.value
        if self.purpose:
            result["purpose"] = self.purpose
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result


@dataclass
class ProjectStructure:
    """Overall project structure analysis"""
    project_type: str  # "kicad", "altium", "eagle", "gerber_only", "mixed"
    main_pcb_file: Optional[str]
    main_schematic_file: Optional[str]
    layer_count: Optional[int]
    has_bom: bool
    has_gerbers: bool
    has_3d_models: bool
    file_count: int
    total_size_bytes: int
    description: str
    key_components: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


# File extension to type mapping
EXTENSION_TYPE_MAP = {
    # PCB Layout
    '.kicad_pcb': FileType.PCB_LAYOUT,
    '.brd': FileType.PCB_LAYOUT,
    '.pcbdoc': FileType.PCB_LAYOUT,
    '.pcb': FileType.PCB_LAYOUT,
    
    # Schematic
    '.kicad_sch': FileType.SCHEMATIC,
    '.sch': FileType.SCHEMATIC,
    '.schdoc': FileType.SCHEMATIC,
    '.dsn': FileType.SCHEMATIC,
    
    # Gerber
    '.gbr': FileType.GERBER,
    '.ger': FileType.GERBER,
    '.gtl': FileType.GERBER,  # Top layer
    '.gbl': FileType.GERBER,  # Bottom layer
    '.gts': FileType.GERBER,  # Top soldermask
    '.gbs': FileType.GERBER,  # Bottom soldermask
    '.gto': FileType.GERBER,  # Top silkscreen
    '.gbo': FileType.GERBER,  # Bottom silkscreen
    '.gko': FileType.GERBER,  # Keep-out
    '.gm1': FileType.GERBER,  # Mechanical
    '.g1': FileType.GERBER,   # Inner layer
    '.g2': FileType.GERBER,
    '.g3': FileType.GERBER,
    '.g4': FileType.GERBER,
    
    # Drill
    '.drl': FileType.DRILL,
    '.xln': FileType.DRILL,
    '.exc': FileType.DRILL,
    '.txt': FileType.DRILL,  # May be drill file
    
    # BOM
    '.csv': FileType.BOM,
    '.xlsx': FileType.BOM,
    '.xls': FileType.BOM,
    
    # Pick and Place
    '.pos': FileType.PICK_AND_PLACE,
    '.xy': FileType.PICK_AND_PLACE,
    '.mnt': FileType.PICK_AND_PLACE,
    
    # Netlist
    '.net': FileType.NETLIST,
    
    # Footprint/Symbol
    '.kicad_mod': FileType.FOOTPRINT,
    '.kicad_sym': FileType.SYMBOL,
    '.lib': FileType.LIBRARY,
    '.lbr': FileType.LIBRARY,
    
    # 3D Models
    '.step': FileType.MODEL_3D,
    '.stp': FileType.MODEL_3D,
    '.wrl': FileType.MODEL_3D,
    
    # Project files
    '.kicad_pro': FileType.PROJECT,
    '.prjpcb': FileType.PROJECT,
    '.opj': FileType.PROJECT,
    
    # Rules
    '.kicad_dru': FileType.RULES,
    
    # Documentation
    '.pdf': FileType.DOCUMENTATION,
    '.md': FileType.DOCUMENTATION,
    '.txt': FileType.DOCUMENTATION,
    '.doc': FileType.DOCUMENTATION,
    '.docx': FileType.DOCUMENTATION,
    
    # Output
    '.zip': FileType.OUTPUT,
    '.rar': FileType.OUTPUT,
}

# Gerber layer descriptions
GERBER_LAYER_MAP = {
    '.gtl': 'Top Copper Layer',
    '.gbl': 'Bottom Copper Layer',
    '.gts': 'Top Soldermask',
    '.gbs': 'Bottom Soldermask',
    '.gto': 'Top Silkscreen',
    '.gbo': 'Bottom Silkscreen',
    '.gko': 'Board Outline (Keep-out)',
    '.gm1': 'Mechanical Layer 1',
    '.gtp': 'Top Paste',
    '.gbp': 'Bottom Paste',
    '.g1': 'Inner Layer 1',
    '.g2': 'Inner Layer 2',
    '.g3': 'Inner Layer 3',
    '.g4': 'Inner Layer 4',
}


class FileAnalyzer:
    """
    Analyzes PCB project files to determine purpose and connections
    
    Uses a combination of:
    1. Extension-based detection (fast, deterministic)
    2. Content analysis (for ambiguous files)
    3. AI analysis (for complex understanding)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.ai_enabled = self.settings.openai_api_key is not None
        
        if self.ai_enabled:
            self.client = OpenAI(api_key=self.settings.openai_api_key)
            logger.info("FileAnalyzer initialized with AI capabilities")
        else:
            logger.info("FileAnalyzer initialized without AI (no API key)")
    
    def analyze_project(self, project_path: Path) -> Tuple[List[FileInfo], FileTreeNode, ProjectStructure]:
        """
        Analyze all files in a project
        
        Args:
            project_path: Path to extracted project files
            
        Returns:
            Tuple of (file_infos, file_tree, project_structure)
        """
        logger.info(f"Analyzing project at: {project_path}")
        
        # Step 1: Collect all files
        files = self._collect_files(project_path)
        logger.info(f"Found {len(files)} files")
        
        # Step 2: Classify each file
        file_infos = []
        for file_path in files:
            info = self._analyze_file(file_path, project_path)
            file_infos.append(info)
        
        # Step 3: Build file tree
        file_tree = self._build_file_tree(project_path, file_infos)
        
        # Step 4: Analyze project structure
        project_structure = self._analyze_project_structure(file_infos, project_path)
        
        # Step 5: Detect file connections
        file_infos = self._detect_connections(file_infos)
        
        # Step 6: AI enhancement (if enabled)
        if self.ai_enabled and len(file_infos) > 0:
            file_infos, project_structure = self._ai_enhance_analysis(
                file_infos, project_structure, project_path
            )
        
        return file_infos, file_tree, project_structure
    
    def _collect_files(self, project_path: Path) -> List[Path]:
        """Collect all files in project, excluding hidden and system files"""
        files = []
        
        for item in project_path.rglob('*'):
            if item.is_file():
                # Skip hidden files
                if item.name.startswith('.'):
                    continue
                # Skip backup files
                if item.name.endswith('.bak') or '-bak' in item.name:
                    continue
                # Skip system files
                if item.name in ['Thumbs.db', 'desktop.ini', '.DS_Store']:
                    continue
                # Skip __pycache__ and similar
                if '__pycache__' in str(item) or '.git' in str(item):
                    continue
                    
                files.append(item)
        
        return sorted(files)
    
    def _analyze_file(self, file_path: Path, project_root: Path) -> FileInfo:
        """Analyze a single file"""
        rel_path = str(file_path.relative_to(project_root))
        extension = file_path.suffix.lower()
        size = file_path.stat().st_size
        
        # Determine file type
        file_type = self._detect_file_type(file_path, extension)
        
        # Generate purpose and description
        purpose, description = self._generate_description(file_path, file_type, extension)
        
        return FileInfo(
            path=rel_path,
            name=file_path.name,
            extension=extension,
            size_bytes=size,
            file_type=file_type,
            purpose=purpose,
            description=description,
            metadata={}
        )
    
    def _detect_file_type(self, file_path: Path, extension: str) -> FileType:
        """Detect file type based on extension and content"""
        # Check extension mapping first
        if extension in EXTENSION_TYPE_MAP:
            return EXTENSION_TYPE_MAP[extension]
        
        # Content-based detection for ambiguous files
        if extension == '.txt':
            # Could be drill file or documentation
            try:
                content = file_path.read_text(errors='ignore')[:500]
                if 'T01' in content or 'M48' in content or 'EXCELLON' in content.upper():
                    return FileType.DRILL
                if 'X' in content and 'Y' in content and content.count('\n') > 10:
                    return FileType.PICK_AND_PLACE
            except:
                pass
            return FileType.DOCUMENTATION
        
        if extension == '.csv':
            # Could be BOM or pick-and-place
            try:
                content = file_path.read_text(errors='ignore')[:1000].lower()
                if 'designator' in content or 'refdes' in content:
                    if 'x' in content and 'y' in content and 'rotation' in content:
                        return FileType.PICK_AND_PLACE
                return FileType.BOM
            except:
                pass
            return FileType.BOM
        
        return FileType.OTHER
    
    def _generate_description(self, file_path: Path, file_type: FileType, extension: str) -> Tuple[str, str]:
        """Generate purpose and description for a file"""
        name = file_path.name
        
        # Gerber files
        if file_type == FileType.GERBER:
            layer_desc = GERBER_LAYER_MAP.get(extension, 'Gerber Layer')
            return (
                f"Manufacturing: {layer_desc}",
                f"Gerber file containing {layer_desc.lower()} data for PCB fabrication"
            )
        
        # Drill files
        if file_type == FileType.DRILL:
            return (
                "Manufacturing: Drill Data",
                "Excellon drill file containing hole positions and sizes for PCB fabrication"
            )
        
        # PCB Layout
        if file_type == FileType.PCB_LAYOUT:
            return (
                "Design: PCB Layout",
                "Main PCB layout file containing component placement, routing, and board outline"
            )
        
        # Schematic
        if file_type == FileType.SCHEMATIC:
            return (
                "Design: Schematic",
                "Circuit schematic showing electrical connections between components"
            )
        
        # BOM
        if file_type == FileType.BOM:
            return (
                "Manufacturing: Bill of Materials",
                "List of components required to build the PCB assembly"
            )
        
        # Pick and Place
        if file_type == FileType.PICK_AND_PLACE:
            return (
                "Manufacturing: Pick & Place",
                "Component placement data for automated assembly machines"
            )
        
        # 3D Model
        if file_type == FileType.MODEL_3D:
            return (
                "Visualization: 3D Model",
                "3D model file for mechanical design integration and visualization"
            )
        
        # Project file
        if file_type == FileType.PROJECT:
            return (
                "Project: Configuration",
                "Project configuration file containing settings and file references"
            )
        
        # Footprint
        if file_type == FileType.FOOTPRINT:
            return (
                "Library: Footprint",
                "Component footprint definition for PCB layout"
            )
        
        # Symbol
        if file_type == FileType.SYMBOL:
            return (
                "Library: Symbol",
                "Component symbol definition for schematic capture"
            )
        
        # Library
        if file_type == FileType.LIBRARY:
            return (
                "Library: Component Library",
                "Library file containing component definitions"
            )
        
        # Documentation
        if file_type == FileType.DOCUMENTATION:
            return (
                "Documentation",
                "Project documentation or notes"
            )
        
        # Rules
        if file_type == FileType.RULES:
            return (
                "Design: Rules",
                "Design rules and constraints for the PCB"
            )
        
        # Netlist
        if file_type == FileType.NETLIST:
            return (
                "Design: Netlist",
                "Electrical netlist defining component connections"
            )
        
        return (
            "Other",
            f"File: {name}"
        )
    
    def _build_file_tree(self, project_path: Path, file_infos: List[FileInfo]) -> FileTreeNode:
        """Build hierarchical file tree structure"""
        # Create lookup for file info by path
        info_map = {info.path: info for info in file_infos}
        
        # Create root node
        root = FileTreeNode(
            name=project_path.name,
            path="",
            is_directory=True,
            size_bytes=sum(f.size_bytes for f in file_infos)
        )
        
        # Build tree structure
        for info in file_infos:
            parts = Path(info.path).parts
            current = root
            
            # Navigate/create directory structure
            for i, part in enumerate(parts[:-1]):
                dir_path = str(Path(*parts[:i+1]))
                
                # Find or create directory node
                existing = next((c for c in current.children if c.name == part and c.is_directory), None)
                if existing:
                    current = existing
                else:
                    new_dir = FileTreeNode(
                        name=part,
                        path=dir_path,
                        is_directory=True
                    )
                    current.children.append(new_dir)
                    current = new_dir
            
            # Add file node
            file_node = FileTreeNode(
                name=info.name,
                path=info.path,
                is_directory=False,
                file_type=info.file_type,
                purpose=info.purpose,
                size_bytes=info.size_bytes
            )
            current.children.append(file_node)
        
        # Sort children: directories first, then alphabetically
        self._sort_tree(root)
        
        # Calculate directory sizes
        self._calculate_sizes(root)
        
        return root
    
    def _sort_tree(self, node: FileTreeNode):
        """Sort tree nodes: directories first, then alphabetically"""
        if node.children:
            node.children.sort(key=lambda x: (not x.is_directory, x.name.lower()))
            for child in node.children:
                self._sort_tree(child)
    
    def _calculate_sizes(self, node: FileTreeNode) -> int:
        """Calculate total size for directories"""
        if not node.is_directory:
            return node.size_bytes
        
        total = sum(self._calculate_sizes(child) for child in node.children)
        node.size_bytes = total
        return total
    
    def _analyze_project_structure(self, file_infos: List[FileInfo], project_path: Path) -> ProjectStructure:
        """Analyze overall project structure"""
        # Count file types
        type_counts = {}
        for info in file_infos:
            type_counts[info.file_type] = type_counts.get(info.file_type, 0) + 1
        
        # Detect project type
        project_type = self._detect_project_type(file_infos, project_path)
        
        # Find main files
        main_pcb = next((f.path for f in file_infos if f.file_type == FileType.PCB_LAYOUT), None)
        main_sch = next((f.path for f in file_infos if f.file_type == FileType.SCHEMATIC), None)
        
        # Count gerber layers to estimate layer count
        gerber_count = type_counts.get(FileType.GERBER, 0)
        layer_count = None
        if gerber_count >= 2:
            # Rough estimate: 2 copper + soldermask + silkscreen per side
            copper_files = sum(1 for f in file_infos if f.extension in ['.gtl', '.gbl', '.g1', '.g2', '.g3', '.g4'])
            layer_count = max(2, copper_files)
        
        return ProjectStructure(
            project_type=project_type,
            main_pcb_file=main_pcb,
            main_schematic_file=main_sch,
            layer_count=layer_count,
            has_bom=FileType.BOM in type_counts,
            has_gerbers=FileType.GERBER in type_counts,
            has_3d_models=FileType.MODEL_3D in type_counts,
            file_count=len(file_infos),
            total_size_bytes=sum(f.size_bytes for f in file_infos),
            description=f"{project_type.title()} project with {len(file_infos)} files"
        )
    
    def _detect_project_type(self, file_infos: List[FileInfo], project_path: Path) -> str:
        """Detect the EDA tool used for this project"""
        extensions = {f.extension for f in file_infos}
        
        if '.kicad_pcb' in extensions or '.kicad_sch' in extensions:
            return "kicad"
        if '.pcbdoc' in extensions or '.schdoc' in extensions:
            return "altium"
        if '.brd' in extensions and '.sch' in extensions:
            # Could be Eagle or OrCAD
            for f in file_infos:
                try:
                    content = Path(project_path / f.path).read_text(errors='ignore')[:100]
                    if 'eagle' in content.lower():
                        return "eagle"
                except:
                    pass
            return "eagle"
        if any(f.extension in ['.gbr', '.ger', '.gtl', '.gbl'] for f in file_infos):
            return "gerber_only"
        
        return "mixed"
    
    def _detect_connections(self, file_infos: List[FileInfo]) -> List[FileInfo]:
        """Detect connections between files"""
        # Group files by type
        pcb_files = [f for f in file_infos if f.file_type == FileType.PCB_LAYOUT]
        sch_files = [f for f in file_infos if f.file_type == FileType.SCHEMATIC]
        gerber_files = [f for f in file_infos if f.file_type == FileType.GERBER]
        bom_files = [f for f in file_infos if f.file_type == FileType.BOM]
        
        for info in file_infos:
            connections = []
            
            if info.file_type == FileType.PCB_LAYOUT:
                # PCB connects to schematics and generates gerbers
                connections.extend([f.path for f in sch_files])
                if gerber_files:
                    connections.append("(generates) Gerber files")
            
            elif info.file_type == FileType.SCHEMATIC:
                # Schematic connects to PCB and BOM
                connections.extend([f.path for f in pcb_files])
                if bom_files:
                    connections.append("(generates) BOM files")
            
            elif info.file_type == FileType.GERBER:
                # Gerbers are generated from PCB
                connections.extend([f"(from) {f.path}" for f in pcb_files])
            
            elif info.file_type == FileType.BOM:
                # BOM is generated from schematic
                connections.extend([f"(from) {f.path}" for f in sch_files])
            
            info.connections = connections
        
        return file_infos
    
    def _ai_enhance_analysis(
        self, 
        file_infos: List[FileInfo], 
        project_structure: ProjectStructure,
        project_path: Path
    ) -> Tuple[List[FileInfo], ProjectStructure]:
        """Use AI to enhance file analysis with better descriptions"""
        try:
            # Build summary for AI
            file_summary = []
            for info in file_infos[:30]:  # Limit to 30 files for context
                file_summary.append({
                    "name": info.name,
                    "type": info.file_type.value,
                    "size": info.size_bytes
                })
            
            prompt = f"""Analyze this PCB project structure and provide insights:

Project Type: {project_structure.project_type}
Files: {json.dumps(file_summary, indent=2)}

Provide a JSON response with:
1. "project_description": A 2-3 sentence description of what this project likely is
2. "key_components": List of likely key components/ICs based on file names (up to 5)
3. "design_notes": Any notable observations about the project organization

Respond with valid JSON only."""

            response = self.client.chat.completions.create(
                model=self.settings.openai_model or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a PCB design expert. Analyze project files and provide insights."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            ai_result = json.loads(content)
            
            # Update project structure
            project_structure.description = ai_result.get("project_description", project_structure.description)
            project_structure.key_components = ai_result.get("key_components", [])
            
            logger.info("AI analysis complete")
            
        except Exception as e:
            logger.warning(f"AI enhancement failed: {e}")
        
        return file_infos, project_structure
    
    def get_file_purposes_dict(self, file_infos: List[FileInfo]) -> Dict[str, Dict]:
        """Convert file infos to dictionary keyed by path"""
        return {
            info.path: {
                "file_type": info.file_type.value,
                "purpose": info.purpose,
                "description": info.description,
                "connections": info.connections,
                "size_bytes": info.size_bytes
            }
            for info in file_infos
        }
