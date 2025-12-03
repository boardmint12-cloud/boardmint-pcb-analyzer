"""
KiCad project parser
Parses .kicad_pcb, .kicad_sch files and extracts relevant data
"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .base_parser import BaseParser, ParsedPCBData, BoardInfo, Net, Component

logger = logging.getLogger(__name__)


class KiCadParser(BaseParser):
    """Parser for KiCad projects"""
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse KiCad project
        
        Args:
            project_path: Path to extracted KiCad project directory
            
        Returns:
            ParsedPCBData with normalized data
        """
        project_dir = Path(project_path)
        
        # Find files (search recursively)
        pcb_file = self._find_file(project_dir, ['.kicad_pcb'])
        # Support both new (.kicad_sch) and old (.sch) KiCad formats
        sch_files = list(project_dir.rglob('*.kicad_sch')) + list(project_dir.rglob('*.sch'))
        # Filter out macOS metadata files
        sch_files = [f for f in sch_files if not f.name.startswith('._') and '__MACOSX' not in str(f)]
        bom_file = self._find_file(project_dir, ['.csv', '_bom.csv'])
        pos_file = self._find_file(project_dir, ['.pos', '_pos.csv', 'position.csv'])
        
        files_found = {
            'pcb': pcb_file is not None,
            'schematic': len(sch_files) > 0,
            'bom': bom_file is not None,
            'position': pos_file is not None
        }
        
        # Parse PCB file
        board_info = None
        nets = []
        components = []
        
        if pcb_file:
            logger.info(f"Parsing PCB file: {pcb_file}")
            board_info, nets, components = self._parse_pcb_file(pcb_file)
        else:
            logger.warning("No KiCad PCB file found")
            board_info = BoardInfo(size_x=0, size_y=0, layer_count=2)
        
        # Enhance with schematic data if available
        if sch_files:
            logger.info(f"Found {len(sch_files)} schematic files")
            # Future: parse schematic for net types, component connections
        
        # Enhance with BOM if available
        if bom_file:
            logger.info(f"Parsing BOM file: {bom_file}")
            self._enhance_with_bom(components, bom_file)
        
        # Enhance with position data if available
        if pos_file:
            logger.info(f"Parsing position file: {pos_file}")
            self._enhance_with_positions(components, pos_file)
        
        return ParsedPCBData(
            board_info=board_info,
            nets=nets,
            components=components,
            files_found=files_found,
            raw_data={}
        )
    
    def _find_file(self, directory: Path, extensions: List[str]) -> Optional[Path]:
        """Find file with given extensions (searches recursively)"""
        for ext in extensions:
            # Search recursively in subdirectories
            files = list(directory.rglob(f'*{ext}'))
            # Filter out macOS metadata files
            files = [f for f in files if not f.name.startswith('._') and '__MACOSX' not in str(f)]
            if files:
                logger.info(f"Found file: {files[0]}")
                return files[0]
        return None
    
    def _parse_pcb_file(self, pcb_file: Path) -> Tuple[BoardInfo, List[Net], List[Component]]:
        """Parse .kicad_pcb file"""
        try:
            with open(pcb_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract board dimensions
            board_info = self._extract_board_info(content)
            
            # Extract nets
            nets = self._extract_nets(content)
            
            # Extract components (footprints)
            components = self._extract_components(content)
            
            return board_info, nets, components
            
        except Exception as e:
            logger.error(f"Failed to parse PCB file: {e}")
            return BoardInfo(size_x=0, size_y=0, layer_count=2), [], []
    
    def _extract_board_info(self, content: str) -> BoardInfo:
        """Extract board information from PCB content"""
        # Find layer count
        layer_count = 2  # default
        layers_match = re.findall(r'\(layers\s+(\d+)', content)
        if layers_match:
            layer_count = int(layers_match[0])
        
        # Find board dimensions from edge cuts
        # KiCad format: (gr_line (start X Y) (end X Y) (layer "Edge.Cuts"))
        edge_coords = []
        edge_pattern = r'\(gr_line\s+\(start\s+([\d.-]+)\s+([\d.-]+)\).*?\(layer\s+"Edge\.Cuts"\)'
        for match in re.finditer(edge_pattern, content):
            x, y = float(match.group(1)), float(match.group(2))
            edge_coords.append((x, y))
        
        edge_pattern2 = r'\(gr_line.*?\(end\s+([\d.-]+)\s+([\d.-]+)\).*?\(layer\s+"Edge\.Cuts"\)'
        for match in re.finditer(edge_pattern2, content):
            x, y = float(match.group(1)), float(match.group(2))
            edge_coords.append((x, y))
        
        # Calculate board size
        if edge_coords:
            xs = [x for x, y in edge_coords]
            ys = [y for x, y in edge_coords]
            size_x = max(xs) - min(xs)
            size_y = max(ys) - min(ys)
        else:
            size_x, size_y = 100.0, 100.0  # default
        
        # Find minimum track width
        min_track = None
        track_widths = re.findall(r'\(width\s+([\d.]+)\)', content)
        if track_widths:
            min_track = min(float(w) for w in track_widths)
        
        return BoardInfo(
            size_x=round(size_x, 2),
            size_y=round(size_y, 2),
            layer_count=layer_count,
            min_track_width=min_track
        )
    
    def _extract_nets(self, content: str) -> List[Net]:
        """Extract nets from PCB content"""
        nets = []
        
        # KiCad format: (net 0 "")  (net 1 "GND")  (net 2 "+3V3")
        net_pattern = r'\(net\s+(\d+)\s+"([^"]*)"\)'
        
        for match in re.finditer(net_pattern, content):
            net_id = int(match.group(1))
            net_name = match.group(2)
            
            if not net_name or net_id == 0:
                continue
            
            net = Net(
                name=net_name,
                is_power=self.detect_power_net(net_name),
                is_ground=self.detect_ground_net(net_name),
                is_mains=self.detect_mains_net(net_name)
            )
            nets.append(net)
        
        logger.info(f"Extracted {len(nets)} nets")
        return nets
    
    def _extract_components(self, content: str) -> List[Component]:
        """Extract components (footprints) from PCB content"""
        components = []
        
        # Try KiCad 6+ format first: (footprint ...)
        # (footprint "Package_TO_SOT_SMD:SOT-23" (layer "F.Cu")
        #   (at 120.5 95.5 90)
        #   (property "Reference" "Q1")
        #   (property "Value" "MMBT3904")
        footprint_pattern = r'\(footprint\s+"([^"]+)".*?\(layer\s+"([^"]+)".*?\(at\s+([\d.-]+)\s+([\d.-]+)\s*([\d.-]+)?\).*?(?:\(property\s+"Reference"\s+"([^"]+)"\))?.*?(?:\(property\s+"Value"\s+"([^"]+)"\))?'
        
        for match in re.finditer(footprint_pattern, content, re.DOTALL):
            footprint = match.group(1)
            layer = match.group(2)
            x = float(match.group(3))
            y = float(match.group(4))
            rotation = float(match.group(5)) if match.group(5) else 0.0
            reference = match.group(6) if match.group(6) else "?"
            value = match.group(7) if match.group(7) else ""
            
            component = Component(
                reference=reference,
                value=value,
                footprint=footprint,
                x=x,
                y=y,
                rotation=rotation,
                layer="Top" if "F.Cu" in layer else "Bottom"
            )
            components.append(component)
        
        # If no components found, try KiCad 5 format: (module ...)
        if len(components) == 0:
            # (module Resistor_SMD:R_0805 (layer F.Cu) ...
            #   (at 120.5 95.5 90)
            #   (fp_text reference R1 ...)
            #   (fp_text value 10k ...)
            module_pattern = r'\(module\s+([^\s]+)\s+\(layer\s+([^\)]+)\).*?\(at\s+([\d.-]+)\s+([\d.-]+)\s*([\d.-]+)?\)'
            ref_pattern = r'\(fp_text\s+reference\s+([^\s]+)'
            value_pattern = r'\(fp_text\s+value\s+([^\)]+?)\s+\('
            
            # Find all modules
            for match in re.finditer(module_pattern, content):
                footprint = match.group(1)
                layer = match.group(2)
                x = float(match.group(3))
                y = float(match.group(4))
                rotation = float(match.group(5)) if match.group(5) else 0.0
                
                # Find the corresponding reference and value within this module
                # Get the text after this module definition (next 500 chars)
                start_pos = match.end()
                module_text = content[start_pos:start_pos+500]
                
                ref_match = re.search(ref_pattern, module_text)
                reference = ref_match.group(1) if ref_match else "?"
                
                val_match = re.search(value_pattern, module_text)
                value = val_match.group(1).strip() if val_match else ""
                
                component = Component(
                    reference=reference,
                    value=value,
                    footprint=footprint,
                    x=x,
                    y=y,
                    rotation=rotation,
                    layer="Top" if "F.Cu" in layer else "Bottom"
                )
                components.append(component)
        
        logger.info(f"Extracted {len(components)} components from PCB")
        return components
    
    def _enhance_with_bom(self, components: List[Component], bom_file: Path):
        """Enhance components with BOM data (MPN, etc.)"""
        try:
            import csv
            
            with open(bom_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    ref = row.get('Reference', row.get('Designator', ''))
                    mpn = row.get('MPN', row.get('Part Number', row.get('Part', '')))
                    
                    # Find matching component
                    for comp in components:
                        if comp.reference == ref and mpn:
                            comp.mpn = mpn
                            break
            
            logger.info(f"Enhanced {sum(1 for c in components if c.mpn)} components with BOM data")
            
        except Exception as e:
            logger.warning(f"Failed to parse BOM file: {e}")
    
    def _enhance_with_positions(self, components: List[Component], pos_file: Path):
        """Enhance components with position data if not already present"""
        try:
            import csv
            
            with open(pos_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    ref = row.get('Ref', row.get('Designator', ''))
                    
                    # Find matching component and update if position not set
                    for comp in components:
                        if comp.reference == ref:
                            if comp.x is None and 'PosX' in row:
                                comp.x = float(row['PosX'])
                            if comp.y is None and 'PosY' in row:
                                comp.y = float(row['PosY'])
                            if comp.rotation is None and 'Rot' in row:
                                comp.rotation = float(row['Rot'])
                            break
            
            logger.info("Enhanced components with position data")
            
        except Exception as e:
            logger.warning(f"Failed to parse position file: {e}")
