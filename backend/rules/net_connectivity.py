"""
Net Connectivity Rule - Detects nets with suspicious connectivity

CRITICAL FIX: This rule now uses the properly populated Net.pads field
to accurately detect unconnected or stub nets.

Before this fix, Net.pads was always empty, causing false positives
for every net (e.g., "BAT(+) has zero connections" even when connected).
"""
from dataclasses import dataclass
from typing import List
from parsers.base_parser import ParsedPCBData
from .base_rule import BaseRule, Issue


@dataclass
class NetConnectivityRule(BaseRule):
    """
    Checks for nets with suspiciously low connectivity.
    
    Rules:
    - 0 pads: Defined but unused net → usually harmless, info-level
    - 1 pad: Stub net → warn, could be missing a connection
    - 2+ pads: Normal, connected net → OK
    """
    
    min_pads_for_ok: int = 2
    
    def run(self, pcb_data: ParsedPCBData) -> List[Issue]:
        """Check all nets for connectivity issues."""
        issues: List[Issue] = []
        
        for net in pcb_data.nets:
            pad_count = len(net.pads or [])
            
            # Skip empty net names (KiCad sometimes has (net 0 ""))
            if not net.name or net.name.strip() == "":
                continue
            
            # Skip unconnected-* nets (intentional no-connects in KiCad)
            if net.name.lower().startswith("unconnected-"):
                continue
            
            # 0-pad nets: defined but not used
            # Usually harmless - could be leftover label from schematic
            if pad_count == 0:
                issues.append(
                    Issue(
                        issue_code="NET_UNUSED",
                        severity="info",
                        category="connectivity",
                        title=f"Net '{net.name}' is defined but not used",
                        description=(
                            f"The net '{net.name}' appears in the design but no pads are "
                            "connected to it. This is usually harmless but could indicate "
                            "a leftover label or unused schematic connection."
                        ),
                        suggested_fix=(
                            "If this net is not needed, you can safely ignore this. "
                            "If it was intended to connect components, double-check the "
                            "schematic and PCB to ensure all intended pins are tied together."
                        ),
                        affected_nets=[net.name],
                        affected_components=[],
                    )
                )
            
            # 1-pad nets: suspicious stub
            # Could indicate a dropped connection or intentional test point
            elif pad_count == 1:
                component_ref = net.pads[0].split(".")[0] if net.pads else "unknown"
                
                issues.append(
                    Issue(
                        issue_code="NET_STUB",
                        severity="warning",
                        category="connectivity",
                        title=f"Net '{net.name}' only connects to one pad",
                        description=(
                            f"The net '{net.name}' connects to a single pad ({net.pads[0]}). "
                            "This could indicate an incomplete connection, a dangling test point, "
                            "or an antenna stub. Verify this is intentional."
                        ),
                        suggested_fix=(
                            "Confirm in the schematic whether this net was meant to "
                            "connect multiple components. If it's intentional (e.g., a "
                            "single test pad, antenna stub, or no-connect pin), you can "
                            "waive this warning."
                        ),
                        affected_nets=[net.name],
                        affected_components=[component_ref],
                    )
                )
            
            # 2+ pads: normal, connected net - no issue
            else:
                continue
        
        return issues
    
    def get_info(self) -> dict:
        """Return rule metadata."""
        return {
            "id": "NET_CONNECTIVITY",
            "name": "Net Connectivity Check",
            "description": "Detects nets with zero or single pad connections",
            "category": "connectivity",
            "severity": "warning",
            "checks": [
                "Nets with no pads (unused nets)",
                "Nets with only one pad (stub nets)"
            ]
        }
