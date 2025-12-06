"""
IPC-2581 Parser
Parses IPC-2581 XML files - the open standard for PCB data exchange

IPC-2581 is a vendor-neutral XML format that includes:
- Complete board geometry
- Component data with MPN
- Net connectivity  
- Stackup information
- Assembly data
- Test data
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from .base_parser import (
    BaseParser, ParsedPCBData, BoardInfo,
    Component, Net, Track, Via, Zone
)

logger = logging.getLogger(__name__)


# IPC-2581 namespace
IPC_NS = {
    'ipc': 'http://webstds.ipc.org/2581'
}


@dataclass
class StackupLayer:
    """PCB stackup layer"""
    name: str
    layer_type: str  # SIGNAL, PLANE, DIELECTRIC
    thickness_mm: float
    material: Optional[str] = None
    copper_weight_oz: Optional[float] = None


@dataclass
class IPC2581Data:
    """Parsed IPC-2581 data"""
    board_info: BoardInfo
    components: List[Component]
    nets: List[Net]
    tracks: List[Track]
    vias: List[Via]
    zones: List[Zone]
    stackup: List[StackupLayer] = field(default_factory=list)
    bom_data: List[Dict] = field(default_factory=list)


class IPC2581Parser(BaseParser):
    """
    Parser for IPC-2581 XML files
    
    IPC-2581 structure:
    <IPC-2581>
      <Content>
        <FunctionMode> - design/fabrication/assembly mode
        <StepRef> - reference to step
        <LayerRef> - layer references
        <DictionaryStandard> - standard definitions
        <DictionaryUser> - user definitions
        <DictionaryColor> - color definitions
      </Content>
      <Bom> - Bill of Materials
      <Ecad> - CAD data
        <CadHeader>
        <CadData>
          <Step> - design steps
            <Stackup> - layer stackup
            <Profile> - board outline
            <Package> - component packages
            <Component> - placed components
            <LayerFeature> - layer features (tracks, pads)
            <Pad> - pad definitions
          </Step>
        </CadData>
      </Ecad>
    </IPC-2581>
    """
    
    def __init__(self):
        """Initialize parser"""
        self.ns = IPC_NS
        self.packages: Dict[str, Dict] = {}
        self.pad_stacks: Dict[str, Dict] = {}
        self.units = 'mm'
        self.unit_scale = 1.0
    
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse IPC-2581 file
        
        Args:
            project_path: Path to directory or .xml file
            
        Returns:
            ParsedPCBData with normalized data
        """
        project_path = Path(project_path)
        
        # Find IPC-2581 file
        if project_path.is_file():
            ipc_file = project_path
        else:
            # Search for IPC-2581 files
            ipc_files = list(project_path.rglob('*.xml'))
            ipc_file = None
            
            for f in ipc_files:
                if self._is_ipc2581_file(f):
                    ipc_file = f
                    break
            
            if not ipc_file:
                logger.warning("No IPC-2581 file found")
                return self._empty_result()
        
        logger.info(f"Parsing IPC-2581: {ipc_file}")
        
        try:
            return self._parse_ipc2581(ipc_file)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return self._empty_result()
        except Exception as e:
            logger.error(f"IPC-2581 parsing failed: {e}", exc_info=True)
            return self._empty_result()
    
    def _is_ipc2581_file(self, file_path: Path) -> bool:
        """Check if file is IPC-2581 format"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.read(1000)
            return 'IPC-2581' in header or 'ipc.org/2581' in header
        except:
            return False
    
    def _parse_ipc2581(self, file_path: Path) -> ParsedPCBData:
        """Parse IPC-2581 XML file"""
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Handle namespace
        if root.tag.startswith('{'):
            ns_end = root.tag.find('}')
            namespace = root.tag[1:ns_end]
            self.ns = {'ipc': namespace}
        
        # Parse units
        self._parse_units(root)
        
        # Parse ECAD data
        ecad = root.find('.//Ecad', self.ns) or root.find('Ecad')
        if ecad is None:
            # Try without namespace
            ecad = self._find_element(root, 'Ecad')
        
        if ecad is None:
            logger.warning("No ECAD section found")
            return self._empty_result()
        
        # Parse CAD data
        cad_data = self._find_element(ecad, 'CadData')
        if cad_data is None:
            return self._empty_result()
        
        # Find step (design data)
        step = self._find_element(cad_data, 'Step')
        if step is None:
            return self._empty_result()
        
        # Parse components
        board_info = self._parse_board_info(step)
        components = self._parse_components(step)
        nets = self._parse_nets(root, step)
        tracks, vias = self._parse_layer_features(step)
        
        # Parse BOM if present
        bom = self._find_element(root, 'Bom')
        if bom is not None:
            self._enhance_with_bom(components, bom)
        
        return ParsedPCBData(
            board_info=board_info,
            components=components,
            nets=nets,
            tracks=tracks,
            vias=vias,
            zones=[],
            files_found={'ipc2581': True}
        )
    
    def _find_element(self, parent: ET.Element, tag: str) -> Optional[ET.Element]:
        """Find element with or without namespace"""
        # Try with namespace
        for ns_prefix, ns_uri in self.ns.items():
            elem = parent.find(f'{{{ns_uri}}}{tag}')
            if elem is not None:
                return elem
        
        # Try without namespace
        elem = parent.find(tag)
        if elem is not None:
            return elem
        
        # Try recursive search
        for child in parent:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag == tag:
                return child
        
        return None
    
    def _find_all_elements(self, parent: ET.Element, tag: str) -> List[ET.Element]:
        """Find all elements with or without namespace"""
        results = []
        
        for child in parent:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag == tag:
                results.append(child)
        
        return results
    
    def _parse_units(self, root: ET.Element):
        """Parse unit specification"""
        content = self._find_element(root, 'Content')
        if content is not None:
            units_elem = self._find_element(content, 'Units')
            if units_elem is not None:
                self.units = units_elem.get('units', 'mm').lower()
                if self.units == 'inch':
                    self.unit_scale = 25.4
                elif self.units == 'mil':
                    self.unit_scale = 0.0254
    
    def _parse_board_info(self, step: ET.Element) -> BoardInfo:
        """Parse board information from Step element"""
        # Get profile (board outline)
        profile = self._find_element(step, 'Profile')
        
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        if profile is not None:
            # Parse polygon outline
            polygon = self._find_element(profile, 'Polygon')
            if polygon is not None:
                for point in self._find_all_elements(polygon, 'PolyStepSegment'):
                    x = float(point.get('x', 0)) * self.unit_scale
                    y = float(point.get('y', 0)) * self.unit_scale
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        
        size_x = max_x - min_x if max_x != float('-inf') else 100.0
        size_y = max_y - min_y if max_y != float('-inf') else 100.0
        
        # Parse stackup for layer count
        layer_count = 2
        stackup = self._find_element(step, 'Stackup')
        if stackup is not None:
            copper_layers = 0
            for group in self._find_all_elements(stackup, 'StackupGroup'):
                for layer in self._find_all_elements(group, 'StackupLayer'):
                    layer_type = layer.get('layerFunctionValue', '')
                    if layer_type in ('SIGNAL', 'PLANE', 'POWER', 'GROUND'):
                        copper_layers += 1
            layer_count = max(2, copper_layers)
        
        return BoardInfo(
            size_x=size_x,
            size_y=size_y,
            layer_count=layer_count
        )
    
    def _parse_components(self, step: ET.Element) -> List[Component]:
        """Parse component placements"""
        components = []
        
        # First parse packages (footprints)
        for package in self._find_all_elements(step, 'Package'):
            pkg_name = package.get('name', '')
            self.packages[pkg_name] = {
                'name': pkg_name,
                'pins': len(self._find_all_elements(package, 'Pin'))
            }
        
        # Parse component placements
        for comp in self._find_all_elements(step, 'Component'):
            ref = comp.get('refDes', '')
            pkg_ref = comp.get('packageRef', '')
            
            # Get location
            location = self._find_element(comp, 'Location')
            x, y, rotation = 0.0, 0.0, 0.0
            if location is not None:
                x = float(location.get('x', 0)) * self.unit_scale
                y = float(location.get('y', 0)) * self.unit_scale
                rotation = float(location.get('rotation', 0))
            
            # Determine side
            layer = self._find_element(comp, 'LayerRef')
            side = 'F.Cu'
            if layer is not None:
                layer_name = layer.get('name', '').lower()
                if 'bot' in layer_name or 'bottom' in layer_name:
                    side = 'B.Cu'
            
            components.append(Component(
                reference=ref,
                value='',  # Will be filled from BOM
                footprint=pkg_ref,
                x=x,
                y=y,
                rotation=rotation,
                layer=side
            ))
        
        return components
    
    def _parse_nets(self, root: ET.Element, step: ET.Element) -> List[Net]:
        """Parse net information"""
        nets = []
        net_map = {}
        
        # Parse from LogicalNet section if present
        for logical_net in self._find_all_elements(root, 'LogicalNet'):
            net_name = logical_net.get('name', '')
            
            # Collect pins
            pads = []
            for pin_ref in self._find_all_elements(logical_net, 'PinRef'):
                comp = pin_ref.get('componentRef', '')
                pin = pin_ref.get('pin', '')
                pads.append(f"{comp}.{pin}")
            
            net_map[net_name] = pads
        
        # Also check NetPoint elements in step
        for layer_feature in self._find_all_elements(step, 'LayerFeature'):
            for set_elem in self._find_all_elements(layer_feature, 'Set'):
                net_name = set_elem.get('net', '')
                if net_name and net_name not in net_map:
                    net_map[net_name] = []
        
        # Build net list
        for net_name, pads in net_map.items():
            nets.append(Net(
                name=net_name,
                is_power=self.detect_power_net(net_name),
                is_ground=self.detect_ground_net(net_name),
                is_mains=self.detect_mains_net(net_name),
                pads=pads
            ))
        
        return nets
    
    def _parse_layer_features(self, step: ET.Element) -> Tuple[List[Track], List[Via]]:
        """Parse tracks and vias from LayerFeature elements"""
        tracks = []
        vias = []
        
        for layer_feature in self._find_all_elements(step, 'LayerFeature'):
            layer_name = layer_feature.get('layerRef', '')
            
            for set_elem in self._find_all_elements(layer_feature, 'Set'):
                net_name = set_elem.get('net', '')
                
                # Parse lines (tracks)
                for line in self._find_all_elements(set_elem, 'Line'):
                    start_x = float(line.get('startX', 0)) * self.unit_scale
                    start_y = float(line.get('startY', 0)) * self.unit_scale
                    end_x = float(line.get('endX', 0)) * self.unit_scale
                    end_y = float(line.get('endY', 0)) * self.unit_scale
                    width = float(line.get('lineWidth', 0.2)) * self.unit_scale
                    
                    tracks.append(Track(
                        net_name=net_name,
                        layer=layer_name,
                        width=width,
                        x1=start_x,
                        y1=start_y,
                        x2=end_x,
                        y2=end_y
                    ))
                
                # Parse vias
                for via in self._find_all_elements(set_elem, 'Via'):
                    x = float(via.get('x', 0)) * self.unit_scale
                    y = float(via.get('y', 0)) * self.unit_scale
                    
                    vias.append(Via(
                        net_name=net_name,
                        x=x,
                        y=y,
                        diameter=0.6,  # Default
                        drill=0.3
                    ))
        
        return tracks, vias
    
    def _enhance_with_bom(self, components: List[Component], bom: ET.Element):
        """Enhance components with BOM data"""
        # Create lookup by refDes
        comp_map = {c.reference: c for c in components}
        
        for bom_item in self._find_all_elements(bom, 'BomItem'):
            for ref_des in self._find_all_elements(bom_item, 'RefDes'):
                ref = ref_des.get('name', '')
                
                if ref in comp_map:
                    # Get characteristics
                    chars = self._find_element(bom_item, 'Characteristics')
                    if chars is not None:
                        value = chars.get('value', '')
                        comp_map[ref].value = value
                    
                    # Get MPN
                    approved = self._find_element(bom_item, 'ApprovedManufacturerPart')
                    if approved is not None:
                        mpn = approved.get('mpn', '')
                        comp_map[ref].mpn = mpn
    
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


def parse_ipc2581_file(file_path: str) -> ParsedPCBData:
    """Convenience function"""
    parser = IPC2581Parser()
    return parser.parse(file_path)
