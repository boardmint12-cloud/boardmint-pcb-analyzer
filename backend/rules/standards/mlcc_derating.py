"""
MLCC (Multi-Layer Ceramic Capacitor) Derating Rules
Based on TDK Application Note on MLCC Voltage Strength

Source: TDK "MLCC Voltage Strength" FAQ Document (20_mlcc_voltage_strength.pdf)
Reference: /Users/pranavchahal/Downloads/extracted_content-1/COMPILED_ALL_PDFS.txt

Key Finding: MLCCs do NOT require voltage derating like tantalum/electrolytic capacitors.
TDK rates MLCCs with sufficient margin - rated voltage equals maximum operating voltage.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List, Tuple
import math


class MLCCDielectric(str, Enum):
    """MLCC Dielectric Types (Class I and Class II)"""
    # Class I - Stable, low loss, linear
    C0G = "C0G"         # NPO, ±30ppm/°C, stable
    NP0 = "NP0"         # Same as C0G
    U2J = "U2J"         # ±120ppm/°C
    
    # Class II - High capacitance, less stable
    X5R = "X5R"         # -55°C to +85°C, ±15%
    X7R = "X7R"         # -55°C to +125°C, ±15%
    X7S = "X7S"         # -55°C to +125°C, ±22%
    X8R = "X8R"         # -55°C to +150°C, ±15%
    Y5V = "Y5V"         # -30°C to +85°C, +22%/-82%
    Z5U = "Z5U"         # +10°C to +85°C, +22%/-56%


class CapacitorType(str, Enum):
    """Capacitor technology types"""
    MLCC = "MLCC"
    TANTALUM = "TANTALUM"
    ALUMINUM_ELECTROLYTIC = "ALUMINUM_ELECTROLYTIC"
    ALUMINUM_POLYMER = "ALUMINUM_POLYMER"
    FILM = "FILM"


@dataclass
class CapacitorDerating:
    """Derating requirements for a capacitor type"""
    technology: CapacitorType
    voltage_derating_factor: float  # Multiply rated voltage by this for max working
    temperature_derating: Dict[int, float]  # Temperature -> factor
    dc_bias_effect: bool  # Does DC bias reduce capacitance?
    notes: str


class MLCCDerating:
    """
    MLCC Derating and Selection Rules
    
    Key insight from TDK documentation:
    "TDK specifies the rated voltage as the maximum voltage that can be 
    continuously applied. The MLCC is designed with sufficient margin,
    so NO DERATING IS REQUIRED for DC voltage applications."
    
    However, Class II ceramics (X5R, X7R) DO lose capacitance under DC bias.
    """
    
    # ==========================================================================
    # VOLTAGE DERATING FACTORS BY CAPACITOR TYPE
    # ==========================================================================
    
    DERATING_RULES: Dict[CapacitorType, CapacitorDerating] = {
        CapacitorType.MLCC: CapacitorDerating(
            technology=CapacitorType.MLCC,
            voltage_derating_factor=1.0,  # NO DERATING for DC
            temperature_derating={
                85: 1.0,
                105: 1.0,
                125: 1.0,  # Depends on dielectric rating
            },
            dc_bias_effect=True,  # Class II only
            notes="TDK MLCCs rated at max operating voltage. No voltage derating required. "
                  "Class II (X5R/X7R) lose capacitance under DC bias - select larger value."
        ),
        CapacitorType.TANTALUM: CapacitorDerating(
            technology=CapacitorType.TANTALUM,
            voltage_derating_factor=0.5,  # 50% derating required!
            temperature_derating={
                85: 1.0,
                105: 0.9,
                125: 0.8,
            },
            dc_bias_effect=False,
            notes="Tantalum capacitors MUST be derated to 50% of rated voltage. "
                  "Failure to derate causes catastrophic shorts and fires."
        ),
        CapacitorType.ALUMINUM_ELECTROLYTIC: CapacitorDerating(
            technology=CapacitorType.ALUMINUM_ELECTROLYTIC,
            voltage_derating_factor=0.8,  # 80% derating recommended
            temperature_derating={
                85: 1.0,
                105: 0.8,
                125: 0.5,
            },
            dc_bias_effect=False,
            notes="Aluminum electrolytics should be derated 20% minimum. "
                  "Lifespan halves for every 10°C above rated temperature."
        ),
        CapacitorType.ALUMINUM_POLYMER: CapacitorDerating(
            technology=CapacitorType.ALUMINUM_POLYMER,
            voltage_derating_factor=0.9,  # 90% derating
            temperature_derating={
                85: 1.0,
                105: 1.0,
                125: 0.9,
            },
            dc_bias_effect=False,
            notes="Polymer aluminum caps more robust than wet electrolytic. "
                  "Still recommend 10% derating for margin."
        ),
        CapacitorType.FILM: CapacitorDerating(
            technology=CapacitorType.FILM,
            voltage_derating_factor=1.0,  # No derating for DC
            temperature_derating={
                85: 1.0,
                105: 1.0,
                125: 0.9,
            },
            dc_bias_effect=False,
            notes="Film capacitors are very stable. No derating required for normal operation."
        ),
    }
    
    # ==========================================================================
    # MLCC DC BIAS EFFECT (Capacitance loss under applied voltage)
    # Class II ceramics lose significant capacitance when DC biased
    # ==========================================================================
    
    # Approximate capacitance retention vs DC bias (% of rated voltage)
    # Values are approximate - always check manufacturer curves
    DC_BIAS_CAPACITANCE_LOSS: Dict[MLCCDielectric, Dict[int, float]] = {
        # Class I - No DC bias effect
        MLCCDielectric.C0G: {0: 1.0, 25: 1.0, 50: 1.0, 75: 1.0, 100: 1.0},
        MLCCDielectric.NP0: {0: 1.0, 25: 1.0, 50: 1.0, 75: 1.0, 100: 1.0},
        
        # Class II - Significant DC bias effect
        MLCCDielectric.X5R: {0: 1.0, 25: 0.85, 50: 0.65, 75: 0.45, 100: 0.30},
        MLCCDielectric.X7R: {0: 1.0, 25: 0.90, 50: 0.75, 75: 0.55, 100: 0.40},
        MLCCDielectric.X7S: {0: 1.0, 25: 0.90, 50: 0.75, 75: 0.55, 100: 0.40},
        MLCCDielectric.Y5V: {0: 1.0, 25: 0.70, 50: 0.40, 75: 0.20, 100: 0.10},
    }
    
    # ==========================================================================
    # MLCC AC VOLTAGE LIMITS
    # AC ripple voltage must be limited to prevent overheating
    # ==========================================================================
    
    # Max AC voltage as percentage of DC rating (depends on frequency)
    AC_VOLTAGE_LIMITS: Dict[MLCCDielectric, Dict[str, float]] = {
        MLCCDielectric.C0G: {"1kHz": 1.0, "100kHz": 1.0, "1MHz": 1.0},
        MLCCDielectric.X7R: {"1kHz": 0.5, "100kHz": 0.3, "1MHz": 0.2},
        MLCCDielectric.X5R: {"1kHz": 0.5, "100kHz": 0.3, "1MHz": 0.2},
        MLCCDielectric.Y5V: {"1kHz": 0.3, "100kHz": 0.2, "1MHz": 0.1},
    }
    
    @classmethod
    def get_derating_factor(cls, cap_type: CapacitorType) -> float:
        """
        Get voltage derating factor for capacitor type
        
        Args:
            cap_type: Type of capacitor
        
        Returns:
            Derating factor (multiply rated voltage to get max working voltage)
        """
        derating = cls.DERATING_RULES.get(cap_type)
        if derating:
            return derating.voltage_derating_factor
        return 0.8  # Default conservative derating
    
    @classmethod
    def validate_capacitor_voltage(
        cls,
        rated_voltage: float,
        working_voltage: float,
        cap_type: CapacitorType,
        temperature_c: float = 25
    ) -> Tuple[bool, str]:
        """
        Validate if capacitor voltage rating is adequate
        
        Args:
            rated_voltage: Capacitor rated voltage
            working_voltage: Actual working voltage in circuit
            cap_type: Type of capacitor
            temperature_c: Operating temperature
        
        Returns:
            Tuple of (is_valid, message)
        """
        derating = cls.DERATING_RULES.get(cap_type)
        if not derating:
            return (False, f"Unknown capacitor type: {cap_type}")
        
        # Calculate max allowed working voltage
        max_working = rated_voltage * derating.voltage_derating_factor
        
        # Apply temperature derating
        temp_factor = 1.0
        for temp, factor in sorted(derating.temperature_derating.items()):
            if temperature_c <= temp:
                temp_factor = factor
                break
        max_working *= temp_factor
        
        if working_voltage <= max_working:
            return (True, f"Voltage OK: {working_voltage}V <= {max_working}V max "
                         f"({cap_type.value} with {derating.voltage_derating_factor:.0%} derating)")
        else:
            return (False, f"VOLTAGE TOO HIGH: {working_voltage}V > {max_working}V max. "
                          f"{cap_type.value} requires {derating.voltage_derating_factor:.0%} derating. "
                          f"Use {working_voltage / derating.voltage_derating_factor:.0f}V rated capacitor.")
    
    @classmethod
    def calculate_effective_capacitance(
        cls,
        nominal_capacitance: float,
        dielectric: MLCCDielectric,
        dc_bias_percent: float
    ) -> Tuple[float, str]:
        """
        Calculate effective capacitance under DC bias
        
        Args:
            nominal_capacitance: Nominal capacitance value
            dielectric: MLCC dielectric type
            dc_bias_percent: DC voltage as percentage of rated voltage (0-100)
        
        Returns:
            Tuple of (effective_capacitance, warning_message)
        """
        # Get DC bias curve
        bias_curve = cls.DC_BIAS_CAPACITANCE_LOSS.get(dielectric, {})
        
        if not bias_curve:
            return (nominal_capacitance, "Unknown dielectric - assuming no DC bias effect")
        
        # Interpolate capacitance retention
        retention = 1.0
        bias_points = sorted(bias_curve.keys())
        
        for i, bp in enumerate(bias_points):
            if dc_bias_percent <= bp:
                if i == 0:
                    retention = bias_curve[bp]
                else:
                    # Linear interpolation
                    prev_bp = bias_points[i-1]
                    prev_ret = bias_curve[prev_bp]
                    curr_ret = bias_curve[bp]
                    fraction = (dc_bias_percent - prev_bp) / (bp - prev_bp)
                    retention = prev_ret + fraction * (curr_ret - prev_ret)
                break
        else:
            retention = bias_curve[max(bias_points)]
        
        effective_cap = nominal_capacitance * retention
        
        if retention < 0.8:
            warning = (f"WARNING: {dielectric.value} at {dc_bias_percent:.0f}% bias "
                      f"retains only {retention:.0%} capacitance. "
                      f"Effective: {effective_cap:.2g}F vs nominal {nominal_capacitance:.2g}F")
        elif retention < 1.0:
            warning = (f"Note: {dielectric.value} at {dc_bias_percent:.0f}% bias "
                      f"retains {retention:.0%} capacitance")
        else:
            warning = "No DC bias effect for this dielectric"
        
        return (effective_cap, warning)
    
    @classmethod
    def recommend_capacitor_size(
        cls,
        required_capacitance: float,
        working_voltage: float,
        dielectric: MLCCDielectric = MLCCDielectric.X7R,
        cap_type: CapacitorType = CapacitorType.MLCC
    ) -> Dict:
        """
        Recommend capacitor rating based on requirements
        
        Args:
            required_capacitance: Minimum required capacitance
            working_voltage: Working voltage in circuit
            dielectric: MLCC dielectric type (for DC bias)
            cap_type: Capacitor technology
        
        Returns:
            Dict with recommendations
        """
        derating = cls.DERATING_RULES.get(cap_type, cls.DERATING_RULES[CapacitorType.MLCC])
        
        # Calculate minimum voltage rating
        min_rated_voltage = working_voltage / derating.voltage_derating_factor
        
        # Standard voltage ratings
        standard_voltages = [6.3, 10, 16, 25, 35, 50, 63, 100, 200, 250, 400, 450, 630, 1000]
        recommended_voltage = next((v for v in standard_voltages if v >= min_rated_voltage), 1000)
        
        # Calculate DC bias effect for MLCC
        if cap_type == CapacitorType.MLCC and derating.dc_bias_effect:
            # Assume operating at recommended voltage
            dc_bias_percent = (working_voltage / recommended_voltage) * 100
            effective_cap, _ = cls.calculate_effective_capacitance(
                required_capacitance, dielectric, dc_bias_percent
            )
            
            # Upsize if significant capacitance loss
            if effective_cap < required_capacitance:
                upsize_factor = required_capacitance / effective_cap
                recommended_capacitance = required_capacitance * upsize_factor * 1.2  # 20% margin
            else:
                recommended_capacitance = required_capacitance
        else:
            recommended_capacitance = required_capacitance
        
        return {
            "required_capacitance": required_capacitance,
            "recommended_capacitance": recommended_capacitance,
            "working_voltage": working_voltage,
            "min_rated_voltage": min_rated_voltage,
            "recommended_voltage": recommended_voltage,
            "derating_factor": derating.voltage_derating_factor,
            "technology": cap_type.value,
            "notes": derating.notes
        }
    
    @classmethod
    def validate_bom_capacitors(
        cls,
        capacitors: List[Dict]
    ) -> List[Dict]:
        """
        Validate a list of capacitors from BOM
        
        Args:
            capacitors: List of dicts with keys:
                - refdes: Reference designator
                - value: Capacitance value
                - voltage_rating: Rated voltage
                - working_voltage: Actual working voltage (optional)
                - type: Capacitor type string
        
        Returns:
            List of validation results
        """
        results = []
        
        for cap in capacitors:
            refdes = cap.get('refdes', 'Unknown')
            value = cap.get('value', 0)
            rated_v = cap.get('voltage_rating', 0)
            working_v = cap.get('working_voltage', rated_v * 0.8)  # Assume 80% if not specified
            cap_type_str = cap.get('type', 'MLCC').upper()
            
            # Determine capacitor type
            try:
                cap_type = CapacitorType(cap_type_str)
            except ValueError:
                if 'TANT' in cap_type_str:
                    cap_type = CapacitorType.TANTALUM
                elif 'ELEC' in cap_type_str or 'ALUM' in cap_type_str:
                    cap_type = CapacitorType.ALUMINUM_ELECTROLYTIC
                else:
                    cap_type = CapacitorType.MLCC
            
            # Validate voltage
            is_valid, message = cls.validate_capacitor_voltage(
                rated_v, working_v, cap_type
            )
            
            results.append({
                "refdes": refdes,
                "value": value,
                "voltage_rating": rated_v,
                "working_voltage": working_v,
                "type": cap_type.value,
                "is_valid": is_valid,
                "message": message
            })
        
        return results
