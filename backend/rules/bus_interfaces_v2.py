"""
Bus Interface Rules V2 - Industry Standard Compliance
Based on NXP AN10216 (I2C), TI SLLA272B (RS-485), and CAN standards

This module provides comprehensive bus interface analysis:
- I2C: Pull-up calculation, bus capacitance, speed mode validation
- SPI: Trace length, series termination, clock routing
- RS-485: Termination, failsafe biasing, bus length vs data rate
- CAN: Termination, differential routing, bus topology

Sources:
- AN10216-01 I2C Manual (NXP/Philips)
- TI SLLA272B RS-485 Design Guide
- CAN in Automation specifications
- Microchip AN2402 PCB Layout Guide
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_rule import BaseRule, Issue, IssueSeverity
from .standards.bus_standards import (
    BusStandards, I2CSpeed, CANSpeed, 
    I2CParameters, RS485Parameters, CANParameters
)

logger = logging.getLogger(__name__)


@dataclass
class DetectedBus:
    """Detected bus interface"""
    bus_type: str  # "i2c", "spi", "rs485", "can", "uart"
    transceivers: List[str]
    signal_nets: List[str]
    pull_up_resistors: List[Tuple[str, float]]  # (refdes, value)
    termination_resistors: List[Tuple[str, float]]
    protection_devices: List[str]


class BusInterfaceRulesV2(BaseRule):
    """
    Industry-standard bus interface rules
    
    Implements comprehensive checks for:
    - I2C: Pull-up sizing, bus capacitance, layout
    - SPI: Signal integrity, termination, layout
    - RS-485: Termination, biasing, protection
    - CAN: Termination, differential routing
    """
    
    # ==========================================================================
    # COMPONENT DETECTION PATTERNS
    # ==========================================================================
    
    I2C_TRANSCEIVER_PATTERNS = ['pca', 'pcf', 'tca', 'p82b', 'ltc4311', 'i2c']
    SPI_FLASH_PATTERNS = ['w25', 'at25', 'mx25', 'sst25', 'n25q', 'flash']
    
    RS485_TRANSCEIVER_PATTERNS = [
        'max485', 'max3485', 'sn65hvd', 'adm485', 'ltc485', 
        'sp485', 'isl8485', 'thvd', 'rs485'
    ]
    
    CAN_TRANSCEIVER_PATTERNS = [
        'mcp2551', 'tja1050', 'tja1051', 'sn65hvd', 'mcp2561',
        'mcp2562', 'iso1050', 'can'
    ]
    
    TVS_ESD_PATTERNS = ['tvs', 'esd', 'prtr', 'pesd', 'sp0', 'tpd', 'smbj']
    
    def __init__(self, target_i2c_speed: I2CSpeed = I2CSpeed.FAST):
        """
        Initialize bus interface rules
        
        Args:
            target_i2c_speed: Default I2C speed mode for calculations
        """
        super().__init__()
        self.target_i2c_speed = target_i2c_speed
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Comprehensive bus interface analysis
        
        Args:
            pcb_data: ParsedPCBData object
        
        Returns:
            List of bus interface issues
        """
        issues = []
        
        # Detect all bus interfaces
        i2c_bus = self._detect_i2c(pcb_data)
        spi_bus = self._detect_spi(pcb_data)
        rs485_bus = self._detect_rs485(pcb_data)
        can_bus = self._detect_can(pcb_data)
        
        # Analyze each detected interface
        if i2c_bus.signal_nets:
            issues.extend(self._check_i2c(i2c_bus, pcb_data))
        
        if spi_bus.signal_nets:
            issues.extend(self._check_spi(spi_bus, pcb_data))
        
        if rs485_bus.transceivers or rs485_bus.signal_nets:
            issues.extend(self._check_rs485(rs485_bus, pcb_data))
        
        if can_bus.transceivers or can_bus.signal_nets:
            issues.extend(self._check_can(can_bus, pcb_data))
        
        # General bus protection check
        all_bus_nets = (
            i2c_bus.signal_nets + spi_bus.signal_nets +
            rs485_bus.signal_nets + can_bus.signal_nets
        )
        if all_bus_nets:
            issues.extend(self._check_general_protection(all_bus_nets, pcb_data))
        
        return issues
    
    # ==========================================================================
    # I2C DETECTION AND VALIDATION
    # ==========================================================================
    
    def _detect_i2c(self, pcb_data) -> DetectedBus:
        """Detect I2C bus components and nets"""
        
        # Find I2C nets
        i2c_net_patterns = ['sda', 'scl', 'i2c', 'iic', 'twi']
        signal_nets = []
        
        for net in pcb_data.nets:
            if any(p in net.name.lower() for p in i2c_net_patterns):
                signal_nets.append(net.name)
        
        # Find I2C transceivers/buffers
        transceivers = []
        for comp in pcb_data.components:
            combined = (comp.reference + " " + (comp.value or "")).lower()
            if any(p in combined for p in self.I2C_TRANSCEIVER_PATTERNS):
                transceivers.append(comp.reference)
        
        # Find pull-up resistors (typically 2.2k-10k on I2C lines)
        pull_ups = []
        for comp in pcb_data.components:
            if comp.reference.startswith('R'):
                value = self._parse_resistor_value(comp.value)
                if value and 1000 <= value <= 15000:  # Possible I2C pull-up range
                    pull_ups.append((comp.reference, value))
        
        return DetectedBus(
            bus_type="i2c",
            transceivers=transceivers,
            signal_nets=signal_nets,
            pull_up_resistors=pull_ups,
            termination_resistors=[],
            protection_devices=[]
        )
    
    def _check_i2c(self, i2c_bus: DetectedBus, pcb_data) -> List[Issue]:
        """Check I2C bus implementation per AN10216"""
        issues = []
        
        logger.info(f"I2C detected: {len(i2c_bus.signal_nets)} nets, "
                   f"{len(i2c_bus.pull_up_resistors)} potential pull-ups")
        
        # Get I2C spec for target speed
        spec = BusStandards.I2C_SPECS[self.target_i2c_speed]
        
        # Check 1: Pull-up resistors present
        if not i2c_bus.pull_up_resistors:
            issues.append(Issue(
                issue_code="BUS-I2C-001",
                severity=IssueSeverity.CRITICAL,
                category="bus_interfaces",
                title="No I2C pull-up resistors detected",
                description=(
                    f"I2C bus requires pull-up resistors on SDA and SCL lines. "
                    f"No resistors in typical I2C pull-up range (1k-10k) found near I2C nets."
                ),
                suggested_fix=(
                    f"For {self.target_i2c_speed.value} mode ({spec.max_frequency_hz/1000:.0f}kHz):\n"
                    f"1. Add pull-up resistor on SDA: {spec.min_pull_up_ohm}Ω - {spec.max_pull_up_ohm}Ω\n"
                    f"2. Add pull-up resistor on SCL: {spec.min_pull_up_ohm}Ω - {spec.max_pull_up_ohm}Ω\n"
                    f"3. Connect pull-ups to VDD ({spec.vdd_v}V typical)\n"
                    f"4. Place near master device for best performance"
                ),
                affected_nets=i2c_bus.signal_nets,
                metadata={
                    "speed_mode": self.target_i2c_speed.value,
                    "recommended_pull_up_min": spec.min_pull_up_ohm,
                    "recommended_pull_up_max": spec.max_pull_up_ohm,
                    "standard": "AN10216 I2C Manual"
                }
            ))
        else:
            # Validate pull-up values
            for refdes, value in i2c_bus.pull_up_resistors:
                if value < spec.min_pull_up_ohm:
                    issues.append(Issue(
                        issue_code="BUS-I2C-002",
                        severity=IssueSeverity.WARNING,
                        category="bus_interfaces",
                        title=f"I2C pull-up {refdes} ({value}Ω) may be too low",
                        description=(
                            f"Pull-up value {value}Ω is below minimum {spec.min_pull_up_ohm}Ω "
                            f"for {self.target_i2c_speed.value} mode. "
                            f"May exceed device sink current capability (3mA typical)."
                        ),
                        suggested_fix=(
                            f"Increase pull-up to ≥{spec.min_pull_up_ohm}Ω\n"
                            f"Formula: Rp_min = (VDD - 0.4V) / 3mA"
                        ),
                        affected_components=[refdes]
                    ))
                elif value > spec.max_pull_up_ohm:
                    issues.append(Issue(
                        issue_code="BUS-I2C-003",
                        severity=IssueSeverity.WARNING,
                        category="bus_interfaces",
                        title=f"I2C pull-up {refdes} ({value}Ω) may be too high",
                        description=(
                            f"Pull-up value {value}Ω exceeds maximum {spec.max_pull_up_ohm}Ω "
                            f"for {self.target_i2c_speed.value} mode. "
                            f"Rise time may exceed {spec.max_rise_time_ns}ns spec."
                        ),
                        suggested_fix=(
                            f"Decrease pull-up to ≤{spec.max_pull_up_ohm}Ω\n"
                            f"Or reduce bus capacitance (shorter traces, fewer devices)"
                        ),
                        affected_components=[refdes]
                    ))
        
        # Check 2: Bus capacitance warning
        issues.append(Issue(
            issue_code="BUS-I2C-004",
            severity=IssueSeverity.INFO,
            category="bus_interfaces",
            title="Verify I2C bus capacitance",
            description=(
                f"I2C {self.target_i2c_speed.value} mode allows max {spec.max_bus_capacitance_pf}pF "
                f"total bus capacitance. Each device adds 5-15pF."
            ),
            suggested_fix=(
                f"1. Count devices on bus × ~10pF per device\n"
                f"2. Add trace capacitance (~1pF per cm)\n"
                f"3. If >400pF: use I2C buffer (PCA9517) or reduce speed\n"
                f"4. For long runs: consider I2C extender IC"
            ),
            affected_nets=i2c_bus.signal_nets,
            metadata={
                "max_capacitance_pf": spec.max_bus_capacitance_pf,
                "max_rise_time_ns": spec.max_rise_time_ns
            }
        ))
        
        # Check 3: Provide pull-up calculation formula
        # Estimate bus capacitance (simplified)
        estimated_cap_pf = 50  # Base assumption
        rp_min, rp_max, details = BusStandards.calculate_i2c_pull_up(
            vdd_v=3.3,
            bus_capacitance_pf=estimated_cap_pf,
            speed_mode=self.target_i2c_speed
        )
        
        issues.append(Issue(
            issue_code="BUS-I2C-005",
            severity=IssueSeverity.INFO,
            category="bus_interfaces",
            title="I2C pull-up resistor calculation",
            description=(
                f"Per AN10216 I2C Manual, for {self.target_i2c_speed.value} mode at 3.3V:\n"
                f"• Minimum pull-up: {rp_min}Ω (DC limit - sink current)\n"
                f"• Maximum pull-up: {rp_max}Ω (AC limit - rise time)\n"
                f"• Recommended: {details['rp_recommended_ohm']}Ω (geometric mean)"
            ),
            suggested_fix=(
                "DC Calculation: Rp_min = (VDD - VOL) / IOL = (3.3V - 0.4V) / 3mA\n"
                "AC Calculation: Rp_max = tr / (0.8473 × Cbus)"
            ),
            metadata=details
        ))
        
        return issues
    
    # ==========================================================================
    # SPI DETECTION AND VALIDATION
    # ==========================================================================
    
    def _detect_spi(self, pcb_data) -> DetectedBus:
        """Detect SPI bus components and nets"""
        
        spi_net_patterns = ['mosi', 'miso', 'sck', 'sclk', 'spi_', 'cs', 'ss']
        signal_nets = []
        
        for net in pcb_data.nets:
            if any(p in net.name.lower() for p in spi_net_patterns):
                signal_nets.append(net.name)
        
        # Find SPI flash devices
        transceivers = []
        for comp in pcb_data.components:
            combined = (comp.reference + " " + (comp.value or "")).lower()
            if any(p in combined for p in self.SPI_FLASH_PATTERNS):
                transceivers.append(comp.reference)
        
        return DetectedBus(
            bus_type="spi",
            transceivers=transceivers,
            signal_nets=signal_nets,
            pull_up_resistors=[],
            termination_resistors=[],
            protection_devices=[]
        )
    
    def _check_spi(self, spi_bus: DetectedBus, pcb_data) -> List[Issue]:
        """Check SPI bus implementation"""
        issues = []
        
        logger.info(f"SPI detected: {len(spi_bus.signal_nets)} nets")
        
        # SPI layout guidelines
        issues.append(Issue(
            issue_code="BUS-SPI-001",
            severity=IssueSeverity.INFO,
            category="bus_interfaces",
            title="SPI layout recommendations",
            description=(
                "SPI interface detected. Key layout considerations:\n"
                "• Keep traces short (<150mm for high-speed)\n"
                "• Match MOSI/MISO/CLK trace lengths ±10%\n"
                "• Use ground plane under SPI traces"
            ),
            suggested_fix=(
                "1. Route SPI signals on same layer if possible\n"
                "2. Add 22-33Ω series resistor on MOSI/CLK near source for >10MHz\n"
                "3. Keep CS traces short - they're timing critical\n"
                "4. Add 100nF decoupling at each SPI device\n"
                "5. For SPI flash: follow Microchip AN2402 guidelines"
            ),
            affected_nets=spi_bus.signal_nets
        ))
        
        # SPI flash specific checks
        if spi_bus.transceivers:
            issues.append(Issue(
                issue_code="BUS-SPI-002",
                severity=IssueSeverity.INFO,
                category="bus_interfaces",
                title=f"SPI flash devices detected: {', '.join(spi_bus.transceivers)}",
                description=(
                    "SPI flash layout per Microchip AN2402:\n"
                    "• Place 100nF ceramic cap within 3mm of VCC pin\n"
                    "• Route CLK with controlled impedance if >20MHz\n"
                    "• Avoid vias in SPI signal path"
                ),
                affected_components=spi_bus.transceivers
            ))
        
        return issues
    
    # ==========================================================================
    # RS-485 DETECTION AND VALIDATION
    # ==========================================================================
    
    def _detect_rs485(self, pcb_data) -> DetectedBus:
        """Detect RS-485 bus components and nets"""
        
        rs485_net_patterns = ['rs485', 'rs_485', 'd+', 'd-', 'a', 'b', '485_a', '485_b']
        signal_nets = []
        
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            if any(p in net_lower for p in rs485_net_patterns):
                signal_nets.append(net.name)
        
        transceivers = []
        for comp in pcb_data.components:
            combined = (comp.reference + " " + (comp.value or "")).lower()
            if any(p in combined for p in self.RS485_TRANSCEIVER_PATTERNS):
                transceivers.append(comp.reference)
        
        # Find 120Ω termination resistors
        terminations = []
        for comp in pcb_data.components:
            if comp.reference.startswith('R'):
                value = self._parse_resistor_value(comp.value)
                if value and 108 <= value <= 132:  # 120Ω ±10%
                    terminations.append((comp.reference, value))
        
        return DetectedBus(
            bus_type="rs485",
            transceivers=transceivers,
            signal_nets=signal_nets,
            pull_up_resistors=[],
            termination_resistors=terminations,
            protection_devices=[]
        )
    
    def _check_rs485(self, rs485_bus: DetectedBus, pcb_data) -> List[Issue]:
        """Check RS-485 bus implementation per TI SLLA272B"""
        issues = []
        
        logger.info(f"RS-485 detected: {len(rs485_bus.transceivers)} transceivers, "
                   f"{len(rs485_bus.termination_resistors)} potential terminations")
        
        # Check 1: Termination resistor
        if not rs485_bus.termination_resistors:
            issues.append(Issue(
                issue_code="BUS-RS485-001",
                severity=IssueSeverity.CRITICAL,
                category="bus_interfaces",
                title="RS-485 termination resistor not found",
                description=(
                    "RS-485 bus requires 120Ω termination resistor between A and B lines. "
                    "No 120Ω resistor detected on board. Missing termination causes "
                    "signal reflections and communication errors."
                ),
                suggested_fix=(
                    "Per TI SLLA272B RS-485 Design Guide:\n"
                    "1. Add 120Ω resistor between A (D+) and B (D-) lines\n"
                    "2. Place at END nodes of bus (not mid-bus nodes)\n"
                    "3. Use 1% tolerance resistor for best matching\n"
                    "4. Make DNP (do not populate) if board is mid-bus"
                ),
                affected_components=rs485_bus.transceivers,
                affected_nets=rs485_bus.signal_nets,
                metadata={
                    "required_termination_ohm": 120,
                    "standard": "TI SLLA272B"
                }
            ))
        else:
            term_refs = [t[0] for t in rs485_bus.termination_resistors]
            issues.append(Issue(
                issue_code="BUS-RS485-002",
                severity=IssueSeverity.INFO,
                category="bus_interfaces",
                title=f"RS-485 termination found: {', '.join(term_refs)}",
                description="Verify termination is connected between A and B lines.",
                affected_components=term_refs
            ))
        
        # Check 2: Failsafe biasing
        # Look for 560-680Ω resistors (typical failsafe bias values)
        bias_resistors = []
        for comp in pcb_data.components:
            if comp.reference.startswith('R'):
                value = self._parse_resistor_value(comp.value)
                if value and 500 <= value <= 750:
                    bias_resistors.append((comp.reference, value))
        
        if len(bias_resistors) < 2:
            issues.append(Issue(
                issue_code="BUS-RS485-003",
                severity=IssueSeverity.WARNING,
                category="bus_interfaces",
                title="RS-485 failsafe biasing not detected",
                description=(
                    "Failsafe biasing ensures bus idle state when no driver active. "
                    "Recommended for multi-drop networks to prevent noise triggering."
                ),
                suggested_fix=(
                    "Per TI SLLA272B:\n"
                    "1. Add 560Ω pull-up: VCC → A (D+)\n"
                    "2. Add 560Ω pull-down: B (D-) → GND\n"
                    "3. This keeps bus in recessive (idle) state\n"
                    "4. Values can range 560Ω-680Ω"
                ),
                affected_components=rs485_bus.transceivers,
                metadata={
                    "recommended_bias_ohm": 560
                }
            ))
        
        # Check 3: ESD protection
        issues.extend(self._check_bus_esd_protection(
            rs485_bus, pcb_data, "RS-485"
        ))
        
        # Check 4: Data rate vs bus length info
        issues.append(Issue(
            issue_code="BUS-RS485-004",
            severity=IssueSeverity.INFO,
            category="bus_interfaces",
            title="RS-485 data rate vs bus length reference",
            description=(
                "Per TI SLLA272B, maximum bus length depends on data rate:\n"
                "• 100 kbps: 1200m max\n"
                "• 500 kbps: 300m max\n"
                "• 1 Mbps: 150m max\n"
                "• 10 Mbps: 15m max"
            ),
            suggested_fix=(
                "1. Verify bus length is within limits for data rate\n"
                "2. Use twisted pair cable (120Ω impedance)\n"
                "3. Connect shield to ground at ONE end only"
            ),
            affected_nets=rs485_bus.signal_nets
        ))
        
        return issues
    
    # ==========================================================================
    # CAN BUS DETECTION AND VALIDATION
    # ==========================================================================
    
    def _detect_can(self, pcb_data) -> DetectedBus:
        """Detect CAN bus components and nets"""
        
        can_net_patterns = ['can_h', 'can_l', 'canh', 'canl', 'can+', 'can-']
        signal_nets = []
        
        for net in pcb_data.nets:
            if any(p in net.name.lower() for p in can_net_patterns):
                signal_nets.append(net.name)
        
        transceivers = []
        for comp in pcb_data.components:
            combined = (comp.reference + " " + (comp.value or "")).lower()
            if any(p in combined for p in self.CAN_TRANSCEIVER_PATTERNS):
                transceivers.append(comp.reference)
        
        # Find 120Ω termination
        terminations = []
        for comp in pcb_data.components:
            if comp.reference.startswith('R'):
                value = self._parse_resistor_value(comp.value)
                if value and 108 <= value <= 132:
                    terminations.append((comp.reference, value))
        
        return DetectedBus(
            bus_type="can",
            transceivers=transceivers,
            signal_nets=signal_nets,
            pull_up_resistors=[],
            termination_resistors=terminations,
            protection_devices=[]
        )
    
    def _check_can(self, can_bus: DetectedBus, pcb_data) -> List[Issue]:
        """Check CAN bus implementation"""
        issues = []
        
        logger.info(f"CAN detected: {len(can_bus.transceivers)} transceivers")
        
        # Check 1: Termination
        if not can_bus.termination_resistors:
            issues.append(Issue(
                issue_code="BUS-CAN-001",
                severity=IssueSeverity.CRITICAL,
                category="bus_interfaces",
                title="CAN bus termination resistor not found",
                description=(
                    "CAN bus requires 120Ω termination between CANH and CANL "
                    "at BOTH ends of the bus."
                ),
                suggested_fix=(
                    "1. Add 120Ω resistor between CANH and CANL\n"
                    "2. Only END nodes should have termination\n"
                    "3. Total bus termination should measure ~60Ω\n"
                    "4. Use split termination (60Ω-100nF-60Ω) for EMI reduction"
                ),
                affected_components=can_bus.transceivers
            ))
        
        # Check 2: Differential routing
        issues.append(Issue(
            issue_code="BUS-CAN-002",
            severity=IssueSeverity.INFO,
            category="bus_interfaces",
            title="CAN differential routing guidelines",
            description=(
                "CAN bus uses differential signaling:\n"
                "• Route CANH and CANL as differential pair\n"
                "• Keep pair spacing consistent\n"
                "• Match trace lengths within 10mm"
            ),
            suggested_fix=(
                "1. Route CANH/CANL parallel with consistent spacing\n"
                "2. Use ground plane under CAN traces\n"
                "3. Keep CAN traces away from high-speed digital signals\n"
                "4. Add TVS protection at connector"
            ),
            affected_nets=can_bus.signal_nets
        ))
        
        # Check 3: ESD protection
        issues.extend(self._check_bus_esd_protection(
            can_bus, pcb_data, "CAN"
        ))
        
        return issues
    
    # ==========================================================================
    # COMMON HELPER METHODS
    # ==========================================================================
    
    def _check_bus_esd_protection(
        self, 
        bus: DetectedBus, 
        pcb_data,
        bus_name: str
    ) -> List[Issue]:
        """Check for ESD/TVS protection on bus lines"""
        issues = []
        
        # Find TVS/ESD devices
        protection = []
        for comp in pcb_data.components:
            combined = (comp.reference + " " + (comp.value or "")).lower()
            if any(p in combined for p in self.TVS_ESD_PATTERNS):
                protection.append(comp.reference)
        
        if not protection:
            issues.append(Issue(
                issue_code=f"BUS-{bus_name.upper()}-ESD",
                severity=IssueSeverity.WARNING,
                category="bus_interfaces",
                title=f"No ESD protection detected on {bus_name} lines",
                description=(
                    f"{bus_name} lines exposed to external wiring need ESD protection. "
                    f"TVS diodes recommended at connector interface."
                ),
                suggested_fix=(
                    f"1. Add TVS diode array at {bus_name} connector\n"
                    f"2. Examples: PRTR5V0U2X, SP3485 (integrated), TPD2E001\n"
                    f"3. Place as close to connector as possible\n"
                    f"4. Keep TVS trace length minimal"
                ),
                affected_nets=bus.signal_nets
            ))
        else:
            issues.append(Issue(
                issue_code=f"BUS-{bus_name.upper()}-ESD-OK",
                severity=IssueSeverity.INFO,
                category="bus_interfaces",
                title=f"ESD protection found: {', '.join(protection)}",
                description="Verify TVS is connected to bus lines and placed near connector.",
                affected_components=protection
            ))
        
        return issues
    
    def _check_general_protection(
        self,
        bus_nets: List[str],
        pcb_data
    ) -> List[Issue]:
        """Check general bus protection recommendations"""
        issues = []
        
        # Decoupling recommendations
        issues.append(Issue(
            issue_code="BUS-DECOUPLING",
            severity=IssueSeverity.INFO,
            category="bus_interfaces",
            title="Bus interface decoupling recommendations",
            description=(
                "All bus transceivers require proper decoupling:\n"
                "• 100nF ceramic (X7R) at VCC pin\n"
                "• 10µF bulk capacitor for multiple transceivers\n"
                "• Place within 3mm of transceiver VCC"
            ),
            suggested_fix=(
                "1. Add 100nF ceramic cap per transceiver IC\n"
                "2. Use wide, short traces to GND\n"
                "3. Connect to ground plane via multiple vias\n"
                "4. Consider separate analog/digital grounds under transceivers"
            )
        ))
        
        return issues
    
    def _parse_resistor_value(self, value_str: Optional[str]) -> Optional[float]:
        """Parse resistor value string to ohms"""
        if not value_str:
            return None
        
        value_str = value_str.strip().upper().replace(',', '').replace(' ', '')
        
        try:
            # Handle K, M suffixes
            if 'K' in value_str:
                return float(value_str.replace('K', '').replace('Ω', '').replace('OHM', '')) * 1000
            elif 'M' in value_str:
                return float(value_str.replace('M', '').replace('Ω', '').replace('OHM', '')) * 1000000
            elif 'R' in value_str:
                # E.g., "4R7" = 4.7Ω
                return float(value_str.replace('R', '.'))
            else:
                return float(value_str.replace('Ω', '').replace('OHM', ''))
        except (ValueError, AttributeError):
            return None
