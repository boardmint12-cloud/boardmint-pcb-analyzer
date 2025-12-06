"""
Cadence Parser
Parses Cadence OrCAD and Allegro files

Cadence formats:
- OrCAD Capture: .DSN (Design), .OPJ (Project)
- Allegro PCB: .BRD (Board), .MCM (Multi-chip module)
- ASCII exports: .ALG, .ASC, various text exports

IMPORTANT: Native Cadence binary formats are proprietary.
This parser handles:
1. ASCII/text exports from Cadence tools
2. Placement files (*.txt, *.csv)
3. Netlist exports
4. Basic binary header detection

For full support, recommend users export to:
- IPC-2581 (File > Export > IPC-2581)
- ODB++ (File > Export > ODB++)
- Gerber + IPC-D-356 netlist
"""

import re
import struct
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .base_parser import (
    BaseParser, ParsedPCBData, BoardInfo,
    Component, Net, Track, Via, Zone
)

logger = logging.getLogger(__name__)


@dataclass
class CadenceFileInfo:
    """Information about a Cadence file"""
    file_type: str  # DSN, BRD, OPJ, ASC, etc.
    version: Optional[str] = None
    is_binary: bool = True
    tool: str = "unknown"  # capture, allegro, etc.


class CadenceParser(BaseParser):
    """
    Parser for Cadence OrCAD/Allegro files
    
    Supports:
    - OrCAD Capture .DSN schematic (partial ASCII parsing)
    - Allegro .BRD board files (header detection + ASCII fallback)
    - ASCII exports (.alg, .asc, placement files)
    - Netlist files
    
    Limitations:
    - Full binary .BRD parsing requires reverse-engineering
    - Recommend ODB++/IPC-2581 export for complete data
    """
    
    # Cadence binary file signatures
    BINARY_SIGNATURES = {
        b'ALMG': ('allegro_brd', 'Allegro Board'),
        b'CDSM': ('allegro_mcm', 'Allegro MCM'),
        b'CPBO': ('capture_dsn', 'OrCAD Capture Design'),
        b'\x00\x00\x00\x16': ('orcad_dsn', 'OrCAD DSN'),
    }
    
    def __init__(self):
        """Initialize parser"""
        self.units = 'mil'
        self.scale = 0.0254  # Convert mils to mm
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse Cadence project
        
        Args:
            project_path: Path to directory or Cadence file
            
        Returns:
            ParsedPCBData with normalized data
        """
        project_path = Path(project_path)
        
        # Find Cadence files
        if project_path.is_file():
            return self._parse_file(project_path)
        
        # Directory - find all Cadence files
        files_found = {
            'brd': [],
            'dsn': [],
            'opj': [],
            'asc': [],
            'alg': [],
            'netlist': [],
            'placement': [],
        }
        
        for f in project_path.rglob('*'):
            if not f.is_file():
                continue
            
            ext = f.suffix.lower()
            name = f.name.lower()
            
            if ext == '.brd':
                files_found['brd'].append(f)
            elif ext == '.dsn':
                files_found['dsn'].append(f)
            elif ext == '.opj':
                files_found['opj'].append(f)
            elif ext in ('.asc', '.alg'):
                files_found['asc'].append(f)
            elif 'netlist' in name or ext in ('.net', '.als'):
                files_found['netlist'].append(f)
            elif 'place' in name or 'component' in name:
                files_found['placement'].append(f)
        
        logger.info(f"Found Cadence files: {[(k, len(v)) for k, v in files_found.items() if v]}")
        
        # Parse in priority order
        result = self._empty_result()
        warnings = []
        
        # Try board files first
        if files_found['brd']:
            brd_result = self._parse_brd(files_found['brd'][0])
            result = self._merge_results(result, brd_result)
            if not brd_result.components:
                warnings.append(
                    "⚠️ Cadence .BRD binary format has limited support. "
                    "For complete analysis, export to ODB++ or IPC-2581."
                )
        
        # Parse DSN schematic
        if files_found['dsn']:
            dsn_result = self._parse_dsn(files_found['dsn'][0])
            result = self._merge_results(result, dsn_result)
        
        # Parse ASCII exports
        for asc_file in files_found['asc'][:3]:
            asc_result = self._parse_ascii_export(asc_file)
            result = self._merge_results(result, asc_result)
        
        # Parse placement files
        for place_file in files_found['placement'][:2]:
            comps = self._parse_placement_file(place_file)
            result.components.extend(comps)
        
        # Parse netlists
        for net_file in files_found['netlist'][:2]:
            nets = self._parse_netlist_file(net_file)
            result.nets.extend(nets)
        
        # Add warnings
        if warnings:
            result.raw_data = result.raw_data or {}
            result.raw_data['warnings'] = warnings
        
        return result
    
    def _parse_file(self, file_path: Path) -> ParsedPCBData:
        """Parse a single Cadence file"""
        ext = file_path.suffix.lower()
        
        if ext == '.brd':
            return self._parse_brd(file_path)
        elif ext == '.dsn':
            return self._parse_dsn(file_path)
        elif ext in ('.asc', '.alg'):
            return self._parse_ascii_export(file_path)
        else:
            return self._empty_result()
    
    def _detect_file_type(self, file_path: Path) -> CadenceFileInfo:
        """Detect Cadence file type from content"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
            
            # Check binary signatures
            for sig, (file_type, tool) in self.BINARY_SIGNATURES.items():
                if header.startswith(sig) or sig in header[:16]:
                    return CadenceFileInfo(
                        file_type=file_type,
                        is_binary=True,
                        tool=tool
                    )
            
            # Check for text content
            try:
                text = header.decode('utf-8', errors='replace')
                if text.strip().startswith('(') or 'DESIGN' in text.upper():
                    return CadenceFileInfo(
                        file_type='ascii',
                        is_binary=False,
                        tool='text_export'
                    )
            except:
                pass
            
            return CadenceFileInfo(file_type='unknown', is_binary=True)
            
        except Exception as e:
            logger.warning(f"File detection failed: {e}")
            return CadenceFileInfo(file_type='unknown', is_binary=True)
    
    def _parse_brd(self, file_path: Path) -> ParsedPCBData:
        """
        Parse Allegro .BRD file
        
        The .BRD format is proprietary binary. We attempt to:
        1. Extract basic info from file structure
        2. Find any embedded text/string data
        3. Recommend export to neutral format
        """
        logger.info(f"Parsing Allegro BRD: {file_path}")
        
        file_info = self._detect_file_type(file_path)
        
        if not file_info.is_binary:
            # It's actually ASCII, parse as such
            return self._parse_ascii_export(file_path)
        
        # Attempt binary extraction
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Extract string table (component references, net names)
            strings = self._extract_strings(content)
            
            # Build components from reference strings
            components = []
            nets = []
            
            ref_pattern = re.compile(r'^[A-Z]{1,3}\d{1,4}$')
            net_pattern = re.compile(r'^[A-Z_][A-Z0-9_]*$')
            
            for s in strings:
                if ref_pattern.match(s) and len(s) <= 6:
                    components.append(Component(
                        reference=s,
                        value='',
                        footprint=''
                    ))
                elif net_pattern.match(s) and len(s) > 2:
                    # Check if it looks like a net
                    if self.detect_power_net(s) or self.detect_ground_net(s) or '_' in s:
                        nets.append(Net(
                            name=s,
                            is_power=self.detect_power_net(s),
                            is_ground=self.detect_ground_net(s),
                            is_mains=self.detect_mains_net(s)
                        ))
            
            # Deduplicate
            components = list({c.reference: c for c in components}.values())
            nets = list({n.name: n for n in nets}.values())
            
            # Try to extract board size from binary
            board_info = self._extract_board_info_binary(content)
            
            logger.info(f"Extracted from BRD: {len(components)} components, {len(nets)} nets")
            
            return ParsedPCBData(
                board_info=board_info,
                components=components[:500],  # Limit
                nets=nets[:200],
                tracks=[],
                vias=[],
                zones=[],
                files_found={'allegro_brd': True},
                raw_data={
                    'parser_note': 'Partial extraction from binary .BRD',
                    'recommendation': 'Export to ODB++ or IPC-2581 for complete data'
                }
            )
            
        except Exception as e:
            logger.error(f"BRD parsing failed: {e}")
            return self._empty_result_with_warning(
                f"Allegro .BRD parsing failed: {e}. "
                "Please export to ODB++ (File > Export > ODB++) or IPC-2581."
            )
    
    def _extract_strings(self, content: bytes, min_length: int = 2) -> List[str]:
        """Extract printable strings from binary content"""
        strings = []
        current = []
        
        for byte in content:
            if 32 <= byte <= 126:  # Printable ASCII
                current.append(chr(byte))
            else:
                if len(current) >= min_length:
                    s = ''.join(current)
                    if s.replace('_', '').replace('-', '').isalnum():
                        strings.append(s)
                current = []
        
        # Don't forget last string
        if len(current) >= min_length:
            strings.append(''.join(current))
        
        return list(set(strings))[:1000]  # Limit and dedupe
    
    def _extract_board_info_binary(self, content: bytes) -> BoardInfo:
        """Attempt to extract board dimensions from binary"""
        # Default values
        size_x, size_y = 100.0, 100.0
        layer_count = 4
        
        # Look for common dimension patterns
        # Allegro stores dimensions as 32-bit integers in mils
        try:
            # Search for dimension-like values (1000-50000 mils = 1-50 inches)
            for i in range(0, min(len(content) - 8, 10000), 4):
                val1 = struct.unpack_from('<I', content, i)[0]
                val2 = struct.unpack_from('<I', content, i + 4)[0]
                
                if 1000 < val1 < 50000 and 1000 < val2 < 50000:
                    # Could be board dimensions
                    size_x = val1 * 0.0254  # mils to mm
                    size_y = val2 * 0.0254
                    break
        except:
            pass
        
        return BoardInfo(
            size_x=size_x,
            size_y=size_y,
            layer_count=layer_count
        )
    
    def _parse_dsn(self, file_path: Path) -> ParsedPCBData:
        """
        Parse OrCAD .DSN schematic file
        
        DSN files are binary but often have an ASCII header section
        """
        logger.info(f"Parsing OrCAD DSN: {file_path}")
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Extract strings for component references
            strings = self._extract_strings(content, min_length=2)
            
            components = []
            nets = []
            
            # Pattern matching for typical schematic references
            ref_pattern = re.compile(r'^[RCLUJQDKFXSTMZP]\d{1,3}$')
            
            for s in strings:
                if ref_pattern.match(s):
                    components.append(Component(
                        reference=s,
                        value='',
                        footprint=''
                    ))
            
            # Deduplicate
            components = list({c.reference: c for c in components}.values())
            
            logger.info(f"Extracted from DSN: {len(components)} components")
            
            return ParsedPCBData(
                board_info=BoardInfo(size_x=0, size_y=0, layer_count=2),
                components=components[:200],
                nets=[],
                tracks=[],
                vias=[],
                zones=[],
                files_found={'orcad_dsn': True}
            )
            
        except Exception as e:
            logger.error(f"DSN parsing failed: {e}")
            return self._empty_result()
    
    def _parse_ascii_export(self, file_path: Path) -> ParsedPCBData:
        """Parse ASCII export files from Cadence tools"""
        logger.info(f"Parsing ASCII export: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            components = []
            nets = []
            tracks = []
            
            # Parse based on content type
            if 'COMPONENT' in content.upper() or 'COMP_DEF' in content.upper():
                components = self._parse_component_section(content)
            
            if 'NET' in content.upper() or 'NETNAME' in content.upper():
                nets = self._parse_net_section(content)
            
            if 'LINE' in content.upper() or 'PATH' in content.upper():
                tracks = self._parse_track_section(content)
            
            return ParsedPCBData(
                board_info=BoardInfo(size_x=0, size_y=0, layer_count=2),
                components=components,
                nets=nets,
                tracks=tracks,
                vias=[],
                zones=[],
                files_found={'cadence_ascii': True}
            )
            
        except Exception as e:
            logger.error(f"ASCII export parsing failed: {e}")
            return self._empty_result()
    
    def _parse_component_section(self, content: str) -> List[Component]:
        """Parse component definitions from ASCII export"""
        components = []
        
        # Pattern: COMPONENT <ref> <x> <y> <rotation> <side> <footprint>
        comp_pattern = re.compile(
            r'COMPONENT\s+(\w+)\s+([\d.-]+)\s+([\d.-]+)\s*([\d.-]*)\s*(\w*)\s*(\S*)',
            re.IGNORECASE
        )
        
        for match in comp_pattern.finditer(content):
            ref = match.group(1)
            try:
                x = float(match.group(2)) * self.scale
                y = float(match.group(3)) * self.scale
                rotation = float(match.group(4)) if match.group(4) else 0
            except ValueError:
                x, y, rotation = 0, 0, 0
            
            side = match.group(5).upper() if match.group(5) else 'TOP'
            footprint = match.group(6) if match.group(6) else ''
            
            components.append(Component(
                reference=ref,
                value='',
                footprint=footprint,
                x=x,
                y=y,
                rotation=rotation,
                layer='F.Cu' if side != 'BOTTOM' else 'B.Cu'
            ))
        
        return components
    
    def _parse_net_section(self, content: str) -> List[Net]:
        """Parse net definitions"""
        nets = []
        
        # Pattern: NET <name> or NETNAME <name>
        net_pattern = re.compile(r'(?:NET|NETNAME)\s+["\']?(\S+)["\']?', re.IGNORECASE)
        
        seen = set()
        for match in net_pattern.finditer(content):
            name = match.group(1).strip('"\'')
            if name and name not in seen:
                seen.add(name)
                nets.append(Net(
                    name=name,
                    is_power=self.detect_power_net(name),
                    is_ground=self.detect_ground_net(name),
                    is_mains=self.detect_mains_net(name)
                ))
        
        return nets
    
    def _parse_track_section(self, content: str) -> List[Track]:
        """Parse track/trace definitions"""
        tracks = []
        
        # Pattern: LINE <layer> <width> <x1> <y1> <x2> <y2>
        line_pattern = re.compile(
            r'LINE\s+(\w+)\s+([\d.]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)',
            re.IGNORECASE
        )
        
        for match in line_pattern.finditer(content):
            try:
                tracks.append(Track(
                    layer=match.group(1),
                    width=float(match.group(2)) * self.scale,
                    x1=float(match.group(3)) * self.scale,
                    y1=float(match.group(4)) * self.scale,
                    x2=float(match.group(5)) * self.scale,
                    y2=float(match.group(6)) * self.scale
                ))
            except ValueError:
                continue
        
        return tracks[:5000]  # Limit
    
    def _parse_placement_file(self, file_path: Path) -> List[Component]:
        """Parse placement/centroid file"""
        components = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Try CSV format
            for line in content.split('\n'):
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    ref = parts[0].strip()
                    if ref and ref[0].isalpha():
                        try:
                            components.append(Component(
                                reference=ref,
                                value=parts[1].strip() if len(parts) > 1 else '',
                                footprint=parts[2].strip() if len(parts) > 2 else '',
                                x=float(parts[3]) * self.scale if len(parts) > 3 else 0,
                                y=float(parts[4]) * self.scale if len(parts) > 4 else 0
                            ))
                        except (ValueError, IndexError):
                            continue
            
        except Exception as e:
            logger.warning(f"Placement file parsing failed: {e}")
        
        return components
    
    def _parse_netlist_file(self, file_path: Path) -> List[Net]:
        """Parse netlist file"""
        nets = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Extract net names
            seen = set()
            for match in re.finditer(r'NET\s+["\']?(\w+)["\']?', content, re.IGNORECASE):
                name = match.group(1)
                if name and name not in seen:
                    seen.add(name)
                    nets.append(Net(
                        name=name,
                        is_power=self.detect_power_net(name),
                        is_ground=self.detect_ground_net(name),
                        is_mains=self.detect_mains_net(name)
                    ))
            
        except Exception as e:
            logger.warning(f"Netlist parsing failed: {e}")
        
        return nets
    
    def _merge_results(self, base: ParsedPCBData, new: ParsedPCBData) -> ParsedPCBData:
        """Merge two results"""
        # Add components
        base_refs = {c.reference for c in base.components}
        for comp in new.components:
            if comp.reference not in base_refs:
                base.components.append(comp)
                base_refs.add(comp.reference)
        
        # Add nets
        base_nets = {n.name for n in base.nets}
        for net in new.nets:
            if net.name not in base_nets:
                base.nets.append(net)
                base_nets.add(net.name)
        
        # Add tracks
        base.tracks.extend(new.tracks)
        base.vias.extend(new.vias)
        
        # Update board info if needed
        if base.board_info.size_x == 0 and new.board_info.size_x > 0:
            base.board_info = new.board_info
        
        return base
    
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
        """Return empty result with warning"""
        result = self._empty_result()
        result.raw_data = {'warning': warning}
        return result


def parse_cadence(path: str) -> ParsedPCBData:
    """Convenience function to parse Cadence files"""
    parser = CadenceParser()
    return parser.parse(path)
