"""
Parser Bridge - Converts old ParsedPCBData to new Canonical Model
Maintains backward compatibility while enabling advanced DRC
"""
import logging
from typing import Optional
from pathlib import Path

from parsers.base_parser import ParsedPCBData
from parsers.kicad_parser import KiCadParser
from parsers.gerber_parser import GerberParser
from models.canonical import (
    Board, BoardOutline, Stackup, Layer, Component, Net, Track, Via, Zone,
    ComponentSide, NetClass, Units, LayerType, Point, Polygon
)

logger = logging.getLogger(__name__)


class ParserBridge:
    """Bridge between old parsers and new canonical model"""
    
    def __init__(self):
        self.kicad_parser = KiCadParser()
        self.gerber_parser = GerberParser()
    
    def parse_to_canonical(self, project_path: str, tool_family: str) -> Board:
        """
        Parse project and convert to canonical model
        
        Args:
            project_path: Path to extracted project
            tool_family: Detected CAD tool family
            
        Returns:
            Canonical Board object
        """
        logger.info(f"Parsing {tool_family} project to canonical model: {project_path}")
        
        # Parse with appropriate parser
        if tool_family.lower() == "kicad":
            parsed_data = self.kicad_parser.parse(project_path)
        elif tool_family.lower() in ["gerber", "unknown"]:
            parsed_data = self.gerber_parser.parse(project_path)
        else:
            # Fallback to Gerber parser for unknown formats
            logger.warning(f"Unknown tool family: {tool_family}, falling back to Gerber parser")
            parsed_data = self.gerber_parser.parse(project_path)
        
        # Convert to canonical model
        board = self._convert_to_canonical(parsed_data, project_path, tool_family)
        
        logger.info(f"Converted to canonical: {board.component_count()} components, {board.net_count()} nets")
        return board
    
    def _convert_to_canonical(self, parsed: ParsedPCBData, project_path: str, tool_family: str) -> Board:
        """Convert ParsedPCBData to canonical Board"""
        
        # Create board ID from path
        board_id = Path(project_path).parent.name
        board_name = Path(project_path).parent.name
        
        # Create stackup
        stackup = self._create_stackup(parsed.board_info)
        
        # Create outline (simplified - just bounding box for now)
        outline = self._create_outline(parsed.board_info)
        
        # Convert components
        components = []
        for comp in parsed.components:
            canonical_comp = Component(
                refdes=comp.reference,
                value=comp.value,
                footprint=comp.footprint,
                position=Point(comp.x, comp.y) if comp.x is not None else None,
                rotation=comp.rotation or 0.0,
                side=ComponentSide.TOP if comp.layer == "Top" else ComponentSide.BOTTOM,
                layer=comp.layer,
                manufacturer=None,
                mpn=comp.mpn,
                height=None  # Would need 3D data
            )
            components.append(canonical_comp)
        
        # Convert nets
        nets = []
        for net in parsed.nets:
            # Classify net
            net_class = self._classify_net(net.name, net.is_power, net.is_ground)
            
            # Detect voltage
            voltage = self._extract_voltage(net.name)
            
            # Check if differential
            is_diff, pair_name, is_pos = self._detect_differential(net.name)
            
            canonical_net = Net(
                name=net.name,
                net_class=net_class,
                is_power=net.is_power,
                is_ground=net.is_ground,
                is_high_voltage=net.is_mains or (voltage and voltage > 48),
                voltage=voltage,
                is_differential=is_diff,
                pair_name=pair_name,
                is_positive=is_pos,
                clearance=net.min_clearance
            )
            nets.append(canonical_net)
        
        # Convert tracks
        tracks = []
        for idx, track in enumerate(parsed.tracks):
            canonical_track = Track(
                id=f"track_{idx}",
                net=track.net_name,
                layer=track.layer,
                start=Point(track.x1, track.y1) if track.x1 is not None else None,
                end=Point(track.x2, track.y2) if track.x2 is not None else None,
                width=track.width
            )
            tracks.append(canonical_track)
        
        # Convert vias
        vias = []
        for idx, via in enumerate(parsed.vias):
            canonical_via = Via(
                id=f"via_{idx}",
                net=via.net_name,
                position=Point(via.x, via.y) if via.x is not None else None,
                size=via.diameter,
                drill=via.drill,
                start_layer=via.start_layer,
                end_layer=via.end_layer,
                is_through=(via.start_layer == "F.Cu" and via.end_layer == "B.Cu") if via.start_layer and via.end_layer else True
            )
            vias.append(canonical_via)
        
        # Convert zones
        zones = []
        for idx, zone in enumerate(parsed.zones):
            # Convert outline points to Point objects
            points = [Point(x, y) for x, y in zone.outline_points]
            polygon = Polygon(points=points) if points else None
            
            canonical_zone = Zone(
                id=f"zone_{idx}",
                net=zone.net_name,
                layer=zone.layer,
                polygon=polygon
            )
            zones.append(canonical_zone)
        
        # Create board
        board = Board(
            id=board_id,
            name=board_name,
            units=Units.MM,
            outline=outline,
            stackup=stackup,
            components=components,
            nets=nets,
            tracks=tracks,
            vias=vias,
            zones=zones,
            ecad_meta={
                "tool_family": tool_family,
                "files_found": parsed.files_found,
                "raw_data": parsed.raw_data
            }
        )
        
        logger.info(f"Converted to canonical: {len(tracks)} tracks, {len(vias)} vias, {len(zones)} zones")
        return board
    
    def _create_stackup(self, board_info) -> Stackup:
        """Create stackup from board info"""
        layers = []
        
        # Create simple stackup based on layer count
        layer_count = board_info.layer_count
        
        if layer_count == 2:
            layers = [
                Layer("F.Cu", "Top Copper", LayerType.SIGNAL, 0, is_signal=True),
                Layer("B.Cu", "Bottom Copper", LayerType.SIGNAL, 1, is_signal=True)
            ]
        elif layer_count == 4:
            layers = [
                Layer("F.Cu", "Top Copper", LayerType.SIGNAL, 0, is_signal=True),
                Layer("In1.Cu", "Inner1 (GND)", LayerType.POWER, 1, is_plane=True),
                Layer("In2.Cu", "Inner2 (Power)", LayerType.POWER, 2, is_plane=True),
                Layer("B.Cu", "Bottom Copper", LayerType.SIGNAL, 3, is_signal=True)
            ]
        elif layer_count >= 6:
            layers = [
                Layer("F.Cu", "Top Copper", LayerType.SIGNAL, 0, is_signal=True),
                Layer("In1.Cu", "Inner1 (GND)", LayerType.POWER, 1, is_plane=True),
                Layer("In2.Cu", "Inner2 (Signal)", LayerType.SIGNAL, 2, is_signal=True),
                Layer("In3.Cu", "Inner3 (Signal)", LayerType.SIGNAL, 3, is_signal=True),
                Layer("In4.Cu", "Inner4 (Power)", LayerType.POWER, 4, is_plane=True),
                Layer("B.Cu", "Bottom Copper", LayerType.SIGNAL, 5, is_signal=True)
            ]
        
        return Stackup(
            layers=layers,
            total_thickness=1.6  # Standard thickness
        )
    
    def _create_outline(self, board_info) -> BoardOutline:
        """Create simple rectangular outline"""
        points = [
            Point(0, 0),
            Point(board_info.size_x, 0),
            Point(board_info.size_x, board_info.size_y),
            Point(0, board_info.size_y)
        ]
        polygon = Polygon(points=points)
        
        return BoardOutline(
            polygon=polygon,
            thickness=1.6
        )
    
    def _classify_net(self, name: str, is_power: bool, is_ground: bool) -> NetClass:
        """Classify net type"""
        if is_ground:
            return NetClass.GROUND
        if is_power:
            return NetClass.POWER
        
        # Check for differential
        name_lower = name.lower()
        if any(x in name_lower for x in ['_p', '_n', 'diff', 'usb_d', 'pcie']):
            return NetClass.DIFFERENTIAL
        
        # Check for high-speed
        if any(x in name_lower for x in ['clk', 'ddr', 'usb', 'eth', 'pcie', 'hdmi']):
            return NetClass.HIGH_SPEED
        
        return NetClass.SIGNAL
    
    def _extract_voltage(self, net_name: str) -> Optional[float]:
        """Extract voltage from net name"""
        import re
        
        # Common patterns: +3V3, 3.3V, +5V, 12V, etc.
        patterns = [
            r'\+?(\d+)v(\d+)',  # 3v3, +3v3
            r'\+?(\d+)\.(\d+)v',  # 3.3v, +3.3v
            r'\+?(\d+)v',  # 5v, +5v, 12v
        ]
        
        name_lower = net_name.lower()
        
        for pattern in patterns:
            match = re.search(pattern, name_lower)
            if match:
                if len(match.groups()) == 2:
                    return float(f"{match.group(1)}.{match.group(2)}")
                else:
                    return float(match.group(1))
        
        # Check for mains voltage
        if any(x in name_lower for x in ['230v', '240v', '120v', 'mains', 'ac_']):
            return 230.0  # Assume 230VAC
        
        return None
    
    def _detect_differential(self, net_name: str) -> tuple[bool, Optional[str], Optional[bool]]:
        """
        Detect if net is part of differential pair
        
        Returns:
            (is_differential, pair_name, is_positive)
        """
        name_lower = net_name.lower()
        
        # Check for _P / _N suffix
        if name_lower.endswith('_p'):
            base_name = net_name[:-2]
            return True, base_name, True
        elif name_lower.endswith('_n'):
            base_name = net_name[:-2]
            return True, base_name, False
        
        # Check for + / - suffix
        if name_lower.endswith('+'):
            base_name = net_name[:-1]
            return True, base_name, True
        elif name_lower.endswith('-'):
            base_name = net_name[:-1]
            return True, base_name, False
        
        # Check for USB_DP / USB_DM pattern
        if 'usb_dp' in name_lower or 'usb_d+' in name_lower:
            return True, 'USB_D', True
        elif 'usb_dm' in name_lower or 'usb_d-' in name_lower:
            return True, 'USB_D', False
        
        return False, None, None
