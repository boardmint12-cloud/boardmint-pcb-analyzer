"""
GPT Extractor V2 - Professional PCB Data Extraction
Enhanced AI-powered extraction with structured parsing

Features:
- Multi-format support (KiCad, Altium, Eagle, Gerber)
- Deterministic parsing with AI fallback
- Structured schema validation
- Vision capabilities for visual extraction
"""

import os
import re
import json
import base64
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from openai import OpenAI
from config import get_settings

logger = logging.getLogger(__name__)


class GPTExtractorV2:
    """
    Professional PCB Data Extractor
    
    Uses a hybrid approach:
    1. Deterministic parsing for known formats
    2. GPT for complex extraction and validation
    3. Vision for image-based extraction
    """
    
    def __init__(self):
        """Initialize GPT extractor"""
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.vision_model = "gpt-4o"
        
        logger.info(f"GPT Extractor V2 initialized: {self.model}")
    
    def extract_board_data(
        self,
        pcb_content: str,
        filename: str,
        use_deterministic: bool = True
    ) -> Dict[str, Any]:
        """
        Extract structured board data from PCB file
        
        Args:
            pcb_content: Raw file content
            filename: File name for format detection
            use_deterministic: Try deterministic parsing first
        
        Returns:
            Structured board data
        """
        logger.info(f"Extracting board data from {filename}")
        
        # Detect format
        file_format = self._detect_format(pcb_content, filename)
        logger.info(f"Detected format: {file_format}")
        
        # Try deterministic parsing first
        if use_deterministic:
            result = self._deterministic_parse(pcb_content, file_format)
            if result and result.get('components'):
                logger.info(f"Deterministic parse successful: {len(result.get('components', []))} components")
                return result
        
        # Fall back to GPT extraction
        return self._gpt_extract_board(pcb_content, filename, file_format)
    
    def _detect_format(self, content: str, filename: str) -> str:
        """Detect PCB file format"""
        filename_lower = filename.lower()
        content_sample = content[:2000].lower()
        
        if '.kicad_pcb' in filename_lower or '(kicad_pcb' in content_sample:
            return 'kicad'
        elif '.brd' in filename_lower and '<eagle' in content_sample:
            return 'eagle'
        elif 'pcbdoc' in filename_lower or 'altium' in content_sample:
            return 'altium'
        elif '%fs' in content_sample or 'g04' in content_sample:
            return 'gerber'
        else:
            return 'unknown'
    
    def _deterministic_parse(
        self,
        content: str,
        file_format: str
    ) -> Optional[Dict[str, Any]]:
        """Try deterministic parsing based on format"""
        
        if file_format == 'kicad':
            return self._parse_kicad(content)
        elif file_format == 'eagle':
            return self._parse_eagle_xml(content)
        
        return None
    
    def _parse_kicad(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse KiCad PCB file deterministically"""
        try:
            result = {
                'board_info': {},
                'components': [],
                'nets': [],
                'tracks': [],
                'vias': [],
                'zones': [],
                'design_rules': {}
            }
            
            # Extract board size from (gr_rect) or calculate from outline
            size_match = re.search(
                r'\(gr_rect\s+\(start\s+([\d.-]+)\s+([\d.-]+)\)\s+\(end\s+([\d.-]+)\s+([\d.-]+)\)',
                content
            )
            if size_match:
                x1, y1, x2, y2 = map(float, size_match.groups())
                result['board_info']['size_x_mm'] = abs(x2 - x1)
                result['board_info']['size_y_mm'] = abs(y2 - y1)
            
            # Count layers
            layers = re.findall(r'\(layer\s+"([^"]+)"\s+\w+\)', content)
            copper_layers = [l for l in layers if '.Cu' in l]
            result['board_info']['layer_count'] = len(copper_layers) or 2
            
            # Extract footprints/modules (components)
            # KiCad 6+: (footprint "..." , KiCad 5: (module "..."
            footprint_pattern = r'\((footprint|module)\s+"([^"]+)"\s+(?:.*?\(layer\s+"([^"]+)"\))?.*?\(at\s+([\d.-]+)\s+([\d.-]+)(?:\s+([\d.-]+))?\).*?\(fp_text\s+reference\s+"([^"]+)"'
            
            for match in re.finditer(footprint_pattern, content, re.DOTALL):
                _, footprint, layer, x, y, rotation, reference = match.groups()
                
                # Find value
                value_match = re.search(
                    rf'\(fp_text\s+value\s+"([^"]+)"',
                    content[match.start():match.start()+2000]
                )
                value = value_match.group(1) if value_match else ""
                
                result['components'].append({
                    'reference': reference,
                    'value': value,
                    'footprint': footprint,
                    'x_mm': float(x),
                    'y_mm': float(y),
                    'rotation_deg': float(rotation) if rotation else 0,
                    'layer': layer or 'F.Cu'
                })
            
            # Extract nets
            net_pattern = r'\(net\s+(\d+)\s+"([^"]*)"\)'
            for match in re.finditer(net_pattern, content):
                net_id, net_name = match.groups()
                
                # Classify net
                name_lower = net_name.lower()
                is_power = any(p in name_lower for p in ['vcc', 'vdd', '3v3', '5v', '12v', 'vin'])
                is_ground = any(p in name_lower for p in ['gnd', 'ground', 'vss'])
                is_mains = any(p in name_lower for p in ['mains', '230v', '120v', 'ac_'])
                
                result['nets'].append({
                    'net_id': int(net_id),
                    'name': net_name,
                    'is_power': is_power,
                    'is_ground': is_ground,
                    'is_mains': is_mains
                })
            
            # Extract tracks (simplified)
            track_pattern = r'\(segment\s+\(start\s+[\d.-]+\s+[\d.-]+\)\s+\(end\s+[\d.-]+\s+[\d.-]+\)\s+\(width\s+([\d.-]+)\)\s+\(layer\s+"([^"]+)"\)\s+\(net\s+(\d+)\)'
            
            track_widths = {}
            for match in re.finditer(track_pattern, content):
                width, layer, net_id = match.groups()
                key = (layer, net_id)
                if key not in track_widths:
                    track_widths[key] = {'width': float(width), 'count': 0}
                track_widths[key]['count'] += 1
            
            for (layer, net_id), data in list(track_widths.items())[:50]:
                result['tracks'].append({
                    'layer': layer,
                    'net_id': int(net_id),
                    'width_mm': data['width'],
                    'segment_count': data['count']
                })
            
            # Extract vias
            via_pattern = r'\(via\s+\(at\s+([\d.-]+)\s+([\d.-]+)\)\s+\(size\s+([\d.-]+)\)\s+\(drill\s+([\d.-]+)\)'
            
            for match in re.finditer(via_pattern, content):
                x, y, size, drill = match.groups()
                result['vias'].append({
                    'x_mm': float(x),
                    'y_mm': float(y),
                    'size_mm': float(size),
                    'drill_mm': float(drill)
                })
            
            # Extract design rules
            clearance_match = re.search(r'\(clearance\s+([\d.-]+)\)', content)
            if clearance_match:
                result['design_rules']['min_clearance_mm'] = float(clearance_match.group(1))
            
            track_width_match = re.search(r'\(min_track_width\s+([\d.-]+)\)', content)
            if track_width_match:
                result['design_rules']['min_track_width_mm'] = float(track_width_match.group(1))
            
            return result if result['components'] else None
            
        except Exception as e:
            logger.warning(f"KiCad deterministic parse failed: {e}")
            return None
    
    def _parse_eagle_xml(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse Eagle XML format"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(content)
            result = {
                'board_info': {},
                'components': [],
                'nets': [],
                'tracks': [],
                'vias': [],
                'zones': [],
                'design_rules': {}
            }
            
            # Find board element
            board = root.find('.//board')
            if board is None:
                return None
            
            # Extract elements (components)
            for element in board.findall('.//element'):
                result['components'].append({
                    'reference': element.get('name', ''),
                    'value': element.get('value', ''),
                    'footprint': element.get('package', ''),
                    'x_mm': float(element.get('x', 0)),
                    'y_mm': float(element.get('y', 0)),
                    'rotation_deg': float(element.get('rot', '0').replace('R', '')),
                    'layer': 'Top'
                })
            
            # Extract signals (nets)
            for signal in board.findall('.//signal'):
                name = signal.get('name', '')
                name_lower = name.lower()
                
                result['nets'].append({
                    'name': name,
                    'is_power': any(p in name_lower for p in ['vcc', 'vdd', '3v3', '5v']),
                    'is_ground': 'gnd' in name_lower,
                    'is_mains': any(p in name_lower for p in ['mains', 'ac', '230v'])
                })
            
            return result if result['components'] else None
            
        except Exception as e:
            logger.warning(f"Eagle XML parse failed: {e}")
            return None
    
    def _gpt_extract_board(
        self,
        content: str,
        filename: str,
        file_format: str
    ) -> Dict[str, Any]:
        """Use GPT for board data extraction"""
        
        # Truncate large files
        if len(content) > 80000:
            content = content[:80000] + "\n... [truncated]"
        
        system_prompt = """You are a PCB data extraction specialist. Your task is to parse PCB design files and extract structured information.

EXTRACTION RULES:
1. Extract ALL components with: reference (R1, U1), value, footprint, position
2. Extract ALL nets with: name, classification (power/ground/signal/mains)
3. Extract board dimensions and layer count
4. Be precise with numbers - use the exact values from the file
5. Do NOT invent or guess data - only extract what's actually present

CLASSIFICATION RULES:
- Power nets: VCC, VDD, +3V3, +5V, +12V, VIN, VOUT, VBAT
- Ground nets: GND, GROUND, VSS, PGND, AGND, DGND
- Mains nets: MAINS, 230V, 120V, AC_*, LINE, NEUTRAL
- Communication: SDA, SCL, MOSI, MISO, TX, RX, RS485_*, CAN_*

OUTPUT: Return ONLY valid JSON matching the exact schema provided."""

        user_prompt = f"""Parse this {file_format.upper()} PCB file and extract structured data.

FILE: {filename}

CONTENT:
```
{content}
```

Return this EXACT JSON structure:
{{
  "board_info": {{
    "size_x_mm": <float or null>,
    "size_y_mm": <float or null>,
    "layer_count": <int>,
    "units": "mm"
  }},
  "components": [
    {{
      "reference": "U1",
      "value": "STM32F103",
      "footprint": "LQFP-48",
      "x_mm": 50.0,
      "y_mm": 50.0,
      "rotation_deg": 0,
      "layer": "Top"
    }}
  ],
  "nets": [
    {{
      "net_id": 1,
      "name": "GND",
      "is_power": false,
      "is_ground": true,
      "is_mains": false
    }}
  ],
  "tracks": [],
  "vias": [],
  "design_rules": {{}}
}}

IMPORTANT:
- Parse EVERY component found in the file
- Correctly classify ALL nets
- Use null for unknown dimensions
- Return ONLY the JSON, no explanations"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"GPT extracted: {len(result.get('components', []))} components, "
                       f"{len(result.get('nets', []))} nets")
            
            return result
            
        except Exception as e:
            logger.error(f"GPT extraction failed: {e}")
            return self._empty_board_data()
    
    def extract_schematic_data(
        self,
        sch_content: str,
        filename: str
    ) -> Dict[str, Any]:
        """Extract schematic data with enhanced parsing"""
        logger.info(f"Extracting schematic from {filename}")
        
        if len(sch_content) > 60000:
            sch_content = sch_content[:60000] + "\n... [truncated]"
        
        system_prompt = """You are a schematic data extraction specialist. Extract component and connectivity information from schematic files.

EXTRACTION FOCUS:
1. All components with reference, value, and any custom fields (MPN, Manufacturer)
2. Net names and their pin-level connections
3. Power supply rails and ground nets
4. Communication buses (I2C, SPI, UART, CAN, RS-485)
5. Hierarchical sheet connections if present

OUTPUT: Return ONLY valid JSON."""

        user_prompt = f"""Parse this schematic file:

FILE: {filename}

CONTENT:
```
{sch_content}
```

Return JSON:
{{
  "components": [
    {{
      "reference": "U1",
      "value": "STM32F103",
      "footprint": "LQFP-48",
      "fields": {{"MPN": "STM32F103C8T6", "Manufacturer": "ST"}}
    }}
  ],
  "nets": [
    {{"name": "3V3", "connections": ["U1-1", "C5-1"]}}
  ],
  "power_nets": ["VCC", "3V3"],
  "ground_nets": ["GND"],
  "communication_buses": {{
    "I2C": ["SDA", "SCL"],
    "SPI": ["MOSI", "MISO", "SCK"]
  }}
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Schematic extraction failed: {e}")
            return {"components": [], "nets": []}
    
    def extract_from_image(
        self,
        image_path: str,
        extraction_type: str = "layout"
    ) -> Dict[str, Any]:
        """
        Extract PCB data from image using vision
        
        Args:
            image_path: Path to image file
            extraction_type: "layout", "schematic", or "bom"
        
        Returns:
            Extracted data
        """
        if not os.path.exists(image_path):
            return {}
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            ext = Path(image_path).suffix.lower()
            media_type = {'png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(ext, 'image/png')
            
            prompts = {
                'layout': """Analyze this PCB layout image and extract:
1. Visible component references (U1, R1, C1, etc.)
2. Approximate board dimensions
3. Layer information (if visible)
4. Notable layout features (ground planes, copper pours)
Return JSON: {"components": [], "observations": []}""",
                
                'schematic': """Analyze this schematic and extract:
1. Component references and values
2. Net connections
3. Power rails
Return JSON: {"components": [], "nets": [], "power_rails": []}""",
                
                'bom': """Extract BOM data from this image:
1. Component references
2. Values/part numbers
3. Quantities
Return JSON: {"bom": [{"reference": "", "value": "", "quantity": 1}]}"""
            }
            
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompts.get(extraction_type, prompts['layout'])},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return {}
    
    def merge_data_sources(
        self,
        board_data: Dict,
        schematic_data: Dict,
        netlist_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Intelligently merge data from multiple sources
        
        Priority:
        1. Board data for positions/layout
        2. Schematic data for connectivity/values
        3. Netlist for additional connections
        """
        logger.info("Merging data sources...")
        
        # Start with board data as base
        merged = {
            'board_info': board_data.get('board_info', {}),
            'components': [],
            'nets': [],
            'tracks': board_data.get('tracks', []),
            'vias': board_data.get('vias', []),
            'zones': board_data.get('zones', []),
            'design_rules': board_data.get('design_rules', {})
        }
        
        # Index schematic components by reference
        sch_components = {
            c.get('reference'): c 
            for c in schematic_data.get('components', [])
        }
        
        # Merge components
        for board_comp in board_data.get('components', []):
            ref = board_comp.get('reference')
            merged_comp = board_comp.copy()
            
            # Enrich with schematic data
            if ref in sch_components:
                sch_comp = sch_components[ref]
                # Use schematic value if board value is empty
                if not merged_comp.get('value') and sch_comp.get('value'):
                    merged_comp['value'] = sch_comp['value']
                # Add custom fields
                if sch_comp.get('fields'):
                    merged_comp['fields'] = sch_comp['fields']
            
            merged['components'].append(merged_comp)
        
        # Add schematic-only components (not placed on board)
        board_refs = {c.get('reference') for c in merged['components']}
        for ref, sch_comp in sch_components.items():
            if ref not in board_refs:
                merged['components'].append({
                    **sch_comp,
                    'placed': False
                })
        
        # Merge nets (prefer schematic connectivity info)
        board_nets = {n.get('name'): n for n in board_data.get('nets', [])}
        sch_nets = {n.get('name'): n for n in schematic_data.get('nets', [])}
        
        all_net_names = set(board_nets.keys()) | set(sch_nets.keys())
        
        for name in all_net_names:
            board_net = board_nets.get(name, {})
            sch_net = sch_nets.get(name, {})
            
            merged['nets'].append({
                'name': name,
                'net_id': board_net.get('net_id'),
                'is_power': board_net.get('is_power') or name in schematic_data.get('power_nets', []),
                'is_ground': board_net.get('is_ground') or name in schematic_data.get('ground_nets', []),
                'is_mains': board_net.get('is_mains', False),
                'connections': sch_net.get('connections', [])
            })
        
        # Add summary
        merged['summary'] = {
            'total_components': len(merged['components']),
            'placed_components': sum(1 for c in merged['components'] if c.get('placed', True)),
            'total_nets': len(merged['nets']),
            'power_nets': [n['name'] for n in merged['nets'] if n.get('is_power')],
            'ground_nets': [n['name'] for n in merged['nets'] if n.get('is_ground')],
            'communication_buses': schematic_data.get('communication_buses', {})
        }
        
        logger.info(f"Merged: {merged['summary']}")
        return merged
    
    def _empty_board_data(self) -> Dict[str, Any]:
        """Return empty board data structure"""
        return {
            'board_info': {'size_x_mm': None, 'size_y_mm': None, 'layer_count': 2},
            'components': [],
            'nets': [],
            'tracks': [],
            'vias': [],
            'zones': [],
            'design_rules': {}
        }
