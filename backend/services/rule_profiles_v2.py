"""
Rule Profiles V2 - Industry Standard Compliance Templates
Pre-configured rule sets based on IPC-2221A, IEC 62368-1, and manufacturer specs

This module provides comprehensive rule profiles for:
- Board technology levels (2L proto, 4L IoT, 6L HDI, etc.)
- Safety compliance (IPC-2221A, IEC 62368-1, UL, CE)
- Manufacturer capabilities (JLCPCB, PCBWay, OSHPark, etc.)
- Application domains (Consumer, Industrial, Medical, Automotive)
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Import industry standards
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rules.standards.ipc_2221a import IPC2221A, ConductorType
from rules.standards.iec_62368 import IEC62368, InsulationType, PollutionDegree, MaterialGroup
from rules.standards.current_capacity import CurrentCapacity, LayerPosition

logger = logging.getLogger(__name__)


class ProfileType(str, Enum):
    """Type of rule profile"""
    BOARD_TECH = "board_tech"           # PCB technology level
    STANDARD = "standard"               # Industry standard compliance
    MANUFACTURER = "manufacturer"       # Fab house capabilities
    APPLICATION = "application"         # Application domain
    CUSTOM = "custom"                   # User-defined


class ComplianceLevel(str, Enum):
    """Safety/Quality compliance level"""
    PROTOTYPE = "prototype"             # No compliance requirements
    CONSUMER = "consumer"               # Basic consumer safety
    INDUSTRIAL = "industrial"           # Industrial equipment
    MEDICAL = "medical"                 # Medical device (IEC 60601)
    AUTOMOTIVE = "automotive"           # Automotive (AEC-Q100)
    AEROSPACE = "aerospace"             # Aerospace/Military


@dataclass
class RuleValue:
    """Single rule value with units and tolerances"""
    value: float
    unit: str = "mm"
    min: Optional[float] = None
    max: Optional[float] = None
    tolerance: Optional[float] = None
    source: Optional[str] = None        # Standard reference


@dataclass
class VoltageClassRules:
    """Voltage-dependent clearance and creepage rules"""
    voltage_class: str                  # "SELV", "LV", "MV", "HV", "MAINS"
    voltage_min: float                  # Minimum voltage for this class
    voltage_max: float                  # Maximum voltage for this class
    clearance: RuleValue                # Minimum air gap
    creepage: RuleValue                 # Minimum surface distance
    insulation_type: str                # "functional", "basic", "reinforced"


@dataclass
class RuleProfile:
    """Complete rule profile with industry-standard parameters"""
    id: str
    name: str
    description: str
    profile_type: ProfileType
    
    # Compliance
    compliance_level: ComplianceLevel = ComplianceLevel.CONSUMER
    standards_referenced: List[str] = field(default_factory=list)
    
    # ==========================================================================
    # TRACE & SPACING RULES
    # ==========================================================================
    min_trace_width: RuleValue = field(default_factory=lambda: RuleValue(0.15, "mm"))
    min_trace_spacing: RuleValue = field(default_factory=lambda: RuleValue(0.15, "mm"))
    
    # Power trace rules (current-based)
    power_trace_rules: Dict[float, RuleValue] = field(default_factory=dict)  # Current (A) -> Width
    
    # ==========================================================================
    # VIA RULES
    # ==========================================================================
    min_via_diameter: RuleValue = field(default_factory=lambda: RuleValue(0.45, "mm"))
    min_via_drill: RuleValue = field(default_factory=lambda: RuleValue(0.3, "mm"))
    min_annular_ring: RuleValue = field(default_factory=lambda: RuleValue(0.075, "mm"))
    max_aspect_ratio: float = 10.0
    
    # Via types supported
    supports_blind_vias: bool = False
    supports_buried_vias: bool = False
    supports_microvias: bool = False
    min_microvia_drill: Optional[RuleValue] = None
    
    # ==========================================================================
    # HOLE & DRILL RULES
    # ==========================================================================
    min_hole_diameter: RuleValue = field(default_factory=lambda: RuleValue(0.2, "mm"))
    max_hole_diameter: RuleValue = field(default_factory=lambda: RuleValue(6.3, "mm"))
    min_hole_to_hole: RuleValue = field(default_factory=lambda: RuleValue(0.3, "mm"))
    min_hole_to_edge: RuleValue = field(default_factory=lambda: RuleValue(0.4, "mm"))
    
    # ==========================================================================
    # VOLTAGE-DEPENDENT CLEARANCE/CREEPAGE (IPC-2221A / IEC 62368-1)
    # ==========================================================================
    voltage_rules: List[VoltageClassRules] = field(default_factory=list)
    
    # Simplified clearance lookup by voltage class
    clearance_rules: Dict[str, RuleValue] = field(default_factory=dict)
    creepage_rules: Dict[str, RuleValue] = field(default_factory=dict)
    
    # ==========================================================================
    # SOLDER MASK RULES
    # ==========================================================================
    min_mask_dam: RuleValue = field(default_factory=lambda: RuleValue(0.1, "mm"))
    mask_expansion: RuleValue = field(default_factory=lambda: RuleValue(0.05, "mm"))
    min_mask_to_edge: RuleValue = field(default_factory=lambda: RuleValue(0.3, "mm"))
    
    # ==========================================================================
    # SILKSCREEN RULES
    # ==========================================================================
    min_silk_width: RuleValue = field(default_factory=lambda: RuleValue(0.15, "mm"))
    min_silk_height: RuleValue = field(default_factory=lambda: RuleValue(0.8, "mm"))
    min_silk_to_pad: RuleValue = field(default_factory=lambda: RuleValue(0.15, "mm"))
    
    # ==========================================================================
    # ASSEMBLY RULES
    # ==========================================================================
    min_component_spacing: RuleValue = field(default_factory=lambda: RuleValue(0.5, "mm"))
    min_edge_clearance: RuleValue = field(default_factory=lambda: RuleValue(0.5, "mm"))
    min_component_to_via: RuleValue = field(default_factory=lambda: RuleValue(0.25, "mm"))
    
    # ==========================================================================
    # BOARD CONSTRAINTS
    # ==========================================================================
    min_layers: int = 1
    max_layers: int = 32
    standard_thickness_mm: List[float] = field(default_factory=lambda: [1.6])
    copper_weights_oz: List[float] = field(default_factory=lambda: [1.0])
    
    # ==========================================================================
    # HIGH-SPEED / IMPEDANCE RULES
    # ==========================================================================
    impedance_tolerance_percent: float = 10.0
    min_diff_pair_spacing: RuleValue = field(default_factory=lambda: RuleValue(0.15, "mm"))
    max_diff_pair_skew_mm: float = 0.1
    
    # ==========================================================================
    # THERMAL RULES
    # ==========================================================================
    max_temp_rise_c: float = 10.0
    thermal_via_drill: RuleValue = field(default_factory=lambda: RuleValue(0.3, "mm"))
    thermal_via_pitch: RuleValue = field(default_factory=lambda: RuleValue(1.0, "mm"))
    
    # ==========================================================================
    # METADATA
    # ==========================================================================
    cost_level: str = "medium"          # "low", "medium", "high", "premium"
    lead_time_days: int = 7
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


class RuleProfileLibrary:
    """
    Library of pre-defined rule profiles based on industry standards
    """
    
    def __init__(self):
        """Initialize with standard profiles"""
        self.profiles: Dict[str, RuleProfile] = {}
        self._load_standard_profiles()
    
    def _create_voltage_rules(
        self,
        compliance: ComplianceLevel
    ) -> Tuple[List[VoltageClassRules], Dict[str, RuleValue], Dict[str, RuleValue]]:
        """
        Create voltage-dependent rules based on compliance level
        
        Uses IPC-2221A for basic requirements, IEC 62368-1 for safety-critical
        """
        voltage_rules = []
        clearance_rules = {}
        creepage_rules = {}
        
        if compliance == ComplianceLevel.PROTOTYPE:
            # Minimal rules for prototypes
            voltage_rules = [
                VoltageClassRules("SELV", 0, 50, RuleValue(0.15, "mm"), RuleValue(0.3, "mm"), "functional"),
                VoltageClassRules("LV", 50, 120, RuleValue(0.5, "mm"), RuleValue(1.0, "mm"), "basic"),
                VoltageClassRules("HV", 120, 500, RuleValue(2.0, "mm"), RuleValue(4.0, "mm"), "basic"),
            ]
        
        elif compliance in [ComplianceLevel.CONSUMER, ComplianceLevel.INDUSTRIAL]:
            # IPC-2221A based rules
            voltage_rules = [
                VoltageClassRules(
                    "SELV", 0, 48,
                    RuleValue(IPC2221A.get_clearance(48, ConductorType.B2_EXTERNAL_UNCOATED), "mm", source="IPC-2221A"),
                    RuleValue(IPC2221A.get_creepage(48), "mm", source="IPC-2221A"),
                    "functional"
                ),
                VoltageClassRules(
                    "LV", 48, 150,
                    RuleValue(IPC2221A.get_clearance(150, ConductorType.B2_EXTERNAL_UNCOATED), "mm", source="IPC-2221A"),
                    RuleValue(IPC2221A.get_creepage(150), "mm", source="IPC-2221A"),
                    "basic"
                ),
                VoltageClassRules(
                    "MV", 150, 300,
                    RuleValue(IPC2221A.get_clearance(300, ConductorType.B2_EXTERNAL_UNCOATED), "mm", source="IPC-2221A"),
                    RuleValue(IPC2221A.get_creepage(300), "mm", source="IPC-2221A"),
                    "basic"
                ),
                VoltageClassRules(
                    "HV", 300, 1000,
                    RuleValue(IPC2221A.get_clearance(500, ConductorType.B2_EXTERNAL_UNCOATED, 1.5), "mm", source="IPC-2221A"),
                    RuleValue(IPC2221A.get_creepage(500, safety_margin=1.5), "mm", source="IPC-2221A"),
                    "reinforced"
                ),
            ]
        
        elif compliance == ComplianceLevel.MEDICAL:
            # IEC 62368-1 / IEC 60601 based - reinforced insulation everywhere
            voltage_rules = [
                VoltageClassRules(
                    "SELV", 0, 48,
                    RuleValue(IEC62368.get_clearance(48, InsulationType.REINFORCED), "mm", source="IEC 62368-1"),
                    RuleValue(IEC62368.get_creepage(48, InsulationType.REINFORCED), "mm", source="IEC 62368-1"),
                    "reinforced"
                ),
                VoltageClassRules(
                    "MAINS", 48, 264,  # Up to 240VAC
                    RuleValue(IEC62368.get_clearance(340, InsulationType.REINFORCED), "mm", source="IEC 62368-1"),
                    RuleValue(IEC62368.get_creepage(264, InsulationType.REINFORCED, PollutionDegree.PD2), "mm", source="IEC 62368-1"),
                    "reinforced"
                ),
            ]
        
        else:
            # Default to IPC-2221A
            voltage_rules = [
                VoltageClassRules("LV", 0, 50, RuleValue(0.2, "mm"), RuleValue(0.4, "mm"), "basic"),
                VoltageClassRules("MV", 50, 300, RuleValue(1.5, "mm"), RuleValue(2.5, "mm"), "basic"),
                VoltageClassRules("HV", 300, 1000, RuleValue(3.0, "mm"), RuleValue(5.0, "mm"), "reinforced"),
            ]
        
        # Convert to simplified dicts
        for vr in voltage_rules:
            clearance_rules[vr.voltage_class.lower()] = vr.clearance
            creepage_rules[vr.voltage_class.lower()] = vr.creepage
        
        return voltage_rules, clearance_rules, creepage_rules
    
    def _create_power_trace_rules(self, copper_oz: float = 1.0) -> Dict[float, RuleValue]:
        """
        Create current-based trace width rules using IPC-2152
        """
        thickness_mm = CurrentCapacity.copper_weight_to_thickness(copper_oz)
        rules = {}
        
        for current in [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0]:
            width, _ = CurrentCapacity.calculate_trace_width_for_current(
                current_a=current,
                thickness_mm=thickness_mm,
                temp_rise_c=10.0,
                layer=LayerPosition.EXTERNAL
            )
            rules[current] = RuleValue(
                round(width, 3), "mm",
                source=f"IPC-2152 for {current}A @ {copper_oz}oz Cu, 10°C rise"
            )
        
        return rules
    
    def _load_standard_profiles(self):
        """Load all standard profiles"""
        
        # ==================================================================
        # BOARD TECHNOLOGY PROFILES
        # ==================================================================
        
        # 2-Layer Cheap Prototype
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.PROTOTYPE)
        self.profiles["2l_cheap_proto"] = RuleProfile(
            id="2l_cheap_proto",
            name="2-Layer Cheap Prototype",
            description="Standard 2-layer board for budget prototyping (JLC, PCBWay, AllPCB)",
            profile_type=ProfileType.BOARD_TECH,
            compliance_level=ComplianceLevel.PROTOTYPE,
            standards_referenced=["IPC-2221A Class 1"],
            min_trace_width=RuleValue(0.15, "mm", source="JLC/PCBWay standard"),
            min_trace_spacing=RuleValue(0.15, "mm"),
            min_via_diameter=RuleValue(0.45, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            max_aspect_ratio=10.0,
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            power_trace_rules=self._create_power_trace_rules(1.0),
            min_layers=2,
            max_layers=2,
            standard_thickness_mm=[0.8, 1.0, 1.2, 1.6],
            copper_weights_oz=[1.0, 2.0],
            cost_level="low",
            lead_time_days=5,
            tags=["prototype", "cheap", "2layer", "jlcpcb", "pcbway"]
        )
        
        # 4-Layer IoT/Consumer
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.CONSUMER)
        self.profiles["4l_iot"] = RuleProfile(
            id="4l_iot",
            name="4-Layer IoT/Consumer",
            description="4-layer board for IoT devices, consumer electronics, moderate complexity",
            profile_type=ProfileType.BOARD_TECH,
            compliance_level=ComplianceLevel.CONSUMER,
            standards_referenced=["IPC-2221A Class 2", "IPC-A-610 Class 2"],
            min_trace_width=RuleValue(0.127, "mm", source="IPC-2221A 5mil"),
            min_trace_spacing=RuleValue(0.127, "mm"),
            min_via_diameter=RuleValue(0.4, "mm"),
            min_via_drill=RuleValue(0.25, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            max_aspect_ratio=12.0,
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            power_trace_rules=self._create_power_trace_rules(1.0),
            min_layers=4,
            max_layers=4,
            standard_thickness_mm=[1.2, 1.6],
            copper_weights_oz=[0.5, 1.0],
            impedance_tolerance_percent=10.0,
            cost_level="medium",
            lead_time_days=7,
            tags=["4layer", "iot", "consumer", "moderate"]
        )
        
        # 6-Layer HDI
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.INDUSTRIAL)
        self.profiles["6l_hdi"] = RuleProfile(
            id="6l_hdi",
            name="6-Layer HDI",
            description="High-density 6-layer for complex designs, BGAs, high-speed interfaces",
            profile_type=ProfileType.BOARD_TECH,
            compliance_level=ComplianceLevel.INDUSTRIAL,
            standards_referenced=["IPC-2221A Class 2", "IPC-6012 Class 2"],
            min_trace_width=RuleValue(0.1, "mm", source="HDI 4mil"),
            min_trace_spacing=RuleValue(0.1, "mm"),
            min_via_diameter=RuleValue(0.3, "mm"),
            min_via_drill=RuleValue(0.15, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            max_aspect_ratio=15.0,
            supports_blind_vias=True,
            supports_microvias=True,
            min_microvia_drill=RuleValue(0.1, "mm"),
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            power_trace_rules=self._create_power_trace_rules(1.0),
            min_layers=6,
            max_layers=6,
            standard_thickness_mm=[1.2, 1.6, 2.0],
            copper_weights_oz=[0.5, 1.0],
            impedance_tolerance_percent=8.0,
            cost_level="high",
            lead_time_days=10,
            tags=["6layer", "hdi", "bga", "high_speed", "complex"]
        )
        
        # High-Voltage Power Board
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.INDUSTRIAL)
        # Override with stricter mains safety
        mains_safety = IEC62368.get_mains_safety_requirements("UNIVERSAL", InsulationType.REINFORCED)
        cr["mains"] = RuleValue(mains_safety.clearance_mm, "mm", source="IEC 62368-1")
        cp["mains"] = RuleValue(mains_safety.creepage_mm, "mm", source="IEC 62368-1")
        
        self.profiles["hv_power"] = RuleProfile(
            id="hv_power",
            name="High-Voltage Power Board",
            description="AC mains / high-voltage power supply board (up to 300VAC)",
            profile_type=ProfileType.BOARD_TECH,
            compliance_level=ComplianceLevel.INDUSTRIAL,
            standards_referenced=["IPC-2221A", "IEC 62368-1", "UL 60950-1"],
            min_trace_width=RuleValue(0.2, "mm"),
            min_trace_spacing=RuleValue(0.2, "mm"),
            min_via_diameter=RuleValue(0.5, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.1, "mm"),
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            power_trace_rules=self._create_power_trace_rules(2.0),
            min_edge_clearance=RuleValue(3.0, "mm", source="Safety clearance from board edge"),
            min_layers=2,
            max_layers=4,
            standard_thickness_mm=[1.6, 2.0],
            copper_weights_oz=[2.0, 3.0],
            max_temp_rise_c=20.0,
            cost_level="medium",
            tags=["power", "high_voltage", "mains", "ac", "230v", "safety"]
        )
        
        # ==================================================================
        # STANDARD / COMPLIANCE PROFILES
        # ==================================================================
        
        # IPC-2221A Generic
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.INDUSTRIAL)
        self.profiles["ipc2221_class2"] = RuleProfile(
            id="ipc2221_class2",
            name="IPC-2221A Class 2",
            description="IPC-2221A Class 2 dedicated service electronic products",
            profile_type=ProfileType.STANDARD,
            compliance_level=ComplianceLevel.INDUSTRIAL,
            standards_referenced=["IPC-2221A Class 2"],
            min_trace_width=RuleValue(0.1, "mm", source="IPC-2221A Table 6-1"),
            min_trace_spacing=RuleValue(0.1, "mm"),
            min_via_diameter=RuleValue(0.4, "mm"),
            min_via_drill=RuleValue(0.25, "mm"),
            min_annular_ring=RuleValue(0.05, "mm", source="IPC-2221A external"),
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            cost_level="medium",
            tags=["ipc", "standard", "class2", "industrial"]
        )
        
        # Medical Device
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.MEDICAL)
        self.profiles["medical_iec60601"] = RuleProfile(
            id="medical_iec60601",
            name="Medical Device IEC 60601",
            description="Medical electrical equipment per IEC 60601-1",
            profile_type=ProfileType.STANDARD,
            compliance_level=ComplianceLevel.MEDICAL,
            standards_referenced=["IEC 60601-1", "IEC 62368-1", "IPC-2221A Class 3"],
            min_trace_width=RuleValue(0.15, "mm"),
            min_trace_spacing=RuleValue(0.15, "mm"),
            min_via_diameter=RuleValue(0.45, "mm"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.1, "mm"),
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            min_component_spacing=RuleValue(1.0, "mm"),
            min_edge_clearance=RuleValue(1.0, "mm"),
            cost_level="premium",
            tags=["medical", "iec60601", "safety", "class3"]
        )
        
        # ==================================================================
        # MANUFACTURER PROFILES
        # ==================================================================
        
        # JLCPCB Standard
        vr, cr, cp = self._create_voltage_rules(ComplianceLevel.CONSUMER)
        self.profiles["jlcpcb_standard"] = RuleProfile(
            id="jlcpcb_standard",
            name="JLCPCB Standard",
            description="JLCPCB standard manufacturing capabilities",
            profile_type=ProfileType.MANUFACTURER,
            compliance_level=ComplianceLevel.CONSUMER,
            standards_referenced=["JLCPCB Design Rules"],
            min_trace_width=RuleValue(0.127, "mm", source="JLCPCB 5mil"),
            min_trace_spacing=RuleValue(0.127, "mm"),
            min_via_diameter=RuleValue(0.45, "mm", source="JLCPCB min via"),
            min_via_drill=RuleValue(0.3, "mm"),
            min_annular_ring=RuleValue(0.075, "mm"),
            max_aspect_ratio=10.0,
            min_hole_diameter=RuleValue(0.2, "mm"),
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            standard_thickness_mm=[0.8, 1.0, 1.2, 1.6, 2.0],
            copper_weights_oz=[1.0, 2.0],
            cost_level="low",
            lead_time_days=5,
            tags=["jlcpcb", "manufacturer", "cheap", "china"]
        )
        
        # OSHPark (Premium US Fab)
        self.profiles["oshpark"] = RuleProfile(
            id="oshpark",
            name="OSHPark",
            description="OSHPark premium purple boards",
            profile_type=ProfileType.MANUFACTURER,
            compliance_level=ComplianceLevel.CONSUMER,
            standards_referenced=["OSHPark Design Rules"],
            min_trace_width=RuleValue(0.152, "mm", source="OSHPark 6mil"),
            min_trace_spacing=RuleValue(0.152, "mm"),
            min_via_diameter=RuleValue(0.4, "mm"),
            min_via_drill=RuleValue(0.254, "mm", source="OSHPark 10mil drill"),
            min_annular_ring=RuleValue(0.127, "mm"),
            voltage_rules=vr,
            clearance_rules=cr,
            creepage_rules=cp,
            standard_thickness_mm=[1.6],
            copper_weights_oz=[1.0, 2.0],
            cost_level="medium",
            lead_time_days=12,
            tags=["oshpark", "manufacturer", "usa", "purple"]
        )
        
        logger.info(f"Loaded {len(self.profiles)} rule profiles")
    
    def get_profile(self, profile_id: str) -> Optional[RuleProfile]:
        """Get profile by ID"""
        return self.profiles.get(profile_id)
    
    def list_profiles(
        self,
        profile_type: Optional[ProfileType] = None,
        compliance_level: Optional[ComplianceLevel] = None
    ) -> List[RuleProfile]:
        """List profiles with optional filtering"""
        profiles = list(self.profiles.values())
        
        if profile_type:
            profiles = [p for p in profiles if p.profile_type == profile_type]
        
        if compliance_level:
            profiles = [p for p in profiles if p.compliance_level == compliance_level]
        
        return profiles
    
    def get_profiles_by_tag(self, tag: str) -> List[RuleProfile]:
        """Get profiles with a specific tag"""
        return [p for p in self.profiles.values() if tag in p.tags]
    
    def recommend_profile(
        self,
        layer_count: int,
        max_voltage: Optional[float] = None,
        has_mains: bool = False,
        compliance: ComplianceLevel = ComplianceLevel.CONSUMER,
        budget: str = "medium"
    ) -> Optional[RuleProfile]:
        """
        Recommend a profile based on board characteristics
        
        Args:
            layer_count: Number of layers
            max_voltage: Maximum operating voltage
            has_mains: Whether board has mains voltage
            compliance: Required compliance level
            budget: "low", "medium", "high", "premium"
        
        Returns:
            Recommended profile
        """
        # High voltage / mains
        if has_mains or (max_voltage and max_voltage > 60):
            return self.get_profile("hv_power")
        
        # Medical
        if compliance == ComplianceLevel.MEDICAL:
            return self.get_profile("medical_iec60601")
        
        # By layer count and budget
        if layer_count == 2:
            if budget == "low":
                return self.get_profile("2l_cheap_proto")
            return self.get_profile("jlcpcb_standard")
        
        elif layer_count == 4:
            return self.get_profile("4l_iot")
        
        elif layer_count >= 6:
            return self.get_profile("6l_hdi")
        
        # Default
        return self.get_profile("ipc2221_class2")
    
    def get_clearance_for_voltage(
        self,
        profile_id: str,
        voltage: float
    ) -> Tuple[float, float, str]:
        """
        Get clearance and creepage for a specific voltage
        
        Args:
            profile_id: Profile to use
            voltage: Voltage in V
        
        Returns:
            Tuple of (clearance_mm, creepage_mm, source_standard)
        """
        profile = self.get_profile(profile_id)
        if not profile:
            return (1.0, 2.0, "Default")
        
        # Find applicable voltage class
        for vr in profile.voltage_rules:
            if vr.voltage_min <= voltage <= vr.voltage_max:
                return (vr.clearance.value, vr.creepage.value, vr.clearance.source or "")
        
        # Extrapolate for high voltages using IPC-2221A
        clearance = IPC2221A.get_clearance(voltage, ConductorType.B2_EXTERNAL_UNCOATED, 1.5)
        creepage = IPC2221A.get_creepage(voltage, safety_margin=1.5)
        
        return (clearance, creepage, "IPC-2221A extrapolated")
    
    def get_trace_width_for_current(
        self,
        profile_id: str,
        current_a: float
    ) -> Tuple[float, str]:
        """
        Get minimum trace width for a given current
        
        Args:
            profile_id: Profile to use
            current_a: Current in Amperes
        
        Returns:
            Tuple of (width_mm, source)
        """
        profile = self.get_profile(profile_id)
        if not profile:
            # Calculate using IPC-2152
            width, _ = CurrentCapacity.calculate_trace_width_for_current(
                current_a, 0.035, 10.0, LayerPosition.EXTERNAL
            )
            return (width, "IPC-2152")
        
        # Find from profile power trace rules
        if profile.power_trace_rules:
            for current, rule in sorted(profile.power_trace_rules.items()):
                if current >= current_a:
                    return (rule.value, rule.source or "Profile rule")
        
        # Calculate using IPC-2152
        copper_oz = profile.copper_weights_oz[0] if profile.copper_weights_oz else 1.0
        thickness = CurrentCapacity.copper_weight_to_thickness(copper_oz)
        width, _ = CurrentCapacity.calculate_trace_width_for_current(
            current_a, thickness, profile.max_temp_rise_c, LayerPosition.EXTERNAL
        )
        
        return (width, "IPC-2152")
    
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
            "compliance": profile.compliance_level.value,
            "standards": profile.standards_referenced,
            "key_specs": {
                "min_trace": f"{profile.min_trace_width.value}{profile.min_trace_width.unit}",
                "min_spacing": f"{profile.min_trace_spacing.value}{profile.min_trace_spacing.unit}",
                "min_via": f"{profile.min_via_diameter.value}{profile.min_via_diameter.unit}",
                "min_drill": f"{profile.min_via_drill.value}{profile.min_via_drill.unit}",
                "min_annular": f"{profile.min_annular_ring.value}{profile.min_annular_ring.unit}",
            },
            "voltage_classes": [
                {
                    "class": vr.voltage_class,
                    "range": f"{vr.voltage_min}-{vr.voltage_max}V",
                    "clearance": f"{vr.clearance.value}mm",
                    "creepage": f"{vr.creepage.value}mm",
                }
                for vr in profile.voltage_rules
            ],
            "cost_level": profile.cost_level,
            "lead_time_days": profile.lead_time_days,
            "tags": profile.tags
        }
