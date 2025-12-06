"""
Eagle XML Parser
Parses Autodesk Eagle .brd and .sch files (XML format)

Eagle uses XML format since version 6.0, making it well-documented and parseable.
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .base_parser import (
    BaseParser, ParsedPCBData, BoardInfo, 
    Component, Net, Track, Via, Zone
)

logger = logging.getLogger(__name__)


@dataclass
class EagleLayer:
    """Eagle layer definition"""
    number: int
    name: str
    color: int
    fill: int
    visible: bool
    active: bool


class EagleParser(BaseParser):
    """
    Parser for Autodesk Eagle PCB files (.brd, .sch)
    
    Eagle XML structure:
    <eagle>
      <drawing>
        <board>
          <plain> - board outline, text, graphics
          <libraries> - component libraries
          <elements> - placed components
          <signals> - nets with wires, vias, polygons
        </board>
      </drawing>
    </eagle>
    """
    
    # Eagle layer number mappings
    LAYER_MAP = {
        1: 'F.Cu',      # Top copper
        16: 'B.Cu',     # Bottom copper
        2: 'In1.Cu',    # Inner 1
        15: 'In2.Cu',   # Inner 2
        21: 'F.SilkS',  # Top silkscreen
        22: 'B.SilkS',  # Bottom silkscreen
        29: 'F.Adhes',  # Top adhesive
        30: 'B.Adhes',  # Bottom adhesive
        31: 'F.Paste',  # Top paste
        32: 'B.Paste',  # Bottom paste
        35: 'F.Fab',    # Top fabrication
        36: 'B.Fab',    # Bottom fabrication
        39: 'F.CrtYd',  # Top courtyard
        40: 'B.CrtYd',  # Bottom courtyard
        41: 'Dwgs.User',
        44: 'Edge.Cuts',
        45: 'Margin',
        51: 'F.Mask',   # Top soldermask
        52: 'B.Mask',   # Bottom soldermask
    }
    
    def __init__(self):
        """Initialize Eagle parser"""
        self.layers: Dict[int, EagleLayer] = {}
        self.libraries: Dict[str, Dict] = {}
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse Eagle project
        
        Args:
            project_path: Path to project directory or .brd file
            
        Returns:
            ParsedPCBData with normalized data
        """
        project_path = Path(project_path)
        
        # Find board file
        if project_path.is_file() and project_path.suffix.lower() == '.brd':
            brd_file = project_path
        else:
            brd_files = list(project_path.rglob('*.brd'))
            brd_file = brd_files[0] if brd_files else None
        
        if not brd_file or not brd_file.exists():
            logger.error("No Eagle .brd file found")
            return self._empty_result()
        
        logger.info(f"Parsing Eagle board: {brd_file}")
        
        try:
            return self._parse_board_file(brd_file)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return self._empty_result()
        except Exception as e:
            logger.error(f"Eagle parsing failed: {e}", exc_info=True)
            return self._empty_result()
    
    def _parse_board_file(self, brd_file: Path) -> ParsedPCBData:
        """Parse a .brd file"""
        tree = ET.parse(brd_file)
        root = tree.getroot()
        
        # Verify this is an Eagle file
        if root.tag != 'eagle':
            logger.warning("Not an Eagle file (missing <eagle> root)")
            return self._empty_result()
        
        # Find the board element
        drawing = root.find('drawing')
        if drawing is None:
            return self._empty_result()
        
        board = drawing.find('board')
        if board is None:
            # Might be a schematic file
            schematic = drawing.find('schematic')
            if schematic is not None:
                return self._parse_schematic_element(schematic)
            return self._empty_result()
        
        # Parse layers
        layers_elem = drawing.find('layers')
        if layers_elem is not None:
            self._parse_layers(layers_elem)
        
        # Parse libraries
        libraries_elem = board.find('libraries')
        if libraries_elem is not None:
            self._parse_libraries(libraries_elem)
        
        # Parse board data
        board_info = self._parse_board_info(board)
        components = self._parse_elements(board)
        nets, tracks, vias, zones = self._parse_signals(board)
        
        return ParsedPCBData(
            board_info=board_info,
            nets=nets,
            components=components,
            tracks=tracks,
            vias=vias,
            zones=zones,
            files_found={'eagle_brd': True}
        )
    
    def _parse_layers(self, layers_elem: ET.Element):
        """Parse layer definitions"""
        for layer in layers_elem.findall('layer'):
            num = int(layer.get('number', 0))
            self.layers[num] = EagleLayer(
                number=num,
                name=layer.get('name', ''),
                color=int(layer.get('color', 0)),
                fill=int(layer.get('fill', 0)),
                visible=layer.get('visible', 'yes') == 'yes',
                active=layer.get('active', 'yes') == 'yes'
            )
    
    def _parse_libraries(self, libraries_elem: ET.Element):
        """Parse library definitions"""
        for library in libraries_elem.findall('library'):
            lib_name = library.get('name', '')
            packages = {}
            
            for package in library.findall('.//package'):
                pkg_name = package.get('name', '')
                packages[pkg_name] = {
                    'name': pkg_name,
                    'description': package.find('description').text if package.find('description') is not None else ''
                }
            
            self.libraries[lib_name] = packages
    
    def _parse_board_info(self, board: ET.Element) -> BoardInfo:
        """Extract board dimensions and info"""
        # Find board outline from plain/wire elements on layer 20 (Dimension)
        # or calculate from element positions
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        plain = board.find('plain')
        if plain is not None:
            for wire in plain.findall('wire'):
                layer = int(wire.get('layer', 0))
                if layer in (20, 44):  # Dimension or Edge.Cuts
                    x1 = float(wire.get('x1', 0))
                    y1 = float(wire.get('y1', 0))
                    x2 = float(wire.get('x2', 0))
                    y2 = float(wire.get('y2', 0))
                    
                    min_x = min(min_x, x1, x2)
                    min_y = min(min_y, y1, y2)
                    max_x = max(max_x, x1, x2)
                    max_y = max(max_y, y1, y2)
        
        # Fallback: calculate from elements
        if min_x == float('inf'):
            for element in board.findall('.//element'):
                x = float(element.get('x', 0))
                y = float(element.get('y', 0))
                min_x = min(min_x, x - 5)
                min_y = min(min_y, y - 5)
                max_x = max(max_x, x + 5)
                max_y = max(max_y, y + 5)
        
        size_x = max_x - min_x if max_x != float('-inf') else 100.0
        size_y = max_y - min_y if max_y != float('-inf') else 100.0
        
        # Count copper layers
        layer_count = 2  # Default
        design_rules = board.find('designrules')
        if design_rules is not None:
            for param in design_rules.findall('.//param'):
                if param.get('name') == 'layerSetup':
                    setup = param.get('value', '')
                    # Count layers in setup string like "(1*16)"
                    layer_count = len([c for c in setup if c.isdigit()])
                    break
        
        return BoardInfo(
            size_x=size_x,
            size_y=size_y,
            layer_count=max(2, layer_count)
        )
    
    def _parse_elements(self, board: ET.Element) -> List[Component]:
        """Parse placed components (elements)"""
        components = []
        
        elements = board.find('elements')
        if elements is None:
            return components
        
        for elem in elements.findall('element'):
            name = elem.get('name', '')
            value = elem.get('value', '')
            package = elem.get('package', '')
            library = elem.get('library', '')
            
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            
            # Parse rotation (e.g., "R90", "MR180")
            rot_str = elem.get('rot', 'R0')
            mirror = rot_str.startswith('M')
            rotation = float(rot_str.replace('M', '').replace('R', '') or '0')
            
            # Determine layer from mirror
            layer = 'B.Cu' if mirror else 'F.Cu'
            
            components.append(Component(
                reference=name,
                value=value,
                footprint=f"{library}:{package}" if library else package,
                x=x,
                y=y,
                rotation=rotation,
                layer=layer
            ))
        
        return components
    
    def _parse_signals(self, board: ET.Element) -> Tuple[List[Net], List[Track], List[Via], List[Zone]]:
        """Parse signals (nets, tracks, vias, polygons)"""
        nets = []
        tracks = []
        vias = []
        zones = []
        
        signals = board.find('signals')
        if signals is None:
            return nets, tracks, vias, zones
        
        for signal in signals.findall('signal'):
            net_name = signal.get('name', '')
            
            # Classify net
            is_power = self.detect_power_net(net_name)
            is_ground = self.detect_ground_net(net_name)
            is_mains = self.detect_mains_net(net_name)
            
            # Collect pads connected to this net
            pads = []
            for contactref in signal.findall('contactref'):
                element = contactref.get('element', '')
                pad = contactref.get('pad', '')
                pads.append(f"{element}.{pad}")
            
            nets.append(Net(
                name=net_name,
                is_power=is_power,
                is_ground=is_ground,
                is_mains=is_mains,
                pads=pads
            ))
            
            # Parse wires (tracks)
            for wire in signal.findall('wire'):
                layer_num = int(wire.get('layer', 0))
                layer_name = self.LAYER_MAP.get(layer_num, f'Layer{layer_num}')
                
                # Only include copper layers
                if layer_num not in (1, 2, 15, 16):
                    continue
                
                tracks.append(Track(
                    net_name=net_name,
                    layer=layer_name,
                    width=float(wire.get('width', 0.254)),
                    x1=float(wire.get('x1', 0)),
                    y1=float(wire.get('y1', 0)),
                    x2=float(wire.get('x2', 0)),
                    y2=float(wire.get('y2', 0))
                ))
            
            # Parse vias
            for via in signal.findall('via'):
                vias.append(Via(
                    net_name=net_name,
                    x=float(via.get('x', 0)),
                    y=float(via.get('y', 0)),
                    diameter=float(via.get('diameter', 0.6)),
                    drill=float(via.get('drill', 0.3)),
                    start_layer='F.Cu',
                    end_layer='B.Cu'
                ))
            
            # Parse polygons (zones)
            for polygon in signal.findall('polygon'):
                layer_num = int(polygon.get('layer', 0))
                layer_name = self.LAYER_MAP.get(layer_num, f'Layer{layer_num}')
                
                outline = []
                for vertex in polygon.findall('vertex'):
                    x = float(vertex.get('x', 0))
                    y = float(vertex.get('y', 0))
                    outline.append((x, y))
                
                if outline:
                    zones.append(Zone(
                        net_name=net_name,
                        layer=layer_name,
                        outline_points=outline
                    ))
        
        return nets, tracks, vias, zones
    
    def _parse_schematic_element(self, schematic: ET.Element) -> ParsedPCBData:
        """Parse schematic element (when .sch file is provided)"""
        logger.info("Parsing Eagle schematic")
        
        components = []
        nets = []
        
        # Parse sheets
        sheets = schematic.find('sheets')
        if sheets is not None:
            for sheet in sheets.findall('sheet'):
                # Parse instances (component instances)
                instances = sheet.find('instances')
                if instances is not None:
                    for instance in instances.findall('instance'):
                        part = instance.get('part', '')
                        gate = instance.get('gate', '')
                        x = float(instance.get('x', 0))
                        y = float(instance.get('y', 0))
                        
                        # Get part info from parts section
                        parts = schematic.find('parts')
                        if parts is not None:
                            part_elem = parts.find(f".//part[@name='{part}']")
                            if part_elem is not None:
                                value = part_elem.get('value', '')
                                device = part_elem.get('device', '')
                                
                                components.append(Component(
                                    reference=part,
                                    value=value,
                                    footprint=device,
                                    x=x,
                                    y=y
                                ))
                
                # Parse nets
                net_section = sheet.find('nets')
                if net_section is not None:
                    for net in net_section.findall('net'):
                        net_name = net.get('name', '')
                        
                        # Get connected pins
                        pads = []
                        for segment in net.findall('segment'):
                            for pinref in segment.findall('pinref'):
                                part = pinref.get('part', '')
                                pin = pinref.get('pin', '')
                                pads.append(f"{part}.{pin}")
                        
                        nets.append(Net(
                            name=net_name,
                            is_power=self.detect_power_net(net_name),
                            is_ground=self.detect_ground_net(net_name),
                            is_mains=self.detect_mains_net(net_name),
                            pads=pads
                        ))
        
        return ParsedPCBData(
            board_info=BoardInfo(size_x=0, size_y=0, layer_count=2),
            components=components,
            nets=nets,
            tracks=[],
            vias=[],
            zones=[],
            files_found={'eagle_sch': True}
        )
    
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


def parse_eagle_file(file_path: str) -> ParsedPCBData:
    """Convenience function to parse Eagle file"""
    parser = EagleParser()
    return parser.parse(file_path)
