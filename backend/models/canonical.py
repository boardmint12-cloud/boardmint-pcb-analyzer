"""
Canonical PCB Data Model
Universal representation of PCB data independent of source CAD tool
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class Units(str, Enum):
    """Measurement units"""
    MM = "mm"
    MIL = "mil"
    INCH = "inch"


class LayerType(str, Enum):
    """PCB layer types"""
    SIGNAL = "signal"
    POWER = "power"
    GROUND = "ground"
    MIXED = "mixed"
    DIELECTRIC = "dielectric"
    SOLDERMASK = "soldermask"
    SILKSCREEN = "silkscreen"
    PASTE = "paste"
    MECHANICAL = "mechanical"


class ComponentSide(str, Enum):
    """Component mounting side"""
    TOP = "top"
    BOTTOM = "bottom"


class NetClass(str, Enum):
    """Net classification"""
    SIGNAL = "signal"
    POWER = "power"
    GROUND = "ground"
    DIFFERENTIAL = "differential"
    HIGH_SPEED = "high_speed"
    HIGH_VOLTAGE = "high_voltage"


@dataclass
class Point:
    """2D point"""
    x: float
    y: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Point3D:
    """3D point"""
    x: float
    y: float
    z: float
    
    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class BoundingBox:
    """Bounding box"""
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    
    @property
    def width(self) -> float:
        return self.max_x - self.min_x
    
    @property
    def height(self) -> float:
        return self.max_y - self.min_y
    
    @property
    def center(self) -> Point:
        return Point(
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2
        )


@dataclass
class Layer:
    """PCB layer definition"""
    id: str
    name: str
    type: LayerType
    order: int  # Stack order (0 = top)
    thickness: Optional[float] = None  # in mm
    material: Optional[str] = None
    copper_weight: Optional[float] = None  # in oz/ft²
    is_signal: bool = False
    is_plane: bool = False


@dataclass
class Stackup:
    """PCB stackup definition"""
    layers: List[Layer]
    total_thickness: Optional[float] = None  # in mm
    layer_count: int = 0
    
    def __post_init__(self):
        self.layer_count = len([l for l in self.layers if l.type == LayerType.SIGNAL or l.type == LayerType.POWER])
    
    def get_signal_layers(self) -> List[Layer]:
        return [l for l in self.layers if l.is_signal]
    
    def get_layer_by_name(self, name: str) -> Optional[Layer]:
        return next((l for l in self.layers if l.name == name), None)


@dataclass
class Polygon:
    """2D polygon"""
    points: List[Point]
    holes: List[List[Point]] = field(default_factory=list)
    
    def bounding_box(self) -> BoundingBox:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return BoundingBox(min(xs), min(ys), max(xs), max(ys))


@dataclass
class Pad:
    """PCB pad"""
    id: str
    net: Optional[str] = None
    layer: Optional[str] = None
    position: Optional[Point] = None
    shape: str = "circle"  # circle, rect, oval, polygon
    size_x: float = 0.0
    size_y: float = 0.0
    drill: Optional[float] = None
    polygon: Optional[Polygon] = None


@dataclass
class Component:
    """PCB component"""
    refdes: str  # Reference designator (R1, U5, etc.)
    value: Optional[str] = None
    footprint: Optional[str] = None
    position: Optional[Point] = None
    rotation: float = 0.0  # degrees
    side: ComponentSide = ComponentSide.TOP
    layer: Optional[str] = None
    
    # Component attributes
    manufacturer: Optional[str] = None
    mpn: Optional[str] = None  # Manufacturer Part Number
    supplier: Optional[str] = None
    spn: Optional[str] = None  # Supplier Part Number
    description: Optional[str] = None
    package: Optional[str] = None
    
    # 3D info
    height: Optional[float] = None  # in mm
    model_path: Optional[str] = None
    
    # Pads
    pads: List[Pad] = field(default_factory=list)
    
    # Bounding box / courtyard
    bbox: Optional[BoundingBox] = None
    courtyard: Optional[Polygon] = None
    
    # Custom properties
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class Net:
    """Electrical net"""
    name: str
    net_class: NetClass = NetClass.SIGNAL
    pins: List[str] = field(default_factory=list)  # Component.Pad references (e.g., "U1.1")
    
    # Electrical properties
    is_power: bool = False
    is_ground: bool = False
    is_differential: bool = False
    is_high_voltage: bool = False
    voltage: Optional[float] = None  # nominal voltage
    current: Optional[float] = None  # max current
    
    # Differential pair info
    pair_name: Optional[str] = None  # e.g., "USB_D"
    is_positive: Optional[bool] = None  # True if _P, False if _N
    
    # High-speed properties
    impedance: Optional[float] = None  # target impedance in ohms
    max_length: Optional[float] = None  # max length in mm
    min_length: Optional[float] = None
    
    # Routing
    width: Optional[float] = None  # default trace width
    clearance: Optional[float] = None  # minimum clearance


@dataclass
class Track:
    """PCB track/trace segment"""
    id: str
    net: Optional[str] = None
    layer: Optional[str] = None
    start: Optional[Point] = None
    end: Optional[Point] = None
    width: float = 0.0
    
    def length(self) -> float:
        if self.start and self.end:
            return ((self.end.x - self.start.x)**2 + (self.end.y - self.start.y)**2)**0.5
        return 0.0


@dataclass
class Via:
    """PCB via"""
    id: str
    net: Optional[str] = None
    position: Optional[Point] = None
    size: float = 0.0  # outer diameter
    drill: float = 0.0  # drill diameter
    start_layer: Optional[str] = None
    end_layer: Optional[str] = None
    is_through: bool = True
    is_buried: bool = False
    is_blind: bool = False
    
    def annular_ring(self) -> float:
        """Calculate annular ring"""
        return (self.size - self.drill) / 2 if self.drill > 0 else 0.0


@dataclass
class Zone:
    """Copper pour / polygon zone"""
    id: str
    net: Optional[str] = None
    layer: Optional[str] = None
    polygon: Optional[Polygon] = None
    clearance: float = 0.0
    min_width: float = 0.0
    is_keepout: bool = False
    priority: int = 0


@dataclass
class Hole:
    """Non-plated hole (mounting, etc.)"""
    id: str
    position: Point
    diameter: float
    is_plated: bool = False
    is_slot: bool = False
    end_position: Optional[Point] = None  # For slots


@dataclass
class Rule:
    """Design rule"""
    name: str
    category: str  # "clearance", "width", "drill", etc.
    layer: Optional[str] = None
    net_class: Optional[str] = None
    value: float = 0.0
    enabled: bool = True


@dataclass
class RuleSet:
    """Collection of design rules"""
    name: str
    rules: List[Rule] = field(default_factory=list)
    
    def get_rule(self, name: str) -> Optional[Rule]:
        return next((r for r in self.rules if r.name == name), None)


@dataclass
class BoardOutline:
    """Board physical outline"""
    polygon: Polygon
    thickness: float = 1.6  # mm
    cutouts: List[Polygon] = field(default_factory=list)


@dataclass
class Board:
    """
    Canonical PCB board representation
    This is the universal model that all parsers translate to
    """
    id: str
    name: str
    units: Units = Units.MM
    
    # Physical
    outline: Optional[BoardOutline] = None
    stackup: Optional[Stackup] = None
    
    # Components
    components: List[Component] = field(default_factory=list)
    
    # Nets
    nets: List[Net] = field(default_factory=list)
    
    # Routing
    tracks: List[Track] = field(default_factory=list)
    vias: List[Via] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    
    # Holes
    holes: List[Hole] = field(default_factory=list)
    
    # Rules
    rules: Optional[RuleSet] = None
    
    # Metadata
    ecad_meta: Dict[str, any] = field(default_factory=dict)
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    version: Optional[str] = None
    
    # 3D models
    step_path: Optional[str] = None
    
    def get_component(self, refdes: str) -> Optional[Component]:
        """Get component by reference designator"""
        return next((c for c in self.components if c.refdes == refdes), None)
    
    def get_net(self, name: str) -> Optional[Net]:
        """Get net by name"""
        return next((n for n in self.nets if n.name == name), None)
    
    def get_layer_components(self, layer: str) -> List[Component]:
        """Get all components on a specific layer"""
        return [c for c in self.components if c.layer == layer or c.side.value == layer]
    
    def get_net_components(self, net_name: str) -> List[Component]:
        """Get all components connected to a net"""
        net = self.get_net(net_name)
        if not net:
            return []
        
        component_refs = set()
        for pin in net.pins:
            if "." in pin:
                refdes = pin.split(".")[0]
                component_refs.add(refdes)
        
        return [c for c in self.components if c.refdes in component_refs]
    
    def get_high_voltage_nets(self, threshold: float = 48.0) -> List[Net]:
        """Get all high-voltage nets above threshold"""
        return [n for n in self.nets if n.voltage and n.voltage >= threshold]
    
    def get_differential_pairs(self) -> List[Tuple[Net, Net]]:
        """Get all differential pairs"""
        pairs = []
        processed = set()
        
        for net in self.nets:
            if net.is_differential and net.pair_name and net.pair_name not in processed:
                # Find the complementary net
                complement = next(
                    (n for n in self.nets 
                     if n.pair_name == net.pair_name and n.is_positive != net.is_positive),
                    None
                )
                if complement:
                    if net.is_positive:
                        pairs.append((net, complement))
                    else:
                        pairs.append((complement, net))
                    processed.add(net.pair_name)
        
        return pairs
    
    def bounding_box(self) -> Optional[BoundingBox]:
        """Calculate board bounding box"""
        if not self.outline:
            return None
        return self.outline.polygon.bounding_box()
    
    def component_count(self) -> int:
        """Total component count"""
        return len(self.components)
    
    def net_count(self) -> int:
        """Total net count"""
        return len(self.nets)
    
    def layer_count(self) -> int:
        """Signal layer count"""
        if self.stackup:
            return self.stackup.layer_count
        return 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "units": self.units.value,
            "component_count": self.component_count(),
            "net_count": self.net_count(),
            "layer_count": self.layer_count(),
            "bbox": self.bounding_box().__dict__ if self.bounding_box() else None,
            "ecad_meta": self.ecad_meta,
        }
