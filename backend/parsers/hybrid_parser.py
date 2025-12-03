"""
Hybrid Parser - Combines deterministic S-expression parsing with GPT semantic analysis

Philosophy:
- Use deterministic parsing for FACTS (geometry, positions, sizes)
- Use GPT for SEMANTICS (component types, net purposes, design intent)
- Never let AI make CRITICAL claims without deterministic backing
"""
import logging
import sexpdata
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from openai import OpenAI
from config import get_settings
from parsers.base_parser import ParsedPCBData, BoardInfo, Component, Net, Track, Via, Zone
from parsers.kicad_sch_parser import KiCadSchematicParser

logger = logging.getLogger(__name__)


class HybridParser:
    """
    Hybrid parser combining:
    1. Deterministic S-expression parsing for geometry
    2. GPT-4o for semantic understanding
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.sch_parser = KiCadSchematicParser()
    
    def parse(self, project_path: Path) -> ParsedPCBData:
        """
        Parse KiCad project with hybrid approach
        
        Args:
            project_path: Path to extracted project folder
            
        Returns:
            ParsedPCBData with reliable geometry + semantic insights
        """
        logger.info("Starting hybrid parsing (deterministic + AI semantic)")
        
        # Step 1: Find files
        pcb_file = self._find_pcb_file(project_path)
        sch_files = self._find_schematic_files(project_path)
        
        if not pcb_file:
            logger.warning("No PCB file found")
            return self._empty_result()
        
        # Step 2: Parse schematic for voltage/component data
        schematic_data = None
        if sch_files:
            logger.info(f"Parsing {len(sch_files)} schematic files")
            schematic_data = self.sch_parser.parse_project_schematics(project_path)
        else:
            logger.info("No schematic files found - using PCB data only")
        
        # Step 3: Deterministic parsing for FACTS
        logger.info(f"Parsing PCB file deterministically: {pcb_file.name}")
        pcb_content = pcb_file.read_text(errors='ignore')
        
        geometric_data = self._parse_geometry_deterministic(pcb_content)
        
        # Step 4: GPT semantic analysis for UNDERSTANDING
        logger.info("Using GPT for semantic classification")
        semantic_data = self._classify_semantics_gpt(geometric_data, pcb_content[:50000])
        
        # Step 5: Merge deterministic facts with semantic insights and schematic data
        return self._merge_results(geometric_data, semantic_data, schematic_data)
    
    def _find_pcb_file(self, project_path: Path) -> Optional[Path]:
        """Find .kicad_pcb file (not backup)"""
        for pcb in project_path.rglob('*.kicad_pcb'):
            if not pcb.name.endswith('-bak') and not pcb.name.startswith('._'):
                return pcb
        return None
    
    def _find_schematic_files(self, project_path: Path) -> List[Path]:
        """Find schematic files"""
        files = []
        for ext in ['*.kicad_sch', '*.sch']:
            for f in project_path.rglob(ext):
                if not f.name.endswith('.bak') and not f.name.startswith('._'):
                    files.append(f)
        return files
    
    def _parse_geometry_deterministic(self, pcb_content: str) -> Dict[str, Any]:
        """
        Parse geometry using deterministic S-expression parsing
        
        Returns facts only - no interpretation
        """
        try:
            # Parse S-expression
            data = sexpdata.loads(pcb_content)
            
            result = {
                'board_info': {},
                'components': [],
                'nets': [],
                'tracks': [],
                'vias': [],
                'zones': [],
                'edge_coords': []  # Collect edge coordinates
            }
            
            # CRITICAL: Extract net map and pad connections first
            # This enables proper net connectivity checking
            net_map = self._extract_net_map(data)
            net_to_pads = self._extract_pad_connections(data, net_map)
            
            # Store for later use when building Net objects
            result['net_map'] = net_map
            result['net_to_pads'] = net_to_pads
            
            # Extract from kicad_pcb root
            if isinstance(data, list) and len(data) > 0:
                for item in data:
                    if not isinstance(item, list):
                        continue
                    
                    tag = str(item[0]) if len(item) > 0 else None
                    
                    if tag == 'general':
                        result['board_info'] = self._extract_general_info(item)
                    elif tag == 'layers':
                        # Extract layer count from (layers ...) block
                        layer_count = self._extract_layer_count(item)
                        if layer_count > 0:
                            result['board_info']['layer_count'] = layer_count
                    elif tag == 'gr_line' or tag == 'gr_rect' or tag == 'gr_arc' or tag == 'gr_poly' or tag == 'gr_circle':
                        # Edge cuts - collect coordinates for board size calculation
                        coords = self._extract_edge_coords(item)
                        if coords:
                            result['edge_coords'].extend(coords)
                    elif tag == 'module' or tag == 'footprint':
                        comp = self._extract_component_deterministic(item)
                        if comp:
                            result['components'].append(comp)
                    elif tag == 'net':
                        net = self._extract_net_deterministic(item)
                        if net:
                            result['nets'].append(net)
                    elif tag == 'segment':
                        track = self._extract_track(item)
                        if track:
                            result['tracks'].append(track)
                    elif tag == 'via':
                        via = self._extract_via(item)
                        if via:
                            result['vias'].append(via)
                    elif tag == 'zone':
                        zone = self._extract_zone(item)
                        if zone:
                            result['zones'].append(zone)
            
            # Calculate board dimensions from edge coordinates
            if result['edge_coords']:
                xs = [coord[0] for coord in result['edge_coords']]
                ys = [coord[1] for coord in result['edge_coords']]
                size_x = max(xs) - min(xs)
                size_y = max(ys) - min(ys)
                result['board_info']['size_x_mm'] = round(size_x, 2)
                result['board_info']['size_y_mm'] = round(size_y, 2)
                logger.info(f"Board dimensions: {size_x:.2f} × {size_y:.2f} mm")
            else:
                result['board_info']['size_x_mm'] = 0
                result['board_info']['size_y_mm'] = 0
                logger.warning("No edge coordinates found, board size = 0")
            
            logger.info(f"Deterministic parse: {len(result['components'])} components, {len(result['nets'])} nets")
            return result
            
        except Exception as e:
            logger.error(f"Deterministic parsing failed: {e}", exc_info=True)
            return {'board_info': {}, 'components': [], 'nets': [], 'tracks': [], 'vias': [], 'zones': [], 'edge_coords': []}
    
    def _extract_general_info(self, general_block: list) -> Dict:
        """Extract board info from (general ...) block"""
        info = {'thickness': 1.6, 'layer_count': 2}
        
        for item in general_block[1:]:
            if not isinstance(item, list) or len(item) < 2:
                continue
            
            key = str(item[0])
            if key == 'thickness':
                info['thickness'] = float(item[1])
        
        return info
    
    def _extract_layer_count(self, layers_block: list) -> int:
        """
        Extract layer count from (layers ...) block.
        
        CRITICAL: Only count signal copper layers, not mask/paste/silk layers.
        
        KiCad format:
        (layers
          (0 "F.Cu" signal)
          (1 "In1.Cu" signal)  <- Inner layers
          (2 "In2.Cu" signal)
          (31 "B.Cu" signal)
          (32 "B.Adhes" user)
          (34 "B.Paste" user)
          (38 "B.Mask" user)
          ...
        )
        
        Only count layers where:
        1. Layer name ends with .Cu (not just contains Cu)
        2. Layer type is "signal" (not "user")
        """
        try:
            copper_layers = []
            
            for item in layers_block[1:]:
                if not isinstance(item, list) or len(item) < 3:
                    continue
                
                # item format: (layer_number "layer_name" layer_type)
                layer_number = item[0]
                layer_name = str(item[1]).strip('"')
                layer_type = str(item[2]) if len(item) > 2 else ""
                
                # CRITICAL: Only count signal copper layers
                # This prevents counting mask layers (B.Mask, F.Mask) or paste layers
                if layer_name.endswith('.Cu') and layer_type == 'signal':
                    copper_layers.append((layer_number, layer_name))
            
            layer_count = len(copper_layers)
            if layer_count > 0:
                layer_names = [name for _, name in copper_layers]
                logger.info(f"✓ Detected {layer_count} signal copper layers: {layer_names}")
                return layer_count
            
            logger.warning("No copper layers detected, defaulting to 2")
            return 2  # Default fallback
            
        except Exception as e:
            logger.error(f"Failed to extract layer count: {e}", exc_info=True)
            return 2  # Default fallback
    
    def _extract_net_map(self, pcb_root: list) -> Dict[int, str]:
        """
        Build a mapping from KiCad net ID -> net name.
        
        KiCad .kicad_pcb has net definitions like:
          (net 0 "")
          (net 1 "GND")
          (net 2 "VBAT")
          (net 3 "BAT(+)")
        
        This creates the foundation for pad-to-net connectivity.
        """
        net_map: Dict[int, str] = {}
        
        try:
            if not isinstance(pcb_root, list):
                return net_map
            
            for elem in pcb_root:
                if not isinstance(elem, list) or len(elem) < 3:
                    continue
                
                # Check if this is a net definition
                tag = str(elem[0]) if elem else None
                if tag != 'net':
                    continue
                
                try:
                    # (net ID "NAME")
                    net_id = int(elem[1])
                    net_name = str(elem[2]).strip('"')
                    net_map[net_id] = net_name
                except (ValueError, TypeError, IndexError) as e:
                    logger.debug(f"Skipping malformed net entry: {elem}")
                    continue
            
            logger.info(f"✓ Extracted {len(net_map)} net definitions")
            return net_map
            
        except Exception as e:
            logger.error(f"Failed to extract net map: {e}", exc_info=True)
            return {}
    
    def _extract_pad_connections(self, pcb_root: list, net_map: Dict[int, str]) -> Dict[str, List[str]]:
        """
        Extract pad-to-net connectivity mapping.
        
        Returns: net_name -> list of 'Ref.PadNum' strings
        
        Example: {"BAT(+)": ["J1.1", "U3.2", "R5.1", "C2.1"], ...}
        
        This is CRITICAL for detecting unconnected nets properly.
        Without this, all nets appear to have zero connections.
        """
        net_to_pads: Dict[str, List[str]] = defaultdict(list)
        
        try:
            if not isinstance(pcb_root, list):
                return dict(net_to_pads)
            
            for elem in pcb_root:
                if not isinstance(elem, list) or not elem:
                    continue
                
                tag = str(elem[0])
                
                # Handle both 'footprint' (KiCad 6+) and 'module' (KiCad 5)
                if tag not in ('footprint', 'module'):
                    continue
                
                # Extract reference designator
                ref = self._find_footprint_reference(elem)
                if not ref:
                    continue
                
                # Extract pads from this footprint
                for sub in elem:
                    if not isinstance(sub, list) or not sub:
                        continue
                    
                    if str(sub[0]) != 'pad':
                        continue
                    
                    # Parse pad: (pad "1" thru_hole rect ... (net 3 "BAT(+)") ...)
                    if len(sub) < 2:
                        continue
                    
                    pad_num = str(sub[1]).strip('"')
                    
                    # Find net assignment in pad
                    net_name = self._find_pad_net(sub, net_map)
                    
                    if net_name and net_name.strip():  # Ignore empty net names
                        pad_ref = f"{ref}.{pad_num}"
                        net_to_pads[net_name].append(pad_ref)
            
            # Log statistics
            total_pads = sum(len(pads) for pads in net_to_pads.values())
            nets_with_pads = len([n for n, p in net_to_pads.items() if len(p) > 0])
            logger.info(f"✓ Extracted {total_pads} pad connections across {nets_with_pads} nets")
            
            # Sample some connections for debugging
            sample_nets = list(net_to_pads.items())[:3]
            for net_name, pads in sample_nets:
                logger.debug(f"  {net_name}: {len(pads)} pads - {pads[:3]}...")
            
            return dict(net_to_pads)
            
        except Exception as e:
            logger.error(f"Failed to extract pad connections: {e}", exc_info=True)
            return {}
    
    def _find_footprint_reference(self, footprint_block: list) -> Optional[str]:
        """Extract reference designator from footprint block."""
        try:
            for sub in footprint_block:
                if not isinstance(sub, list) or len(sub) < 3:
                    continue
                
                # (fp_text reference "U1" ...)
                if (str(sub[0]) == 'fp_text' and 
                    len(sub) >= 3 and 
                    str(sub[1]) == 'reference'):
                    return str(sub[2]).strip('"')
            
            return None
        except Exception:
            return None
    
    def _find_pad_net(self, pad_block: list, net_map: Dict[int, str]) -> Optional[str]:
        """Extract net name from pad block."""
        try:
            for token in pad_block:
                if not isinstance(token, list) or not token:
                    continue
                
                if str(token[0]) != 'net':
                    continue
                
                # (net 3 "BAT(+)") or (net 3)
                if len(token) >= 2:
                    try:
                        net_id = int(token[1])
                        # Prefer net_map lookup for consistency
                        return net_map.get(net_id)
                    except (ValueError, TypeError):
                        continue
            
            return None
        except Exception:
            return None
    
    def _extract_component_deterministic(self, module_block: list) -> Optional[Dict]:
        """Extract component with positions, no interpretation"""
        try:
            comp = {
                'reference': 'Unknown',
                'value': '',
                'footprint': '',
                'x': 0.0,
                'y': 0.0,
                'rotation': 0.0,
                'layer': 'F.Cu'
            }
            
            # Module/footprint name is usually second element
            if len(module_block) > 1:
                comp['footprint'] = str(module_block[1])
            
            # Parse sub-items
            for item in module_block[2:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                
                tag = str(item[0])
                
                if tag == 'at':
                    # Position (at X Y [rotation])
                    comp['x'] = float(item[1]) if len(item) > 1 else 0.0
                    comp['y'] = float(item[2]) if len(item) > 2 else 0.0
                    comp['rotation'] = float(item[3]) if len(item) > 3 else 0.0
                
                elif tag == 'layer':
                    comp['layer'] = str(item[1])
                
                elif tag == 'fp_text':
                    # (fp_text reference "U1" ...)
                    # (fp_text value "ATmega328P" ...)
                    if len(item) > 2:
                        text_type = str(item[1])
                        text_value = str(item[2]).strip('"')
                        
                        if text_type == 'reference':
                            comp['reference'] = text_value
                        elif text_type == 'value':
                            comp['value'] = text_value
            
            return comp if comp['reference'] != 'Unknown' else None
            
        except Exception as e:
            logger.warning(f"Failed to extract component: {e}")
            return None
    
    def _extract_net_deterministic(self, net_block: list) -> Optional[Dict]:
        """Extract net - just facts, no classification"""
        try:
            if len(net_block) < 3:
                return None
            
            return {
                'number': int(net_block[1]),
                'name': str(net_block[2]).strip('"'),
                'is_power': False,  # Will be classified by GPT
                'is_ground': False,
                'is_mains': False
            }
        except Exception as e:
            logger.warning(f"Failed to extract net: {e}")
            return None
    
    def _extract_track(self, track_block: list) -> Optional[Dict]:
        """Extract track geometry"""
        try:
            track = {'layer': '', 'width': 0.0, 'start_x': 0.0, 'start_y': 0.0, 'end_x': 0.0, 'end_y': 0.0, 'net': None}
            
            for item in track_block[1:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                
                tag = str(item[0])
                if tag == 'start':
                    track['start_x'] = float(item[1])
                    track['start_y'] = float(item[2])
                elif tag == 'end':
                    track['end_x'] = float(item[1])
                    track['end_y'] = float(item[2])
                elif tag == 'width':
                    track['width'] = float(item[1])
                elif tag == 'layer':
                    track['layer'] = str(item[1]).strip('"')
                elif tag == 'net':
                    track['net'] = int(item[1]) if len(item) > 1 else None
            
            return track
        except Exception as e:
            return None
    
    def _extract_via(self, via_block: list) -> Optional[Dict]:
        """Extract via geometry"""
        try:
            via = {'x': 0.0, 'y': 0.0, 'size': 0.0, 'drill': 0.0, 'net': None, 'layers': None}
            
            for item in via_block[1:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                
                tag = str(item[0])
                if tag == 'at':
                    via['x'] = float(item[1])
                    via['y'] = float(item[2])
                elif tag == 'size':
                    via['size'] = float(item[1])
                elif tag == 'drill':
                    via['drill'] = float(item[1])
                elif tag == 'net':
                    via['net'] = int(item[1]) if len(item) > 1 else None
                elif tag == 'layers':
                    # (layers "F.Cu" "B.Cu") or (layers "F.Cu" "In1.Cu")
                    if len(item) > 2:
                        via['layers'] = (str(item[1]).strip('"'), str(item[-1]).strip('"'))
            
            return via
        except Exception as e:
            return None
    
    def _extract_zone(self, zone_block: list) -> Optional[Dict]:
        """
        Extract zone (copper pour) geometry
        
        KiCad format:
        (zone (net 1) (net_name "GND") (layer "F.Cu")
          (polygon
            (pts
              (xy 100 50)
              (xy 150 50)
              ...
            )
          )
        )
        """
        try:
            zone = {'net': None, 'net_name': None, 'layer': None, 'outline_points': []}
            
            for item in zone_block[1:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                
                tag = str(item[0])
                if tag == 'net':
                    zone['net'] = int(item[1]) if len(item) > 1 else None
                elif tag == 'net_name':
                    zone['net_name'] = str(item[1]).strip('"')
                elif tag == 'layer':
                    zone['layer'] = str(item[1]).strip('"')
                elif tag == 'polygon' or tag == 'filled_polygon':
                    # Extract polygon points
                    points = self._extract_polygon_points(item)
                    if points:
                        zone['outline_points'] = points
            
            # Only return if we have meaningful data
            if zone['layer'] and zone['outline_points']:
                return zone
            return None
        except Exception as e:
            logger.debug(f"Failed to extract zone: {e}")
            return None
    
    def _extract_polygon_points(self, polygon_expr: list) -> List[tuple]:
        """Extract (xy x y) points from polygon"""
        points = []
        try:
            for item in polygon_expr:
                if isinstance(item, list):
                    tag = str(item[0]) if len(item) > 0 else None
                    if tag == 'pts':
                        # (pts (xy x1 y1) (xy x2 y2) ...)
                        for pt in item[1:]:
                            if isinstance(pt, list) and len(pt) >= 3 and str(pt[0]) == 'xy':
                                x = float(pt[1])
                                y = float(pt[2])
                                points.append((x, y))
        except Exception as e:
            logger.debug(f"Failed to extract polygon points: {e}")
        return points
    
    def _extract_edge_coords(self, graphics_item: list) -> List[tuple]:
        """
        Extract coordinates from graphical items (lines, rectangles, arcs, etc.)
        Only process items on Edge.Cuts layer
        
        Returns list of (x, y) coordinate tuples
        """
        try:
            coords = []
            
            # Check if this is on Edge.Cuts layer
            is_edge_cuts = False
            for sub_item in graphics_item:
                if isinstance(sub_item, list) and len(sub_item) >= 2:
                    if str(sub_item[0]) == 'layer':
                        layer_name = str(sub_item[1]).strip('"')
                        if 'Edge.Cuts' in layer_name or 'Edge_Cuts' in layer_name:
                            is_edge_cuts = True
                            break
            
            if not is_edge_cuts:
                return []
            
            # Extract coordinates based on element type
            tag = str(graphics_item[0])
            
            for sub_item in graphics_item:
                if not isinstance(sub_item, list) or len(sub_item) < 2:
                    continue
                
                sub_tag = str(sub_item[0])
                
                if sub_tag == 'start':
                    # (start X Y)
                    x, y = float(sub_item[1]), float(sub_item[2])
                    coords.append((x, y))
                
                elif sub_tag == 'end':
                    # (end X Y)
                    x, y = float(sub_item[1]), float(sub_item[2])
                    coords.append((x, y))
                
                elif sub_tag == 'center':
                    # (center X Y) - for circles/arcs
                    x, y = float(sub_item[1]), float(sub_item[2])
                    coords.append((x, y))
                
                elif sub_tag == 'pts':
                    # (pts (xy X1 Y1) (xy X2 Y2) ...) - for polygons
                    for pt in sub_item[1:]:
                        if isinstance(pt, list) and len(pt) >= 3 and str(pt[0]) == 'xy':
                            x, y = float(pt[1]), float(pt[2])
                            coords.append((x, y))
                
                elif sub_tag == 'xy':
                    # Direct (xy X Y) format
                    if len(sub_item) >= 3:
                        x, y = float(sub_item[1]), float(sub_item[2])
                        coords.append((x, y))
            
            return coords
            
        except Exception as e:
            logger.debug(f"Failed to extract edge coordinates: {e}")
            return []
    
    def _classify_semantics_gpt(self, geometric_data: Dict, pcb_sample: str) -> Dict:
        """
        Use GPT to classify semantic meaning:
        - Which nets are power/ground/mains?
        - What type is each component?
        - What is the design intent?
        
        NOT for geometry - only for understanding
        """
        try:
            # Build component list for GPT
            comp_list = []
            for comp in geometric_data['components'][:50]:  # Limit to first 50
                comp_list.append(f"{comp['reference']}: {comp['value']} ({comp['footprint']})")
            
            # Build net list
            net_list = [net['name'] for net in geometric_data['nets'][:50]]
            
            prompt = f"""Classify components and nets from this PCB design for IoT/Smart Building analysis.

**COMPONENTS ({len(comp_list)}):**
{chr(10).join(comp_list[:30])}

**NETS ({len(net_list)}):**
{chr(10).join(net_list[:30])}

Provide ONLY classification, no geometry analysis:

Return JSON:
{{
  "power_nets": ["VCC", "3V3", "5V", "12V", ...],
  "ground_nets": ["GND", "AGND", ...],
  "mains_nets": ["230V", "MAINS_L", "AC_IN", ...],
  "battery_nets": ["VBAT", "BAT+", "BATTERY", ...],
  "wireless_nets": ["WIFI_TX", "WIFI_RX", "ANT", "RF_OUT", "BLE", ...],
  "communication_buses": {{
    "RS485": ["RS485_A", "RS485_B"],
    "I2C": ["SDA", "SCL"],
    "SPI": ["MOSI", "MISO", "SCK"],
    "CAN": ["CANH", "CANL"],
    "UART": ["TX", "RX"]
  }},
  "component_types": {{
    "U1": "microcontroller",
    "U2": "wireless_module",
    "U3": "voltage_regulator",
    "BT1": "battery_holder",
    ...
  }},
  "has_mains_voltage": true/false,
  "has_wireless_module": true/false,
  "has_battery_power": true/false,
  "board_purpose": "smart building sensor node / HVAC controller / IoT gateway / etc."
}}

DETECTION GUIDELINES:
- **has_wireless_module**: Set true if any component appears to be Wi-Fi, Zigbee, BLE, LoRa, NB-IoT radio module (e.g. ESP32, nRF52, RFM95)
- **has_battery_power**: Set true if battery holder, battery connector, or battery charging circuit detected (BT prefix, BAT nets, charging ICs)
- **battery_nets**: Include VBAT, BAT+, BAT-, BATTERY, or any nets connected to battery power
- **wireless_nets**: Include antenna feeds, RF traces, wireless module TX/RX pins

Be specific. Only classify what you see. Return ONLY JSON."""

            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a PCB design analyst. Classify components and nets. Return only JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000
            )
            
            import json
            classification = json.loads(response.choices[0].message.content)
            logger.info(f"GPT classified: {len(classification.get('power_nets', []))} power nets, {len(classification.get('ground_nets', []))} ground nets")
            
            return classification
            
        except Exception as e:
            logger.error(f"GPT semantic classification failed: {e}")
            return {}
    
    def _merge_results(self, geometric: Dict, semantic: Dict, schematic=None) -> ParsedPCBData:
        """Merge deterministic geometry with semantic understanding"""
        
        # Create net ID to name mapping
        net_id_to_name = {}
        for net_data in geometric['nets']:
            if 'id' in net_data:
                net_id_to_name[net_data['id']] = net_data['name']
        
        # Create components with semantic types
        components = []
        for comp_data in geometric['components']:
            comp = Component(
                reference=comp_data['reference'],
                value=comp_data['value'],
                footprint=comp_data['footprint'],
                x=comp_data['x'],
                y=comp_data['y'],
                rotation=comp_data['rotation'],
                layer=comp_data['layer']
            )
            components.append(comp)
        
        # Create nets with semantic classification and schematic voltage data
        nets = []
        power_nets = set(semantic.get('power_nets', []))
        ground_nets = set(semantic.get('ground_nets', []))
        mains_nets = set(semantic.get('mains_nets', []))
        
        # CRITICAL: Get pad connectivity data
        net_to_pads = geometric.get('net_to_pads', {})
        
        for net_data in geometric['nets']:
            net_name = net_data['name']
            
            # Get voltage from schematic if available
            voltage = None
            if schematic and net_name in schematic.nets:
                voltage = schematic.nets[net_name].voltage
            
            # Determine if high voltage
            is_hv = False
            if voltage and voltage >= 48:
                is_hv = True
            elif net_name in mains_nets:
                is_hv = True
            
            # CRITICAL: Populate pads field from extracted connectivity
            pads = net_to_pads.get(net_name, [])
            
            net = Net(
                name=net_name,
                is_power=net_name in power_nets or (schematic and schematic.nets.get(net_name, None) and schematic.nets[net_name].is_power),
                is_ground=net_name in ground_nets or (schematic and schematic.nets.get(net_name, None) and schematic.nets[net_name].is_ground),
                is_mains=net_name in mains_nets,
                voltage_level=voltage,
                is_high_voltage=is_hv,
                pads=pads  # ← THIS WAS MISSING! Now nets know their connections
            )
            nets.append(net)
        
        # Create tracks
        tracks = []
        for track_data in geometric.get('tracks', []):
            net_id = track_data.get('net')
            net_name = net_id_to_name.get(net_id) if net_id is not None else None
            
            track = Track(
                net_name=net_name,
                layer=track_data.get('layer'),
                width=track_data.get('width', 0.0),
                x1=track_data.get('start_x', 0.0),
                y1=track_data.get('start_y', 0.0),
                x2=track_data.get('end_x', 0.0),
                y2=track_data.get('end_y', 0.0)
            )
            tracks.append(track)
        
        # Create vias
        vias = []
        for via_data in geometric.get('vias', []):
            net_id = via_data.get('net')
            net_name = net_id_to_name.get(net_id) if net_id is not None else None
            layers = via_data.get('layers')
            
            via = Via(
                net_name=net_name,
                x=via_data.get('x', 0.0),
                y=via_data.get('y', 0.0),
                diameter=via_data.get('size', 0.0),
                drill=via_data.get('drill', 0.0),
                start_layer=layers[0] if layers else None,
                end_layer=layers[1] if layers else None
            )
            vias.append(via)
        
        # Create zones
        zones = []
        for zone_data in geometric.get('zones', []):
            zone = Zone(
                net_name=zone_data.get('net_name'),
                layer=zone_data.get('layer'),
                outline_points=zone_data.get('outline_points', [])
            )
            zones.append(zone)
        
        # Board info
        board_info = BoardInfo(
            size_x=geometric['board_info'].get('size_x_mm', 0),
            size_y=geometric['board_info'].get('size_y_mm', 0),
            layer_count=geometric['board_info'].get('layer_count', 2)
        )
        
        # Count nets with voltage data
        nets_with_voltage = sum(1 for n in nets if n.voltage_level is not None)
        logger.info(f"Merged results: {len(tracks)} tracks, {len(vias)} vias, {len(zones)} zones")
        logger.info(f"Schematic data: {nets_with_voltage}/{len(nets)} nets have voltage info")
        
        return ParsedPCBData(
            board_info=board_info,
            components=components,
            nets=nets,
            tracks=tracks,
            vias=vias,
            zones=zones,
            files_found={'pcb': True, 'schematic': False, 'bom': False, 'position': False},
            raw_data={
                'geometric': geometric,
                'semantic': semantic
            }
        )
    
    def _empty_result(self) -> ParsedPCBData:
        """Return empty result"""
        return ParsedPCBData(
            board_info=BoardInfo(size_x=0, size_y=0, layer_count=2),
            components=[],
            nets=[],
            files_found={'pcb': False, 'schematic': False, 'bom': False, 'position': False},
            raw_data={}
        )
