"""
Rule Profiles & Compliance Templates
Pre-configured rule sets for different board types, standards, and manufacturers
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProfileType(str, Enum):
    """Type of rule profile"""
    BOARD_TECH = "board_tech"
    STANDARD = "standard"
    MANUFACTURER = "manufacturer"
    CUSTOM = "custom"


@dataclass
class RuleValue:
    """Single rule value with optional tolerance"""
    value: float
    unit: str = "mm"
    min: Optional[float] = None
    max: Optional[float] = None
    tolerance: Optional[float] = None


@dataclass
class RuleProfile:
    """Complete rule profile"""
    id: str
    name: str
    description: str
    profile_type: ProfileType
    
    # Trace & spacing rules
    min_trace_width: RuleValue
    min_trace_spacing: RuleValue
    
    # Via rules
    min_via_diameter: RuleValue
    min_via_drill: RuleValue
    min_annular_ring: RuleValue
    max_aspect_ratio: Optional[float] = None  # depth/diameter
    
    # Drill rules
    min_hole_diameter: RuleValue = field(default_factory=lambda: RuleValue(0.2, "mm"))
    max_hole_diameter: Optional[RuleValue] = None
    min_hole_spacing: RuleValue = field(default_factory=lambda: RuleValue(0.3, "mm"))
    
    # Clearance rules (voltage-dependent)
    clearance_rules: Dict[str, RuleValue] = field(default_factory=dict)
    # Keys: "lv" (0-48V), "mv" (48-300V), "hv" (>300V)
    
    # Creepage rules (IPC-2221 based)
    creepage_rules: Dict[str, RuleValue] = field(default_factory=dict)
    # Keys same as clearance
    
    # Solder mask
    min_mask_sliver: RuleValue = field(default_factory=lambda: RuleValue(0.1, "mm"))
    mask_expansion: RuleValue = field(default_factory=lambda: RuleValue(0.05, "mm"))
    
    # Assembly rules
    min_component_spacing: RuleValue = field(default_factory=lambda: RuleValue(0.5, "mm"))
    min_edge_clearance: RuleValue = field(default_factory=lambda: RuleValue(0.5, "mm"))
    
    # Board constraints
    max_layers: Optional[int] = None
    min_layers: Optional[int] = None
    standard_thickness: List[float] = field(default_factory=lambda: [1.6])  # mm
    
    # Cost indicator
    cost_level: str = "medium"  # "low", "medium", "high"
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


class RuleProfileLibrary:
    """Library of pre-defined rule profiles"""
    
    def __init__(self):
        """Initialize with standard profiles"""
        self.profiles: Dict[str, RuleProfile] = {}
        self._load_standard_profiles()
    
    def _load_standard_profiles(self):
        """Load all standard profiles"""
        
        # ============= BOARD TECH PROFILES =============
        
        # 2-Layer Cheap Prototype (JLC, PCBWay, etc.)
        self.profiles["2l_cheap_proto"] = RuleProfile(
            id="2l_cheap_proto",
            name="2-Layer Cheap Prototype",
            description="Standard 2-layer board for cheap Chinese fabs (JLC, PCBWay, AllPCB)",
            profile_type=ProfileType.BOARD_TECH,
            min_trace_width=RuleValue(0.15, "mm"),  # 6mil
            min_trace_spacing=RuleValue(0.15, "mm"),
            min_via_diameter=RuleValue(0.45, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),  # 3mil
            max_aspect_ratio=10.0,
            clearance_rules={
                "lv": RuleValue(0.2, "mm"),
                "mv": RuleValue(1.5, "mm"),
                "hv": RuleValue(2.5, "mm"),
            },
            creepage_rules={
                "lv": RuleValue(0.3, "mm"),
                "mv": RuleValue(2.0, "mm"),
                "hv": RuleValue(3.0, "mm"),
            },
            max_layers=2,
            min_layers=2,
            cost_level="low",
            tags=["prototype", "cheap", "2layer", "jlc", "pcbway"]
        )
        
        # 4-Layer IoT/Consumer
        self.profiles["4l_iot"] = RuleProfile(
            id="4l_iot",
            name="4-Layer IoT/Consumer",
            description="Standard 4-layer for IoT, consumer electronics, moderate complexity",
            profile_type=ProfileType.BOARD_TECH,
            min_trace_width=RuleValue(0.127, "mm"),  # 5mil
            min_trace_spacing=RuleValue(0.127, "mm"),
            min_via_diameter=RuleValue(0.4, "mm"),
            min_via_drill=RuleValue(0.25, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            max_aspect_ratio=12.0,
            clearance_rules={
                "lv": RuleValue(0.15, "mm"),
                "mv": RuleValue(1.5, "mm"),
                "hv": RuleValue(2.5, "mm"),
            },
            creepage_rules={
                "lv": RuleValue(0.25, "mm"),
                "mv": RuleValue(2.0, "mm"),
                "hv": RuleValue(3.0, "mm"),
            },
            max_layers=4,
            min_layers=4,
            cost_level="medium",
            tags=["4layer", "iot", "consumer", "moderate"]
        )
        
        # 6-Layer HDI (High Density)
        self.profiles["6l_hdi"] = RuleProfile(
            id="6l_hdi",
            name="6-Layer HDI",
            description="High-density 6-layer for complex designs, BGA, high-speed",
            profile_type=ProfileType.BOARD_TECH,
            min_trace_width=RuleValue(0.1, "mm"),  # 4mil
            min_trace_spacing=RuleValue(0.1, "mm"),
            min_via_diameter=RuleValue(0.3, "mm"),
            min_via_drill=RuleValue(0.15, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            max_aspect_ratio=15.0,
            clearance_rules={
                "lv": RuleValue(0.1, "mm"),
                "mv": RuleValue(1.5, "mm"),
                "hv": RuleValue(2.5, "mm"),
            },
            creepage_rules={
                "lv": RuleValue(0.2, "mm"),
                "mv": RuleValue(2.0, "mm"),
                "hv": RuleValue(3.0, "mm"),
            },
            max_layers=6,
            min_layers=6,
            cost_level="high",
            tags=["6layer", "hdi", "bga", "high_speed", "complex"]
        )
        
        # High-Voltage Power Board
        self.profiles["hv_power"] = RuleProfile(
            id="hv_power",
            name="High-Voltage Power Board",
            description="AC mains / high-voltage power supply board (up to 300VAC)",
            profile_type=ProfileType.BOARD_TECH,
            min_trace_width=RuleValue(0.2, "mm"),
            min_trace_spacing=RuleValue(0.2, "mm"),  # Base spacing
            min_via_diameter=RuleValue(0.5, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.1, "mm"),
            clearance_rules={
                "lv": RuleValue(0.3, "mm"),
                "mv": RuleValue(2.5, "mm"),  # 48-300V
                "hv": RuleValue(4.0, "mm"),  # >300V
            },
            creepage_rules={
                "lv": RuleValue(0.5, "mm"),
                "mv": RuleValue(3.0, "mm"),  # IPC-2221 for 230VAC
                "hv": RuleValue(5.0, "mm"),
            },
            min_edge_clearance=RuleValue(3.0, "mm"),  # Keep HV away from edge
            cost_level="medium",
            tags=["power", "high_voltage", "mains", "ac", "230v"]
        )
        
        # ============= STANDARD / COMPLIANCE PROFILES =============
        
        # IPC-2221 Generic
        self.profiles["ipc2221_generic"] = RuleProfile(
            id="ipc2221_generic",
            name="IPC-2221 Generic",
            description="IPC-2221 generic standard with conservative clearances",
            profile_type=ProfileType.STANDARD,
            min_trace_width=RuleValue(0.13, "mm"),  # Table 6-1
            min_trace_spacing=RuleValue(0.13, "mm"),
            min_via_diameter=RuleValue(0.4, "mm"),
            min_via_drill=RuleValue(0.25, "mm"),
            min_annular_ring=RuleValue(0.05, "mm"),
            clearance_rules={
                "lv": RuleValue(0.13, "mm"),  # <50V
                "mv": RuleValue(1.5, "mm"),   # 50-300V
                "hv": RuleValue(2.5, "mm"),   # >300V
            },
            creepage_rules={
                "lv": RuleValue(0.25, "mm"),
                "mv": RuleValue(2.5, "mm"),   # IPC-2221 Table 6-2
                "hv": RuleValue(4.0, "mm"),
            },
            cost_level="medium",
            tags=["ipc", "standard", "generic", "conservative"]
        )
        
        # Medical Device (Conservative)
        self.profiles["medical_conservative"] = RuleProfile(
            id="medical_conservative",
            name="Medical Conservative",
            description="Conservative rules for medical devices (not certified, for reference)",
            profile_type=ProfileType.STANDARD,
            min_trace_width=RuleValue(0.15, "mm"),
            min_trace_spacing=RuleValue(0.15, "mm"),
            min_via_diameter=RuleValue(0.45, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.1, "mm"),
            clearance_rules={
                "lv": RuleValue(0.25, "mm"),
                "mv": RuleValue(2.0, "mm"),
                "hv": RuleValue(3.0, "mm"),
            },
            creepage_rules={
                "lv": RuleValue(0.4, "mm"),
                "mv": RuleValue(3.0, "mm"),
                "hv": RuleValue(5.0, "mm"),
            },
            min_component_spacing=RuleValue(1.0, "mm"),
            cost_level="high",
            tags=["medical", "conservative", "safety"]
        )
        
        # ============= MANUFACTURER PROFILES =============
        
        # JLCPCB Standard
        self.profiles["jlc_standard"] = RuleProfile(
            id="jlc_standard",
            name="JLCPCB Standard",
            description="JLCPCB standard capabilities (most common)",
            profile_type=ProfileType.MANUFACTURER,
            min_trace_width=RuleValue(0.127, "mm"),  # 5mil
            min_trace_spacing=RuleValue(0.127, "mm"),
            min_via_diameter=RuleValue(0.45, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            min_hole_diameter=RuleValue(0.2, "mm"),
            clearance_rules={
                "lv": RuleValue(0.15, "mm"),
                "mv": RuleValue(1.5, "mm"),
                "hv": RuleValue(2.5, "mm"),
            },
            creepage_rules={
                "lv": RuleValue(0.3, "mm"),
                "mv": RuleValue(2.0, "mm"),
                "hv": RuleValue(3.0, "mm"),
            },
            standard_thickness=[0.8, 1.0, 1.2, 1.6, 2.0],
            cost_level="low",
            tags=["jlcpcb", "manufacturer", "cheap", "china"]
        )
        
        # PCBWay Standard
        self.profiles["pcbway_standard"] = RuleProfile(
            id="pcbway_standard",
            name="PCBWay Standard",
            description="PCBWay standard capabilities",
            profile_type=ProfileType.MANUFACTURER,
            min_trace_width=RuleValue(0.127, "mm"),
            min_trace_spacing=RuleValue(0.127, "mm"),
            min_via_diameter=RuleValue(0.45, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            clearance_rules={
                "lv": RuleValue(0.15, "mm"),
                "mv": RuleValue(1.5, "mm"),
                "hv": RuleValue(2.5, "mm"),
            },
            creepage_rules={
                "lv": RuleValue(0.3, "mm"),
                "mv": RuleValue(2.0, "mm"),
                "hv": RuleValue(3.0, "mm"),
            },
            cost_level="low",
            tags=["pcbway", "manufacturer", "china"]
        )
        
        logger.info(f"Loaded {len(self.profiles)} rule profiles")
    
    def get_profile(self, profile_id: str) -> Optional[RuleProfile]:
        """Get profile by ID"""
        return self.profiles.get(profile_id)
    
    def list_profiles(self, profile_type: Optional[ProfileType] = None) -> List[RuleProfile]:
        """List all profiles, optionally filtered by type"""
        if profile_type:
            return [p for p in self.profiles.values() if p.profile_type == profile_type]
        return list(self.profiles.values())
    
    def get_profiles_by_tag(self, tag: str) -> List[RuleProfile]:
        """Get profiles with a specific tag"""
        return [p for p in self.profiles.values() if tag in p.tags]
    
    def recommend_profile(self, layer_count: int, voltage: Optional[float] = None, 
                         budget: str = "medium") -> Optional[RuleProfile]:
        """
        Recommend a profile based on board characteristics
        
        Args:
            layer_count: Number of layers
            voltage: Maximum operating voltage
            budget: "low", "medium", "high"
        
        Returns:
            Recommended profile
        """
        # High voltage board
        if voltage and voltage > 100:
            return self.get_profile("hv_power")
        
        # By layer count and budget
        if layer_count == 2:
            if budget == "low":
                return self.get_profile("2l_cheap_proto")
            return self.get_profile("ipc2221_generic")
        
        elif layer_count == 4:
            return self.get_profile("4l_iot")
        
        elif layer_count >= 6:
            return self.get_profile("6l_hdi")
        
        # Default
        return self.get_profile("ipc2221_generic")
    
    def profile_summary(self, profile_id: str) -> Dict:
        """Get human-readable summary of profile"""
        profile = self.get_profile(profile_id)
        if not profile:
            return {}
        
        return {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "type": profile.profile_type.value,
            "key_specs": {
                "min_trace": f"{profile.min_trace_width.value}{profile.min_trace_width.unit}",
                "min_spacing": f"{profile.min_trace_spacing.value}{profile.min_trace_spacing.unit}",
                "min_via": f"{profile.min_via_diameter.value}{profile.min_via_diameter.unit}",
                "min_drill": f"{profile.min_via_drill.value}{profile.min_via_drill.unit}",
            },
            "voltage_clearances": {
                k: f"{v.value}{v.unit}" for k, v in profile.clearance_rules.items()
            },
            "cost_level": profile.cost_level,
            "tags": profile.tags
        }
