"""
Assembly and testability rules
Checks for test points, polarity marking, edge clearances
"""
import logging
from typing import List
from .base_rule import BaseRule, Issue, IssueSeverity

logger = logging.getLogger(__name__)


class AssemblyTestRules(BaseRule):
    """Rules for assembly and testability"""
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Analyze assembly and test aspects
        
        Args:
            pcb_data: ParsedPCBData object
            
        Returns:
            List of assembly/test issues
        """
        issues = []
        
        # Check for test points
        issues.extend(self._check_test_points(pcb_data))
        
        # Check polarity markings (for diodes, electrolytics, LEDs)
        issues.extend(self._check_polarity_components(pcb_data))
        
        # Check component placement near edges
        issues.extend(self._check_edge_clearances(pcb_data))
        
        # Check for mounting holes
        issues.extend(self._check_mounting_holes(pcb_data))
        
        return issues
    
    def _check_test_points(self, pcb_data) -> List[Issue]:
        """Check for test points on key nets"""
        issues = []
        
        # Find test points
        test_points = [
            comp for comp in pcb_data.components
            if 'tp' in comp.reference.lower() or 'test' in comp.footprint.lower()
        ]
        
        logger.info(f"Found {len(test_points)} test points")
        
        # Get power nets
        power_nets = [net for net in pcb_data.nets if net.is_power or net.is_ground]
        
        if len(test_points) < 3 and len(power_nets) > 2:
            issue = Issue(
                issue_code="ASM-001",
                severity=IssueSeverity.WARNING,
                category="assembly_test",
                title="Limited test points detected",
                description=(
                    f"Found only {len(test_points)} test point(s) but {len(power_nets)} power rails. "
                    "Test points on key nets (power rails, critical signals) greatly simplify "
                    "bring-up, debugging, and field troubleshooting."
                ),
                suggested_fix=(
                    "1. Add test points (TP) for each power rail: 3V3, 5V, 12V, etc.\n"
                    "2. Add TP for GND\n"
                    "3. Add TPs for bus signals (RS485_A/B, CAN_H/L)\n"
                    "4. Add TPs for MCU debug signals (UART TX/RX, SWD)\n"
                    "5. Use standard 1mm or 0.1\" through-hole test points"
                ),
                affected_nets=[net.name for net in power_nets[:5]]
            )
            issues.append(issue)
        elif len(test_points) >= 3:
            issue = Issue(
                issue_code="ASM-002",
                severity=IssueSeverity.INFO,
                category="assembly_test",
                title=f"Good: {len(test_points)} test points found",
                description=(
                    "Adequate test points detected. Verify they cover: "
                    "power rails, ground, and critical signals."
                ),
                suggested_fix="Ensure test points are accessible and documented in assembly drawing.",
                affected_components=[tp.reference for tp in test_points[:10]]
            )
            issues.append(issue)
        
        return issues
    
    def _check_polarity_components(self, pcb_data) -> List[Issue]:
        """Check for polarized components"""
        issues = []
        
        # Find diodes
        diodes = [c for c in pcb_data.components if c.reference.startswith('D')]
        
        # Find electrolytic capacitors (guess from value)
        electrolytics = [
            c for c in pcb_data.components 
            if c.reference.startswith('C') and 
            any(unit in c.value.lower() for unit in ['uf', 'µf']) and
            any(char.isdigit() and int(char) >= 1 for char in c.value if char.isdigit())
        ]
        
        # Find LEDs
        leds = [
            c for c in pcb_data.components
            if 'led' in c.value.lower() or 'led' in c.reference.lower()
        ]
        
        polarized_count = len(diodes) + len(electrolytics) + len(leds)
        
        if polarized_count > 0:
            issue = Issue(
                issue_code="ASM-003",
                severity=IssueSeverity.INFO,
                category="assembly_test",
                title=f"Verify polarity marking for {polarized_count} components",
                description=(
                    f"Found {len(diodes)} diode(s), {len(electrolytics)} likely electrolytic cap(s), "
                    f"and {len(leds)} LED(s). These require correct polarity for proper function."
                ),
                suggested_fix=(
                    "1. Ensure silkscreen shows polarity (+ for caps, cathode mark for diodes)\n"
                    "2. Use clear, visible markings (not just footprint outline)\n"
                    "3. Add polarity to assembly drawing\n"
                    "4. Consider photo of assembled board for reference"
                ),
                affected_components=(
                    [d.reference for d in diodes[:3]] +
                    [c.reference for c in electrolytics[:3]] +
                    [l.reference for l in leds[:3]]
                )
            )
            issues.append(issue)
        
        return issues
    
    def _check_edge_clearances(self, pcb_data) -> List[Issue]:
        """Check if components are too close to board edges"""
        issues = []
        
        if not pcb_data.components:
            return issues
        
        # Components with position data
        positioned_comps = [c for c in pcb_data.components if c.x is not None and c.y is not None]
        
        if not positioned_comps:
            return issues
        
        board_size_x = pcb_data.board_info.size_x
        board_size_y = pcb_data.board_info.size_y
        
        # Assume board origin is at (0,0) - simplified
        edge_threshold = 1.0  # mm
        
        near_edge = []
        for comp in positioned_comps:
            # Check if near any edge (simplified - assumes board at origin)
            if (comp.x < edge_threshold or 
                comp.y < edge_threshold or
                comp.x > board_size_x - edge_threshold or
                comp.y > board_size_y - edge_threshold):
                near_edge.append(comp)
        
        if near_edge:
            issue = Issue(
                issue_code="ASM-004",
                severity=IssueSeverity.WARNING,
                category="assembly_test",
                title=f"{len(near_edge)} component(s) near board edge",
                description=(
                    f"Found {len(near_edge)} components within {edge_threshold}mm of board edge. "
                    "Components near edges risk damage during depanelization, handling, or enclosure mounting."
                ),
                suggested_fix=(
                    f"1. Keep components >{edge_threshold}mm from board edge\n"
                    "2. Especially important for tall components (connectors, electrolytics)\n"
                    "3. Check mechanical drawing for enclosure standoffs\n"
                    "4. Consider adding keepout zones in layout"
                ),
                affected_components=[c.reference for c in near_edge[:5]]
            )
            issues.append(issue)
        
        return issues
    
    def _check_mounting_holes(self, pcb_data) -> List[Issue]:
        """Check for mounting holes"""
        issues = []
        
        mounting_keywords = ['hole', 'mount', 'h1', 'h2', 'mh']
        
        mounting_holes = [
            comp for comp in pcb_data.components
            if any(kw in comp.reference.lower() for kw in mounting_keywords)
        ]
        
        if len(mounting_holes) < 2:
            issue = Issue(
                issue_code="ASM-005",
                severity=IssueSeverity.INFO,
                category="assembly_test",
                title="Few/no mounting holes detected",
                description=(
                    f"Found {len(mounting_holes)} mounting hole(s). Building automation boards "
                    "typically mount in enclosures or DIN rails. Ensure mechanical mounting is considered."
                ),
                suggested_fix=(
                    "1. Add mounting holes at corners (M3 or M4 typical)\n"
                    "2. Clearance around holes: 3-5mm radius from copper\n"
                    "3. For DIN rail mounting, consider DIN rail clip footprint\n"
                    "4. Ensure board size fits target enclosure"
                )
            )
            issues.append(issue)
        
        return issues
