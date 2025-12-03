"""
Base parser class and data structures
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Net:
    """Represents a net in the PCB"""
    name: str
    net_class: Optional[str] = None
    is_power: bool = False
    is_ground: bool = False
    is_mains: bool = False
    voltage_level: Optional[float] = None  # Voltage in volts (from schematic)
    is_high_voltage: bool = False  # True if >= 48V
    min_clearance: Optional[float] = None  # in mm
    pads: List[str] = field(default_factory=list)  # List of connected pads (e.g., ["R1.1", "U1.2"])
    

@dataclass
class Component:
    """Represents a component on the PCB"""
    reference: str
    value: str
    footprint: str
    mpn: Optional[str] = None  # Manufacturer Part Number
    x: Optional[float] = None  # X position in mm
    y: Optional[float] = None  # Y position in mm
    rotation: Optional[float] = None  # Rotation in degrees
    layer: Optional[str] = None  # Top or Bottom
    width: Optional[float] = None  # Bounding box width
    height: Optional[float] = None  # Bounding box height
    

@dataclass
class Track:
    """Represents a track/trace segment"""
    net_name: Optional[str] = None
    layer: Optional[str] = None
    width: float = 0.0  # mm
    x1: float = 0.0  # start x
    y1: float = 0.0  # start y
    x2: float = 0.0  # end x
    y2: float = 0.0  # end y


@dataclass
class Via:
    """Represents a via"""
    net_name: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    diameter: float = 0.0  # outer diameter (size)
    drill: float = 0.0  # drill diameter
    start_layer: Optional[str] = None
    end_layer: Optional[str] = None


@dataclass
class Zone:
    """Represents a copper zone/pour"""
    net_name: Optional[str] = None
    layer: Optional[str] = None
    outline_points: List[tuple] = field(default_factory=list)  # List of (x, y) tuples


@dataclass
class BoardInfo:
    """Basic board information"""
    size_x: float  # mm
    size_y: float  # mm
    layer_count: int
    min_track_width: Optional[float] = None  # mm
    min_via_size: Optional[float] = None  # mm
    copper_weight: Optional[int] = None  # oz
    

@dataclass
class ParsedPCBData:
    """Normalized PCB data structure from any EDA tool"""
    board_info: BoardInfo
    nets: List[Net] = field(default_factory=list)
    components: List[Component] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    vias: List[Via] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    files_found: Dict[str, bool] = field(default_factory=dict)
    

class BaseParser(ABC):
    """Base class for PCB parsers"""
    
    @abstractmethod
    def parse(self, project_path: str) -> ParsedPCBData:
        """
        Parse PCB project files
        
        Args:
            project_path: Path to extracted project directory
            
        Returns:
            ParsedPCBData object with normalized data
        """
        pass
    
    @staticmethod
    def detect_power_net(net_name: str) -> bool:
        """Detect if net is a power net based on naming"""
        power_keywords = [
            'vcc', 'vdd', 'vss', 'vee', 'v+', 'v-',
            '+3v', '+5v', '+12v', '+24v', '+48v',
            '3v3', '5v0', '12v', '24v', '3.3v', '5.0v'
        ]
        net_lower = net_name.lower()
        return any(kw in net_lower for kw in power_keywords)
    
    @staticmethod
    def detect_ground_net(net_name: str) -> bool:
        """Detect if net is a ground net"""
        ground_keywords = ['gnd', 'ground', 'earth', 'agnd', 'dgnd', 'pgnd']
        net_lower = net_name.lower()
        return any(kw in net_lower for kw in ground_keywords)
    
    @staticmethod
    def detect_mains_net(net_name: str) -> bool:
        """Detect if net is connected to mains/AC"""
        mains_keywords = [
            'ac', 'mains', 'l_in', 'n_in', 'line', 'neutral',
            '230v', '240v', '120v', 'l1', 'l2', 'l3'
        ]
        net_lower = net_name.lower().replace(' ', '_')
        return any(kw in net_lower for kw in mains_keywords)
