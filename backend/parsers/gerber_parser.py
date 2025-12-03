"""
Gerber/Generic PCB parser
Parses Gerber files, drill files, BOM, and centroid/position files
"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .base_parser import BaseParser, ParsedPCBData, BoardInfo, Net, Component

logger = logging.getLogger(__name__)


class GerberParser(BaseParser):
    """Parser for Gerber files and generic PCB projects"""
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse Gerber project
        
        Args:
            project_path: Path to extracted project directory with Gerbers
            
        Returns:
            ParsedPCBData with normalized data
        """
        project_dir = Path(project_path)
        
        # Find files
        gerber_files = self._find_gerber_files(project_dir)
        drill_files = list(project_dir.glob('*.drl')) + list(project_dir.glob('*.txt'))
        bom_files = list(project_dir.glob('*bom*.csv')) + list(project_dir.glob('*.xlsx')) + list(project_dir.glob('*.xls'))
        pos_files = list(project_dir.glob('*.csv')) + list(project_dir.glob('*.xy')) + list(project_dir.glob('*.pos'))
        netlist_files = list(project_dir.glob('*.ipc')) + list(project_dir.glob('*.d356')) + list(project_dir.glob('*.net'))
        
        files_found = {
            'gerbers': len(gerber_files) > 0,
            'drill': len(drill_files) > 0,
            'bom': len(bom_files) > 0,
            'position': len(pos_files) > 0
        }
        
        logger.info(f"Found files - Gerbers: {len(gerber_files)}, Drill: {len(drill_files)}, BOM: {len(bom_files)}, Pos: {len(pos_files)}")
        
        # Parse board info from gerbers
        board_info = self._parse_board_info(gerber_files)
        
        # Parse BOM
        components = []
        if bom_files:
            logger.info(f"Parsing BOM: {bom_files[0]}")
            components = self._parse_bom(bom_files[0])
        
        # Enhance with position data
        if pos_files:
            logger.info(f"Parsing position file: {pos_files[0]}")
            self._enhance_with_positions(components, pos_files[0])
        
        # Parse netlist if available (IPC-D-356 format)
        nets = []
        if netlist_files:
            logger.info(f"Parsing IPC-D-356 netlist: {netlist_files[0]}")
            nets = self._parse_ipc_netlist(netlist_files[0], components)
        else:
            # Extract nets from component list (limited without netlist)
            nets = self._extract_nets_from_components(components)
        
        return ParsedPCBData(
            board_info=board_info,
            nets=nets,
            components=components,
            files_found=files_found,
            raw_data={'gerber_count': len(gerber_files)}
        )
    
    def _find_gerber_files(self, directory: Path) -> List[Path]:
        """Find Gerber files in directory"""
        gerber_extensions = ['.gbr', '.pho', '.art', '.ger', '.gko', '.gtl', '.gbl', '.gts', '.gbs']
        gerber_files = []
        
        for ext in gerber_extensions:
            gerber_files.extend(directory.glob(f'*{ext}'))
        
        # Also check for files without extension but with gerber-like names
        gerber_patterns = ['*copper*', '*silk*', '*mask*', '*paste*', '*outline*']
        for pattern in gerber_patterns:
            gerber_files.extend(directory.glob(pattern))
        
        return list(set(gerber_files))  # Remove duplicates
    
    def _parse_board_info(self, gerber_files: List[Path]) -> BoardInfo:
        """Parse board information from Gerber files"""
        # Try to find outline/edge file
        outline_file = None
        for gf in gerber_files:
            name_lower = gf.name.lower()
            if any(kw in name_lower for kw in ['outline', 'edge', 'gko', 'boardoutline']):
                outline_file = gf
                break
        
        size_x, size_y = 100.0, 100.0  # defaults
        
        if outline_file:
            try:
                # Simple parsing of Gerber outline for dimensions
                with open(outline_file, 'r') as f:
                    content = f.read()
                
                # Extract coordinates (very simplified)
                coords = re.findall(r'X([-\d]+)Y([-\d]+)', content)
                if coords:
                    xs = [int(x) / 10000 for x, y in coords]  # Convert from Gerber units
                    ys = [int(y) / 10000 for x, y in coords]
                    
                    if xs and ys:
                        size_x = max(xs) - min(xs)
                        size_y = max(ys) - min(ys)
            
            except Exception as e:
                logger.warning(f"Failed to parse outline file: {e}")
        
        # Estimate layer count from file names
        layer_count = 2  # default
        layer_keywords = ['top', 'bottom', 'inner', 'l1', 'l2', 'l3', 'l4']
        found_layers = set()
        
        for gf in gerber_files:
            name_lower = gf.name.lower()
            for kw in layer_keywords:
                if kw in name_lower:
                    found_layers.add(kw)
        
        if 'inner' in found_layers or any(f'l{i}' in found_layers for i in range(3, 10)):
            layer_count = 4  # At least 4 layers
        
        return BoardInfo(
            size_x=round(size_x, 2),
            size_y=round(size_y, 2),
            layer_count=layer_count
        )
    
    def _parse_bom(self, bom_file: Path) -> List[Component]:
        """Parse BOM file"""
        components = []
        
        try:
            import csv
            
            # Handle both CSV and text-based BOMs
            with open(bom_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter
                first_line = f.readline()
                f.seek(0)
                
                delimiter = ',' if ',' in first_line else '\t'
                
                reader = csv.DictReader(f, delimiter=delimiter)
                
                for row in reader:
                    # Try different column name variations
                    ref = (row.get('Reference') or row.get('Designator') or 
                           row.get('Ref') or row.get('RefDes') or '')
                    
                    value = (row.get('Value') or row.get('Val') or 
                            row.get('Comment') or '')
                    
                    footprint = (row.get('Footprint') or row.get('Package') or 
                                row.get('Foot Print') or '')
                    
                    mpn = (row.get('MPN') or row.get('Part Number') or 
                          row.get('Part') or row.get('Manufacturer Part Number') or '')
                    
                    if ref:
                        component = Component(
                            reference=ref,
                            value=value,
                            footprint=footprint,
                            mpn=mpn if mpn else None
                        )
                        components.append(component)
            
            logger.info(f"Parsed {len(components)} components from BOM")
            
        except Exception as e:
            logger.error(f"Failed to parse BOM: {e}")
        
        return components
    
    def _enhance_with_positions(self, components: List[Component], pos_file: Path):
        """Enhance components with position data"""
        try:
            import csv
            
            with open(pos_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect format
                first_line = f.readline()
                f.seek(0)
                
                delimiter = ',' if ',' in first_line else '\t'
                
                reader = csv.DictReader(f, delimiter=delimiter)
                
                for row in reader:
                    ref = (row.get('Ref') or row.get('Designator') or 
                          row.get('Reference') or row.get('RefDes') or '')
                    
                    if not ref:
                        continue
                    
                    # Find matching component
                    for comp in components:
                        if comp.reference == ref:
                            # Get position
                            x_str = row.get('PosX') or row.get('X') or row.get('Mid X') or ''
                            y_str = row.get('PosY') or row.get('Y') or row.get('Mid Y') or ''
                            rot_str = row.get('Rot') or row.get('Rotation') or row.get('Angle') or ''
                            layer = row.get('Layer') or row.get('Side') or 'Top'
                            
                            try:
                                if x_str:
                                    comp.x = float(x_str.replace('mm', '').strip())
                                if y_str:
                                    comp.y = float(y_str.replace('mm', '').strip())
                                if rot_str:
                                    comp.rotation = float(rot_str.replace('°', '').strip())
                                
                                comp.layer = "Top" if 'top' in layer.lower() else "Bottom"
                            except ValueError:
                                pass
                            
                            break
            
            logger.info(f"Enhanced {sum(1 for c in components if c.x is not None)} components with positions")
            
        except Exception as e:
            logger.warning(f"Failed to parse position file: {e}")
    
    def _extract_nets_from_components(self, components: List[Component]) -> List[Net]:
        """
        Extract likely nets from component values and references
        This is limited without a netlist, but we can infer some power nets
        """
        nets = []
        net_names = set()
        
        # Look for power rails in component values
        for comp in components:
            value_lower = comp.value.lower() if comp.value else ''
            
            # Voltage regulators often indicate their output voltage
            if any(kw in comp.reference.lower() for kw in ['u', 'vreg', 'ldo']):
                # Try to extract voltage from value
                voltage_match = re.search(r'(\d+\.?\d*)v', value_lower)
                if voltage_match:
                    voltage = voltage_match.group(0)
                    net_name = f"+{voltage.upper()}"
                    if net_name not in net_names:
                        net_names.add(net_name)
                        nets.append(Net(
                            name=net_name,
                            is_power=True
                        ))
        
        # Add common power nets
        common_nets = ['+3V3', '+5V', '+12V', '+24V', 'GND', 'AGND', 'DGND']
        for net_name in common_nets:
            if net_name not in net_names:
                net_names.add(net_name)
                nets.append(Net(
                    name=net_name,
                    is_power=self.detect_power_net(net_name),
                    is_ground=self.detect_ground_net(net_name)
                ))
        
        logger.info(f"Extracted {len(nets)} inferred nets")
        return nets
    
    def _parse_ipc_netlist(self, netlist_file: Path, components: List[Component]) -> List[Net]:
        """
        Parse IPC-D-356 netlist file
        
        Common format from Altium/EasyEDA exports
        Format:
        317NET_NAME   VIA         D0150PA00X+019685Y+012446X0315Y0000R000S3
        327NET_NAME   U1    -1    D0394PA00X+014961Y+012559X0394Y0000R000S0
        
        Args:
            netlist_file: Path to IPC-D-356 file
            components: Component list to reference
        
        Returns:
            List of nets with connectivity
        """
        nets_dict = {}
        
        try:
            with open(netlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Skip comments and empty lines
                    if not line.strip() or line.startswith('#') or line.startswith('P'):
                        continue
                    
                    # IPC-D-356 record starts with 3xx
                    if line.startswith('3'):
                        try:
                            # Parse record
                            record_type = line[0:3]
                            
                            if record_type in ['317', '327', '337']:  # Test point, pad, via records
                                # Extract net name (typically columns 3-17)
                                net_name = line[3:17].strip()
                                
                                if not net_name or net_name == '':
                                    continue
                                
                                # Extract component reference (if present)
                                comp_ref = None
                                if record_type in ['327', '337']:  # Pad records
                                    comp_ref = line[17:23].strip()
                                
                                # Create or update net
                                if net_name not in nets_dict:
                                    nets_dict[net_name] = Net(
                                        name=net_name,
                                        is_power=self.detect_power_net(net_name),
                                        is_ground=self.detect_ground_net(net_name),
                                        pads=[]
                                    )
                                
                                # Add pad to net
                                if comp_ref:
                                    pad_ref = f"{comp_ref}.{line[23:27].strip()}"
                                    if pad_ref not in nets_dict[net_name].pads:
                                        nets_dict[net_name].pads.append(pad_ref)
                        
                        except Exception as e:
                            logger.debug(f"Failed to parse IPC line: {line[:50]}... Error: {e}")
                            continue
            
            nets = list(nets_dict.values())
            logger.info(f"Parsed {len(nets)} nets from IPC-D-356 netlist")
            
            # Log statistics
            nets_with_pads = sum(1 for n in nets if len(n.pads) > 0)
            logger.info(f"  - {nets_with_pads} nets have pad connections")
            
            return nets
            
        except Exception as e:
            logger.error(f"Failed to parse IPC-D-356 netlist: {e}", exc_info=True)
            # Fallback to inferred nets
            return self._extract_nets_from_components(components)
