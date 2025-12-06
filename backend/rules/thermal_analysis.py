"""
Thermal Analysis Rules - Power Dissipation and Current Capacity
Based on IPC-2152 and component thermal guidelines

This module provides thermal analysis:
- Trace current carrying capacity validation
- Via current handling calculations
- Component power dissipation estimates
- Thermal via recommendations
- Heat sink pad identification

Sources:
- IPC-2152: Current Carrying Capacity
- IPC-2221A: Thermal Guidelines
- TI Application Notes: Power Dissipation
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

from .base_rule import BaseRule, Issue, IssueSeverity
from .standards.current_capacity import CurrentCapacity, LayerPosition

logger = logging.getLogger(__name__)


@dataclass
class ThermalComponent:
    """Component with thermal significance"""
    refdes: str
    component_type: str  # "regulator", "mosfet", "resistor", "led", "ic"
    estimated_power_w: float
    has_thermal_pad: bool
    thermal_vias_needed: int
    package: Optional[str] = None


@dataclass  
class PowerNet:
    """Power net with current estimate"""
    net_name: str
    voltage: float
    estimated_current_a: float
    net_type: str  # "input", "output", "internal"


class ThermalAnalysisRules(BaseRule):
    """
    Thermal analysis and current capacity rules
    
    Validates:
    - Trace widths for current handling
    - Via counts for current paths
    - Thermal via patterns for power ICs
    - Component thermal management
    """
    
    # ==========================================================================
    # COMPONENT DETECTION AND POWER ESTIMATION
    # ==========================================================================
    
    # Power dissipation components
    POWER_COMPONENT_PATTERNS = {
        'regulator': ['lm78', 'lm79', 'ldo', 'ams1117', 'ld1117', 'mcp1700', 
                     'tps7', 'lm1117', 'ap2112', 'xc6206'],
        'smps': ['lm2596', 'mp1584', 'mp2307', 'tps54', 'lmr', 'buck', 'boost'],
        'mosfet': ['irf', 'si', 'ao', 'q1', 'q2', 'fet', 'mos'],
        'power_resistor': ['power', 'shunt', 'sense'],
        'led_driver': ['led', 'al8', 'pam', 'bcr'],
    }
    
    # Typical power dissipation estimates
    TYPICAL_POWER_DISSIPATION = {
        'ldo_3v3_from_5v': 0.5,   # (5V-3.3V) × 300mA typical
        'ldo_3v3_from_12v': 1.5,  # (12V-3.3V) × 175mA
        'smps_1a': 0.3,           # ~90% efficient, 5V/1A
        'mosfet_1a': 0.1,         # Rds_on × I²
        'power_led': 0.3,         # 100mA × 3V drop
    }
    
    # Exposed pad (EP) / thermal pad packages
    THERMAL_PAD_PACKAGES = [
        'qfn', 'dfn', 'mlp', 'wqfn', 'vqfn',  # QFN variants
        'tqfp-ep', 'lqfp-ep',                  # LQFP with EP
        'soic-ep', 'msop-ep',                  # SOIC with EP
        'powerpad', 'ddpak', 'dpak', 'd2pak',  # Power packages
        'to-252', 'to-263', 'to-220',          # TO packages
    ]
    
    def __init__(self, copper_oz: float = 1.0, ambient_temp_c: float = 25.0):
        """
        Initialize thermal analysis
        
        Args:
            copper_oz: Copper weight in oz/ft²
            ambient_temp_c: Ambient temperature in °C
        """
        super().__init__()
        self.copper_oz = copper_oz
        self.ambient_temp_c = ambient_temp_c
        self.copper_thickness_mm = CurrentCapacity.copper_weight_to_thickness(copper_oz)
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Comprehensive thermal analysis
        
        Args:
            pcb_data: ParsedPCBData object
        
        Returns:
            List of thermal issues
        """
        issues = []
        
        # Identify thermal-significant components
        thermal_components = self._identify_thermal_components(pcb_data)
        
        # Analyze each thermal component
        for tc in thermal_components:
            issues.extend(self._check_component_thermal(tc, pcb_data))
        
        # Power net analysis
        power_nets = self._identify_power_nets(pcb_data)
        if power_nets:
            issues.extend(self._check_power_net_traces(power_nets, pcb_data))
        
        # Via current capacity
        issues.extend(self._create_via_guidelines())
        
        # General thermal guidelines
        issues.extend(self._create_general_thermal_guidelines())
        
        return issues
    
    def _identify_thermal_components(self, pcb_data) -> List[ThermalComponent]:
        """Identify components with thermal significance"""
        thermal_comps = []
        
        for comp in pcb_data.components:
            ref_lower = comp.reference.lower()
            value_lower = (comp.value or "").lower()
            combined = ref_lower + " " + value_lower
            
            # Check for power regulators
            if any(p in combined for p in self.POWER_COMPONENT_PATTERNS['regulator']):
                thermal_comps.append(ThermalComponent(
                    refdes=comp.reference,
                    component_type="regulator",
                    estimated_power_w=0.5,  # Typical
                    has_thermal_pad=self._has_thermal_pad(value_lower),
                    thermal_vias_needed=9 if self._has_thermal_pad(value_lower) else 0,
                    package=self._extract_package(comp.value)
                ))
            
            # Check for SMPS controllers
            elif any(p in combined for p in self.POWER_COMPONENT_PATTERNS['smps']):
                thermal_comps.append(ThermalComponent(
                    refdes=comp.reference,
                    component_type="smps",
                    estimated_power_w=0.3,
                    has_thermal_pad=self._has_thermal_pad(value_lower),
                    thermal_vias_needed=5 if self._has_thermal_pad(value_lower) else 0,
                    package=self._extract_package(comp.value)
                ))
            
            # Check for MOSFETs
            elif any(p in combined for p in self.POWER_COMPONENT_PATTERNS['mosfet']):
                thermal_comps.append(ThermalComponent(
                    refdes=comp.reference,
                    component_type="mosfet",
                    estimated_power_w=0.2,
                    has_thermal_pad=True,  # Most power MOSFETs have thermal tab
                    thermal_vias_needed=4,
                    package=self._extract_package(comp.value)
                ))
        
        return thermal_comps
    
    def _has_thermal_pad(self, value: str) -> bool:
        """Check if component likely has thermal/exposed pad"""
        return any(p in value for p in self.THERMAL_PAD_PACKAGES)
    
    def _extract_package(self, value: Optional[str]) -> Optional[str]:
        """Extract package type from value string"""
        if not value:
            return None
        
        value_upper = value.upper()
        packages = ['QFN', 'DFN', 'SOIC', 'TSSOP', 'LQFP', 'TO-220', 'TO-252', 
                   'DPAK', 'D2PAK', 'SOT-223', 'SOT-23']
        
        for pkg in packages:
            if pkg in value_upper:
                return pkg
        
        return None
    
    def _check_component_thermal(
        self, 
        tc: ThermalComponent,
        pcb_data
    ) -> List[Issue]:
        """Check thermal requirements for a component"""
        issues = []
        
        # Thermal pad vias
        if tc.has_thermal_pad and tc.thermal_vias_needed > 0:
            issues.append(Issue(
                issue_code=f"THERM-{tc.refdes}-001",
                severity=IssueSeverity.WARNING,
                category="thermal",
                title=f"Thermal vias required for {tc.refdes} ({tc.component_type})",
                description=(
                    f"Component {tc.refdes} has exposed thermal pad.\n"
                    f"Package: {tc.package or 'Unknown'}\n"
                    f"Estimated power: {tc.estimated_power_w}W\n"
                    f"Recommended thermal vias: {tc.thermal_vias_needed}+"
                ),
                suggested_fix=(
                    f"1. Add {tc.thermal_vias_needed}+ thermal vias in exposed pad area\n"
                    f"2. Via diameter: 0.3mm (12 mil), pitch: 1mm grid\n"
                    f"3. Connect to internal copper pour or bottom plane\n"
                    f"4. Tent vias on top to prevent solder wicking\n"
                    f"5. Use via-in-pad if footprint supports it"
                ),
                affected_components=[tc.refdes],
                metadata={
                    "thermal_vias_needed": tc.thermal_vias_needed,
                    "estimated_power_w": tc.estimated_power_w
                }
            ))
        
        # LDO power dissipation warning
        if tc.component_type == "regulator":
            issues.append(Issue(
                issue_code=f"THERM-{tc.refdes}-002",
                severity=IssueSeverity.INFO,
                category="thermal",
                title=f"LDO power dissipation check: {tc.refdes}",
                description=(
                    "LDO power dissipation = (Vin - Vout) × Iout\n\n"
                    "Example calculations:\n"
                    "• 5V→3.3V @ 500mA: (5-3.3)×0.5 = 0.85W\n"
                    "• 12V→3.3V @ 300mA: (12-3.3)×0.3 = 2.6W (HIGH!)\n\n"
                    "Max power depends on package thermal resistance."
                ),
                suggested_fix=(
                    "1. Calculate: P = (Vin - Vout) × Iload\n"
                    "2. Check datasheet for θJA (thermal resistance)\n"
                    "3. Verify: Tj = Ta + (P × θJA) < Tj_max\n"
                    "4. Add copper pour around component for heat spreading\n"
                    "5. Consider SMPS if dropout power is excessive"
                ),
                affected_components=[tc.refdes]
            ))
        
        return issues
    
    def _identify_power_nets(self, pcb_data) -> List[PowerNet]:
        """Identify power nets from design"""
        power_nets = []
        
        power_patterns = {
            'vcc': 5.0,
            '5v': 5.0,
            '3v3': 3.3,
            '3.3v': 3.3,
            '12v': 12.0,
            'vbat': 4.2,
            'vin': 12.0,
            'vdd': 3.3,
        }
        
        for net in pcb_data.nets:
            net_lower = net.name.lower().replace('_', '').replace('-', '')
            
            for pattern, voltage in power_patterns.items():
                if pattern in net_lower:
                    power_nets.append(PowerNet(
                        net_name=net.name,
                        voltage=voltage,
                        estimated_current_a=1.0,  # Default estimate
                        net_type="power"
                    ))
                    break
        
        return power_nets
    
    def _check_power_net_traces(
        self, 
        power_nets: List[PowerNet],
        pcb_data
    ) -> List[Issue]:
        """Check power net trace widths"""
        issues = []
        
        # Create trace width reference table
        trace_table = []
        for current in [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0]:
            width_ext, _ = CurrentCapacity.calculate_trace_width_for_current(
                current, self.copper_thickness_mm, 10.0, LayerPosition.EXTERNAL
            )
            width_int, _ = CurrentCapacity.calculate_trace_width_for_current(
                current, self.copper_thickness_mm, 10.0, LayerPosition.INTERNAL
            )
            trace_table.append(
                f"• {current}A: {width_ext:.2f}mm external, {width_int:.2f}mm internal"
            )
        
        issues.append(Issue(
            issue_code="THERM-TRACE-001",
            severity=IssueSeverity.WARNING,
            category="thermal",
            title=f"Power trace width requirements ({self.copper_oz}oz Cu, 10°C rise)",
            description=(
                f"Minimum trace widths per IPC-2152:\n\n" +
                "\n".join(trace_table) +
                "\n\nDetected power nets:\n" +
                "\n".join([f"• {pn.net_name}" for pn in power_nets[:5]])
            ),
            suggested_fix=(
                "1. Identify maximum current for each power net\n"
                "2. Size traces according to table above\n"
                "3. Use polygon pours for high-current paths\n"
                "4. Add vias for layer transitions (1 via per 0.5A)\n"
                "5. Consider 2oz copper for high-current boards"
            ),
            affected_nets=[pn.net_name for pn in power_nets],
            metadata={
                "copper_oz": self.copper_oz,
                "ambient_temp_c": self.ambient_temp_c,
                "temp_rise_c": 10.0
            }
        ))
        
        return issues
    
    def _create_via_guidelines(self) -> List[Issue]:
        """Create via current capacity guidelines"""
        issues = []
        
        # Calculate via capacities
        via_table = []
        for drill in [0.3, 0.4, 0.5]:
            cap, _ = CurrentCapacity.calculate_via_current_capacity(
                diameter_mm=drill + 0.2,
                drill_mm=drill,
                temp_rise_c=10.0
            )
            via_table.append(f"• {drill}mm drill: ~{cap}A per via")
        
        issues.append(Issue(
            issue_code="THERM-VIA-001",
            severity=IssueSeverity.INFO,
            category="thermal",
            title="Via current carrying capacity reference",
            description=(
                "Via current capacity (10°C rise, 1mil plating):\n\n" +
                "\n".join(via_table) +
                "\n\nFor layer transitions:\n"
                "• 1A: Use 2+ vias\n"
                "• 3A: Use 6+ vias\n"
                "• 5A: Use 10+ vias"
            ),
            suggested_fix=(
                "1. Use multiple vias for power transitions\n"
                "2. Distribute vias across trace width\n"
                "3. Larger drill = more current capacity\n"
                "4. Via arrays better than via stitching"
            )
        ))
        
        return issues
    
    def _create_general_thermal_guidelines(self) -> List[Issue]:
        """Create general thermal design guidelines"""
        issues = []
        
        issues.append(Issue(
            issue_code="THERM-GENERAL-001",
            severity=IssueSeverity.INFO,
            category="thermal",
            title="General thermal design guidelines",
            description=(
                "PCB thermal management best practices:\n\n"
                "1. COPPER SPREADING:\n"
                "   • Add copper pours around hot components\n"
                "   • Connect to internal planes for heat spreading\n"
                "   • Larger area = lower thermal resistance\n\n"
                "2. THERMAL VIAS:\n"
                "   • 0.3mm drill, 1mm pitch grid pattern\n"
                "   • Connect exposed pads to inner GND plane\n"
                "   • More vias = better heat transfer\n\n"
                "3. COMPONENT PLACEMENT:\n"
                "   • Don't cluster heat sources\n"
                "   • Place hot components near airflow\n"
                "   • Keep sensitive components away from heat"
            ),
            suggested_fix=(
                "1. Review thermal paths from each heat source\n"
                "2. Add copper pours on unused areas\n"
                "3. Consider heatsinks for high-power components\n"
                "4. Calculate total board power dissipation"
            )
        ))
        
        # Thermal resistance reference
        issues.append(Issue(
            issue_code="THERM-GENERAL-002",
            severity=IssueSeverity.INFO,
            category="thermal",
            title="Thermal resistance (θJA) reference",
            description=(
                "Typical package thermal resistance (θJA):\n\n"
                "• SOT-23: 200-300 °C/W\n"
                "• SOT-223: 50-80 °C/W (with tab to plane)\n"
                "• SOIC-8: 100-150 °C/W\n"
                "• TQFP-48: 40-60 °C/W\n"
                "• QFN-16 (exposed pad): 30-50 °C/W\n"
                "• TO-220: 30-60 °C/W (no heatsink)\n\n"
                "Junction temp: Tj = Ta + (P × θJA)"
            ),
            suggested_fix=(
                "1. Calculate junction temperature for power devices\n"
                "2. Verify Tj < Tj_max (typically 125-150°C)\n"
                "3. Add thermal vias to reduce θJA\n"
                "4. Consider forced air cooling for high power"
            )
        ))
        
        return issues
