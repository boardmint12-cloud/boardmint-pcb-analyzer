"""
High-Performance DRC Engine
Parallel processing with caching for fast violation detection
"""
import logging
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing as mp

from models.canonical import Board, Component, Net, Via, Track
from services.rule_profiles import RuleProfile, RuleProfileLibrary
from services import geometry_utils

logger = logging.getLogger(__name__)


class ViolationSeverity(str, Enum):
    """Severity levels for violations"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ViolationCategory(str, Enum):
    """Violation categories"""
    CLEARANCE = "clearance"
    TRACE_WIDTH = "trace_width"
    VIA_SIZE = "via_size"
    ANNULAR_RING = "annular_ring"
    CREEPAGE = "creepage"
    COMPONENT_SPACING = "component_spacing"
    SOLDER_MASK = "solder_mask"
    SILKSCREEN = "silkscreen"
    HIGH_VOLTAGE = "high_voltage"
    DIFFERENTIAL_PAIR = "differential_pair"
    FAB_CAPABILITY = "fab_capability"
    ASSEMBLY = "assembly"
    CONNECTIVITY = "connectivity"  # CRITICAL FIX: Net connectivity checks


@dataclass
class Violation:
    """DRC violation"""
    id: str
    category: ViolationCategory
    severity: ViolationSeverity
    rule: str
    description: str
    
    # Location
    layer: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    
    # Related objects
    net1: Optional[str] = None
    net2: Optional[str] = None
    component: Optional[str] = None
    
    # Measurements
    actual: Optional[float] = None
    required: Optional[float] = None
    
    # Context
    details: Dict = field(default_factory=dict)


class DRCEngine:
    """
    High-performance DRC engine with parallel processing
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize DRC engine
        
        Args:
            max_workers: Max parallel workers (default: CPU count * 2)
        """
        if max_workers is None:
            max_workers = mp.cpu_count() * 2  # Aggressive parallelism
        
        self.max_workers = max_workers
        self.profile_library = RuleProfileLibrary()
        
        logger.info(f"DRC Engine initialized with {self.max_workers} workers")
    
    def run_checks(self, board: Board, profile_id: str) -> List[Violation]:
        """
        Run all DRC checks on board with given profile
        
        Args:
            board: Canonical board model
            profile_id: Rule profile to use
            
        Returns:
            List of violations
        """
        start_time = time.time()
        
        # Get profile
        profile = self.profile_library.get_profile(profile_id)
        if not profile:
            logger.error(f"Profile not found: {profile_id}")
            return []
        
        logger.info(f"Running DRC with profile: {profile.name}")
        
        # Run checks in parallel
        violations = []
        
        # Define check functions
        check_functions = [
            (self._check_component_spacing, "Component Spacing"),
            (self._check_high_voltage_clearance, "HV Clearance"),
            (self._check_high_voltage_creepage, "HV Creepage"),
            (self._check_via_annular_ring, "Via Annular Ring"),
            (self._check_component_edge_clearance, "Edge Clearance"),
            (self._check_differential_pairs, "Differential Pairs"),
            (self._check_trace_width, "Trace Width"),
            (self._check_net_connectivity, "Net Connectivity"),  # CRITICAL FIX
        ]
        
        # Run checks in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_check = {
                executor.submit(check_func, board, profile): check_name
                for check_func, check_name in check_functions
            }
            
            for future in as_completed(future_to_check):
                check_name = future_to_check[future]
                try:
                    result = future.result()
                    violations.extend(result)
                    logger.info(f"✓ {check_name}: {len(result)} violations")
                except Exception as e:
                    logger.error(f"✗ {check_name} failed: {e}", exc_info=True)
        
        elapsed = time.time() - start_time
        logger.info(f"DRC completed in {elapsed:.2f}s - {len(violations)} total violations")
        
        return violations
    
    def _check_component_spacing(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check component-to-component spacing"""
        violations = []
        min_spacing = profile.min_component_spacing.value
        
        components = board.components
        
        # Parallel processing of component pairs
        # For very large boards, we can chunk this
        for i, comp1 in enumerate(components):
            for comp2 in components[i+1:]:
                # Skip if different sides
                if comp1.side != comp2.side:
                    continue
                
                # Skip if positions not known
                if not (comp1.position and comp2.position):
                    continue
                
                # Calculate bbox-to-bbox distance (more accurate than center-to-center)
                bbox1 = geometry_utils.component_bounding_box(comp1)
                bbox2 = geometry_utils.component_bounding_box(comp2)
                
                if bbox1 and bbox2:
                    distance = geometry_utils.bbox_distance(bbox1, bbox2)
                else:
                    # Fallback to center-to-center if bbox unavailable
                    distance = geometry_utils.point_distance(comp1.position, comp2.position)
                
                if distance < min_spacing:
                    violations.append(Violation(
                        id=f"comp_spacing_{comp1.refdes}_{comp2.refdes}",
                        category=ViolationCategory.COMPONENT_SPACING,
                        severity=ViolationSeverity.WARNING,
                        rule="min_component_spacing",
                        description=f"Components too close: {comp1.refdes} and {comp2.refdes}",
                        layer=comp1.side.value,
                        x=(comp1.position.x + comp2.position.x) / 2,
                        y=(comp1.position.y + comp2.position.y) / 2,
                        component=f"{comp1.refdes},{comp2.refdes}",
                        actual=round(distance, 3),
                        required=min_spacing,
                        details={
                            "comp1": comp1.refdes,
                            "comp2": comp2.refdes,
                            "side": comp1.side.value
                        }
                    ))
        
        return violations
    
    def _check_high_voltage_clearance(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check high-voltage net clearances"""
        violations = []
        
        # Get HV nets
        hv_nets = board.get_high_voltage_nets(threshold=48.0)
        
        if not hv_nets:
            return violations
        
        logger.info(f"Checking {len(hv_nets)} high-voltage nets")
        
        for hv_net in hv_nets:
            # Determine required clearance based on voltage
            if hv_net.voltage and hv_net.voltage >= 300:
                required_clearance = profile.clearance_rules.get('hv', profile.clearance_rules['mv']).value
                severity = ViolationSeverity.CRITICAL
            elif hv_net.voltage and hv_net.voltage >= 48:
                required_clearance = profile.clearance_rules.get('mv', profile.clearance_rules['lv']).value
                severity = ViolationSeverity.ERROR
            else:
                required_clearance = profile.clearance_rules['lv'].value
                severity = ViolationSeverity.WARNING
            
            # Get components on this net
            hv_components = board.get_net_components(hv_net.name)
            
            # Check clearance to other components
            for hv_comp in hv_components:
                if not hv_comp.position:
                    continue
                
                for other_comp in board.components:
                    # Skip same component
                    if other_comp.refdes == hv_comp.refdes:
                        continue
                    
                    # Skip if on different side
                    if other_comp.side != hv_comp.side:
                        continue
                    
                    if not other_comp.position:
                        continue
                    
                    # Calculate clearance using bounding boxes
                    hv_bbox = geometry_utils.component_bounding_box(hv_comp)
                    other_bbox = geometry_utils.component_bounding_box(other_comp)
                    
                    if hv_bbox and other_bbox:
                        distance = geometry_utils.bbox_distance(hv_bbox, other_bbox)
                    else:
                        # Fallback to center-to-center
                        distance = geometry_utils.point_distance(hv_comp.position, other_comp.position)
                    
                    if distance < required_clearance:
                        violations.append(Violation(
                            id=f"hv_clearance_{hv_net.name}_{hv_comp.refdes}_{other_comp.refdes}",
                            category=ViolationCategory.HIGH_VOLTAGE,
                            severity=severity,
                            rule="high_voltage_clearance",
                            description=f"HV net {hv_net.name} ({hv_net.voltage}V) too close to {other_comp.refdes}",
                            layer=hv_comp.side.value,
                            x=(hv_comp.position.x + other_comp.position.x) / 2,
                            y=(hv_comp.position.y + other_comp.position.y) / 2,
                            net1=hv_net.name,
                            component=other_comp.refdes,
                            actual=round(distance, 3),
                            required=required_clearance,
                            details={
                                "voltage": hv_net.voltage,
                                "hv_component": hv_comp.refdes,
                                "nearby_component": other_comp.refdes
                            }
                        ))
        
        return violations
    
    def _check_high_voltage_creepage(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check creepage distances for HV nets (IPC-2221)"""
        violations = []
        
        # Get HV nets
        hv_nets = board.get_high_voltage_nets(threshold=48.0)
        
        if not hv_nets:
            return violations
        
        logger.info(f"Checking creepage for {len(hv_nets)} HV nets")
        
        for hv_net in hv_nets:
            # Determine required creepage based on voltage
            if hv_net.voltage and hv_net.voltage >= 300:
                required_creepage = profile.creepage_rules.get('hv', profile.creepage_rules['mv']).value
                severity = ViolationSeverity.CRITICAL
            elif hv_net.voltage and hv_net.voltage >= 48:
                required_creepage = profile.creepage_rules.get('mv', profile.creepage_rules['lv']).value
                severity = ViolationSeverity.ERROR
            else:
                required_creepage = profile.creepage_rules['lv'].value
                severity = ViolationSeverity.WARNING
            
            # Creepage is surface distance - for now we approximate with Euclidean
            # Real implementation would trace along board surface
            
            hv_components = board.get_net_components(hv_net.name)
            
            for hv_comp in hv_components:
                if not hv_comp.position:
                    continue
                
                # Check distance to edge (critical for HV)
                bbox = board.bounding_box()
                if bbox:
                    edge_distances = [
                        hv_comp.position.x - bbox.min_x,  # Left edge
                        bbox.max_x - hv_comp.position.x,  # Right edge
                        hv_comp.position.y - bbox.min_y,  # Bottom edge
                        bbox.max_y - hv_comp.position.y,  # Top edge
                    ]
                    min_edge_distance = min(edge_distances)
                    
                    if min_edge_distance < required_creepage:
                        violations.append(Violation(
                            id=f"hv_creepage_edge_{hv_net.name}_{hv_comp.refdes}",
                            category=ViolationCategory.CREEPAGE,
                            severity=severity,
                            rule="high_voltage_creepage_edge",
                            description=f"HV component {hv_comp.refdes} ({hv_net.voltage}V) too close to board edge",
                            layer=hv_comp.side.value,
                            x=hv_comp.position.x,
                            y=hv_comp.position.y,
                            net1=hv_net.name,
                            component=hv_comp.refdes,
                            actual=round(min_edge_distance, 3),
                            required=required_creepage,
                            details={
                                "voltage": hv_net.voltage,
                                "standard": "IPC-2221"
                            }
                        ))
        
        return violations
    
    def _check_via_annular_ring(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check via annular ring sizes"""
        violations = []
        min_annular = profile.min_annular_ring.value
        
        for via in board.vias:
            annular_ring = via.annular_ring()
            
            if annular_ring < min_annular:
                violations.append(Violation(
                    id=f"via_annular_{via.id}",
                    category=ViolationCategory.ANNULAR_RING,
                    severity=ViolationSeverity.ERROR,
                    rule="min_annular_ring",
                    description=f"Via annular ring too small",
                    layer="all",
                    x=via.position.x if via.position else None,
                    y=via.position.y if via.position else None,
                    net1=via.net,
                    actual=round(annular_ring, 3),
                    required=min_annular,
                    details={
                        "via_size": via.size,
                        "drill": via.drill,
                        "via_id": via.id
                    }
                ))
        
        return violations
    
    def _check_trace_width(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check trace widths against minimum requirements"""
        violations = []
        min_trace_width = profile.min_trace_width.value
        
        # Build net power requirements map
        power_nets = {}
        for net in board.nets:
            if net.is_power or net.voltage:
                # For power nets, use more strict width requirements
                # Simple heuristic: higher voltage = more strict
                if net.voltage and net.voltage > 12:
                    power_nets[net.name] = min_trace_width * 1.5
                else:
                    power_nets[net.name] = min_trace_width * 1.2
        
        for track in board.tracks:
            # Skip if no net
            if not track.net:
                continue
            
            # Determine required width
            required_width = power_nets.get(track.net, min_trace_width)
            
            # Check if track width is below minimum
            if track.width < required_width:
                severity = ViolationSeverity.ERROR if track.width < min_trace_width * 0.8 else ViolationSeverity.WARNING
                
                violations.append(Violation(
                    id=f"trace_width_{track.id}",
                    category=ViolationCategory.TRACE_WIDTH,
                    severity=severity,
                    rule="min_trace_width",
                    description=f"Trace width too narrow on {track.net}",
                    layer=track.layer,
                    x=track.start.x if track.start else None,
                    y=track.start.y if track.start else None,
                    net1=track.net,
                    actual=round(track.width, 3),
                    required=round(required_width, 3),
                    details={
                        "track_id": track.id,
                        "track_length": round(track.length(), 2) if track.start and track.end else 0,
                        "is_power_net": track.net in power_nets
                    }
                ))
        
        return violations
    
    def _check_component_edge_clearance(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check component clearance from board edge"""
        violations = []
        min_clearance = profile.min_edge_clearance.value
        
        bbox = board.bounding_box()
        if not bbox:
            return violations
        
        for comp in board.components:
            if not comp.position:
                continue
            
            # Calculate distance to each edge
            edge_distances = {
                "left": comp.position.x - bbox.min_x,
                "right": bbox.max_x - comp.position.x,
                "bottom": comp.position.y - bbox.min_y,
                "top": bbox.max_y - comp.position.y,
            }
            
            min_dist = min(edge_distances.values())
            edge = min(edge_distances, key=edge_distances.get)
            
            if min_dist < min_clearance:
                violations.append(Violation(
                    id=f"edge_clearance_{comp.refdes}",
                    category=ViolationCategory.ASSEMBLY,
                    severity=ViolationSeverity.WARNING,
                    rule="min_edge_clearance",
                    description=f"Component {comp.refdes} too close to {edge} edge",
                    layer=comp.side.value,
                    x=comp.position.x,
                    y=comp.position.y,
                    component=comp.refdes,
                    actual=round(min_dist, 3),
                    required=min_clearance,
                    details={
                        "edge": edge,
                        "value": comp.value
                    }
                ))
        
        return violations
    
    def _check_differential_pairs(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check differential pair matching"""
        violations = []
        
        pairs = board.get_differential_pairs()
        
        if not pairs:
            return violations
        
        logger.info(f"Checking {len(pairs)} differential pairs")
        
        for pos_net, neg_net in pairs:
            # Check if both nets exist
            if not pos_net or not neg_net:
                violations.append(Violation(
                    id=f"diff_missing_{pos_net.name if pos_net else neg_net.name}",
                    category=ViolationCategory.DIFFERENTIAL_PAIR,
                    severity=ViolationSeverity.ERROR,
                    rule="differential_pair_complete",
                    description=f"Differential pair incomplete: {pos_net.name if pos_net else neg_net.name}",
                    net1=pos_net.name if pos_net else None,
                    net2=neg_net.name if neg_net else None,
                    details={
                        "pair_name": pos_net.pair_name if pos_net else neg_net.pair_name
                    }
                ))
                continue
            
            # Check if width and impedance match (if specified)
            if pos_net.width and neg_net.width:
                if abs(pos_net.width - neg_net.width) > 0.01:  # 0.01mm tolerance
                    violations.append(Violation(
                        id=f"diff_width_{pos_net.name}_{neg_net.name}",
                        category=ViolationCategory.DIFFERENTIAL_PAIR,
                        severity=ViolationSeverity.WARNING,
                        rule="differential_pair_width_match",
                        description=f"Differential pair width mismatch: {pos_net.name} vs {neg_net.name}",
                        net1=pos_net.name,
                        net2=neg_net.name,
                        actual=abs(pos_net.width - neg_net.width),
                        required=0.01,
                        details={
                            "pos_width": pos_net.width,
                            "neg_width": neg_net.width,
                            "pair_name": pos_net.pair_name
                        }
                    ))
        
        return violations
    
    def _check_net_connectivity(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """
        Check for nets with suspicious connectivity.
        
        CRITICAL FIX: This now properly uses Net.pads field (populated by hybrid_parser)
        to detect unconnected or stub nets.
        
        Before this fix, Net.pads was always empty, causing false positives
        for ALL nets (e.g., "BAT(+) has zero connections" even when fully connected).
        """
        violations = []
        
        for net in board.nets:
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
                violations.append(Violation(
                    id=f"net_unused_{net.name}",
                    category=ViolationCategory.CONNECTIVITY,
                    severity=ViolationSeverity.INFO,
                    rule="net_connectivity",
                    description=f"Net '{net.name}' is defined but has no connections",
                    layer=None,
                    x=None,
                    y=None,
                    net1=net.name,
                    details={
                        "net_name": net.name,
                        "pad_count": 0,
                        "issue_type": "unused_net"
                    }
                ))
            
            # 1-pad nets: suspicious stub
            # Could indicate a dropped connection or intentional test point
            elif pad_count == 1:
                component_ref = net.pads[0].split(".")[0] if net.pads else "unknown"
                
                violations.append(Violation(
                    id=f"net_stub_{net.name}",
                    category=ViolationCategory.CONNECTIVITY,
                    severity=ViolationSeverity.WARNING,
                    rule="net_connectivity",
                    description=f"Net '{net.name}' only connects to one pad ({net.pads[0]})",
                    layer=None,
                    x=None,
                    y=None,
                    net1=net.name,
                    component=component_ref,
                    actual=1,
                    required=2,  # Expect at least 2 connections
                    details={
                        "net_name": net.name,
                        "pad_count": 1,
                        "pad": net.pads[0],
                        "issue_type": "stub_net"
                    }
                ))
            
            # 2+ pads: normal, connected net - no issue
        
        return violations
    
    def generate_report(self, violations: List[Violation], board: Board, profile_id: str) -> Dict:
        """
        Generate comprehensive DRC report
        
        Args:
            violations: List of violations
            board: Board that was checked
            profile_id: Profile used
            
        Returns:
            Report dictionary
        """
        # Group by severity
        by_severity = {
            ViolationSeverity.CRITICAL: [],
            ViolationSeverity.ERROR: [],
            ViolationSeverity.WARNING: [],
            ViolationSeverity.INFO: []
        }
        
        for v in violations:
            by_severity[v.severity].append(v)
        
        # Group by category
        by_category = {}
        for v in violations:
            if v.category not in by_category:
                by_category[v.category] = []
            by_category[v.category].append(v)
        
        # Calculate pass/fail
        has_critical = len(by_severity[ViolationSeverity.CRITICAL]) > 0
        has_errors = len(by_severity[ViolationSeverity.ERROR]) > 0
        
        if has_critical:
            status = "FAIL_CRITICAL"
        elif has_errors:
            status = "FAIL_ERRORS"
        elif len(by_severity[ViolationSeverity.WARNING]) > 0:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "PASS"
        
        report = {
            "status": status,
            "board_info": board.to_dict(),
            "profile_id": profile_id,
            "summary": {
                "total_violations": len(violations),
                "critical": len(by_severity[ViolationSeverity.CRITICAL]),
                "errors": len(by_severity[ViolationSeverity.ERROR]),
                "warnings": len(by_severity[ViolationSeverity.WARNING]),
                "info": len(by_severity[ViolationSeverity.INFO]),
            },
            "by_category": {
                cat.value: len(viols) for cat, viols in by_category.items()
            },
            "violations": [
                {
                    "id": v.id,
                    "category": v.category.value,
                    "severity": v.severity.value,
                    "rule": v.rule,
                    "description": v.description,
                    "layer": v.layer,
                    "location": {"x": v.x, "y": v.y} if v.x is not None else None,
                    "net1": v.net1,
                    "net2": v.net2,
                    "component": v.component,
                    "actual": v.actual,
                    "required": v.required,
                    "details": v.details
                }
                for v in violations
            ]
        }
        
        return report
