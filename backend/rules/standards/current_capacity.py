"""
PCB Current Carrying Capacity Calculations
Based on IPC-2152 and IPC-2221A standards

Source: IPC-2152 Standard for Determining Current Carrying Capacity
        MIL-STD-275E Current Density Curves
Reference: /Users/pranavchahal/Downloads/extracted_content-1/COMPILED_ALL_PDFS.txt (AN-1229)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple, List
import math


class LayerPosition(str, Enum):
    """PCB Layer Position"""
    EXTERNAL = "external"   # Top or bottom layer (better cooling)
    INTERNAL = "internal"   # Inner layer (trapped heat)


class CopperWeight(float, Enum):
    """Standard Copper Weights (oz/ft²)"""
    HALF_OZ = 0.5      # 0.5 oz = 17.5µm = 0.7mil
    ONE_OZ = 1.0       # 1 oz = 35µm = 1.4mil
    TWO_OZ = 2.0       # 2 oz = 70µm = 2.8mil
    THREE_OZ = 3.0     # 3 oz = 105µm = 4.2mil
    FOUR_OZ = 4.0      # 4 oz = 140µm = 5.6mil


@dataclass
class TraceSpec:
    """PCB Trace Specification"""
    width_mm: float
    thickness_mm: float
    length_mm: float
    layer: LayerPosition
    temperature_rise_c: float = 10.0  # Allowed temp rise


@dataclass 
class ViaSpec:
    """PCB Via Specification"""
    diameter_mm: float
    drill_mm: float
    plating_thickness_mm: float = 0.025  # Typical 1mil plating
    length_mm: float = 1.6  # Board thickness


class CurrentCapacity:
    """
    PCB Current Carrying Capacity Calculator
    
    Based on IPC-2152 and IPC-2221A standards.
    Uses empirical formulas derived from extensive testing.
    """
    
    # ==========================================================================
    # COPPER PROPERTIES
    # ==========================================================================
    
    COPPER_RESISTIVITY_OHM_M = 1.724e-8  # At 20°C
    COPPER_TEMP_COEFFICIENT = 0.00393    # Per °C
    COPPER_DENSITY_G_CM3 = 8.96
    
    # Copper weight to thickness conversion
    COPPER_WEIGHT_TO_MM: Dict[float, float] = {
        0.5: 0.0175,   # 0.5 oz = 17.5µm
        1.0: 0.035,    # 1 oz = 35µm  
        2.0: 0.070,    # 2 oz = 70µm
        3.0: 0.105,    # 3 oz = 105µm
        4.0: 0.140,    # 4 oz = 140µm
    }
    
    # ==========================================================================
    # IPC-2152 CURRENT CAPACITY CONSTANTS
    # Formula: I = k * ΔT^b * A^c
    # Where: I = current (A), ΔT = temp rise (°C), A = cross-section (mil²)
    # ==========================================================================
    
    # External layers (better cooling)
    IPC2152_EXTERNAL = {
        'k': 0.048,
        'b': 0.44,
        'c': 0.725,
    }
    
    # Internal layers (worse cooling)
    IPC2152_INTERNAL = {
        'k': 0.024,
        'b': 0.44,
        'c': 0.725,
    }
    
    # ==========================================================================
    # MIL-STD-275E TRACE WIDTH TABLE (simplified)
    # Current (A) -> Trace width (mils) for 10°C rise, 1oz copper, external
    # ==========================================================================
    
    MIL_STD_275E_TABLE: Dict[float, float] = {
        0.5: 10,
        1.0: 20,
        2.0: 50,
        3.0: 80,
        4.0: 110,
        5.0: 150,
        6.0: 200,
        7.0: 250,
        8.0: 300,
        10.0: 400,
    }
    
    # ==========================================================================
    # VIA CURRENT CAPACITY
    # Based on plating area and thermal constraints
    # ==========================================================================
    
    # Via current capacity per mil² of copper cross-section
    VIA_CURRENT_DENSITY_A_PER_MIL2 = 0.03  # Conservative
    
    @classmethod
    def copper_weight_to_thickness(cls, weight_oz: float) -> float:
        """
        Convert copper weight to thickness
        
        Args:
            weight_oz: Copper weight in oz/ft²
        
        Returns:
            Thickness in mm
        """
        return cls.COPPER_WEIGHT_TO_MM.get(weight_oz, weight_oz * 0.035)
    
    @classmethod
    def calculate_trace_current_capacity(
        cls,
        width_mm: float,
        thickness_mm: float,
        temp_rise_c: float = 10.0,
        layer: LayerPosition = LayerPosition.EXTERNAL,
        ambient_temp_c: float = 25.0
    ) -> Tuple[float, Dict]:
        """
        Calculate trace current capacity per IPC-2152
        
        Args:
            width_mm: Trace width in mm
            thickness_mm: Copper thickness in mm
            temp_rise_c: Allowed temperature rise in °C
            layer: Layer position (external/internal)
            ambient_temp_c: Ambient temperature in °C
        
        Returns:
            Tuple of (current_capacity_A, details_dict)
        """
        # Convert to mils for IPC formula
        width_mils = width_mm / 0.0254
        thickness_mils = thickness_mm / 0.0254
        
        # Cross-sectional area in mil²
        area_mil2 = width_mils * thickness_mils
        
        # Get constants for layer type
        if layer == LayerPosition.EXTERNAL:
            k = cls.IPC2152_EXTERNAL['k']
            b = cls.IPC2152_EXTERNAL['b']
            c = cls.IPC2152_EXTERNAL['c']
        else:
            k = cls.IPC2152_INTERNAL['k']
            b = cls.IPC2152_INTERNAL['b']
            c = cls.IPC2152_INTERNAL['c']
        
        # IPC-2152 formula: I = k * ΔT^b * A^c
        current = k * (temp_rise_c ** b) * (area_mil2 ** c)
        
        # Temperature derating above 25°C ambient
        if ambient_temp_c > 25:
            derating = 1 - (ambient_temp_c - 25) * 0.005  # 0.5% per °C
            current *= max(0.5, derating)
        
        details = {
            "width_mm": width_mm,
            "width_mils": round(width_mils, 1),
            "thickness_mm": thickness_mm,
            "thickness_mils": round(thickness_mils, 2),
            "area_mil2": round(area_mil2, 1),
            "temp_rise_c": temp_rise_c,
            "layer": layer.value,
            "ambient_temp_c": ambient_temp_c,
            "formula": "IPC-2152",
            "max_temp_c": ambient_temp_c + temp_rise_c,
        }
        
        return (round(current, 2), details)
    
    @classmethod
    def calculate_trace_width_for_current(
        cls,
        current_a: float,
        thickness_mm: float,
        temp_rise_c: float = 10.0,
        layer: LayerPosition = LayerPosition.EXTERNAL
    ) -> Tuple[float, Dict]:
        """
        Calculate required trace width for given current
        
        Args:
            current_a: Required current in Amperes
            thickness_mm: Copper thickness in mm
            temp_rise_c: Allowed temperature rise in °C
            layer: Layer position
        
        Returns:
            Tuple of (required_width_mm, details_dict)
        """
        # Get constants
        if layer == LayerPosition.EXTERNAL:
            k = cls.IPC2152_EXTERNAL['k']
            b = cls.IPC2152_EXTERNAL['b']
            c = cls.IPC2152_EXTERNAL['c']
        else:
            k = cls.IPC2152_INTERNAL['k']
            b = cls.IPC2152_INTERNAL['b']
            c = cls.IPC2152_INTERNAL['c']
        
        # Rearrange formula: A = (I / (k * ΔT^b))^(1/c)
        area_mil2 = (current_a / (k * (temp_rise_c ** b))) ** (1 / c)
        
        # Convert thickness to mils
        thickness_mils = thickness_mm / 0.0254
        
        # Calculate width
        width_mils = area_mil2 / thickness_mils
        width_mm = width_mils * 0.0254
        
        details = {
            "current_a": current_a,
            "thickness_mm": thickness_mm,
            "temp_rise_c": temp_rise_c,
            "layer": layer.value,
            "area_mil2": round(area_mil2, 1),
            "width_mils": round(width_mils, 1),
        }
        
        return (round(width_mm, 3), details)
    
    @classmethod
    def calculate_trace_resistance(
        cls,
        width_mm: float,
        thickness_mm: float,
        length_mm: float,
        temperature_c: float = 25.0
    ) -> Tuple[float, Dict]:
        """
        Calculate trace DC resistance
        
        Args:
            width_mm: Trace width in mm
            thickness_mm: Copper thickness in mm
            length_mm: Trace length in mm
            temperature_c: Operating temperature in °C
        
        Returns:
            Tuple of (resistance_ohms, details_dict)
        """
        # Cross-sectional area in m²
        area_m2 = (width_mm * 1e-3) * (thickness_mm * 1e-3)
        length_m = length_mm * 1e-3
        
        # Base resistance at 20°C
        resistance_20c = cls.COPPER_RESISTIVITY_OHM_M * length_m / area_m2
        
        # Temperature correction
        resistance = resistance_20c * (1 + cls.COPPER_TEMP_COEFFICIENT * (temperature_c - 20))
        
        # Voltage drop at 1A
        voltage_drop_1a = resistance
        
        details = {
            "width_mm": width_mm,
            "thickness_mm": thickness_mm,
            "length_mm": length_mm,
            "area_mm2": round(width_mm * thickness_mm, 4),
            "temperature_c": temperature_c,
            "resistance_mohm": round(resistance * 1000, 2),
            "voltage_drop_per_amp_mv": round(voltage_drop_1a * 1000, 2),
        }
        
        return (resistance, details)
    
    @classmethod
    def calculate_via_current_capacity(
        cls,
        diameter_mm: float,
        drill_mm: float,
        plating_thickness_mm: float = 0.025,
        board_thickness_mm: float = 1.6,
        temp_rise_c: float = 10.0
    ) -> Tuple[float, Dict]:
        """
        Calculate single via current capacity
        
        Args:
            diameter_mm: Via pad diameter
            drill_mm: Drill hole diameter
            plating_thickness_mm: Copper plating thickness
            board_thickness_mm: PCB thickness
            temp_rise_c: Allowed temperature rise
        
        Returns:
            Tuple of (current_capacity_A, details_dict)
        """
        # Via is a hollow copper cylinder
        # Inner diameter = drill diameter
        # Outer diameter = drill + 2*plating
        
        outer_d_mm = drill_mm
        inner_d_mm = drill_mm - 2 * plating_thickness_mm
        
        # Cross-sectional area of copper annulus
        area_mm2 = math.pi * ((outer_d_mm/2)**2 - (inner_d_mm/2)**2)
        area_mil2 = area_mm2 / (0.0254 ** 2)
        
        # Conservative current based on area
        # Via has worse thermal characteristics than trace
        current = cls.VIA_CURRENT_DENSITY_A_PER_MIL2 * area_mil2
        
        # Temperature adjustment
        current *= (temp_rise_c / 10) ** 0.5
        
        details = {
            "diameter_mm": diameter_mm,
            "drill_mm": drill_mm,
            "plating_thickness_mm": plating_thickness_mm,
            "copper_area_mm2": round(area_mm2, 4),
            "temp_rise_c": temp_rise_c,
        }
        
        return (round(current, 2), details)
    
    @classmethod
    def calculate_vias_needed(
        cls,
        current_a: float,
        drill_mm: float = 0.3,
        plating_thickness_mm: float = 0.025,
        temp_rise_c: float = 10.0
    ) -> Tuple[int, Dict]:
        """
        Calculate number of vias needed for current
        
        Args:
            current_a: Required current
            drill_mm: Via drill size
            plating_thickness_mm: Copper plating
            temp_rise_c: Allowed temperature rise
        
        Returns:
            Tuple of (via_count, details_dict)
        """
        single_via_current, _ = cls.calculate_via_current_capacity(
            diameter_mm=drill_mm + 0.2,  # Typical pad = drill + 0.2mm
            drill_mm=drill_mm,
            plating_thickness_mm=plating_thickness_mm,
            temp_rise_c=temp_rise_c
        )
        
        via_count = math.ceil(current_a / single_via_current)
        
        details = {
            "current_a": current_a,
            "single_via_capacity_a": single_via_current,
            "drill_mm": drill_mm,
            "recommended_via_count": via_count,
        }
        
        return (via_count, details)
    
    @classmethod
    def validate_power_trace(
        cls,
        width_mm: float,
        copper_oz: float,
        current_a: float,
        layer: LayerPosition = LayerPosition.EXTERNAL,
        temp_rise_limit_c: float = 10.0
    ) -> Tuple[bool, str, Dict]:
        """
        Validate if trace can handle specified current
        
        Args:
            width_mm: Trace width
            copper_oz: Copper weight in oz
            current_a: Required current
            layer: Layer position
            temp_rise_limit_c: Maximum allowed temperature rise
        
        Returns:
            Tuple of (is_valid, message, details)
        """
        thickness_mm = cls.copper_weight_to_thickness(copper_oz)
        
        capacity, details = cls.calculate_trace_current_capacity(
            width_mm=width_mm,
            thickness_mm=thickness_mm,
            temp_rise_c=temp_rise_limit_c,
            layer=layer
        )
        
        details['required_current_a'] = current_a
        details['capacity_a'] = capacity
        details['margin_percent'] = round((capacity - current_a) / current_a * 100, 1)
        
        if capacity >= current_a:
            message = (f"Trace OK: {width_mm}mm x {copper_oz}oz can carry {capacity}A "
                      f"(need {current_a}A, {details['margin_percent']}% margin)")
            return (True, message, details)
        else:
            # Calculate required width
            req_width, _ = cls.calculate_trace_width_for_current(
                current_a, thickness_mm, temp_rise_limit_c, layer
            )
            message = (f"Trace UNDERSIZED: {width_mm}mm can only carry {capacity}A, "
                      f"need {current_a}A. Increase width to {req_width}mm minimum.")
            details['required_width_mm'] = req_width
            return (False, message, details)
