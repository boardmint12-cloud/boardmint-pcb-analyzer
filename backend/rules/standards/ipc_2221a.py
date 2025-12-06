"""
IPC-2221A Generic Standard on Printed Board Design
Tables and calculations for electrical clearance and spacing

Source: IPC-2221A Table 6-1 (Electrical Conductor Spacing)
Reference: /Users/pranavchahal/Documents/pcb - 1st intro/extracted_content/COMPILED_ALL_PDFS.txt
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple
import math


class ConductorType(str, Enum):
    """IPC-2221A Conductor Location Types"""
    B1_INTERNAL = "B1"           # Internal conductors
    B2_EXTERNAL_UNCOATED = "B2"  # External conductors, uncoated, sea level
    B3_EXTERNAL_COATED = "B3"    # External conductors, with conformal coating
    B4_EXTERNAL_COATED_SEA = "B4"  # External, coated, sea level to 3050m
    A5_EXTERNAL_UNCOATED = "A5"  # External conductors, uncoated, >3050m
    A6_EXTERNAL_COATED = "A6"    # External conductors, coated, >3050m
    A7_EXTERNAL_COATED_HIGH = "A7"  # External, polymer coating over assembly


class BoardMaterial(str, Enum):
    """PCB Base Material Types"""
    FR4 = "FR4"
    FR4_HIGH_TG = "FR4_HIGH_TG"
    POLYIMIDE = "POLYIMIDE"
    CERAMIC = "CERAMIC"
    ROGERS = "ROGERS"
    ALUMINUM = "ALUMINUM"


@dataclass
class DielectricProperties:
    """Material dielectric properties"""
    name: str
    dielectric_constant: float  # Er at 1MHz
    dissipation_factor: float   # tan delta
    cti_group: int              # CTI group for creepage (1-4)
    tg: Optional[float] = None  # Glass transition temperature


class IPC2221A:
    """
    IPC-2221A Standard Implementation
    
    Provides lookup tables and calculations for:
    - Electrical conductor spacing (Table 6-1)
    - Creepage distances
    - Dielectric strength
    - Board material properties
    """
    
    # ==========================================================================
    # TABLE 6-1: ELECTRICAL CONDUCTOR SPACING (mm)
    # ==========================================================================
    # Voltage Peak (V) -> spacing for each conductor type
    # Source: IPC-2221A Table 6-1
    # Converted from mils to mm (1 mil = 0.0254 mm)
    # ==========================================================================
    
    CLEARANCE_TABLE_6_1: Dict[int, Dict[ConductorType, float]] = {
        # Voltage: {ConductorType: spacing_mm}
        0:    {ConductorType.B1_INTERNAL: 0.05, ConductorType.B2_EXTERNAL_UNCOATED: 0.1,  ConductorType.B3_EXTERNAL_COATED: 0.05, ConductorType.B4_EXTERNAL_COATED_SEA: 0.1},
        15:   {ConductorType.B1_INTERNAL: 0.05, ConductorType.B2_EXTERNAL_UNCOATED: 0.1,  ConductorType.B3_EXTERNAL_COATED: 0.05, ConductorType.B4_EXTERNAL_COATED_SEA: 0.1},
        30:   {ConductorType.B1_INTERNAL: 0.05, ConductorType.B2_EXTERNAL_UNCOATED: 0.1,  ConductorType.B3_EXTERNAL_COATED: 0.05, ConductorType.B4_EXTERNAL_COATED_SEA: 0.1},
        50:   {ConductorType.B1_INTERNAL: 0.1,  ConductorType.B2_EXTERNAL_UNCOATED: 0.6,  ConductorType.B3_EXTERNAL_COATED: 0.13, ConductorType.B4_EXTERNAL_COATED_SEA: 0.6},
        100:  {ConductorType.B1_INTERNAL: 0.1,  ConductorType.B2_EXTERNAL_UNCOATED: 0.6,  ConductorType.B3_EXTERNAL_COATED: 0.13, ConductorType.B4_EXTERNAL_COATED_SEA: 1.5},
        150:  {ConductorType.B1_INTERNAL: 0.2,  ConductorType.B2_EXTERNAL_UNCOATED: 0.6,  ConductorType.B3_EXTERNAL_COATED: 0.4,  ConductorType.B4_EXTERNAL_COATED_SEA: 3.2},
        170:  {ConductorType.B1_INTERNAL: 0.25, ConductorType.B2_EXTERNAL_UNCOATED: 1.25, ConductorType.B3_EXTERNAL_COATED: 0.4,  ConductorType.B4_EXTERNAL_COATED_SEA: 3.2},
        250:  {ConductorType.B1_INTERNAL: 0.25, ConductorType.B2_EXTERNAL_UNCOATED: 1.25, ConductorType.B3_EXTERNAL_COATED: 0.4,  ConductorType.B4_EXTERNAL_COATED_SEA: 6.4},
        300:  {ConductorType.B1_INTERNAL: 0.25, ConductorType.B2_EXTERNAL_UNCOATED: 1.25, ConductorType.B3_EXTERNAL_COATED: 0.4,  ConductorType.B4_EXTERNAL_COATED_SEA: 12.5},
        500:  {ConductorType.B1_INTERNAL: 0.25, ConductorType.B2_EXTERNAL_UNCOATED: 2.5,  ConductorType.B3_EXTERNAL_COATED: 0.8,  ConductorType.B4_EXTERNAL_COATED_SEA: 12.5},
    }
    
    # ==========================================================================
    # TABLE 6-2: TYPICAL RELATIVE DIELECTRIC CONSTANT OF BOARD MATERIALS
    # ==========================================================================
    
    DIELECTRIC_MATERIALS: Dict[str, DielectricProperties] = {
        "FR4": DielectricProperties(
            name="FR4 Glass Epoxy",
            dielectric_constant=4.5,
            dissipation_factor=0.02,
            cti_group=2,
            tg=130
        ),
        "FR4_HIGH_TG": DielectricProperties(
            name="FR4 High Tg",
            dielectric_constant=4.3,
            dissipation_factor=0.018,
            cti_group=2,
            tg=170
        ),
        "POLYIMIDE": DielectricProperties(
            name="Polyimide",
            dielectric_constant=3.5,
            dissipation_factor=0.008,
            cti_group=1,
            tg=250
        ),
        "ROGERS_4350": DielectricProperties(
            name="Rogers RO4350B",
            dielectric_constant=3.48,
            dissipation_factor=0.0037,
            cti_group=1,
            tg=280
        ),
        "CERAMIC": DielectricProperties(
            name="Ceramic (Alumina)",
            dielectric_constant=9.8,
            dissipation_factor=0.0001,
            cti_group=1,
            tg=None
        ),
    }
    
    # ==========================================================================
    # Dielectric Withstand Voltage (per IPC-2221A Section 6.3)
    # Minimum 500V + 250V per 0.025mm (1 mil) of dielectric thickness
    # ==========================================================================
    
    @classmethod
    def get_clearance(
        cls,
        voltage_peak: float,
        conductor_type: ConductorType = ConductorType.B2_EXTERNAL_UNCOATED,
        safety_margin: float = 1.0
    ) -> float:
        """
        Get minimum clearance from IPC-2221A Table 6-1
        
        Args:
            voltage_peak: Peak voltage between conductors (V)
            conductor_type: Type of conductor/location
            safety_margin: Multiplier for safety (1.0 = exact, 1.5 = 50% margin)
        
        Returns:
            Minimum clearance in mm
        """
        # Find the applicable voltage row
        applicable_voltage = 0
        for v in sorted(cls.CLEARANCE_TABLE_6_1.keys()):
            if v <= voltage_peak:
                applicable_voltage = v
            else:
                break
        
        # If voltage exceeds table, extrapolate
        if voltage_peak > 500:
            # Linear extrapolation: approximately 0.005mm per volt above 500V
            base_clearance = cls.CLEARANCE_TABLE_6_1[500].get(
                conductor_type, 
                cls.CLEARANCE_TABLE_6_1[500][ConductorType.B2_EXTERNAL_UNCOATED]
            )
            extra_clearance = (voltage_peak - 500) * 0.005
            return (base_clearance + extra_clearance) * safety_margin
        
        clearance = cls.CLEARANCE_TABLE_6_1[applicable_voltage].get(
            conductor_type,
            cls.CLEARANCE_TABLE_6_1[applicable_voltage][ConductorType.B2_EXTERNAL_UNCOATED]
        )
        
        return clearance * safety_margin
    
    @classmethod
    def get_creepage(
        cls,
        voltage_rms: float,
        pollution_degree: int = 2,
        material_group: int = 2,
        safety_margin: float = 1.0
    ) -> float:
        """
        Calculate creepage distance per IPC-2221A and IEC 60664-1
        
        Args:
            voltage_rms: RMS working voltage (V)
            pollution_degree: 1-4 (1=sealed, 2=normal indoor, 3=conductive pollution, 4=outdoor)
            material_group: CTI material group 1-4 (1=best insulation)
            safety_margin: Multiplier for safety
        
        Returns:
            Minimum creepage distance in mm
        """
        # Base creepage table (mm) - IEC 60664-1 simplified
        # Pollution Degree 2, Material Group II
        creepage_base = {
            50: 0.6,
            100: 1.0,
            150: 1.6,
            200: 2.0,
            250: 2.5,
            300: 3.2,
            400: 4.0,
            500: 5.0,
            600: 6.3,
            800: 8.0,
            1000: 10.0,
        }
        
        # Find applicable voltage
        applicable_voltage = 50
        for v in sorted(creepage_base.keys()):
            if v <= voltage_rms:
                applicable_voltage = v
        
        base = creepage_base.get(applicable_voltage, 10.0)
        
        # Adjust for pollution degree
        pd_multiplier = {1: 0.8, 2: 1.0, 3: 1.6, 4: 2.0}
        base *= pd_multiplier.get(pollution_degree, 1.0)
        
        # Adjust for material group
        mg_multiplier = {1: 0.8, 2: 1.0, 3: 1.25, 4: 1.6}
        base *= mg_multiplier.get(material_group, 1.0)
        
        return base * safety_margin
    
    @classmethod
    def get_dielectric_withstand_voltage(
        cls,
        dielectric_thickness_mm: float,
        material: str = "FR4"
    ) -> float:
        """
        Calculate dielectric withstand voltage
        
        Per IPC-2221A Section 6.3:
        Minimum 500V + 250V per 0.025mm (1 mil) of dielectric
        
        Args:
            dielectric_thickness_mm: Thickness in mm
            material: Material type
        
        Returns:
            Withstand voltage in V
        """
        thickness_mils = dielectric_thickness_mm / 0.0254
        return 500 + (250 * thickness_mils)
    
    @classmethod
    def calculate_impedance_microstrip(
        cls,
        trace_width_mm: float,
        dielectric_height_mm: float,
        trace_thickness_mm: float = 0.035,
        dielectric_constant: float = 4.5
    ) -> float:
        """
        Calculate microstrip impedance (IPC-2221A Section 6.4)
        
        Formula: Z0 = (87 / sqrt(Er + 1.41)) * ln(5.98 * H / (0.8 * W + T))
        
        Args:
            trace_width_mm: Trace width in mm
            dielectric_height_mm: Height above ground plane in mm
            trace_thickness_mm: Copper thickness in mm (default 1oz = 0.035mm)
            dielectric_constant: Er of material
        
        Returns:
            Characteristic impedance in ohms
        """
        W = trace_width_mm
        H = dielectric_height_mm
        T = trace_thickness_mm
        Er = dielectric_constant
        
        if W <= 0 or H <= 0:
            return 0.0
        
        # IPC-2221A microstrip formula
        Z0 = (87 / math.sqrt(Er + 1.41)) * math.log(5.98 * H / (0.8 * W + T))
        
        return max(0, Z0)
    
    @classmethod
    def calculate_impedance_stripline(
        cls,
        trace_width_mm: float,
        dielectric_height_mm: float,
        trace_thickness_mm: float = 0.035,
        dielectric_constant: float = 4.5
    ) -> float:
        """
        Calculate stripline impedance (IPC-2221A Section 6.4)
        
        Formula: Z0 = (60 / sqrt(Er)) * ln(4 * B / (0.67 * pi * (0.8 * W + T)))
        Where B = dielectric_height (total between planes)
        
        Args:
            trace_width_mm: Trace width in mm
            dielectric_height_mm: Total height between ground planes in mm
            trace_thickness_mm: Copper thickness in mm
            dielectric_constant: Er of material
        
        Returns:
            Characteristic impedance in ohms
        """
        W = trace_width_mm
        B = dielectric_height_mm
        T = trace_thickness_mm
        Er = dielectric_constant
        
        if W <= 0 or B <= 0:
            return 0.0
        
        # IPC-2221A stripline formula
        Z0 = (60 / math.sqrt(Er)) * math.log(4 * B / (0.67 * math.pi * (0.8 * W + T)))
        
        return max(0, Z0)
    
    @classmethod
    def get_via_aspect_ratio_limit(cls, via_type: str = "standard") -> float:
        """
        Get maximum via aspect ratio per IPC-2221A
        
        Args:
            via_type: "standard", "microvia", "blind", "buried"
        
        Returns:
            Maximum aspect ratio (depth/diameter)
        """
        limits = {
            "standard": 10.0,    # Standard through-hole
            "microvia": 1.0,    # Laser-drilled microvia
            "blind": 8.0,       # Blind via
            "buried": 8.0,      # Buried via
            "hdi": 12.0,        # HDI process
        }
        return limits.get(via_type, 10.0)
    
    @classmethod
    def validate_annular_ring(
        cls,
        pad_diameter_mm: float,
        drill_diameter_mm: float,
        layer_type: str = "external"
    ) -> Tuple[bool, float, float]:
        """
        Validate annular ring per IPC-2221A
        
        Args:
            pad_diameter_mm: Pad diameter in mm
            drill_diameter_mm: Drill diameter in mm
            layer_type: "external" or "internal"
        
        Returns:
            Tuple of (is_valid, actual_ring_mm, required_ring_mm)
        """
        # IPC-2221A minimum annular ring requirements
        min_ring = {
            "external": 0.05,   # 2 mils external
            "internal": 0.025,  # 1 mil internal
        }
        
        actual_ring = (pad_diameter_mm - drill_diameter_mm) / 2
        required_ring = min_ring.get(layer_type, 0.05)
        
        return (actual_ring >= required_ring, actual_ring, required_ring)
