"""
GPT-5.1 powered PCB data extraction
Uses AI to parse KiCad files and extract structured information
"""
import json
import logging
from typing import Dict, List, Any
from openai import OpenAI
from config import get_settings

logger = logging.getLogger(__name__)


class GPTExtractor:
    """Use GPT-5.1 to extract structured data from PCB files"""
    
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        logger.info(f"GPT Extractor initialized with model: {self.model}")
    
    def extract_board_data(self, pcb_content: str, filename: str) -> Dict[str, Any]:
        """
        Extract structured board data from .kicad_pcb file
        
        Args:
            pcb_content: Raw file content
            filename: File name
            
        Returns:
            Structured board data (JSON)
        """
        logger.info(f"Extracting board data from {filename}")
        
        # Truncate if too large (GPT context limits)
        if len(pcb_content) > 100000:
            logger.warning(f"PCB file too large ({len(pcb_content)} chars), truncating")
            pcb_content = pcb_content[:100000] + "\n... [truncated]"
        
        prompt = f"""You are a PCB design data extraction expert. Parse this PCB design file and extract ALL structured information.

MULTI-FORMAT SUPPORT - First detect the file format:
- **KiCad** (detect by '(kicad_pcb' or '(module' S-expressions):
  - (module ...) for KiCad 5 footprints
  - (footprint ...) for KiCad 6+ footprints  
  - (net ...) for nets
  - (segment ...) for traces
  
- **Altium** (detect by 'PcbDoc' or Altium-specific tags):
  - `Component` blocks for components
  - `Net` connectivity lists for nets
  - Track segments for routing
  
- **Eagle** (detect by XML structure with '<eagle' root):
  - `<element>` tags for components
  - `<signal>` tags for nets
  - `<wire>` tags for traces
  
- **Gerber/ODB++** (detect by Gerber commands like %FS or ODB++ folders):
  - Extract board outline, layers, drill data
  - Note: Limited connectivity info (use assembly files if available)

FILE: {filename}

CONTENT:
```
{pcb_content}
```

Extract and return this EXACT JSON structure:

{{
  "board_info": {{
    "size_x_mm": <float>,
    "size_y_mm": <float>,
    "layer_count": <int>,
    "units": "mm",
    "thickness_mm": <float or null>
  }},
  "components": [
    {{
      "reference": "U1",
      "value": "STM32F103",
      "footprint": "Package_QFP:LQFP-48_7x7mm_P0.5mm",
      "x_mm": 120.5,
      "y_mm": 95.2,
      "rotation_deg": 0,
      "layer": "Top"
    }}
  ],
  "nets": [
    {{
      "net_id": 1,
      "name": "GND",
      "is_power": true,
      "is_ground": true,
      "is_mains": false,
      "pad_count": 45
    }}
  ],
  "tracks": [
    {{
      "net_name": "3V3",
      "width_mm": 0.25,
      "length_mm": 15.3,
      "layer": "F.Cu"
    }}
  ],
  "vias": [
    {{
      "net_name": "GND",
      "x_mm": 125.0,
      "y_mm": 100.0,
      "drill_mm": 0.3,
      "size_mm": 0.6
    }}
  ],
  "zones": [
    {{
      "net_name": "GND",
      "layer": "F.Cu",
      "area_mm2": 1250.0
    }}
  ],
  "design_rules": {{
    "min_track_width_mm": 0.15,
    "min_clearance_mm": 0.15,
    "min_via_drill_mm": 0.2
  }}
}}

CRITICAL INSTRUCTIONS:
1. **Detect format** - Identify if this is KiCad, Altium, Eagle, Gerber, or other
2. **Parse ALL components** according to detected format:
   - KiCad: (module ...) OR (footprint ...) blocks
   - Altium: Component records
   - Eagle: <element> tags
   - Gerber: Use component centroid/pick-and-place files if available
3. **Extract component data** (reference, value, footprint, position):
   - KiCad: (fp_text reference ...), (at X Y ROTATION)
   - Altium: Designator, Comment, Pattern, Location
   - Eagle: name, value, package, x/y attributes
4. **Parse ALL nets** according to format:
   - KiCad: (net N "NAME") declarations
   - Altium: Net connectivity lists
   - Eagle: <signal name="..."> tags
   - Gerber: Limited (netlist file needed)
5. **Classify nets**: GND/GROUND = ground, VCC/VDD/V+/3V3/5V/12V/VBAT = power, 230V/MAINS/AC = mains, WIFI/ANTENNA/RF = wireless
6. **Count actual components and nets** - don't make up data!
7. **Return ONLY valid JSON**, no explanations
8. **If uncertain about format**, default to KiCad parsing but note in board_info

If file is truncated or you can't parse something, use null values but extract what you CAN."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a PCB data extraction expert. Parse KiCad files and return structured JSON. Always return valid JSON, never plain text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Very low for consistent parsing
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Extracted: {len(result.get('components', []))} components, {len(result.get('nets', []))} nets")
            
            return result
            
        except Exception as e:
            logger.error(f"GPT extraction failed: {e}")
            return self._empty_board_data()
    
    def extract_schematic_data(self, sch_content: str, filename: str) -> Dict[str, Any]:
        """
        Extract components and connectivity from schematic
        
        Args:
            sch_content: Raw schematic file content
            filename: File name
            
        Returns:
            Structured schematic data
        """
        logger.info(f"Extracting schematic data from {filename}")
        
        if len(sch_content) > 80000:
            sch_content = sch_content[:80000] + "\n... [truncated]"
        
        prompt = f"""Parse this schematic file and extract component and net information.

MULTI-FORMAT SUPPORT - Detect the schematic format:
- **KiCad** (.kicad_sch or .sch with S-expressions):
  - Components in (symbol ...) blocks
  - Nets from (wire ...) and (label ...) connections
  
- **Altium** (.SchDoc or ASCII SchDoc):
  - Components as `|COMPONENT` records  
  - Nets from wire connections and net labels
  
- **Eagle** (.sch XML):
  - Components in <part> and <instance> tags
  - Nets from <segment> with <wire> and <junction> tags

FILE: {filename}

CONTENT:
```
{sch_content}
```

Return this JSON structure:

{{
  "components": [
    {{
      "reference": "U1",
      "value": "STM32F103",
      "footprint": "LQFP-48",
      "fields": {{
        "Manufacturer": "STMicroelectronics",
        "MPN": "STM32F103C8T6"
      }}
    }}
  ],
  "nets": [
    {{
      "name": "3V3",
      "connections": ["U1-1", "C5-1", "C6-1"]
    }}
  ],
  "power_nets": ["VCC", "GND", "3V3", "5V", "VBAT"],
  "communication_buses": {{
    "I2C": ["SDA", "SCL"],
    "SPI": ["MOSI", "MISO", "SCK"],
    "RS485": ["RS485_A", "RS485_B"],
    "UART": ["TX", "RX"]
  }},
  "wireless_nets": ["WIFI_TX", "WIFI_RX", "ANT", "RF_OUT"],
  "annotations": []
}}

INSTRUCTIONS:
1. **Detect schematic format** (KiCad, Altium, Eagle)
2. **Extract ALL components** with references, values, footprints, and custom fields (MPN, Manufacturer)
3. **Extract ALL nets** and their pin-level connections
4. **Identify power nets** (VCC, GND, +3V3, VBAT, etc.)
5. **Identify communication buses** (I2C, SPI, RS-485, CAN, UART)
6. **Identify wireless/RF nets** (ANTENNA, WIFI, BLE, RF, etc.)
7. **Return ONLY valid JSON**, no explanations"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Schematic: {len(result.get('components', []))} components, {len(result.get('nets', []))} nets")
            
            return result
            
        except Exception as e:
            logger.error(f"Schematic extraction failed: {e}")
            return {"components": [], "nets": [], "power_nets": []}
    
    def extract_netlist_data(self, netlist_content: str) -> Dict[str, Any]:
        """Extract connectivity from netlist file"""
        logger.info("Extracting netlist data")
        
        prompt = f"""Parse this netlist file and extract component connectivity.

CONTENT:
```
{netlist_content[:20000]}
```

Return JSON:
{{
  "components": [{{"reference": "U1", "value": "IC", "pins": []}}],
  "nets": [{{"name": "GND", "connections": ["U1-8", "C1-2"]}}]
}}

Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Netlist extraction failed: {e}")
            return {"components": [], "nets": []}
    
    def merge_data_sources(
        self,
        board_data: Dict,
        schematic_data: Dict,
        netlist_data: Dict
    ) -> Dict[str, Any]:
        """
        Merge data from multiple sources into unified structure
        
        Args:
            board_data: From PCB file
            schematic_data: From schematic
            netlist_data: From netlist
            
        Returns:
            Merged, deduplicated data
        """
        logger.info("Merging data from multiple sources")
        
        # Use GPT to intelligently merge conflicting data
        prompt = f"""Merge these three data sources into one unified PCB project representation.

BOARD DATA (from .kicad_pcb):
```json
{json.dumps(board_data, indent=2)[:15000]}
```

SCHEMATIC DATA (from .sch):
```json
{json.dumps(schematic_data, indent=2)[:10000]}
```

NETLIST DATA (from .net):
```json
{json.dumps(netlist_data, indent=2)[:5000]}
```

MERGE RULES:
1. Components: Match by reference designator (R1, C5, U3, etc.)
2. Enrich board components with schematic values/fields if missing
3. Nets: Merge by name, combine connection info
4. Resolve conflicts: PCB position data is authoritative for placement
5. Add any components from schematic/netlist that aren't in PCB (DNP/not placed)

Return unified JSON:
{{
  "board_info": {{}},
  "components": [{{complete component data}}],
  "nets": [{{complete net data}}],
  "design_rules": {{}},
  "summary": {{
    "total_components": N,
    "placed_components": N,
    "not_placed": N,
    "total_nets": N,
    "power_nets": [],
    "ground_nets": [],
    "mains_nets": []
  }}
}}

Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            merged = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Merged data: {merged.get('summary', {})}")
            
            return merged
            
        except Exception as e:
            logger.error(f"Data merge failed: {e}")
            # Fallback: use board data
            return board_data
    
    def _empty_board_data(self) -> Dict[str, Any]:
        """Return empty board data structure"""
        return {
            "board_info": {
                "size_x_mm": 0,
                "size_y_mm": 0,
                "layer_count": 2
            },
            "components": [],
            "nets": [],
            "tracks": [],
            "vias": [],
            "zones": [],
            "design_rules": {}
        }
