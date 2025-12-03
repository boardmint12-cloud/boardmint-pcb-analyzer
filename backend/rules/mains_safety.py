"""
Mains safety rules for building automation PCBs
Checks clearances, creepage, isolation between mains and low voltage
"""
import logging
from typing import List
from .base_rule import BaseRule, Issue, IssueSeverity

logger = logging.getLogger(__name__)


class MainsSafetyRules(BaseRule):
    """Rules for mains/AC safety compliance"""
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Analyze mains safety
        
        Args:
            pcb_data: ParsedPCBData object
            
        Returns:
            List of safety issues
        """
        issues = []
        
        # Find mains nets
        mains_nets = [net for net in pcb_data.nets if net.is_mains]
        
        if not mains_nets:
            logger.info("No mains nets detected - skipping mains safety checks")
            return issues
        
        logger.info(f"Found {len(mains_nets)} mains nets: {[n.name for n in mains_nets]}")
        
        # Find low voltage nets
        low_voltage_nets = [
            net for net in pcb_data.nets 
            if not net.is_mains and (net.is_power or net.is_ground)
        ]
        
        # Check 1: Clearance between mains and low voltage
        issues.extend(self._check_mains_clearance(
            mains_nets, low_voltage_nets, pcb_data
        ))
        
        # Check 2: Look for isolation components (optocouplers, relays)
        issues.extend(self._check_isolation_components(
            mains_nets, pcb_data
        ))
        
        # Check 3: Check for MOV/TVS protection on mains
        issues.extend(self._check_mains_protection(
            mains_nets, pcb_data
        ))
        
        return issues
    
    def _check_mains_clearance(self, mains_nets, lv_nets, pcb_data) -> List[Issue]:
        """Check clearance between mains and low voltage"""
        issues = []
        
        if not lv_nets:
            return issues
        
        required_clearance = self.fab_rules["mains_clearance"]
        
        # This is a simplified check - in reality, you'd need layout geometry
        # For MVP, we create an informational warning if both exist
        
        mains_names = [n.name for n in mains_nets]
        lv_names = [n.name for n in lv_nets[:3]]  # Show first 3
        
        issue = Issue(
            issue_code="MNS-001",
            severity=IssueSeverity.CRITICAL,
            category="mains_safety",
            title=f"Verify mains-to-low-voltage clearance",
            description=(
                f"Board contains both mains voltage nets ({', '.join(mains_names)}) "
                f"and low-voltage nets ({', '.join(lv_names)}). "
                f"Minimum clearance between mains and low voltage must be ≥{required_clearance}mm. "
                "Manual verification required with layout viewer."
            ),
            suggested_fix=(
                f"1. Review layout and measure minimum copper-to-copper distance between mains and LV nets\n"
                f"2. Ensure clearance is ≥{required_clearance}mm everywhere\n"
                f"3. Consider adding slots or cutouts for additional creepage\n"
                f"4. Add keepout zones in layout around mains traces"
            ),
            affected_nets=mains_names + lv_names,
            metadata={
                "required_clearance_mm": required_clearance,
                "mains_net_count": len(mains_nets),
                "lv_net_count": len(lv_nets)
            }
        )
        issues.append(issue)
        
        return issues
    
    def _check_isolation_components(self, mains_nets, pcb_data) -> List[Issue]:
        """Check for isolation components between mains and logic"""
        issues = []
        
        # Look for optocouplers, relays, transformers
        isolation_keywords = ['opto', 'opt', 'relay', 'transf', 'iso']
        
        isolation_components = [
            comp for comp in pcb_data.components
            if any(kw in comp.reference.lower() or kw in comp.value.lower() 
                   for kw in isolation_keywords)
        ]
        
        if not isolation_components:
            issue = Issue(
                issue_code="MNS-002",
                severity=IssueSeverity.WARNING,
                category="mains_safety",
                title="No isolation components detected",
                description=(
                    "Could not find optocouplers, relays, or transformers on the board. "
                    "If your design switches mains or communicates across mains-LV boundary, "
                    "you need isolation components for safety."
                ),
                suggested_fix=(
                    "1. If controlling mains loads: Add relay with adequate coil-to-contact isolation\n"
                    "2. If sensing mains: Add optocoupler or isolated amplifier\n"
                    "3. If using transformer: Ensure proper safety rating and pinout"
                ),
                affected_nets=[n.name for n in mains_nets]
            )
            issues.append(issue)
        else:
            # Found isolation - create info
            issue = Issue(
                issue_code="MNS-003",
                severity=IssueSeverity.INFO,
                category="mains_safety",
                title=f"Found {len(isolation_components)} isolation component(s)",
                description=(
                    f"Detected potential isolation components: {', '.join(c.reference for c in isolation_components[:5])}. "
                    "Verify these provide adequate isolation rating for your application."
                ),
                suggested_fix=(
                    "1. Check datasheet for isolation voltage rating (should be ≥1500V for building automation)\n"
                    "2. Verify PCB clearances around isolation components\n"
                    "3. Ensure proper orientation and soldering"
                ),
                affected_components=[c.reference for c in isolation_components]
            )
            issues.append(issue)
        
        return issues
    
    def _check_mains_protection(self, mains_nets, pcb_data) -> List[Issue]:
        """Check for surge/transient protection on mains input"""
        issues = []
        
        # Look for MOVs, TVS, fuses on mains
        protection_keywords = ['mov', 'varistor', 'tvs', 'fuse', 'f1', 'f2']
        
        protection_components = [
            comp for comp in pcb_data.components
            if any(kw in comp.reference.lower() or kw in comp.value.lower() 
                   for kw in protection_keywords)
        ]
        
        if not protection_components:
            issue = Issue(
                issue_code="MNS-004",
                severity=IssueSeverity.WARNING,
                category="mains_safety",
                title="No surge protection detected on mains input",
                description=(
                    "Could not find MOV, TVS, or fuse components near mains input. "
                    "Building automation installations often experience surges from "
                    "inductive loads, lightning, and switching transients."
                ),
                suggested_fix=(
                    "1. Add MOV (metal oxide varistor) across L-N for surge protection\n"
                    "2. Add fuse in series with L (line) for overcurrent protection\n"
                    "3. Consider common-mode choke for EMI filtering\n"
                    "4. TVS diodes on low-voltage side of transformer/SMPS"
                ),
                affected_nets=[n.name for n in mains_nets]
            )
            issues.append(issue)
        
        return issues
