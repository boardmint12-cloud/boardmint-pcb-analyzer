"""
KiCad Schematic Parser
Parses .kicad_sch files to extract:
- Component properties (voltage ratings, power ratings)
- Net labels and voltages
- Power connections
"""
import logging
import sexpdata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SchematicComponent:
    """Component from schematic with properties"""
    reference: str
    value: str
    lib_id: str
    properties: Dict[str, str] = field(default_factory=dict)
    position: Tuple[float, float] = (0, 0)
    unit: int = 1


@dataclass
class SchematicNet:
    """Net from schematic with labels"""
    name: str
    labels: List[str] = field(default_factory=list)
    voltage: Optional[float] = None
    is_power: bool = False
    is_ground: bool = False


@dataclass
class SchematicData:
    """Parsed schematic data"""
    components: List[SchematicComponent] = field(default_factory=list)
    nets: Dict[str, SchematicNet] = field(default_factory=dict)
    power_flags: List[str] = field(default_factory=list)
    global_labels: Dict[str, str] = field(default_factory=dict)


class KiCadSchematicParser:
    """Parser for KiCad 6+ schematic files (.kicad_sch)"""
    
    def __init__(self):
        self.voltage_keywords = {
            '230v': 230.0, '240v': 240.0, '120v': 120.0,
            '48v': 48.0, '24v': 24.0, '12v': 12.0,
            '5v': 5.0, '3v3': 3.3, '3.3v': 3.3,
            '1v8': 1.8, '1.8v': 1.8,
        }
    
    def parse_schematic(self, sch_path: Path) -> SchematicData:
        """
        Parse a KiCad schematic file
        
        Args:
            sch_path: Path to .kicad_sch file
        
        Returns:
            SchematicData with components and nets
        """
        try:
            content = sch_path.read_text(errors='ignore')
            data = sexpdata.loads(content)
            
            result = SchematicData()
            
            # Parse S-expression tree
            if isinstance(data, list) and len(data) > 0:
                for item in data:
                    if not isinstance(item, list):
                        continue
                    
                    tag = str(item[0]) if len(item) > 0 else None
                    
                    if tag == 'symbol':
                        comp = self._parse_symbol(item)
                        if comp:
                            result.components.append(comp)
                    
                    elif tag == 'label' or tag == 'global_label':
                        label_name, voltage = self._parse_label(item)
                        if label_name:
                            if label_name not in result.nets:
                                result.nets[label_name] = SchematicNet(name=label_name)
                            result.nets[label_name].labels.append(label_name)
                            if voltage:
                                result.nets[label_name].voltage = voltage
                            
                            # Detect power/ground
                            result.nets[label_name].is_power = self._is_power_net(label_name)
                            result.nets[label_name].is_ground = self._is_ground_net(label_name)
                    
                    elif tag == 'power':
                        # Power flag - indicates power net
                        power_net = self._parse_power_flag(item)
                        if power_net:
                            result.power_flags.append(power_net)
            
            logger.info(f"Parsed schematic: {len(result.components)} components, {len(result.nets)} nets")
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse schematic {sch_path}: {e}", exc_info=True)
            return SchematicData()
    
    def parse_project_schematics(self, project_path: Path) -> SchematicData:
        """
        Parse all schematic files in a project
        
        Args:
            project_path: Path to project directory
        
        Returns:
            Combined SchematicData from all sheets
        """
        combined = SchematicData()
        
        # Find all .kicad_sch files
        sch_files = list(project_path.rglob('*.kicad_sch'))
        sch_files = [f for f in sch_files if not f.name.startswith('._') and '__MACOSX' not in str(f)]
        
        if not sch_files:
            logger.warning("No schematic files found")
            return combined
        
        logger.info(f"Found {len(sch_files)} schematic files")
        
        # Parse each file
        for sch_file in sch_files:
            logger.info(f"Parsing schematic: {sch_file.name}")
            sch_data = self.parse_schematic(sch_file)
            
            # Merge into combined
            combined.components.extend(sch_data.components)
            
            for net_name, net_data in sch_data.nets.items():
                if net_name in combined.nets:
                    # Merge with existing
                    combined.nets[net_name].labels.extend(net_data.labels)
                    if net_data.voltage:
                        combined.nets[net_name].voltage = net_data.voltage
                else:
                    combined.nets[net_name] = net_data
            
            combined.power_flags.extend(sch_data.power_flags)
            combined.global_labels.update(sch_data.global_labels)
        
        logger.info(f"Combined: {len(combined.components)} components, {len(combined.nets)} nets")
        return combined
    
    def _parse_symbol(self, symbol_expr: list) -> Optional[SchematicComponent]:
        """
        Parse a symbol (component instance) from schematic
        
        Format:
        (symbol (lib_id "Device:R") (at x y rotation)
          (property "Reference" "R1")
          (property "Value" "10k")
          (property "Voltage" "50V")  <- Custom properties
        )
        """
        try:
            lib_id = None
            reference = None
            value = None
            properties = {}
            position = (0, 0)
            
            for item in symbol_expr[1:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                
                tag = str(item[0])
                
                if tag == 'lib_id':
                    lib_id = str(item[1]).strip('"')
                
                elif tag == 'at':
                    # Position: (at x y rotation)
                    if len(item) >= 3:
                        position = (float(item[1]), float(item[2]))
                
                elif tag == 'property':
                    # Property: (property "Name" "Value")
                    if len(item) >= 3:
                        prop_name = str(item[1]).strip('"')
                        prop_value = str(item[2]).strip('"')
                        
                        if prop_name == 'Reference':
                            reference = prop_value
                        elif prop_name == 'Value':
                            value = prop_value
                        else:
                            properties[prop_name] = prop_value
            
            # Only return if we have minimum data
            if lib_id and reference:
                return SchematicComponent(
                    reference=reference,
                    value=value or "",
                    lib_id=lib_id,
                    properties=properties,
                    position=position
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse symbol: {e}")
            return None
    
    def _parse_label(self, label_expr: list) -> Tuple[Optional[str], Optional[float]]:
        """
        Parse a label or global_label
        
        Format:
        (label "GND" (at x y rotation))
        (global_label "230VAC" (at x y rotation))
        """
        try:
            label_name = None
            
            for item in label_expr[1:]:
                if isinstance(item, str):
                    label_name = item.strip('"')
                    break
            
            if label_name:
                # Try to extract voltage from name
                voltage = self._extract_voltage_from_name(label_name)
                return label_name, voltage
            
            return None, None
            
        except Exception as e:
            logger.debug(f"Failed to parse label: {e}")
            return None, None
    
    def _parse_power_flag(self, power_expr: list) -> Optional[str]:
        """Parse power flag (indicates power net)"""
        # Power flags in KiCad mark nets as power nets
        # Format varies, but typically has net name
        try:
            for item in power_expr:
                if isinstance(item, str):
                    return item.strip('"')
            return None
        except:
            return None
    
    def _extract_voltage_from_name(self, name: str) -> Optional[float]:
        """
        Extract voltage from net name
        
        Examples:
        - "230VAC" -> 230.0
        - "+12V" -> 12.0
        - "3V3" -> 3.3
        - "VCC_5V" -> 5.0
        """
        name_lower = name.lower().replace('_', '').replace('-', '')
        
        # Check known keywords
        for keyword, voltage in self.voltage_keywords.items():
            if keyword in name_lower:
                return voltage
        
        # Try to extract number followed by 'v'
        import re
        patterns = [
            r'(\d+)vac',  # 230VAC
            r'(\d+)vdc',  # 12VDC
            r'(\d+)v',    # 5V
            r'(\d+)\.(\d+)v',  # 3.3V
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name_lower)
            if match:
                if len(match.groups()) == 2:
                    # Decimal voltage like 3.3V
                    return float(f"{match.group(1)}.{match.group(2)}")
                else:
                    return float(match.group(1))
        
        return None
    
    def _is_power_net(self, name: str) -> bool:
        """Check if net name indicates a power net"""
        power_keywords = [
            'vcc', 'vdd', 'vss', 'vee', 'vbat', 'vbus',
            'v+', 'v-', '+', 'supply', 'power',
            '3v3', '5v', '12v', '24v', '48v', '230v'
        ]
        name_lower = name.lower()
        return any(kw in name_lower for kw in power_keywords)
    
    def _is_ground_net(self, name: str) -> bool:
        """Check if net name indicates a ground net"""
        ground_keywords = ['gnd', 'ground', 'earth', 'agnd', 'dgnd', 'pgnd', 'chassis']
        name_lower = name.lower()
        return any(kw in name_lower for kw in ground_keywords)
    
    def get_component_voltage_rating(self, component: SchematicComponent) -> Optional[float]:
        """
        Get voltage rating from component properties
        
        Looks for properties like:
        - "Voltage"
        - "Voltage_Rating"
        - "Max_Voltage"
        """
        # Check common property names
        for prop_name in ['Voltage', 'Voltage_Rating', 'Max_Voltage', 'V_max', 'Vmax']:
            if prop_name in component.properties:
                voltage_str = component.properties[prop_name]
                # Extract number from string like "50V" or "50"
                import re
                match = re.search(r'(\d+\.?\d*)', voltage_str)
                if match:
                    return float(match.group(1))
        
        return None
