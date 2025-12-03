"""
Bus interface rules for RS-485, CAN, Ethernet, etc.
Common in building automation for fieldbus communication
"""
import logging
from typing import List
from .base_rule import BaseRule, Issue, IssueSeverity

logger = logging.getLogger(__name__)


class BusInterfaceRules(BaseRule):
    """Rules for communication bus interfaces"""
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Analyze bus interfaces
        
        Args:
            pcb_data: ParsedPCBData object
            
        Returns:
            List of bus interface issues
        """
        issues = []
        
        # Detect RS-485 interfaces
        rs485_info = self._detect_rs485(pcb_data)
        if rs485_info['detected']:
            issues.extend(self._check_rs485(rs485_info, pcb_data))
        
        # Detect CAN interfaces
        can_info = self._detect_can(pcb_data)
        if can_info['detected']:
            issues.extend(self._check_can(can_info, pcb_data))
        
        # Check general bus protection
        bus_nets = rs485_info.get('nets', []) + can_info.get('nets', [])
        if bus_nets:
            issues.extend(self._check_bus_protection(bus_nets, pcb_data))
        
        return issues
    
    def _detect_rs485(self, pcb_data) -> dict:
        """Detect RS-485 transceivers and nets"""
        rs485_keywords = ['485', 'rs485', 'max485', 'sn65', 'ltc485']
        
        transceivers = [
            comp for comp in pcb_data.components
            if any(kw in comp.value.lower() or kw in comp.reference.lower() 
                   for kw in rs485_keywords)
        ]
        
        # Find A/B nets
        ab_nets = [
            net for net in pcb_data.nets
            if any(kw in net.name.lower() 
                   for kw in ['rs485', 'rs_485', '_a', '_b', 'd+', 'd-'])
        ]
        
        detected = len(transceivers) > 0 or len(ab_nets) > 0
        
        if detected:
            logger.info(f"RS-485 detected: {len(transceivers)} transceivers, {len(ab_nets)} nets")
        
        return {
            'detected': detected,
            'transceivers': transceivers,
            'nets': ab_nets
        }
    
    def _check_rs485(self, rs485_info, pcb_data) -> List[Issue]:
        """Check RS-485 implementation"""
        issues = []
        
        transceivers = rs485_info['transceivers']
        
        # Check 1: Termination resistor (120Ω)
        termination_found = False
        for comp in pcb_data.components:
            if comp.reference.startswith('R') and '120' in comp.value:
                termination_found = True
                break
        
        if not termination_found:
            issue = Issue(
                issue_code="BUS-001",
                severity=IssueSeverity.CRITICAL,
                category="bus_interfaces",
                title="RS-485 termination resistor not found",
                description=(
                    "RS-485 bus requires 120Ω termination resistor between A and B lines "
                    "at each end of the bus. Missing termination causes signal reflections "
                    "and unreliable communication, especially in building automation with "
                    "long cable runs (10-100m+)."
                ),
                suggested_fix=(
                    "1. Add 120Ω resistor between RS485_A and RS485_B near the transceiver\n"
                    "2. Make it optional (DNP or switch) if board may be mid-bus\n"
                    "3. For end-node boards, populate by default\n"
                    "4. Consider failsafe bias resistors (e.g., 560Ω pull-up on A, pull-down on B)"
                ),
                affected_components=[t.reference for t in transceivers],
                affected_nets=rs485_info.get('nets', [])
            )
            issues.append(issue)
        
        # Check 2: ESD protection
        tvs_near_connector = self._find_tvs_near_bus(pcb_data)
        
        if not tvs_near_connector:
            issue = Issue(
                issue_code="BUS-002",
                severity=IssueSeverity.WARNING,
                category="bus_interfaces",
                title="No ESD protection detected on RS-485 lines",
                description=(
                    "RS-485 lines in building automation are exposed to ESD, surges, and "
                    "electrical noise from long wiring in walls/conduits. TVS diodes or "
                    "protection arrays recommended at connector."
                ),
                suggested_fix=(
                    "1. Add TVS diode array at connector (e.g., PRTR5V0U2X, SP3485)\n"
                    "2. Alternatively, individual TVS diodes on A and B lines\n"
                    "3. Place close to connector for effective protection\n"
                    "4. Consider common-mode choke for additional noise immunity"
                ),
                affected_components=[t.reference for t in transceivers]
            )
            issues.append(issue)
        
        # Check 3: Failsafe biasing
        bias_resistors = [
            comp for comp in pcb_data.components
            if comp.reference.startswith('R') and 
            any(val in comp.value for val in ['560', '680', '1k', '1K'])
        ]
        
        if len(bias_resistors) < 2:
            issue = Issue(
                issue_code="BUS-003",
                severity=IssueSeverity.INFO,
                category="bus_interfaces",
                title="RS-485 failsafe biasing not detected",
                description=(
                    "Failsafe biasing (pull-up on A, pull-down on B) ensures bus idles at "
                    "known state when no driver active. Not critical but improves robustness "
                    "in building automation multi-drop networks."
                ),
                suggested_fix=(
                    "1. Add 560-680Ω pull-up resistor from A to VCC\n"
                    "2. Add 560-680Ω pull-down resistor from B to GND\n"
                    "3. This keeps bus in recessive state when idle\n"
                    "4. Helps with false triggers in noisy environments"
                ),
                affected_components=[t.reference for t in transceivers]
            )
            issues.append(issue)
        
        return issues
    
    def _detect_can(self, pcb_data) -> dict:
        """Detect CAN transceivers and nets"""
        can_keywords = ['can', 'mcp2551', 'tja1050', 'sn65hvd']
        
        transceivers = [
            comp for comp in pcb_data.components
            if any(kw in comp.value.lower() or kw in comp.reference.lower() 
                   for kw in can_keywords)
        ]
        
        # Find CANH/CANL nets
        can_nets = [
            net for net in pcb_data.nets
            if any(kw in net.name.lower() 
                   for kw in ['can_h', 'can_l', 'canh', 'canl'])
        ]
        
        detected = len(transceivers) > 0 or len(can_nets) > 0
        
        if detected:
            logger.info(f"CAN detected: {len(transceivers)} transceivers, {len(can_nets)} nets")
        
        return {
            'detected': detected,
            'transceivers': transceivers,
            'nets': can_nets
        }
    
    def _check_can(self, can_info, pcb_data) -> List[Issue]:
        """Check CAN bus implementation"""
        issues = []
        
        transceivers = can_info['transceivers']
        
        # Check termination (120Ω between CANH and CANL)
        termination_found = any(
            comp.reference.startswith('R') and '120' in comp.value
            for comp in pcb_data.components
        )
        
        if not termination_found:
            issue = Issue(
                issue_code="BUS-004",
                severity=IssueSeverity.CRITICAL,
                category="bus_interfaces",
                title="CAN bus termination resistor not found",
                description=(
                    "CAN bus requires 120Ω termination resistor between CANH and CANL "
                    "at both ends of the bus. Missing termination causes communication errors."
                ),
                suggested_fix=(
                    "1. Add 120Ω resistor between CANH and CANL\n"
                    "2. Make it optional if board may be mid-bus\n"
                    "3. For end-nodes, populate by default"
                ),
                affected_components=[t.reference for t in transceivers]
            )
            issues.append(issue)
        
        return issues
    
    def _check_bus_protection(self, bus_nets, pcb_data) -> List[Issue]:
        """Check general bus protection"""
        issues = []
        
        # This is a simplified check
        tvs_count = len([
            comp for comp in pcb_data.components
            if 'tvs' in comp.value.lower() or 'esd' in comp.value.lower()
        ])
        
        if tvs_count == 0:
            issue = Issue(
                issue_code="BUS-005",
                severity=IssueSeverity.WARNING,
                category="bus_interfaces",
                title="Limited ESD protection for bus interfaces",
                description=(
                    "Bus interfaces exposed to building wiring should have TVS protection "
                    "against ESD and transients from long cable runs."
                ),
                suggested_fix=(
                    "Add TVS diode arrays or individual TVS diodes at connectors"
                ),
                affected_nets=[net.name for net in bus_nets] if hasattr(bus_nets[0], 'name') else bus_nets
            )
            issues.append(issue)
        
        return issues
    
    def _find_tvs_near_bus(self, pcb_data) -> bool:
        """Check if TVS components exist"""
        tvs_components = [
            comp for comp in pcb_data.components
            if any(kw in comp.value.lower() or kw in comp.reference.lower()
                   for kw in ['tvs', 'esd', 'prtr', 'sp3'])
        ]
        return len(tvs_components) > 0
