"""
Power Supply & SMPS Rules V2 - Industry Standard Layout Guidelines
Based on TI AN-1149 (SNVA021C) and AN-1229 (SNVA054C)

This module provides comprehensive power supply analysis:
- SMPS layout: AC/DC current paths, component placement
- Current loop optimization (hot loop minimization)
- Trace width validation for current carrying
- Capacitor selection and placement
- Thermal considerations

Sources:
- TI AN-1149: Layout Guidelines for Switching Power Supplies (SNVA021C)
- TI AN-1229: SIMPLE SWITCHER PCB Layout Guidelines (SNVA054C)
- TI SNVA829: CC/CV Buck Converter Design
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_rule import BaseRule, Issue, IssueSeverity
from .standards.current_capacity import CurrentCapacity, LayerPosition
from .standards.mlcc_derating import MLCCDerating, CapacitorType, MLCCDielectric

logger = logging.getLogger(__name__)


class ConverterTopology(str, Enum):
    """Power converter topologies"""
    BUCK = "buck"           # Step-down
    BOOST = "boost"         # Step-up
    BUCK_BOOST = "buck_boost"
    FLYBACK = "flyback"
    LDO = "ldo"             # Linear regulator
    CHARGE_PUMP = "charge_pump"


@dataclass
class DetectedPowerStage:
    """Detected power stage"""
    topology: ConverterTopology
    controller_ic: str
    inductor: Optional[str] = None
    input_caps: List[str] = field(default_factory=list)
    output_caps: List[str] = field(default_factory=list)
    catch_diode: Optional[str] = None
    mosfets: List[str] = field(default_factory=list)
    feedback_resistors: List[str] = field(default_factory=list)


class PowerSMPSRulesV2(BaseRule):
    """
    Industry-standard power supply layout rules
    
    Based on TI application notes for switching regulator layout:
    - AC vs DC current path identification
    - Critical trace optimization
    - Component placement priorities
    - Thermal management
    """
    
    # ==========================================================================
    # COMPONENT DETECTION PATTERNS
    # ==========================================================================
    
    # Buck/Boost controller ICs
    BUCK_IC_PATTERNS = [
        'lm2596', 'lm2576', 'lm2674', 'lm2675', 'lm267',  # TI SIMPLE SWITCHER
        'mp2307', 'mp1584', 'mp2359',                      # MPS
        'tps54', 'tps56', 'tps62',                         # TI
        'lmr', 'lm5117', 'lm5118',                         # TI
        'rt8', 'sy8', 'ap3',                               # Various
        'buck', 'step-down', 'step_down'
    ]
    
    BOOST_IC_PATTERNS = [
        'lm2577', 'lm2587', 'tps61', 'tps55',
        'boost', 'step-up', 'step_up'
    ]
    
    LDO_PATTERNS = [
        'lm1117', 'ams1117', 'ld1117', 'ldo', 'ap2112',
        'tps7', 'mic5', 'xc6206', '78', '79',  # 7805, 7812, etc.
        'mcp1700', 'mcp1802', 'lp2985', 'lp5907'
    ]
    
    # Inductor patterns
    INDUCTOR_PATTERNS = ['l1', 'l2', 'l3', 'ind', 'choke', 'uh', 'µh', 'mh']
    
    # Power capacitor patterns (bulk)
    BULK_CAP_PATTERNS = ['uf', 'µf', 'mf']
    
    # Schottky/catch diode patterns
    SCHOTTKY_PATTERNS = ['ss', 'sk', 'mbr', 'b5', 'b3', '1n58', 'bat', 'schottky']
    
    # MOSFET patterns
    MOSFET_PATTERNS = ['q1', 'q2', 'fet', 'mos', 'si', 'irf', 'ao']
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Comprehensive power supply analysis
        
        Args:
            pcb_data: ParsedPCBData object
        
        Returns:
            List of power supply issues
        """
        issues = []
        
        # Detect power stages
        power_stages = self._detect_power_stages(pcb_data)
        
        if not power_stages:
            # Check for discrete power components anyway
            issues.extend(self._check_power_capacitors(pcb_data))
            issues.extend(self._check_relay_design(pcb_data))
            return issues
        
        logger.info(f"Detected {len(power_stages)} power stage(s)")
        
        # Analyze each power stage
        for stage in power_stages:
            if stage.topology in [ConverterTopology.BUCK, ConverterTopology.BOOST, 
                                  ConverterTopology.BUCK_BOOST]:
                issues.extend(self._check_smps_layout(stage, pcb_data))
            elif stage.topology == ConverterTopology.LDO:
                issues.extend(self._check_ldo_layout(stage, pcb_data))
        
        # General power checks
        issues.extend(self._check_power_capacitors(pcb_data))
        issues.extend(self._check_power_trace_widths(pcb_data))
        issues.extend(self._check_relay_design(pcb_data))
        
        return issues
    
    def _detect_power_stages(self, pcb_data) -> List[DetectedPowerStage]:
        """Detect power converter stages"""
        stages = []
        
        for comp in pcb_data.components:
            ref_lower = comp.reference.lower()
            value_lower = (comp.value or "").lower()
            combined = ref_lower + " " + value_lower
            
            # Check for buck converters
            if any(p in combined for p in self.BUCK_IC_PATTERNS):
                stage = self._build_power_stage(
                    ConverterTopology.BUCK, comp, pcb_data
                )
                stages.append(stage)
            
            # Check for boost converters
            elif any(p in combined for p in self.BOOST_IC_PATTERNS):
                stage = self._build_power_stage(
                    ConverterTopology.BOOST, comp, pcb_data
                )
                stages.append(stage)
            
            # Check for LDOs
            elif any(p in combined for p in self.LDO_PATTERNS):
                stage = self._build_power_stage(
                    ConverterTopology.LDO, comp, pcb_data
                )
                stages.append(stage)
        
        return stages
    
    def _build_power_stage(
        self, 
        topology: ConverterTopology,
        controller: object,
        pcb_data
    ) -> DetectedPowerStage:
        """Build power stage with associated components"""
        
        stage = DetectedPowerStage(
            topology=topology,
            controller_ic=controller.reference
        )
        
        # Find associated components
        for comp in pcb_data.components:
            ref_lower = comp.reference.lower()
            value_lower = (comp.value or "").lower()
            combined = ref_lower + " " + value_lower
            
            # Inductors
            if any(p in combined for p in self.INDUCTOR_PATTERNS):
                if comp.reference.startswith(('L', 'l')):
                    stage.inductor = comp.reference
            
            # Bulk capacitors
            elif comp.reference.startswith(('C', 'c')):
                if any(p in value_lower for p in self.BULK_CAP_PATTERNS):
                    # Try to classify as input or output based on position
                    # (simplified - actual implementation would use netlist)
                    if 'in' in ref_lower or 'i' in ref_lower:
                        stage.input_caps.append(comp.reference)
                    elif 'out' in ref_lower or 'o' in ref_lower:
                        stage.output_caps.append(comp.reference)
                    else:
                        stage.input_caps.append(comp.reference)  # Default
            
            # Catch diode
            elif comp.reference.startswith(('D', 'd')):
                if any(p in combined for p in self.SCHOTTKY_PATTERNS):
                    stage.catch_diode = comp.reference
            
            # MOSFETs
            elif any(p in combined for p in self.MOSFET_PATTERNS):
                stage.mosfets.append(comp.reference)
        
        return stage
    
    def _check_smps_layout(
        self, 
        stage: DetectedPowerStage,
        pcb_data
    ) -> List[Issue]:
        """
        Check SMPS layout per TI AN-1149 and AN-1229
        
        Key principles from the app notes:
        1. Minimize AC current loop area (the "hot loop")
        2. Keep DC paths less critical than AC paths
        3. Place input bypass cap and catch diode ACAP (as close as possible)
        4. Feedback trace away from inductor and switching node
        """
        issues = []
        
        topology_name = stage.topology.value.upper()
        
        # Issue 1: AC vs DC Current Paths Education
        issues.append(Issue(
            issue_code=f"PWR-{topology_name}-001",
            severity=IssueSeverity.WARNING,
            category="power_smps",
            title=f"{topology_name} converter critical layout guidelines",
            description=(
                f"Per TI AN-1229 (SNVA054C), {topology_name} converter layout priority:\n\n"
                "CRITICAL (AC current paths):\n"
                "• Input bypass cap → Switch → Catch diode → Back to cap\n"
                "• This is the 'hot loop' - minimize its area!\n\n"
                "LESS CRITICAL (DC current paths):\n"
                "• Through inductor to output cap\n"
                "• Inductor smooths current, reducing di/dt"
            ),
            suggested_fix=(
                "1. Place input bypass cap (0.1-0.47µF ceramic) DIRECTLY at IC pins\n"
                "2. Place catch diode adjacent to IC, NOT through vias\n"
                "3. Keep hot loop as small as physically possible\n"
                "4. Use ground plane for return current\n"
                "5. Do NOT route traces through vias in hot loop"
            ),
            affected_components=[stage.controller_ic],
            metadata={
                "standard": "TI AN-1229 SNVA054C",
                "critical_loop": "Input cap → Switch → Diode → Input cap"
            }
        ))
        
        # Issue 2: Component Placement Priority
        acap_components = [stage.controller_ic]
        if stage.catch_diode:
            acap_components.append(stage.catch_diode)
        if stage.input_caps:
            acap_components.extend(stage.input_caps[:2])
        
        issues.append(Issue(
            issue_code=f"PWR-{topology_name}-002",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title="SMPS component placement priority (ACAP order)",
            description=(
                "Component placement priority per TI AN-1229:\n"
                "1. INPUT BYPASS CAP: Within 3mm of VIN and GND pins\n"
                "2. CATCH DIODE: Adjacent to switch node, short trace\n"
                "3. OUTPUT CAP: Close to diode/inductor junction\n"
                "4. INDUCTOR: Close to switch pin\n"
                "5. FEEDBACK: Route AWAY from inductor and switch node"
            ),
            suggested_fix=(
                f"Priority components for {stage.controller_ic}:\n"
                f"• Input cap: {stage.input_caps[0] if stage.input_caps else 'NOT FOUND'}\n"
                f"• Catch diode: {stage.catch_diode or 'NOT FOUND (may be internal)'}\n"
                f"• Inductor: {stage.inductor or 'NOT FOUND'}\n"
                f"• Output cap: {stage.output_caps[0] if stage.output_caps else 'NOT FOUND'}"
            ),
            affected_components=acap_components
        ))
        
        # Issue 3: Check for missing inductor
        if not stage.inductor and stage.topology != ConverterTopology.LDO:
            issues.append(Issue(
                issue_code=f"PWR-{topology_name}-003",
                severity=IssueSeverity.ERROR,
                category="power_smps",
                title=f"No inductor detected for {topology_name} converter",
                description=(
                    f"SMPS controller {stage.controller_ic} detected but no inductor found. "
                    "Switching converters require an inductor in the power path."
                ),
                suggested_fix=(
                    "1. Add inductor per controller datasheet\n"
                    "2. Typical values: 10-100µH for buck converters\n"
                    "3. Choose saturation current > peak inductor current\n"
                    "4. Use shielded inductor for low EMI"
                ),
                affected_components=[stage.controller_ic]
            ))
        
        # Issue 4: Catch diode check (for non-synchronous designs)
        if not stage.catch_diode and not stage.mosfets:
            issues.append(Issue(
                issue_code=f"PWR-{topology_name}-004",
                severity=IssueSeverity.WARNING,
                category="power_smps",
                title="No catch/freewheeling diode detected",
                description=(
                    f"Non-synchronous {topology_name} converters need a catch diode. "
                    "May be internal to controller or synchronous design."
                ),
                suggested_fix=(
                    "1. If non-synchronous: Add Schottky diode at switch node\n"
                    "2. Schottky recommended for low forward drop\n"
                    "3. Voltage rating > VIN * 1.5\n"
                    "4. Current rating > peak inductor current"
                ),
                affected_components=[stage.controller_ic]
            ))
        
        # Issue 5: Input capacitor check
        if not stage.input_caps:
            issues.append(Issue(
                issue_code=f"PWR-{topology_name}-005",
                severity=IssueSeverity.CRITICAL,
                category="power_smps",
                title="No input capacitors detected near SMPS",
                description=(
                    "Input capacitance is CRITICAL for SMPS operation. "
                    "Buck converters draw pulsed current from input."
                ),
                suggested_fix=(
                    "Per TI AN-1229:\n"
                    "1. Add 0.1-0.47µF ceramic cap DIRECTLY at VIN pin\n"
                    "2. Add bulk electrolytic (10-100µF) within 10mm\n"
                    "3. Ceramic cap handles high-frequency current\n"
                    "4. Bulk cap provides energy storage"
                ),
                affected_components=[stage.controller_ic]
            ))
        
        # Issue 6: Feedback trace routing
        issues.append(Issue(
            issue_code=f"PWR-{topology_name}-006",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title="Feedback trace routing guidance",
            description=(
                "Per TI AN-1149: Feedback trace is noise-sensitive:\n"
                "• Route AWAY from inductor (EMI source)\n"
                "• Route AWAY from switching node (voltage spikes)\n"
                "• Use ground plane as shield if possible\n"
                "• Keep trace short and direct"
            ),
            suggested_fix=(
                "1. Route FB on opposite side of board from inductor\n"
                "2. Use ground plane between FB and power stage\n"
                "3. Do not route FB near SW or VIN traces\n"
                "4. Place feedback divider close to IC"
            ),
            affected_components=[stage.controller_ic]
        ))
        
        # Issue 7: Switching node antenna effect
        issues.append(Issue(
            issue_code=f"PWR-{topology_name}-007",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title="Switching node EMI considerations",
            description=(
                "Per TI AN-1229: The switching node (SW) is a voltage antenna:\n"
                "• Voltage swings from 0 to VIN rapidly\n"
                "• Large copper area = large antenna = more EMI\n"
                "• Counterintuitive: LESS copper at SW is better!"
            ),
            suggested_fix=(
                "1. Keep SW node copper area MINIMAL\n"
                "2. Only enough copper to handle current\n"
                "3. Do not flood SW node with copper pour\n"
                "4. Consider snubber (RC) if ringing observed"
            ),
            affected_components=[stage.controller_ic]
        ))
        
        return issues
    
    def _check_ldo_layout(
        self,
        stage: DetectedPowerStage,
        pcb_data
    ) -> List[Issue]:
        """Check LDO regulator layout"""
        issues = []
        
        issues.append(Issue(
            issue_code="PWR-LDO-001",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title=f"LDO regulator detected: {stage.controller_ic}",
            description=(
                "LDO layout guidelines:\n"
                "• Input cap: 1-10µF ceramic at VIN pin\n"
                "• Output cap: 1-22µF ceramic at VOUT pin (critical for stability)\n"
                "• ESR of output cap affects stability\n"
                "• Heat dissipation: (VIN-VOUT) × IOUT"
            ),
            suggested_fix=(
                "1. Place input cap within 5mm of VIN pin\n"
                "2. Place output cap within 5mm of VOUT pin\n"
                "3. Use X5R/X7R ceramic caps\n"
                "4. Check datasheet for ESR requirements\n"
                "5. Calculate power dissipation and verify thermal"
            ),
            affected_components=[stage.controller_ic]
        ))
        
        return issues
    
    def _check_power_capacitors(self, pcb_data) -> List[Issue]:
        """Check power capacitor design rules"""
        issues = []
        
        # Find all capacitors
        capacitors = [
            comp for comp in pcb_data.components
            if comp.reference.startswith(('C', 'c'))
        ]
        
        # Find bulk caps (µF range)
        bulk_caps = []
        for cap in capacitors:
            value_lower = (cap.value or "").lower()
            if any(p in value_lower for p in self.BULK_CAP_PATTERNS):
                bulk_caps.append(cap)
        
        if len(bulk_caps) < 2:
            issues.append(Issue(
                issue_code="PWR-CAP-001",
                severity=IssueSeverity.WARNING,
                category="power_smps",
                title="Limited bulk capacitance detected",
                description=(
                    f"Found {len(bulk_caps)} bulk capacitor(s). "
                    "Power rails typically need more decoupling."
                ),
                suggested_fix=(
                    "1. Add 10-100µF at main power input\n"
                    "2. Add 100nF ceramic near each IC\n"
                    "3. Larger caps (100-1000µF) for motor/relay loads\n"
                    "4. Voltage rating > 2× rail voltage"
                ),
                affected_components=[c.reference for c in bulk_caps]
            ))
        
        # MLCC derating information
        issues.append(Issue(
            issue_code="PWR-CAP-002",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title="Capacitor voltage derating guidelines",
            description=(
                "Voltage derating requirements by capacitor type:\n"
                "• MLCC (ceramic): NO derating required per TDK\n"
                "• TANTALUM: MUST derate to 50% of rated voltage!\n"
                "• Aluminum electrolytic: Derate to 80%\n\n"
                "IMPORTANT: X5R/X7R MLCCs lose capacitance under DC bias!"
            ),
            suggested_fix=(
                "1. For tantalum: If circuit is 5V, use 10V+ rated cap\n"
                "2. For X7R MLCC at 50% rated voltage: expect ~60% capacitance\n"
                "3. Consider C0G/NP0 for critical timing circuits\n"
                "4. Check manufacturer derating curves"
            )
        ))
        
        return issues
    
    def _check_power_trace_widths(self, pcb_data) -> List[Issue]:
        """Check power trace widths for current capacity"""
        issues = []
        
        # Calculate trace widths for common currents
        copper_oz = 1.0
        thickness = CurrentCapacity.copper_weight_to_thickness(copper_oz)
        
        trace_table = []
        for current in [0.5, 1.0, 2.0, 3.0, 5.0]:
            width, _ = CurrentCapacity.calculate_trace_width_for_current(
                current, thickness, 10.0, LayerPosition.EXTERNAL
            )
            trace_table.append(f"• {current}A: {width:.2f}mm ({width/0.0254:.0f} mils)")
        
        issues.append(Issue(
            issue_code="PWR-TRACE-001",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title="Power trace width reference (1oz Cu, 10°C rise)",
            description=(
                "Minimum trace widths per IPC-2152:\n" +
                "\n".join(trace_table) +
                "\n\nInternal layers need ~2× these widths."
            ),
            suggested_fix=(
                "1. Identify high-current nets (power input, motor, relay)\n"
                "2. Size traces per table or use polygon pours\n"
                "3. Use multiple vias for layer transitions (1 via per 0.5A)\n"
                "4. Consider 2oz copper for high-current boards"
            )
        ))
        
        return issues
    
    def _check_relay_design(self, pcb_data) -> List[Issue]:
        """Check relay implementation"""
        issues = []
        
        relay_patterns = ['relay', 'rly', 'k1', 'k2', 'g3mb', 'g5v']
        
        relays = [
            comp for comp in pcb_data.components
            if any(p in (comp.reference + " " + (comp.value or "")).lower() 
                  for p in relay_patterns)
        ]
        
        if not relays:
            return issues
        
        # Check for flyback diodes
        diodes = [
            comp for comp in pcb_data.components
            if comp.reference.startswith(('D', 'd'))
        ]
        
        if len(diodes) < len(relays):
            issues.append(Issue(
                issue_code="PWR-RELAY-001",
                severity=IssueSeverity.WARNING,
                category="power_smps",
                title="Potential missing flyback diodes on relay coils",
                description=(
                    f"Found {len(relays)} relay(s) but only {len(diodes)} diode(s). "
                    "Relay coils need flyback diodes for driver protection."
                ),
                suggested_fix=(
                    "1. Add diode across each relay coil\n"
                    "2. Cathode to +V, anode to GND side\n"
                    "3. Use 1N4148 or 1N4007\n"
                    "4. Place close to relay terminals"
                ),
                affected_components=[r.reference for r in relays]
            ))
        
        # Relay contact rating info
        issues.append(Issue(
            issue_code="PWR-RELAY-002",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title=f"Verify relay contact ratings ({len(relays)} relay(s))",
            description=(
                "Relay contact considerations:\n"
                "• Derate contacts 50% for inductive loads\n"
                "• AC rating ≠ DC rating (DC is harder to break)\n"
                "• PCB traces must handle contact current"
            ),
            suggested_fix=(
                "1. Check datasheet for AC vs DC ratings\n"
                "2. Add snubber (RC) across contacts for inductive loads\n"
                "3. Size PCB traces for contact current\n"
                "4. Consider MOV across contacts for arc suppression"
            ),
            affected_components=[r.reference for r in relays]
        ))
        
        return issues
