"""
Power supply and SMPS rules
Checks regulators, relay sizing, current paths
"""
import logging
from typing import List
from .base_rule import BaseRule, Issue, IssueSeverity

logger = logging.getLogger(__name__)


class PowerSMPSRules(BaseRule):
    """Rules for power supplies and high-current paths"""
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Analyze power supply design
        
        Args:
            pcb_data: ParsedPCBData object
            
        Returns:
            List of power-related issues
        """
        issues = []
        
        # Detect power regulators
        regulators = self._detect_regulators(pcb_data)
        if regulators:
            issues.extend(self._check_regulator_design(regulators, pcb_data))
        
        # Detect relays
        relays = self._detect_relays(pcb_data)
        if relays:
            issues.extend(self._check_relay_design(relays, pcb_data))
        
        # Check for bulk capacitors
        issues.extend(self._check_power_capacitors(pcb_data))
        
        return issues
    
    def _detect_regulators(self, pcb_data) -> List:
        """Detect voltage regulators and SMPS ICs"""
        regulator_keywords = [
            'lm2596', 'lm2575', 'mp2307', 'tps', 'lm317', 'ams1117',
            '7805', '7812', 'ld1117', 'ldo', 'vreg', 'buck', 'boost'
        ]
        
        regulators = [
            comp for comp in pcb_data.components
            if any(kw in comp.value.lower() or kw in comp.reference.lower()
                   for kw in regulator_keywords)
        ]
        
        if regulators:
            logger.info(f"Found {len(regulators)} power regulators")
        
        return regulators
    
    def _check_regulator_design(self, regulators, pcb_data) -> List[Issue]:
        """Check regulator implementation"""
        issues = []
        
        # Check for inductors (SMPS indicators)
        inductors = [
            comp for comp in pcb_data.components
            if comp.reference.startswith('L') and 
            any(unit in comp.value.lower() for unit in ['uh', 'µh', 'mh'])
        ]
        
        if len(inductors) == 0 and any('buck' in r.value.lower() or 'boost' in r.value.lower() 
                                       for r in regulators):
            issue = Issue(
                issue_code="PWR-001",
                severity=IssueSeverity.WARNING,
                category="power_smps",
                title="SMPS regulator without inductor detected",
                description=(
                    "Switching regulators detected but no inductors found. SMPS designs "
                    "require inductors in the power path. Missing inductor will cause "
                    "regulator failure."
                ),
                suggested_fix=(
                    "1. Add appropriately rated inductor per regulator datasheet\n"
                    "2. Typical values: 22-100µH for buck converters\n"
                    "3. Choose saturation current > peak inductor current\n"
                    "4. Low DCR for efficiency"
                ),
                affected_components=[r.reference for r in regulators]
            )
            issues.append(issue)
        
        # Check component proximity (simplified - just info message)
        if inductors and regulators:
            issue = Issue(
                issue_code="PWR-002",
                severity=IssueSeverity.INFO,
                category="power_smps",
                title=f"SMPS design detected with {len(inductors)} inductor(s)",
                description=(
                    "Switching regulator found. For optimal performance and low EMI, "
                    "ensure tight layout of power loop components."
                ),
                suggested_fix=(
                    "1. Keep input cap → switch → diode → output cap loop area small\n"
                    "2. Place inductor close to switch pin\n"
                    "3. Keep high-current traces short and wide\n"
                    "4. Ground plane under components for heat dissipation\n"
                    "5. Review thermal requirements for expected load current"
                ),
                affected_components=[r.reference for r in regulators] + [l.reference for l in inductors]
            )
            issues.append(issue)
        
        return issues
    
    def _detect_relays(self, pcb_data) -> List:
        """Detect relays and triacs"""
        relay_keywords = ['relay', 'rly', 'k1', 'k2', 'triac', 'g3mb']
        
        relays = [
            comp for comp in pcb_data.components
            if any(kw in comp.value.lower() or kw in comp.reference.lower()
                   for kw in relay_keywords)
        ]
        
        if relays:
            logger.info(f"Found {len(relays)} relays/switching elements")
        
        return relays
    
    def _check_relay_design(self, relays, pcb_data) -> List[Issue]:
        """Check relay implementation"""
        issues = []
        
        # Check for flyback diodes (if relay is present)
        diodes = [
            comp for comp in pcb_data.components
            if comp.reference.startswith('D')
        ]
        
        if len(diodes) < len(relays):
            issue = Issue(
                issue_code="PWR-003",
                severity=IssueSeverity.WARNING,
                category="power_smps",
                title="Potential missing flyback diodes on relay coils",
                description=(
                    f"Found {len(relays)} relays but only {len(diodes)} diodes on board. "
                    "Relay coils need flyback diodes to protect driver transistors from "
                    "inductive kickback when coil is de-energized."
                ),
                suggested_fix=(
                    "1. Add diode across each relay coil (cathode to +V, anode to GND side)\n"
                    "2. Use fast recovery diode like 1N4148 or 1N4007\n"
                    "3. Place diode physically close to relay\n"
                    "4. For faster relay release, can use diode + zener in series"
                ),
                affected_components=[r.reference for r in relays]
            )
            issues.append(issue)
        
        # Info about contact ratings
        issue = Issue(
            issue_code="PWR-004",
            severity=IssueSeverity.INFO,
            category="power_smps",
            title=f"Verify relay contact ratings for load current",
            description=(
                f"Board has {len(relays)} relay(s). Ensure contact ratings exceed "
                "expected load current with safety margin. Building automation often "
                "switches inductive loads (motors, solenoids) requiring derating."
            ),
            suggested_fix=(
                "1. Check relay datasheet for AC/DC current ratings\n"
                "2. Derate by 50% for inductive loads\n"
                "3. Consider MOV or snubber across contacts for arc suppression\n"
                "4. Ensure PCB traces to/from relay can handle load current"
            ),
            affected_components=[r.reference for r in relays]
        )
        issues.append(issue)
        
        return issues
    
    def _check_power_capacitors(self, pcb_data) -> List[Issue]:
        """Check for bulk capacitors on power rails"""
        issues = []
        
        # Find capacitors
        capacitors = [
            comp for comp in pcb_data.components
            if comp.reference.startswith('C')
        ]
        
        # Look for bulk caps (typically >10µF)
        bulk_caps = [
            cap for cap in capacitors
            if any(unit in cap.value.lower() for unit in ['uf', 'µf', 'mf'])
            and any(char.isdigit() for char in cap.value)
        ]
        
        if len(bulk_caps) < 2:
            issue = Issue(
                issue_code="PWR-005",
                severity=IssueSeverity.WARNING,
                category="power_smps",
                title="Limited bulk capacitance detected",
                description=(
                    "Few bulk capacitors found. Power rails need adequate decoupling "
                    "especially for motors, relays, and communication modules common in "
                    "building automation."
                ),
                suggested_fix=(
                    "1. Add 10-100µF electrolytic caps on main power rails\n"
                    "2. Add 0.1µF ceramics near each IC\n"
                    "3. Larger bulk caps (100-1000µF) for motor drivers or high-current loads\n"
                    "4. Check voltage rating > 2x rail voltage for reliability"
                ),
                affected_components=[c.reference for c in bulk_caps] if bulk_caps else []
            )
            issues.append(issue)
        
        return issues
