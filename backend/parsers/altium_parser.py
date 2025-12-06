"""
Altium Parser
Parses Altium Designer .PcbDoc and .SchDoc files

Altium uses OLE Compound Document format (like old MS Office files).
This parser uses reverse-engineered knowledge to extract data.

LIMITATIONS:
- Not all Altium features are supported
- Newer Altium versions may have format changes
- For best results, export to IPC-2581 or ODB++
"""

import logging
import struct
import zlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, BinaryIO
from dataclasses import dataclass, field
from io import BytesIO

from .base_parser import (
    BaseParser, ParsedPCBData, BoardInfo,
    Component, Net, Track, Via, Zone
)

logger = logging.getLogger(__name__)

# Try to import olefile for OLE compound document parsing
try:
    import olefile
    HAS_OLEFILE = True
except ImportError:
    HAS_OLEFILE = False
    logger.warning("olefile not installed - Altium native parsing limited")


@dataclass
class AltiumRecord:
    """Parsed Altium record"""
    record_type: int
    data: Dict[str, Any]
    raw: bytes


class AltiumParser(BaseParser):
    """
    Parser for Altium Designer files (.PcbDoc, .SchDoc)
    
    Altium file structure:
    - OLE Compound Document container
    - Contains multiple streams (FileHeader, Board, Components, etc.)
    - Data is stored in binary records with key-value pairs
    
    Streams in .PcbDoc:
    - FileHeader: Version info
    - Board6: Board data
    - Components6: Placed components
    - Nets6: Net definitions
    - Tracks6: Track segments
    - Arcs6: Arc segments  
    - Vias6: Via data
    - Polygons6: Copper pours
    - Rules6: Design rules
    """
    
    # Altium record types (partial list)
    RECORD_TYPES = {
        1: 'Arc',
        2: 'Pad',
        3: 'Via',
        4: 'Track',
        5: 'Text',
        6: 'Fill',
        7: 'Connection',
        8: 'Net',
        11: 'Component',
        12: 'Polygon',
        13: 'Region',
        14: 'ComponentBody',
        16: 'Dimension',
        17: 'Coordinate',
        28: 'Class',
    }
    
    # Layer mappings
    LAYER_MAP = {
        1: 'F.Cu',
        2: 'In1.Cu',
        3: 'In2.Cu',
        4: 'In3.Cu',
        32: 'B.Cu',
        33: 'F.SilkS',
        34: 'B.SilkS',
        35: 'F.Paste',
        36: 'B.Paste',
        37: 'F.Mask',
        38: 'B.Mask',
    }
    
    def __init__(self):
        """Initialize parser"""
        self.units = 'mil'  # Altium uses mils internally
        self.scale = 0.0254  # Convert to mm
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse Altium project
        
        Args:
            project_path: Path to directory or .PcbDoc file
            
        Returns:
            ParsedPCBData with normalized data
        """
        if not HAS_OLEFILE:
            logger.error("olefile not installed - cannot parse Altium files")
            return self._empty_result_with_warning(
                "Install 'olefile' package for Altium support, or export to IPC-2581/ODB++"
            )
        
        project_path = Path(project_path)
        
        # Find PcbDoc file
        if project_path.is_file() and project_path.suffix.lower() == '.pcbdoc':
            pcb_file = project_path
        else:
            pcb_files = list(project_path.rglob('*.PcbDoc')) + list(project_path.rglob('*.pcbdoc'))
            pcb_file = pcb_files[0] if pcb_files else None
        
        if not pcb_file or not pcb_file.exists():
            logger.warning("No Altium .PcbDoc file found")
            return self._empty_result()
        
        logger.info(f"Parsing Altium PCB: {pcb_file}")
        
        try:
            return self._parse_pcbdoc(pcb_file)
        except Exception as e:
            logger.error(f"Altium parsing failed: {e}", exc_info=True)
            return self._empty_result_with_warning(
                f"Altium parsing error: {e}. Consider exporting to IPC-2581 or Gerber."
            )
    
    def _parse_pcbdoc(self, pcb_file: Path) -> ParsedPCBData:
        """Parse .PcbDoc file"""
        ole = olefile.OleFileIO(str(pcb_file))
        
        try:
            # List available streams
            streams = ole.listdir()
            logger.debug(f"OLE streams: {streams}")
            
            # Parse board info
            board_info = self._parse_board_stream(ole)
            
            # Parse components
            components = self._parse_components_stream(ole)
            
            # Parse nets
            nets = self._parse_nets_stream(ole)
            
            # Parse tracks
            tracks = self._parse_tracks_stream(ole)
            
            # Parse vias
            vias = self._parse_vias_stream(ole)
            
            # Parse polygons
            zones = self._parse_polygons_stream(ole)
            
            return ParsedPCBData(
                board_info=board_info,
                components=components,
                nets=nets,
                tracks=tracks,
                vias=vias,
                zones=zones,
                files_found={'altium_pcbdoc': True},
                raw_data={'parser_note': 'Parsed from Altium native format (partial support)'}
            )
            
        finally:
            ole.close()
    
    def _get_stream(self, ole: 'olefile.OleFileIO', stream_name: str) -> Optional[bytes]:
        """Get stream data from OLE file"""
        # Try different stream path formats
        paths_to_try = [
            [stream_name],
            ['Board6', stream_name],
            ['Data', stream_name],
        ]
        
        for path in paths_to_try:
            try:
                if ole.exists(path):
                    return ole.openstream(path).read()
            except:
                continue
        
        # Try to find by name
        for stream_path in ole.listdir():
            if stream_name.lower() in [s.lower() for s in stream_path]:
                try:
                    return ole.openstream(stream_path).read()
                except:
                    continue
        
        return None
    
    def _parse_board_stream(self, ole: 'olefile.OleFileIO') -> BoardInfo:
        """Parse board information"""
        # Default values
        size_x, size_y = 100.0, 100.0
        layer_count = 2
        
        # Try to get board data
        board_data = self._get_stream(ole, 'Board6')
        
        if board_data:
            try:
                records = self._parse_binary_records(board_data)
                
                for record in records:
                    data = record.data
                    
                    # Look for board dimensions
                    if 'SHEETWIDTH' in data:
                        size_x = float(data['SHEETWIDTH']) * self.scale
                    if 'SHEETHEIGHT' in data:
                        size_y = float(data['SHEETHEIGHT']) * self.scale
                    
                    # Layer count from LAYERMASTERSTACK_V8STACK
                    if 'LAYERV8_0NAME' in data:
                        # Count layers
                        for i in range(100):
                            if f'LAYERV8_{i}NAME' not in data:
                                layer_count = max(2, i // 2)  # Rough estimate
                                break
                                
            except Exception as e:
                logger.warning(f"Board stream parse error: {e}")
        
        return BoardInfo(
            size_x=size_x,
            size_y=size_y,
            layer_count=layer_count
        )
    
    def _parse_components_stream(self, ole: 'olefile.OleFileIO') -> List[Component]:
        """Parse component placements"""
        components = []
        
        comp_data = self._get_stream(ole, 'Components6')
        
        if not comp_data:
            return components
        
        try:
            records = self._parse_binary_records(comp_data)
            
            for record in records:
                data = record.data
                
                # Extract component info
                ref = data.get('DESIGNITEMID', data.get('NAME', ''))
                if not ref:
                    continue
                
                # Position
                x = float(data.get('X', 0)) * self.scale
                y = float(data.get('Y', 0)) * self.scale
                rotation = float(data.get('ROTATION', 0))
                
                # Layer (0 = top, 1 = bottom typically)
                layer_num = int(data.get('LAYER', 1))
                layer = self.LAYER_MAP.get(layer_num, 'F.Cu')
                
                # Footprint
                footprint = data.get('PATTERN', data.get('SOURCELIBRARYNAME', ''))
                
                # Value (often in comment)
                value = data.get('COMMENT', data.get('SOURCEDESIGNATOR', ''))
                
                components.append(Component(
                    reference=ref,
                    value=value,
                    footprint=footprint,
                    x=x,
                    y=y,
                    rotation=rotation,
                    layer=layer
                ))
                
        except Exception as e:
            logger.warning(f"Components stream parse error: {e}")
        
        return components
    
    def _parse_nets_stream(self, ole: 'olefile.OleFileIO') -> List[Net]:
        """Parse net definitions"""
        nets = []
        
        net_data = self._get_stream(ole, 'Nets6')
        
        if not net_data:
            return nets
        
        try:
            records = self._parse_binary_records(net_data)
            
            for record in records:
                data = record.data
                
                net_name = data.get('NAME', '')
                if not net_name:
                    continue
                
                nets.append(Net(
                    name=net_name,
                    is_power=self.detect_power_net(net_name),
                    is_ground=self.detect_ground_net(net_name),
                    is_mains=self.detect_mains_net(net_name)
                ))
                
        except Exception as e:
            logger.warning(f"Nets stream parse error: {e}")
        
        return nets
    
    def _parse_tracks_stream(self, ole: 'olefile.OleFileIO') -> List[Track]:
        """Parse track segments"""
        tracks = []
        
        track_data = self._get_stream(ole, 'Tracks6')
        
        if not track_data:
            return tracks
        
        try:
            records = self._parse_binary_records(track_data)
            
            for record in records:
                data = record.data
                
                # Get coordinates
                x1 = float(data.get('X1', 0)) * self.scale
                y1 = float(data.get('Y1', 0)) * self.scale
                x2 = float(data.get('X2', 0)) * self.scale
                y2 = float(data.get('Y2', 0)) * self.scale
                width = float(data.get('WIDTH', 0.254 / self.scale)) * self.scale
                
                # Layer
                layer_num = int(data.get('LAYER', 1))
                layer = self.LAYER_MAP.get(layer_num, f'Layer{layer_num}')
                
                # Net
                net_name = data.get('NET', '')
                
                tracks.append(Track(
                    net_name=net_name,
                    layer=layer,
                    width=width,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2
                ))
                
        except Exception as e:
            logger.warning(f"Tracks stream parse error: {e}")
        
        return tracks
    
    def _parse_vias_stream(self, ole: 'olefile.OleFileIO') -> List[Via]:
        """Parse vias"""
        vias = []
        
        via_data = self._get_stream(ole, 'Vias6')
        
        if not via_data:
            return vias
        
        try:
            records = self._parse_binary_records(via_data)
            
            for record in records:
                data = record.data
                
                x = float(data.get('X', 0)) * self.scale
                y = float(data.get('Y', 0)) * self.scale
                diameter = float(data.get('DIAMETER', 0.6 / self.scale)) * self.scale
                drill = float(data.get('HOLESIZE', 0.3 / self.scale)) * self.scale
                
                net_name = data.get('NET', '')
                
                vias.append(Via(
                    net_name=net_name,
                    x=x,
                    y=y,
                    diameter=diameter,
                    drill=drill,
                    start_layer='F.Cu',
                    end_layer='B.Cu'
                ))
                
        except Exception as e:
            logger.warning(f"Vias stream parse error: {e}")
        
        return vias
    
    def _parse_polygons_stream(self, ole: 'olefile.OleFileIO') -> List[Zone]:
        """Parse copper pours/polygons"""
        zones = []
        
        poly_data = self._get_stream(ole, 'Polygons6')
        
        if not poly_data:
            return zones
        
        try:
            records = self._parse_binary_records(poly_data)
            
            for record in records:
                data = record.data
                
                net_name = data.get('NET', '')
                layer_num = int(data.get('LAYER', 1))
                layer = self.LAYER_MAP.get(layer_num, f'Layer{layer_num}')
                
                # Polygon outline (simplified - actual parsing is complex)
                zones.append(Zone(
                    net_name=net_name,
                    layer=layer,
                    outline_points=[]  # Would need detailed polygon parsing
                ))
                
        except Exception as e:
            logger.warning(f"Polygons stream parse error: {e}")
        
        return zones
    
    def _parse_binary_records(self, data: bytes) -> List[AltiumRecord]:
        """
        Parse Altium binary record format
        
        Record format:
        - First few bytes may be header/count
        - Records are key-value pairs separated by |
        - Keys are uppercase, values follow =
        - Records end with specific terminator
        """
        records = []
        
        # Try to decompress if compressed
        try:
            decompressed = zlib.decompress(data)
            data = decompressed
        except:
            pass
        
        # Convert to string and split by record separator
        try:
            text = data.decode('utf-8', errors='replace')
        except:
            text = data.decode('latin-1', errors='replace')
        
        # Common record separators in Altium
        separators = ['\x00', '|RECORD=']
        
        for sep in separators:
            if sep in text:
                parts = text.split(sep)
                break
        else:
            parts = [text]
        
        for part in parts:
            if not part.strip():
                continue
            
            record_data = {}
            
            # Parse key=value pairs
            # Split by | but handle embedded |
            pairs = part.split('|')
            
            for pair in pairs:
                if '=' in pair:
                    key, _, value = pair.partition('=')
                    key = key.strip().upper()
                    value = value.strip()
                    
                    if key:
                        record_data[key] = value
            
            if record_data:
                record_type = int(record_data.get('RECORD', 0))
                records.append(AltiumRecord(
                    record_type=record_type,
                    data=record_data,
                    raw=part.encode('latin-1', errors='replace')
                ))
        
        return records
    
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
    
    def _empty_result_with_warning(self, warning: str) -> ParsedPCBData:
        """Return empty result with warning in raw_data"""
        result = self._empty_result()
        result.raw_data = {'warning': warning}
        return result


def parse_altium_file(file_path: str) -> ParsedPCBData:
    """Convenience function to parse Altium file"""
    parser = AltiumParser()
    return parser.parse(file_path)
