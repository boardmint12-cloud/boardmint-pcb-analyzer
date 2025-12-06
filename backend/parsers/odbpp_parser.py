"""
ODB++ Parser
Parses ODB++ directory structure - the open manufacturing data format

ODB++ is a directory-based format containing:
- matrix/matrix: Job structure and layer definitions
- steps/{step}/: Design steps (usually "pcb")
  - profile: Board outline
  - layers/{layer}/: Layer data
    - features: Copper, mask, silk features
  - components/: Component placements
  - eda/data: CAD netlist data
- symbols/: Pad/feature symbol definitions
- fonts/: Text font definitions

Reference: https://odbplusplus.com/design/specification/
"""

import os
import re
import gzip
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

from .base_parser import (
    BaseParser, ParsedPCBData, BoardInfo,
    Component, Net, Track, Via, Zone
)

logger = logging.getLogger(__name__)


@dataclass
class ODBLayer:
    """ODB++ layer definition"""
    name: str
    layer_type: str  # SIGNAL, POWER_GROUND, MIXED, SOLDER_MASK, SILK_SCREEN, etc.
    polarity: str    # POSITIVE or NEGATIVE
    context: str     # BOARD or MISC
    row: int
    start_name: Optional[str] = None
    end_name: Optional[str] = None


@dataclass
class ODBSymbol:
    """ODB++ symbol (pad/feature) definition"""
    name: str
    symbol_type: str
    width: float = 0
    height: float = 0
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ODBFeature:
    """ODB++ feature (line, arc, pad, etc.)"""
    feature_type: str  # LINE, ARC, PAD, SURFACE, TEXT
    x: float = 0
    y: float = 0
    x2: float = 0  # End point for lines
    y2: float = 0
    symbol: str = ""
    polarity: str = "P"  # P=positive, N=negative
    net_num: int = 0
    attributes: Dict[str, str] = field(default_factory=dict)


class ODBPPParser(BaseParser):
    """
    Parser for ODB++ format
    
    ODB++ is a comprehensive PCB manufacturing format that includes:
    - Complete layer stackup
    - Copper features with net assignment
    - Component placements with attributes
    - Drill/via data
    - Test points
    - Netlist connectivity
    """
    
    # Layer type mapping
    LAYER_TYPE_MAP = {
        'SIGNAL': 'signal',
        'POWER_GROUND': 'plane',
        'MIXED': 'mixed',
        'SOLDER_MASK': 'soldermask',
        'SILK_SCREEN': 'silkscreen',
        'SOLDER_PASTE': 'paste',
        'DRILL': 'drill',
        'ROUT': 'outline',
        'DOCUMENT': 'document',
    }
    
    def __init__(self):
        """Initialize parser"""
        self.layers: Dict[str, ODBLayer] = {}
        self.symbols: Dict[str, ODBSymbol] = {}
        self.units = 'mm'
        self.scale = 1.0
        self.net_names: Dict[int, str] = {}
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse ODB++ directory
        
        Args:
            project_path: Path to ODB++ directory (or .tgz/.zip)
            
        Returns:
            ParsedPCBData with normalized data
        """
        project_path = Path(project_path)
        
        # Find ODB++ root
        odb_root = self._find_odb_root(project_path)
        
        if not odb_root:
            logger.error("Not a valid ODB++ structure")
            return self._empty_result()
        
        logger.info(f"Parsing ODB++ from: {odb_root}")
        
        try:
            # Parse matrix (layer definitions)
            self._parse_matrix(odb_root)
            
            # Parse symbols
            self._parse_symbols(odb_root)
            
            # Find the main step (usually 'pcb' or first step)
            step_name = self._find_main_step(odb_root)
            if not step_name:
                logger.error("No step found in ODB++")
                return self._empty_result()
            
            step_path = odb_root / 'steps' / step_name
            
            # Parse EDA data (netlist)
            self._parse_eda_data(step_path)
            
            # Parse board outline
            board_info = self._parse_profile(step_path)
            
            # Parse components
            components = self._parse_components(step_path)
            
            # Parse layer features
            tracks, vias, zones = self._parse_layers(step_path)
            
            # Build nets from collected data
            nets = self._build_nets()
            
            return ParsedPCBData(
                board_info=board_info,
                components=components,
                nets=nets,
                tracks=tracks,
                vias=vias,
                zones=zones,
                files_found={'odbpp': True},
                raw_data={
                    'odb_root': str(odb_root),
                    'step': step_name,
                    'layers': list(self.layers.keys())
                }
            )
            
        except Exception as e:
            logger.error(f"ODB++ parsing failed: {e}", exc_info=True)
            return self._empty_result()
    
    def _find_odb_root(self, path: Path) -> Optional[Path]:
        """Find the ODB++ root directory"""
        # Check if this is already ODB++ root
        if (path / 'matrix').exists() and (path / 'steps').exists():
            return path
        
        # Check subdirectories
        for subdir in path.iterdir():
            if subdir.is_dir():
                if (subdir / 'matrix').exists() and (subdir / 'steps').exists():
                    return subdir
        
        # Check for ODB++ markers
        for subdir in path.rglob('matrix'):
            if subdir.is_dir() and (subdir.parent / 'steps').exists():
                return subdir.parent
        
        return None
    
    def _read_odb_file(self, file_path: Path) -> str:
        """Read ODB++ file (handles gzip compression)"""
        if not file_path.exists():
            # Try with .z extension (gzip)
            gz_path = file_path.with_suffix(file_path.suffix + '.z')
            if gz_path.exists():
                file_path = gz_path
            else:
                gz_path = Path(str(file_path) + '.z')
                if gz_path.exists():
                    file_path = gz_path
                else:
                    return ""
        
        try:
            if str(file_path).endswith('.z'):
                with gzip.open(file_path, 'rt', encoding='utf-8', errors='replace') as f:
                    return f.read()
            else:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return ""
    
    def _parse_matrix(self, odb_root: Path):
        """Parse matrix/matrix file for layer definitions"""
        matrix_file = odb_root / 'matrix' / 'matrix'
        content = self._read_odb_file(matrix_file)
        
        if not content:
            return
        
        # Parse STEP and LAYER sections
        current_section = None
        current_layer = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('STEP {'):
                current_section = 'STEP'
            elif line.startswith('LAYER {'):
                current_section = 'LAYER'
                current_layer = {}
            elif line == '}':
                if current_section == 'LAYER' and current_layer:
                    name = current_layer.get('NAME', '')
                    if name:
                        self.layers[name] = ODBLayer(
                            name=name,
                            layer_type=current_layer.get('TYPE', 'SIGNAL'),
                            polarity=current_layer.get('POLARITY', 'POSITIVE'),
                            context=current_layer.get('CONTEXT', 'BOARD'),
                            row=int(current_layer.get('ROW', 0)),
                            start_name=current_layer.get('START_NAME'),
                            end_name=current_layer.get('END_NAME')
                        )
                current_section = None
                current_layer = None
            elif current_section == 'LAYER' and '=' in line:
                key, _, value = line.partition('=')
                current_layer[key.strip()] = value.strip()
        
        logger.info(f"Parsed {len(self.layers)} layers from matrix")
    
    def _parse_symbols(self, odb_root: Path):
        """Parse symbols directory for pad definitions"""
        symbols_dir = odb_root / 'symbols'
        
        if not symbols_dir.exists():
            return
        
        for sym_file in symbols_dir.iterdir():
            if sym_file.is_file():
                sym_name = sym_file.stem
                content = self._read_odb_file(sym_file)
                
                # Parse symbol definition
                symbol = self._parse_symbol_content(sym_name, content)
                if symbol:
                    self.symbols[sym_name] = symbol
        
        logger.info(f"Parsed {len(self.symbols)} symbols")
    
    def _parse_symbol_content(self, name: str, content: str) -> Optional[ODBSymbol]:
        """Parse symbol file content"""
        if not content:
            return None
        
        symbol = ODBSymbol(name=name, symbol_type='unknown')
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Standard symbol definitions
            if line.startswith('$'):
                # Shape definition
                if 'r' in line.lower():
                    symbol.symbol_type = 'round'
                elif 's' in line.lower():
                    symbol.symbol_type = 'square'
                elif 'rect' in line.lower():
                    symbol.symbol_type = 'rectangle'
            
            # Extract dimensions from common patterns
            match = re.search(r'(\d+\.?\d*)\s*[xX]\s*(\d+\.?\d*)', line)
            if match:
                symbol.width = float(match.group(1)) * self.scale
                symbol.height = float(match.group(2)) * self.scale
        
        return symbol
    
    def _find_main_step(self, odb_root: Path) -> Optional[str]:
        """Find the main step name"""
        steps_dir = odb_root / 'steps'
        
        if not steps_dir.exists():
            return None
        
        # Prefer 'pcb' step
        if (steps_dir / 'pcb').exists():
            return 'pcb'
        
        # Otherwise use first step
        for step_dir in steps_dir.iterdir():
            if step_dir.is_dir():
                return step_dir.name
        
        return None
    
    def _parse_eda_data(self, step_path: Path):
        """Parse EDA/data file for net names"""
        eda_file = step_path / 'eda' / 'data'
        content = self._read_odb_file(eda_file)
        
        if not content:
            return
        
        # Parse NET definitions
        for line in content.split('\n'):
            line = line.strip()
            
            # NET definition: NET <net_name>
            if line.startswith('NET '):
                parts = line.split()
                if len(parts) >= 2:
                    # Assign sequential net number
                    net_num = len(self.net_names)
                    self.net_names[net_num] = parts[1]
            
            # Or SNT (subnet) definition
            elif line.startswith('SNT '):
                parts = line.split()
                if len(parts) >= 2:
                    net_num = len(self.net_names)
                    self.net_names[net_num] = parts[1]
        
        logger.info(f"Parsed {len(self.net_names)} net names from EDA data")
    
    def _parse_profile(self, step_path: Path) -> BoardInfo:
        """Parse profile file for board outline"""
        profile_file = step_path / 'profile'
        content = self._read_odb_file(profile_file)
        
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        if content:
            # Parse polygon points
            for line in content.split('\n'):
                line = line.strip()
                
                # OB (outline begin) or OS (outline segment)
                if line.startswith('OB') or line.startswith('OS'):
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            x = float(parts[1]) * self.scale
                            y = float(parts[2]) * self.scale
                            min_x = min(min_x, x)
                            min_y = min(min_y, y)
                            max_x = max(max_x, x)
                            max_y = max(max_y, y)
                        except ValueError:
                            pass
        
        # Calculate dimensions
        if min_x == float('inf'):
            size_x, size_y = 100.0, 100.0
        else:
            size_x = max_x - min_x
            size_y = max_y - min_y
        
        # Count copper layers
        copper_layers = sum(
            1 for layer in self.layers.values()
            if layer.layer_type in ('SIGNAL', 'POWER_GROUND', 'MIXED')
        )
        
        return BoardInfo(
            size_x=size_x,
            size_y=size_y,
            layer_count=max(2, copper_layers)
        )
    
    def _parse_components(self, step_path: Path) -> List[Component]:
        """Parse components from top and bottom files"""
        components = []
        
        for side in ['top', 'bot']:
            comp_file = step_path / 'components' / side
            content = self._read_odb_file(comp_file)
            
            if not content:
                continue
            
            layer = 'F.Cu' if side == 'top' else 'B.Cu'
            
            # Parse component definitions
            current_comp = None
            
            for line in content.split('\n'):
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                # CMP (component) definition
                if line.startswith('CMP '):
                    if current_comp:
                        components.append(current_comp)
                    
                    parts = line.split()
                    # CMP <pkg_ref> <x> <y> <rotation> <mirror> <comp_name>
                    if len(parts) >= 7:
                        try:
                            current_comp = Component(
                                reference=parts[6] if len(parts) > 6 else parts[1],
                                value='',
                                footprint=parts[1],
                                x=float(parts[2]) * self.scale,
                                y=float(parts[3]) * self.scale,
                                rotation=float(parts[4]),
                                layer=layer
                            )
                        except (ValueError, IndexError):
                            current_comp = None
                
                # PRP (property) for component attributes
                elif line.startswith('PRP ') and current_comp:
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        prop_name = parts[1].upper()
                        prop_value = parts[2].strip("'\"")
                        
                        if prop_name == 'PART_NAME' or prop_name == 'VALUE':
                            current_comp.value = prop_value
                        elif prop_name == 'MPN' or prop_name == 'PART_NUMBER':
                            current_comp.mpn = prop_value
            
            # Don't forget last component
            if current_comp:
                components.append(current_comp)
        
        logger.info(f"Parsed {len(components)} components")
        return components
    
    def _parse_layers(self, step_path: Path) -> Tuple[List[Track], List[Via], List[Zone]]:
        """Parse layer features"""
        tracks = []
        vias = []
        zones = []
        
        layers_dir = step_path / 'layers'
        
        if not layers_dir.exists():
            return tracks, vias, zones
        
        for layer_name, layer_info in self.layers.items():
            # Only parse copper layers
            if layer_info.layer_type not in ('SIGNAL', 'POWER_GROUND', 'MIXED'):
                continue
            
            layer_dir = layers_dir / layer_name
            features_file = layer_dir / 'features'
            
            content = self._read_odb_file(features_file)
            if not content:
                continue
            
            # Map layer name
            mapped_layer = self._map_layer_name(layer_name, layer_info)
            
            # Parse features
            for line in content.split('\n'):
                line = line.strip()
                
                if not line or line.startswith('#') or line.startswith('$'):
                    continue
                
                # Line feature: L <xs> <ys> <xe> <ye> <sym> <polarity> <dcode> <net>
                if line.startswith('L '):
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            # Get symbol for width
                            sym_name = parts[5] if len(parts) > 5 else ''
                            width = self._get_symbol_width(sym_name)
                            
                            net_num = int(parts[-1]) if parts[-1].isdigit() else 0
                            net_name = self.net_names.get(net_num, '')
                            
                            tracks.append(Track(
                                net_name=net_name,
                                layer=mapped_layer,
                                width=width,
                                x1=float(parts[1]) * self.scale,
                                y1=float(parts[2]) * self.scale,
                                x2=float(parts[3]) * self.scale,
                                y2=float(parts[4]) * self.scale
                            ))
                        except (ValueError, IndexError):
                            pass
                
                # Pad feature (could be via): P <x> <y> <symbol> <polarity> <dcode> <net>
                elif line.startswith('P '):
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            x = float(parts[1]) * self.scale
                            y = float(parts[2]) * self.scale
                            sym_name = parts[3] if len(parts) > 3 else ''
                            
                            # Check if this is a via (appears on multiple layers)
                            symbol = self.symbols.get(sym_name)
                            if symbol and 'via' in sym_name.lower():
                                net_num = int(parts[-1]) if parts[-1].isdigit() else 0
                                net_name = self.net_names.get(net_num, '')
                                
                                vias.append(Via(
                                    net_name=net_name,
                                    x=x,
                                    y=y,
                                    diameter=symbol.width if symbol else 0.6,
                                    drill=symbol.width * 0.5 if symbol else 0.3
                                ))
                        except (ValueError, IndexError):
                            pass
        
        logger.info(f"Parsed {len(tracks)} tracks, {len(vias)} vias")
        return tracks, vias, zones
    
    def _map_layer_name(self, name: str, layer_info: ODBLayer) -> str:
        """Map ODB++ layer name to standard name"""
        name_lower = name.lower()
        
        if 'top' in name_lower or layer_info.row == 1:
            return 'F.Cu'
        elif 'bot' in name_lower or 'bottom' in name_lower:
            return 'B.Cu'
        elif 'inner' in name_lower or name_lower.startswith('in'):
            # Try to extract layer number
            match = re.search(r'(\d+)', name)
            if match:
                return f'In{match.group(1)}.Cu'
            return 'In1.Cu'
        
        return name
    
    def _get_symbol_width(self, sym_name: str) -> float:
        """Get width from symbol name"""
        symbol = self.symbols.get(sym_name)
        if symbol and symbol.width > 0:
            return symbol.width
        
        # Try to parse from name (e.g., "r100" = 100 mils = 2.54mm)
        match = re.search(r'r?(\d+)', sym_name.lower())
        if match:
            mils = float(match.group(1))
            return mils * 0.0254  # Convert mils to mm
        
        return 0.2  # Default width
    
    def _build_nets(self) -> List[Net]:
        """Build net list from collected data"""
        nets = []
        
        for net_num, net_name in self.net_names.items():
            nets.append(Net(
                name=net_name,
                is_power=self.detect_power_net(net_name),
                is_ground=self.detect_ground_net(net_name),
                is_mains=self.detect_mains_net(net_name)
            ))
        
        return nets
    
    def _empty_result(self) -> ParsedPCBData:
        """Return empty result"""
        return ParsedPCBData(
            board_info=BoardInfo(size_x=0, size_y=0, layer_count=2),
            components=[],
            nets=[],
            tracks=[],
            vias=[],
            zones=[]
        )


def parse_odbpp(path: str) -> ParsedPCBData:
    """Convenience function to parse ODB++"""
    parser = ODBPPParser()
    return parser.parse(path)
