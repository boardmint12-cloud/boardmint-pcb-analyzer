"""
BOM Validation Rules - Component Value and Selection Verification
Based on IEC 60063 E-Series and manufacturer derating guidelines

This module provides comprehensive BOM analysis:
- E-series resistor/capacitor value validation
- MLCC DC bias derating checks
- Capacitor voltage derating validation
- Component value sanity checks
- Preferred value recommendations

Sources:
- IEC 60063 E-Series Standard
- Vishay E-Series Application Note
- TDK MLCC Voltage Strength FAQ
- ROHM Resistor Value Standards
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_rule import BaseRule, Issue, IssueSeverity
from .standards.e_series import ESeries, ESeriesType
from .standards.mlcc_derating import MLCCDerating, CapacitorType, MLCCDielectric

logger = logging.getLogger(__name__)


@dataclass
class ComponentAnalysis:
    """Analysis result for a single component"""
    refdes: str
    value: str
    parsed_value: Optional[float]
    component_type: str  # "resistor", "capacitor", "inductor"
    is_standard_value: bool
    nearest_standard: Optional[float]
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BOMValidationRules(BaseRule):
    """
    BOM validation and component selection rules
    
    Validates:
    - Resistor values against E-series standards
    - Capacitor values and voltage ratings
    - MLCC DC bias derating
    - Component value consistency
    """
    
    # Value parsing patterns
    RESISTOR_PATTERN = re.compile(
        r'^(\d+\.?\d*)\s*(p|n|u|µ|m|k|M|G|R|Ω|ohm|OHM)?(\s*Ω|ohm|OHM)?$',
        re.IGNORECASE
    )
    
    CAPACITOR_PATTERN = re.compile(
        r'^(\d+\.?\d*)\s*(p|n|u|µ|m)?\s*(F|f)?$',
        re.IGNORECASE
    )
    
    INDUCTOR_PATTERN = re.compile(
        r'^(\d+\.?\d*)\s*(p|n|u|µ|m)?\s*(H|h)?$',
        re.IGNORECASE
    )
    
    # Suspicious values that often indicate errors
    SUSPICIOUS_RESISTOR_VALUES = {
        0.0: "Zero ohm - verify this is intentional jumper",
        1.0: "1Ω is unusual - verify not meant to be 1kΩ",
        10.0: "10Ω is uncommon - verify value",
    }
    
    def __init__(self, target_series: ESeriesType = ESeriesType.E24):
        """
        Initialize BOM validation rules
        
        Args:
            target_series: E-series to validate against (E24 is most common)
        """
        super().__init__()
        self.target_series = target_series
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Comprehensive BOM validation
        
        Args:
            pcb_data: ParsedPCBData object
        
        Returns:
            List of BOM issues
        """
        issues = []
        
        # Categorize components
        resistors = []
        capacitors = []
        inductors = []
        
        for comp in pcb_data.components:
            ref_upper = comp.reference.upper()
            
            if ref_upper.startswith('R'):
                resistors.append(comp)
            elif ref_upper.startswith('C'):
                capacitors.append(comp)
            elif ref_upper.startswith('L'):
                inductors.append(comp)
        
        logger.info(f"BOM Analysis: {len(resistors)} resistors, "
                   f"{len(capacitors)} capacitors, {len(inductors)} inductors")
        
        # Validate resistors
        issues.extend(self._validate_resistors(resistors))
        
        # Validate capacitors
        issues.extend(self._validate_capacitors(capacitors))
        
        # Validate inductors
        issues.extend(self._validate_inductors(inductors))
        
        # Cross-component checks
        issues.extend(self._check_value_consistency(resistors, capacitors))
        
        # Add E-series reference information
        issues.append(self._create_eseries_reference())
        
        return issues
    
    def _validate_resistors(self, resistors: List) -> List[Issue]:
        """Validate resistor values against E-series"""
        issues = []
        non_standard = []
        suspicious = []
        
        for comp in resistors:
            value = self._parse_resistor_value(comp.value)
            
            if value is None:
                continue
            
            # Check if standard E-series value
            is_std, nearest, reason = ESeries.is_standard_value(
                value, self.target_series
            )
            
            if not is_std and value > 0:
                non_standard.append({
                    'refdes': comp.reference,
                    'value': comp.value,
                    'parsed': value,
                    'nearest': nearest,
                    'reason': reason
                })
            
            # Check for suspicious values
            if value in self.SUSPICIOUS_RESISTOR_VALUES:
                suspicious.append({
                    'refdes': comp.reference,
                    'value': value,
                    'warning': self.SUSPICIOUS_RESISTOR_VALUES[value]
                })
        
        # Report non-standard values
        if non_standard:
            # Group by type of issue
            details = "\n".join([
                f"• {r['refdes']}: {r['value']} → nearest {self.target_series.value}: "
                f"{self._format_value(r['nearest'], 'Ω')}"
                for r in non_standard[:10]
            ])
            
            if len(non_standard) > 10:
                details += f"\n... and {len(non_standard) - 10} more"
            
            issues.append(Issue(
                issue_code="BOM-R-001",
                severity=IssueSeverity.WARNING,
                category="bom_validation",
                title=f"{len(non_standard)} resistor(s) with non-standard {self.target_series.value} values",
                description=(
                    f"The following resistors have values not in the {self.target_series.value} series:\n\n"
                    f"{details}\n\n"
                    f"Non-standard values may indicate:\n"
                    f"• Typo in schematic\n"
                    f"• Intentional precision requirement\n"
                    f"• Obsolete/unavailable value"
                ),
                suggested_fix=(
                    f"1. Verify non-standard values are intentional\n"
                    f"2. Consider using nearest {self.target_series.value} value\n"
                    f"3. For precision: use E96 (1%) or E192 (0.5%) values\n"
                    f"4. Use parallel resistor calculator for exact values"
                ),
                affected_components=[r['refdes'] for r in non_standard],
                metadata={
                    "series": self.target_series.value,
                    "non_standard_count": len(non_standard)
                }
            ))
        
        # Report suspicious values
        for susp in suspicious:
            issues.append(Issue(
                issue_code="BOM-R-002",
                severity=IssueSeverity.INFO,
                category="bom_validation",
                title=f"Verify resistor {susp['refdes']} value: {susp['value']}Ω",
                description=susp['warning'],
                suggested_fix="Double-check schematic and design intent.",
                affected_components=[susp['refdes']]
            ))
        
        return issues
    
    def _validate_capacitors(self, capacitors: List) -> List[Issue]:
        """Validate capacitor values and ratings"""
        issues = []
        
        # Categorize capacitors
        ceramic_caps = []
        electrolytic_caps = []
        tantalum_caps = []
        other_caps = []
        
        for comp in capacitors:
            value_lower = (comp.value or "").lower()
            
            # Try to identify type from value string
            if any(t in value_lower for t in ['tant', 'ta', 'tantalum']):
                tantalum_caps.append(comp)
            elif any(t in value_lower for t in ['elec', 'electro', 'alum']):
                electrolytic_caps.append(comp)
            elif any(t in value_lower for t in ['x5r', 'x7r', 'c0g', 'np0', 'y5v', 'ceramic']):
                ceramic_caps.append(comp)
            else:
                # Assume ceramic for small values, electrolytic for large
                cap_value = self._parse_capacitor_value(comp.value)
                if cap_value and cap_value >= 10e-6:  # >= 10µF
                    other_caps.append(comp)  # Could be either
                else:
                    ceramic_caps.append(comp)  # Likely ceramic
        
        # MLCC DC bias warning
        if ceramic_caps:
            issues.append(Issue(
                issue_code="BOM-C-001",
                severity=IssueSeverity.INFO,
                category="bom_validation",
                title=f"MLCC DC bias derating reminder ({len(ceramic_caps)} ceramic caps)",
                description=(
                    "Per TDK MLCC Voltage Strength FAQ:\n\n"
                    "• MLCCs do NOT require voltage derating (unlike tantalum)\n"
                    "• BUT: Class II (X5R/X7R) lose capacitance under DC bias:\n"
                    "  - At 50% rated voltage: ~60-75% capacitance remains\n"
                    "  - At 75% rated voltage: ~40-55% capacitance remains\n"
                    "• C0G/NP0 (Class I) have NO DC bias effect"
                ),
                suggested_fix=(
                    "1. For filtering/decoupling: DC bias loss usually acceptable\n"
                    "2. For timing circuits: Use C0G/NP0 or upsize X7R value\n"
                    "3. Check manufacturer DC bias curves for critical apps\n"
                    "4. Consider using higher voltage rating to reduce bias effect"
                ),
                affected_components=[c.reference for c in ceramic_caps[:10]]
            ))
        
        # Tantalum voltage derating CRITICAL warning
        if tantalum_caps:
            issues.append(Issue(
                issue_code="BOM-C-002",
                severity=IssueSeverity.CRITICAL,
                category="bom_validation",
                title=f"CRITICAL: Tantalum capacitor voltage derating ({len(tantalum_caps)} caps)",
                description=(
                    "TANTALUM CAPACITORS MUST BE DERATED TO 50% OF RATED VOLTAGE!\n\n"
                    f"Tantalum caps detected: {', '.join(c.reference for c in tantalum_caps[:5])}\n\n"
                    "Failure to derate causes:\n"
                    "• Catastrophic short-circuit failure\n"
                    "• Potential fire hazard\n"
                    "• Field failures under stress"
                ),
                suggested_fix=(
                    "1. For 5V circuit: Use 10V or higher rated tantalum\n"
                    "2. For 12V circuit: Use 25V or higher rated tantalum\n"
                    "3. Consider polymer tantalum for better reliability\n"
                    "4. Or switch to MLCC for new designs"
                ),
                affected_components=[c.reference for c in tantalum_caps],
                metadata={
                    "derating_factor": 0.5,
                    "standard": "Industry best practice"
                }
            ))
        
        # Electrolytic life warning
        if electrolytic_caps:
            issues.append(Issue(
                issue_code="BOM-C-003",
                severity=IssueSeverity.INFO,
                category="bom_validation",
                title=f"Electrolytic capacitor lifetime consideration ({len(electrolytic_caps)} caps)",
                description=(
                    "Aluminum electrolytic capacitor notes:\n"
                    "• Lifespan halves for every 10°C above rated temp\n"
                    "• Derate voltage to 80% for extended life\n"
                    "• ESR increases with age\n"
                    "• Consider polymer aluminum for better reliability"
                ),
                suggested_fix=(
                    "1. Use 105°C rated caps in warm environments\n"
                    "2. Keep away from heat sources\n"
                    "3. Allow airflow around large electrolytics\n"
                    "4. Consider low-ESR types for switching supplies"
                ),
                affected_components=[c.reference for c in electrolytic_caps[:10]]
            ))
        
        return issues
    
    def _validate_inductors(self, inductors: List) -> List[Issue]:
        """Validate inductor specifications"""
        issues = []
        
        if not inductors:
            return issues
        
        issues.append(Issue(
            issue_code="BOM-L-001",
            severity=IssueSeverity.INFO,
            category="bom_validation",
            title=f"Inductor selection checklist ({len(inductors)} inductors)",
            description=(
                "Key inductor parameters to verify:\n"
                "• Saturation current (Isat) > peak current\n"
                "• RMS current rating > continuous current\n"
                "• DCR (DC resistance) affects efficiency\n"
                "• Shielded vs unshielded (EMI consideration)"
            ),
            suggested_fix=(
                "1. Verify Isat is 20-30% above peak inductor current\n"
                "2. Check DCR for acceptable power loss\n"
                "3. Use shielded inductors for noise-sensitive designs\n"
                "4. Consider core material for frequency range"
            ),
            affected_components=[l.reference for l in inductors]
        ))
        
        return issues
    
    def _check_value_consistency(
        self, 
        resistors: List, 
        capacitors: List
    ) -> List[Issue]:
        """Check for value consistency and common errors"""
        issues = []
        
        # Check for duplicate reference designators
        all_refs = [r.reference for r in resistors] + [c.reference for c in capacitors]
        duplicates = [ref for ref in set(all_refs) if all_refs.count(ref) > 1]
        
        if duplicates:
            issues.append(Issue(
                issue_code="BOM-DUP-001",
                severity=IssueSeverity.ERROR,
                category="bom_validation",
                title=f"Duplicate reference designators found",
                description=f"Duplicates: {', '.join(duplicates)}",
                suggested_fix="Fix reference designator conflicts in schematic.",
                affected_components=duplicates
            ))
        
        # Check for missing values
        missing_values = []
        for comp in resistors + capacitors:
            if not comp.value or comp.value.strip() in ['', '?', 'DNP', 'NC']:
                missing_values.append(comp.reference)
        
        if missing_values:
            issues.append(Issue(
                issue_code="BOM-MISS-001",
                severity=IssueSeverity.WARNING,
                category="bom_validation",
                title=f"{len(missing_values)} component(s) with missing/undefined values",
                description=f"Components: {', '.join(missing_values[:10])}",
                suggested_fix="Add values or mark as DNP (Do Not Populate) if intentional.",
                affected_components=missing_values
            ))
        
        return issues
    
    def _create_eseries_reference(self) -> Issue:
        """Create E-series reference information"""
        e24_values = ESeries.E24_VALUES
        
        return Issue(
            issue_code="BOM-REF-001",
            severity=IssueSeverity.INFO,
            category="bom_validation",
            title="E-Series Standard Value Reference",
            description=(
                f"Standard {self.target_series.value} values per decade:\n"
                f"{', '.join(str(v) for v in e24_values)}\n\n"
                "Multiply by powers of 10 for actual values:\n"
                "• 10, 100, 1k, 10k, 100k, 1M for resistors\n"
                "• 10pF, 100pF, 1nF, 10nF, 100nF, 1µF for capacitors"
            ),
            suggested_fix=(
                f"Use {self.target_series.value} values for best availability and cost.\n"
                "E96 (1%) for precision, E24 (5%) for general use."
            ),
            metadata={
                "series": self.target_series.value,
                "values_per_decade": len(e24_values),
                "tolerance": ESeries.SERIES_TOLERANCE[self.target_series]
            }
        )
    
    # ==========================================================================
    # VALUE PARSING HELPERS
    # ==========================================================================
    
    def _parse_resistor_value(self, value_str: Optional[str]) -> Optional[float]:
        """Parse resistor value string to ohms"""
        if not value_str:
            return None
        
        # Use E-series parser
        return ESeries.parse_value_string(value_str)
    
    def _parse_capacitor_value(self, value_str: Optional[str]) -> Optional[float]:
        """Parse capacitor value string to Farads"""
        if not value_str:
            return None
        
        value_str = value_str.strip().upper()
        
        # Remove common suffixes
        value_str = value_str.replace('F', '').replace('FARAD', '').strip()
        
        multipliers = {
            'P': 1e-12,
            'N': 1e-9,
            'U': 1e-6,
            'µ': 1e-6,
            'M': 1e-3,  # millifarad (rare)
        }
        
        try:
            # Extract number and suffix
            match = re.match(r'^([0-9.]+)\s*([PNUµM])?', value_str, re.IGNORECASE)
            if not match:
                return None
            
            number = float(match.group(1))
            suffix = (match.group(2) or '').upper()
            
            if suffix == 'µ':
                suffix = 'U'
            
            multiplier = multipliers.get(suffix, 1)
            
            # Handle common notation without suffix (e.g., "100" meaning 100pF)
            if not suffix and number < 1000:
                multiplier = 1e-12  # Assume pF
            
            return number * multiplier
            
        except (ValueError, AttributeError):
            return None
    
    def _format_value(self, value: float, unit: str) -> str:
        """Format value with appropriate SI prefix"""
        if value is None:
            return "?"
        
        if value >= 1e6:
            return f"{value/1e6:.2g}M{unit}"
        elif value >= 1e3:
            return f"{value/1e3:.2g}k{unit}"
        elif value >= 1:
            return f"{value:.2g}{unit}"
        elif value >= 1e-3:
            return f"{value*1e3:.2g}m{unit}"
        elif value >= 1e-6:
            return f"{value*1e6:.2g}µ{unit}"
        elif value >= 1e-9:
            return f"{value*1e9:.2g}n{unit}"
        else:
            return f"{value*1e12:.2g}p{unit}"
