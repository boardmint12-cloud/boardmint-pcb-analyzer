"""
IEC 62368-1 Safety Standard for Audio/Video, IT Equipment
Tables for clearance, creepage, and safety requirements

Source: IEC 62368-1:2018 Sections 5.4.2, 5.4.3
Reference: /Users/pranavchahal/Documents/pcb - 1st intro/extracted_content/COMPILED_ALL_PDFS.txt
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple, List
import math


class InsulationType(str, Enum):
    """IEC 62368-1 Insulation Types"""
    FUNCTIONAL = "functional"           # Insulation for correct operation only
    BASIC = "basic"                     # Single level of protection
    SUPPLEMENTARY = "supplementary"     # Second level of protection  
    DOUBLE = "double"                   # Basic + Supplementary
    REINFORCED = "reinforced"           # Single insulation = Double


class OvervoltageCategory(str, Enum):
    """IEC 62368-1 Overvoltage Categories"""
    OVC_I = "I"     # Equipment with transient overvoltage control
    OVC_II = "II"   # Equipment connected to fixed installations
    OVC_III = "III" # Equipment in fixed installations
    OVC_IV = "IV"   # Equipment at origin of installation


class PollutionDegree(int, Enum):
    """IEC 62368-1 Pollution Degrees"""
    PD1 = 1  # No pollution or only dry, non-conductive pollution
    PD2 = 2  # Normally non-conductive pollution, temporary condensation
    PD3 = 3  # Conductive pollution or dry non-conductive that becomes conductive


class MaterialGroup(str, Enum):
    """Material groups based on CTI (Comparative Tracking Index)"""
    GROUP_I = "I"       # CTI >= 600V
    GROUP_II = "II"     # 400V <= CTI < 600V
    GROUP_IIIa = "IIIa" # 175V <= CTI < 400V
    GROUP_IIIb = "IIIb" # 100V <= CTI < 175V


@dataclass
class SafetyMargins:
    """Safety clearance and creepage requirements"""
    clearance_mm: float
    creepage_mm: float
    insulation_type: InsulationType
    voltage_working: float
    voltage_peak: float
    notes: Optional[str] = None


class IEC62368:
    """
    IEC 62368-1 Safety Standard Implementation
    
    For Audio/Video, Information and Communication Technology Equipment
    Safety requirements for clearance, creepage, and insulation
    """
    
    # ==========================================================================
    # TABLE G.11: CLEARANCES FOR BASIC AND SUPPLEMENTARY INSULATION
    # Working voltage peak/DC (V) -> Clearance (mm)
    # For Pollution Degree 2, up to 2000m altitude
    # ==========================================================================
    
    CLEARANCE_BASIC: Dict[int, Dict[OvervoltageCategory, float]] = {
        # Voltage: {OVC: clearance_mm}
        50:   {OvervoltageCategory.OVC_I: 0.2,  OvervoltageCategory.OVC_II: 0.5,  OvervoltageCategory.OVC_III: 0.8,  OvervoltageCategory.OVC_IV: 1.5},
        100:  {OvervoltageCategory.OVC_I: 0.2,  OvervoltageCategory.OVC_II: 0.5,  OvervoltageCategory.OVC_III: 1.5,  OvervoltageCategory.OVC_IV: 3.0},
        150:  {OvervoltageCategory.OVC_I: 0.5,  OvervoltageCategory.OVC_II: 0.5,  OvervoltageCategory.OVC_III: 1.5,  OvervoltageCategory.OVC_IV: 3.0},
        300:  {OvervoltageCategory.OVC_I: 0.5,  OvervoltageCategory.OVC_II: 1.5,  OvervoltageCategory.OVC_III: 3.0,  OvervoltageCategory.OVC_IV: 5.5},
        600:  {OvervoltageCategory.OVC_I: 1.0,  OvervoltageCategory.OVC_II: 3.0,  OvervoltageCategory.OVC_III: 5.5,  OvervoltageCategory.OVC_IV: 8.0},
        1000: {OvervoltageCategory.OVC_I: 1.5,  OvervoltageCategory.OVC_II: 5.0,  OvervoltageCategory.OVC_III: 8.0,  OvervoltageCategory.OVC_IV: 14.0},
        1500: {OvervoltageCategory.OVC_I: 2.0,  OvervoltageCategory.OVC_II: 8.0,  OvervoltageCategory.OVC_III: 14.0, OvervoltageCategory.OVC_IV: 18.0},
    }
    
    # ==========================================================================
    # TABLE G.13: CREEPAGE DISTANCES FOR BASIC INSULATION
    # Working voltage RMS (V) -> Creepage (mm) by Material Group
    # Pollution Degree 2
    # ==========================================================================
    
    CREEPAGE_BASIC_PD2: Dict[int, Dict[MaterialGroup, float]] = {
        # Voltage: {MaterialGroup: creepage_mm}
        50:   {MaterialGroup.GROUP_I: 0.6,  MaterialGroup.GROUP_II: 0.9,  MaterialGroup.GROUP_IIIa: 1.2,  MaterialGroup.GROUP_IIIb: 1.5},
        100:  {MaterialGroup.GROUP_I: 1.0,  MaterialGroup.GROUP_II: 1.4,  MaterialGroup.GROUP_IIIa: 1.8,  MaterialGroup.GROUP_IIIb: 2.2},
        150:  {MaterialGroup.GROUP_I: 1.6,  MaterialGroup.GROUP_II: 2.0,  MaterialGroup.GROUP_IIIa: 2.5,  MaterialGroup.GROUP_IIIb: 3.2},
        200:  {MaterialGroup.GROUP_I: 2.0,  MaterialGroup.GROUP_II: 2.5,  MaterialGroup.GROUP_IIIa: 3.2,  MaterialGroup.GROUP_IIIb: 4.0},
        250:  {MaterialGroup.GROUP_I: 2.5,  MaterialGroup.GROUP_II: 3.2,  MaterialGroup.GROUP_IIIa: 4.0,  MaterialGroup.GROUP_IIIb: 5.0},
        300:  {MaterialGroup.GROUP_I: 3.2,  MaterialGroup.GROUP_II: 4.0,  MaterialGroup.GROUP_IIIa: 5.0,  MaterialGroup.GROUP_IIIb: 6.3},
        400:  {MaterialGroup.GROUP_I: 4.0,  MaterialGroup.GROUP_II: 5.0,  MaterialGroup.GROUP_IIIa: 6.3,  MaterialGroup.GROUP_IIIb: 8.0},
        600:  {MaterialGroup.GROUP_I: 6.3,  MaterialGroup.GROUP_II: 8.0,  MaterialGroup.GROUP_IIIa: 10.0, MaterialGroup.GROUP_IIIb: 12.5},
        1000: {MaterialGroup.GROUP_I: 10.0, MaterialGroup.GROUP_II: 12.5, MaterialGroup.GROUP_IIIa: 16.0, MaterialGroup.GROUP_IIIb: 20.0},
    }
    
    # ==========================================================================
    # TABLE G.14: CREEPAGE DISTANCES FOR POLLUTION DEGREE 3
    # ==========================================================================
    
    CREEPAGE_BASIC_PD3: Dict[int, Dict[MaterialGroup, float]] = {
        50:   {MaterialGroup.GROUP_I: 1.2,  MaterialGroup.GROUP_II: 1.7,  MaterialGroup.GROUP_IIIa: 2.4,  MaterialGroup.GROUP_IIIb: 3.0},
        100:  {MaterialGroup.GROUP_I: 1.8,  MaterialGroup.GROUP_II: 2.4,  MaterialGroup.GROUP_IIIa: 3.6,  MaterialGroup.GROUP_IIIb: 4.5},
        150:  {MaterialGroup.GROUP_I: 2.4,  MaterialGroup.GROUP_II: 3.2,  MaterialGroup.GROUP_IIIa: 4.8,  MaterialGroup.GROUP_IIIb: 6.0},
        200:  {MaterialGroup.GROUP_I: 3.2,  MaterialGroup.GROUP_II: 4.2,  MaterialGroup.GROUP_IIIa: 6.4,  MaterialGroup.GROUP_IIIb: 8.0},
        250:  {MaterialGroup.GROUP_I: 4.0,  MaterialGroup.GROUP_II: 5.3,  MaterialGroup.GROUP_IIIa: 8.0,  MaterialGroup.GROUP_IIIb: 10.0},
        300:  {MaterialGroup.GROUP_I: 5.0,  MaterialGroup.GROUP_II: 6.7,  MaterialGroup.GROUP_IIIa: 10.0, MaterialGroup.GROUP_IIIb: 12.5},
    }
    
    # ==========================================================================
    # MAINS VOLTAGE DEFINITIONS
    # ==========================================================================
    
    MAINS_VOLTAGES: Dict[str, Dict[str, float]] = {
        "EU_230V": {"nominal": 230, "peak": 325, "working": 253},
        "US_120V": {"nominal": 120, "peak": 170, "working": 132},
        "UK_240V": {"nominal": 240, "peak": 340, "working": 264},
        "JP_100V": {"nominal": 100, "peak": 141, "working": 110},
        "UNIVERSAL": {"nominal": 230, "peak": 340, "working": 264},
    }
    
    # ==========================================================================
    # TABLE 31: MINIMUM PROTECTIVE BONDING CONDUCTOR SIZE
    # For protective earthing requirements
    # ==========================================================================
    
    BONDING_CONDUCTOR_SIZE: Dict[Tuple[float, float], float] = {
        # (min_current_A, max_current_A): conductor_mm2
        (0, 6): 0.75,
        (6, 10): 1.0,
        (10, 16): 1.5,
        (16, 25): 2.5,
        (25, 32): 4.0,
        (32, 63): 6.0,
        (63, 100): 10.0,
    }
    
    @classmethod
    def get_clearance(
        cls,
        voltage_peak: float,
        insulation_type: InsulationType = InsulationType.BASIC,
        overvoltage_category: OvervoltageCategory = OvervoltageCategory.OVC_II,
        altitude_m: float = 0
    ) -> float:
        """
        Get minimum clearance per IEC 62368-1
        
        Args:
            voltage_peak: Peak working voltage (V)
            insulation_type: Type of insulation required
            overvoltage_category: Installation overvoltage category
            altitude_m: Altitude in meters (affects clearance >2000m)
        
        Returns:
            Minimum clearance in mm
        """
        # Find applicable voltage row
        applicable_voltage = 50
        for v in sorted(cls.CLEARANCE_BASIC.keys()):
            if v <= voltage_peak:
                applicable_voltage = v
            else:
                break
        
        # Extrapolate for voltages above table
        if voltage_peak > 1500:
            base = cls.CLEARANCE_BASIC[1500][overvoltage_category]
            extra = (voltage_peak - 1500) * 0.01  # ~10mm per 1000V
            clearance = base + extra
        else:
            clearance = cls.CLEARANCE_BASIC[applicable_voltage].get(
                overvoltage_category,
                cls.CLEARANCE_BASIC[applicable_voltage][OvervoltageCategory.OVC_II]
            )
        
        # Altitude correction factor (IEC 62368-1 Table G.12)
        if altitude_m > 2000:
            # Clearance increases by factor for every 1000m above 2000m
            correction = 1.0 + (altitude_m - 2000) / 5000
            clearance *= correction
        
        # Double/Reinforced insulation requires 2x basic
        if insulation_type in [InsulationType.DOUBLE, InsulationType.REINFORCED]:
            clearance *= 2.0
        elif insulation_type == InsulationType.SUPPLEMENTARY:
            clearance *= 1.0  # Same as basic
        
        return round(clearance, 2)
    
    @classmethod
    def get_creepage(
        cls,
        voltage_rms: float,
        insulation_type: InsulationType = InsulationType.BASIC,
        pollution_degree: PollutionDegree = PollutionDegree.PD2,
        material_group: MaterialGroup = MaterialGroup.GROUP_II
    ) -> float:
        """
        Get minimum creepage per IEC 62368-1
        
        Args:
            voltage_rms: RMS working voltage (V)
            insulation_type: Type of insulation required
            pollution_degree: Environmental pollution degree
            material_group: PCB material CTI group
        
        Returns:
            Minimum creepage in mm
        """
        # Select table based on pollution degree
        if pollution_degree == PollutionDegree.PD3:
            table = cls.CREEPAGE_BASIC_PD3
        else:
            table = cls.CREEPAGE_BASIC_PD2
        
        # Find applicable voltage row
        applicable_voltage = 50
        for v in sorted(table.keys()):
            if v <= voltage_rms:
                applicable_voltage = v
            else:
                break
        
        # Get base creepage
        if applicable_voltage in table:
            creepage = table[applicable_voltage].get(
                material_group,
                table[applicable_voltage][MaterialGroup.GROUP_II]
            )
        else:
            # Extrapolate for high voltages
            creepage = 20.0 + (voltage_rms - 1000) * 0.02
        
        # Double/Reinforced insulation requires 2x basic
        if insulation_type in [InsulationType.DOUBLE, InsulationType.REINFORCED]:
            creepage *= 2.0
        
        return round(creepage, 2)
    
    @classmethod
    def get_mains_safety_requirements(
        cls,
        mains_type: str = "EU_230V",
        insulation_type: InsulationType = InsulationType.REINFORCED,
        pollution_degree: PollutionDegree = PollutionDegree.PD2
    ) -> SafetyMargins:
        """
        Get complete safety requirements for mains-powered equipment
        
        Args:
            mains_type: Type of mains supply
            insulation_type: Required insulation type
            pollution_degree: Environmental pollution
        
        Returns:
            SafetyMargins with clearance and creepage
        """
        mains = cls.MAINS_VOLTAGES.get(mains_type, cls.MAINS_VOLTAGES["UNIVERSAL"])
        
        clearance = cls.get_clearance(
            mains["peak"],
            insulation_type,
            OvervoltageCategory.OVC_II
        )
        
        creepage = cls.get_creepage(
            mains["working"],
            insulation_type,
            pollution_degree,
            MaterialGroup.GROUP_II
        )
        
        return SafetyMargins(
            clearance_mm=clearance,
            creepage_mm=creepage,
            insulation_type=insulation_type,
            voltage_working=mains["working"],
            voltage_peak=mains["peak"],
            notes=f"IEC 62368-1 for {mains_type} mains"
        )
    
    @classmethod
    def get_protective_conductor_size(cls, current_a: float) -> float:
        """
        Get minimum protective bonding conductor size per Table 31
        
        Args:
            current_a: Rated current in Amperes
        
        Returns:
            Minimum conductor cross-section in mm²
        """
        for (min_i, max_i), size in cls.BONDING_CONDUCTOR_SIZE.items():
            if min_i <= current_a < max_i:
                return size
        return 10.0  # Default for high current
    
    @classmethod
    def calculate_slot_creepage_benefit(
        cls,
        slot_width_mm: float,
        slot_depth_mm: float
    ) -> float:
        """
        Calculate creepage benefit from routed slots
        
        Slots in PCB can add creepage distance if properly designed
        
        Args:
            slot_width_mm: Width of slot
            slot_depth_mm: Depth of slot (board thickness typically)
        
        Returns:
            Additional effective creepage in mm
        """
        # Per IEC 62368-1, slots add to creepage path
        # Minimum slot width 1mm for PD2, 1.5mm for PD3
        if slot_width_mm < 1.0:
            return 0.0
        
        # Slot adds 2x depth to creepage (down and up)
        return 2 * slot_depth_mm
    
    @classmethod
    def validate_isolation_barrier(
        cls,
        clearance_mm: float,
        creepage_mm: float,
        voltage_peak: float,
        insulation_type: InsulationType = InsulationType.REINFORCED
    ) -> Tuple[bool, List[str]]:
        """
        Validate an isolation barrier meets IEC 62368-1
        
        Args:
            clearance_mm: Actual clearance distance
            creepage_mm: Actual creepage distance
            voltage_peak: Peak isolation voltage
            insulation_type: Required insulation type
        
        Returns:
            Tuple of (passes, list of issues)
        """
        issues = []
        
        required_clearance = cls.get_clearance(voltage_peak, insulation_type)
        required_creepage = cls.get_creepage(voltage_peak / 1.414, insulation_type)  # Convert peak to RMS
        
        if clearance_mm < required_clearance:
            issues.append(
                f"Clearance {clearance_mm}mm < required {required_clearance}mm "
                f"for {voltage_peak}V {insulation_type.value} insulation"
            )
        
        if creepage_mm < required_creepage:
            issues.append(
                f"Creepage {creepage_mm}mm < required {required_creepage}mm "
                f"for {voltage_peak}V {insulation_type.value} insulation"
            )
        
        return (len(issues) == 0, issues)
