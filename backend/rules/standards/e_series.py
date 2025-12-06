"""
E-Series Standard Resistor and Capacitor Values
Per IEC 60063 - Preferred Number Series for Resistors and Capacitors

Source: Vishay E-Series Document, ROHM Application Note
Reference: /Users/pranavchahal/Downloads/extracted_content-1/COMPILED_ALL_PDFS.txt
"""

from typing import List, Optional, Tuple, Set
from enum import Enum
import math


class ESeriesType(str, Enum):
    """E-Series types"""
    E3 = "E3"     # 3 values/decade - 50% tolerance (obsolete)
    E6 = "E6"     # 6 values/decade - 20% tolerance
    E12 = "E12"   # 12 values/decade - 10% tolerance
    E24 = "E24"   # 24 values/decade - 5% tolerance
    E48 = "E48"   # 48 values/decade - 2% tolerance
    E96 = "E96"   # 96 values/decade - 1% tolerance
    E192 = "E192" # 192 values/decade - 0.5%, 0.25%, 0.1% tolerance


class ESeries:
    """
    E-Series Standard Value Calculator
    
    IEC 60063 defines preferred number series for resistors and capacitors.
    Values are geometrically spaced within each decade.
    """
    
    # ==========================================================================
    # E-SERIES BASE VALUES (values in one decade, 100-999 range normalized)
    # Source: IEC 60063
    # ==========================================================================
    
    # E3: 3 values per decade (50% tolerance - largely obsolete)
    E3_VALUES: List[int] = [10, 22, 47]
    
    # E6: 6 values per decade (20% tolerance)
    E6_VALUES: List[int] = [10, 15, 22, 33, 47, 68]
    
    # E12: 12 values per decade (10% tolerance)
    E12_VALUES: List[int] = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]
    
    # E24: 24 values per decade (5% tolerance)
    E24_VALUES: List[int] = [
        10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30,
        33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91
    ]
    
    # E48: 48 values per decade (2% tolerance)
    E48_VALUES: List[int] = [
        100, 105, 110, 115, 121, 127, 133, 140, 147, 154, 162, 169,
        178, 187, 196, 205, 215, 226, 237, 249, 261, 274, 287, 301,
        316, 332, 348, 365, 383, 402, 422, 442, 464, 487, 511, 536,
        562, 590, 619, 649, 681, 715, 750, 787, 825, 866, 909, 953
    ]
    
    # E96: 96 values per decade (1% tolerance)
    E96_VALUES: List[int] = [
        100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130,
        133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169, 174,
        178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
        237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
        316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
        422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
        562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732,
        750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976
    ]
    
    # E192: 192 values per decade (0.5%, 0.25%, 0.1% tolerance)
    E192_VALUES: List[int] = [
        100, 101, 102, 104, 105, 106, 107, 109, 110, 111, 113, 114,
        115, 117, 118, 120, 121, 123, 124, 126, 127, 129, 130, 132,
        133, 135, 137, 138, 140, 142, 143, 145, 147, 149, 150, 152,
        154, 156, 158, 160, 162, 164, 165, 167, 169, 172, 174, 176,
        178, 180, 182, 184, 187, 189, 191, 193, 196, 198, 200, 203,
        205, 208, 210, 213, 215, 218, 221, 223, 226, 229, 232, 234,
        237, 240, 243, 246, 249, 252, 255, 258, 261, 264, 267, 271,
        274, 277, 280, 284, 287, 291, 294, 298, 301, 305, 309, 312,
        316, 320, 324, 328, 332, 336, 340, 344, 348, 352, 357, 361,
        365, 370, 374, 379, 383, 388, 392, 397, 402, 407, 412, 417,
        422, 427, 432, 437, 442, 448, 453, 459, 464, 470, 475, 481,
        487, 493, 499, 505, 511, 517, 523, 530, 536, 542, 549, 556,
        562, 569, 576, 583, 590, 597, 604, 612, 619, 626, 634, 642,
        649, 657, 665, 673, 681, 690, 698, 706, 715, 723, 732, 741,
        750, 759, 768, 777, 787, 796, 806, 816, 825, 835, 845, 856,
        866, 876, 887, 898, 909, 920, 931, 942, 953, 965, 976, 988
    ]
    
    # Tolerance for each series
    SERIES_TOLERANCE: dict = {
        ESeriesType.E3: 50.0,
        ESeriesType.E6: 20.0,
        ESeriesType.E12: 10.0,
        ESeriesType.E24: 5.0,
        ESeriesType.E48: 2.0,
        ESeriesType.E96: 1.0,
        ESeriesType.E192: 0.5,
    }
    
    # ==========================================================================
    # COMMON NON-STANDARD VALUES (often used despite not being E-series)
    # ==========================================================================
    
    COMMON_NON_STANDARD: Set[float] = {
        0.0,        # Zero ohm jumper
        4.7,        # Common capacitor value
        100.0,      # Often used directly
        1000.0,     # 1k
        10000.0,    # 10k
        100000.0,   # 100k
    }
    
    @classmethod
    def get_series_values(cls, series: ESeriesType) -> List[int]:
        """Get base values for a series"""
        mapping = {
            ESeriesType.E3: cls.E3_VALUES,
            ESeriesType.E6: cls.E6_VALUES,
            ESeriesType.E12: cls.E12_VALUES,
            ESeriesType.E24: cls.E24_VALUES,
            ESeriesType.E48: cls.E48_VALUES,
            ESeriesType.E96: cls.E96_VALUES,
            ESeriesType.E192: cls.E192_VALUES,
        }
        return mapping.get(series, cls.E24_VALUES)
    
    @classmethod
    def normalize_value(cls, value: float) -> Tuple[float, int]:
        """
        Normalize a value to mantissa and exponent
        
        Args:
            value: Component value (e.g., 4700 for 4.7k)
        
        Returns:
            Tuple of (mantissa in 10-99 range, exponent)
        """
        if value <= 0:
            return (0, 0)
        
        exponent = int(math.floor(math.log10(value)))
        mantissa = value / (10 ** exponent)
        
        # Normalize to 10-99 range (or 100-999 for E48+)
        while mantissa < 10:
            mantissa *= 10
            exponent -= 1
        while mantissa >= 100:
            mantissa /= 10
            exponent += 1
        
        return (mantissa, exponent)
    
    @classmethod
    def is_standard_value(
        cls,
        value: float,
        series: ESeriesType = ESeriesType.E24,
        tolerance_percent: Optional[float] = None
    ) -> Tuple[bool, Optional[float], str]:
        """
        Check if a value is a standard E-series value
        
        Args:
            value: Component value to check
            series: E-series to check against
            tolerance_percent: Custom tolerance (default: use series tolerance)
        
        Returns:
            Tuple of (is_standard, nearest_standard, reason)
        """
        if value <= 0:
            return (False, None, "Value must be positive")
        
        # Zero ohm jumpers are always valid
        if value == 0:
            return (True, 0, "Zero ohm jumper")
        
        # Get series values
        series_values = cls.get_series_values(series)
        tol = tolerance_percent if tolerance_percent else cls.SERIES_TOLERANCE[series]
        
        # Normalize value
        mantissa, exponent = cls.normalize_value(value)
        
        # For E48+ series, use 100-999 range
        if series in [ESeriesType.E48, ESeriesType.E96, ESeriesType.E192]:
            target_mantissa = mantissa * 10
        else:
            target_mantissa = mantissa
        
        # Find closest match
        closest = min(series_values, key=lambda x: abs(x - target_mantissa))
        
        # Check if within tolerance
        if series in [ESeriesType.E48, ESeriesType.E96, ESeriesType.E192]:
            closest_actual = closest * (10 ** (exponent - 1))
        else:
            closest_actual = closest * (10 ** exponent)
        
        percent_diff = abs(value - closest_actual) / closest_actual * 100
        
        if percent_diff <= tol * 0.1:  # Allow 10% of tolerance for exact match
            return (True, closest_actual, f"Standard {series.value} value")
        elif percent_diff <= tol:
            return (True, closest_actual, f"Within {series.value} tolerance ({percent_diff:.1f}%)")
        else:
            return (False, closest_actual, f"Not standard - nearest {series.value} value is {closest_actual} ({percent_diff:.1f}% off)")
    
    @classmethod
    def find_nearest_standard(
        cls,
        value: float,
        series: ESeriesType = ESeriesType.E24
    ) -> float:
        """
        Find the nearest standard E-series value
        
        Args:
            value: Target value
            series: E-series to use
        
        Returns:
            Nearest standard value
        """
        if value <= 0:
            return 0.0
        
        series_values = cls.get_series_values(series)
        mantissa, exponent = cls.normalize_value(value)
        
        # For E48+ series, use 100-999 range
        if series in [ESeriesType.E48, ESeriesType.E96, ESeriesType.E192]:
            target = mantissa * 10
            closest = min(series_values, key=lambda x: abs(x - target))
            return closest * (10 ** (exponent - 1))
        else:
            closest = min(series_values, key=lambda x: abs(x - mantissa))
            return closest * (10 ** exponent)
    
    @classmethod
    def get_parallel_combination(
        cls,
        target: float,
        series: ESeriesType = ESeriesType.E24,
        max_values: int = 2
    ) -> Optional[List[float]]:
        """
        Find parallel resistor combination to achieve target value
        
        Useful when exact E-series value not available
        
        Args:
            target: Target resistance
            series: E-series to use
            max_values: Maximum number of parallel resistors (2-3)
        
        Returns:
            List of parallel resistor values, or None if not found
        """
        if target <= 0:
            return None
        
        series_values = cls.get_series_values(series)
        best_combo = None
        best_error = float('inf')
        
        # Generate all possible values in reasonable range
        all_values = []
        for exp in range(-1, 7):  # 0.1 to 1M range
            for val in series_values:
                if series in [ESeriesType.E48, ESeriesType.E96, ESeriesType.E192]:
                    all_values.append(val * (10 ** (exp - 1)))
                else:
                    all_values.append(val * (10 ** exp))
        
        # Filter to reasonable range around target
        all_values = [v for v in all_values if 0.5 * target <= v <= 10 * target]
        
        # Try pairs
        for r1 in all_values:
            for r2 in all_values:
                if r2 < r1:
                    continue
                parallel = (r1 * r2) / (r1 + r2)
                error = abs(parallel - target) / target
                if error < best_error:
                    best_error = error
                    best_combo = [r1, r2]
                    if error < 0.001:  # Close enough
                        return best_combo
        
        return best_combo if best_error < 0.05 else None  # 5% tolerance
    
    @classmethod
    def validate_bom_values(
        cls,
        values: List[Tuple[str, float, str]],
        series: ESeriesType = ESeriesType.E24
    ) -> List[dict]:
        """
        Validate a list of BOM component values
        
        Args:
            values: List of (refdes, value, component_type) tuples
            series: E-series to validate against
        
        Returns:
            List of validation results
        """
        results = []
        
        for refdes, value, comp_type in values:
            is_valid, nearest, reason = cls.is_standard_value(value, series)
            
            results.append({
                "refdes": refdes,
                "value": value,
                "component_type": comp_type,
                "is_standard": is_valid,
                "nearest_standard": nearest,
                "series": series.value,
                "message": reason
            })
        
        return results
    
    @classmethod
    def parse_value_string(cls, value_str: str) -> Optional[float]:
        """
        Parse a component value string to numeric value
        
        Handles formats like: "10k", "4.7K", "100R", "1M", "47uF", "0.1uF"
        
        Args:
            value_str: String representation of value
        
        Returns:
            Numeric value, or None if unparseable
        """
        if not value_str:
            return None
        
        value_str = value_str.strip().upper()
        
        # Multiplier suffixes
        multipliers = {
            'P': 1e-12,  # pico
            'N': 1e-9,   # nano
            'U': 1e-6,   # micro
            'µ': 1e-6,   # micro (unicode)
            'M': 1e-3,   # milli (for caps) or Mega (for resistors)
            'K': 1e3,    # kilo
            'R': 1,      # ohms
            'OHM': 1,
            'OHMS': 1,
        }
        
        # Try to extract number and suffix
        import re
        
        # Pattern: number with optional suffix
        match = re.match(r'^([0-9.]+)\s*([A-Zµ]*)', value_str)
        if not match:
            return None
        
        number_str = match.group(1)
        suffix = match.group(2)
        
        try:
            number = float(number_str)
        except ValueError:
            return None
        
        # Apply multiplier
        if suffix:
            if suffix == 'M' and number >= 100:
                # Likely "100M" meaning 100 Megaohms
                multiplier = 1e6
            elif suffix in multipliers:
                multiplier = multipliers[suffix]
            elif suffix.startswith('U') or suffix.startswith('µ'):
                multiplier = 1e-6
            elif suffix.startswith('N'):
                multiplier = 1e-9
            elif suffix.startswith('P'):
                multiplier = 1e-12
            elif suffix.startswith('K'):
                multiplier = 1e3
            else:
                multiplier = 1
        else:
            multiplier = 1
        
        return number * multiplier
