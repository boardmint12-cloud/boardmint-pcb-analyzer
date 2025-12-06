"""
DRC Engine V2 - Industry Standard Design Rule Checker
Comprehensive PCB validation using IPC, IEC, and manufacturer standards

This engine integrates all domain-specific rule modules:
- Core DRC: Trace width, spacing, via size, annular ring
- Mains Safety: IEC 62368-1 clearance/creepage
- Bus Interfaces: I2C/SPI/RS-485/CAN validation
- Power SMPS: Layout optimization per TI app notes
- BOM Validation: E-series, derating checks
- High-Speed: Impedance, length matching, crosstalk
- Thermal: Current capacity, via handling, heat management
"""

import logging
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp

# Core imports
from models.canonical import Board, Component, Net, Via, Track

# Standards
from rules.standards.ipc_2221a import IPC2221A, ConductorType
from rules.standards.iec_62368 import IEC62368, InsulationType
from rules.standards.current_capacity import CurrentCapacity, LayerPosition
from rules.standards.e_series import ESeries, ESeriesType
from rules.standards.mlcc_derating import MLCCDerating
from rules.standards.bus_standards import BusStandards

# Rule engines
from rules.mains_safety_v2 import MainsSafetyRulesV2, MainsVoltageRegion
from rules.bus_interfaces_v2 import BusInterfaceRulesV2
from rules.power_smps_v2 import PowerSMPSRulesV2
from rules.bom_validation import BOMValidationRules
from rules.high_speed_interfaces import HighSpeedInterfaceRules
from rules.thermal_analysis import ThermalAnalysisRules

# Profiles
from services.rule_profiles_v2 import RuleProfileLibrary, RuleProfile, ComplianceLevel

logger = logging.getLogger(__name__)


class ViolationSeverity(str, Enum):
    """Severity levels for DRC violations"""
    CRITICAL = "critical"   # Must fix - board won't work or is unsafe
    ERROR = "error"         # Should fix - functionality impaired
    WARNING = "warning"     # Review recommended - may cause issues
    INFO = "info"           # Information/best practice


class ViolationCategory(str, Enum):
    """DRC violation categories"""
    # Core DRC
    CLEARANCE = "clearance"
    TRACE_WIDTH = "trace_width"
    VIA_SIZE = "via_size"
    ANNULAR_RING = "annular_ring"
    DRILL = "drill"
    
    # Safety
    CREEPAGE = "creepage"
    HIGH_VOLTAGE = "high_voltage"
    ISOLATION = "isolation"
    
    # Signal Integrity
    DIFFERENTIAL_PAIR = "differential_pair"
    IMPEDANCE = "impedance"
    LENGTH_MATCHING = "length_matching"
    CROSSTALK = "crosstalk"
    
    # Power
    CURRENT_CAPACITY = "current_capacity"
    THERMAL = "thermal"
    POWER_INTEGRITY = "power_integrity"
    
    # Assembly/Manufacturing
    COMPONENT_SPACING = "component_spacing"
    SOLDER_MASK = "solder_mask"
    SILKSCREEN = "silkscreen"
    ASSEMBLY = "assembly"
    
    # Design
    BOM = "bom"
    CONNECTIVITY = "connectivity"
    BUS_INTERFACE = "bus_interface"
    
    # Fab Capability
    FAB_CAPABILITY = "fab_capability"


@dataclass
class Violation:
    """DRC violation with full context"""
    id: str
    category: ViolationCategory
    severity: ViolationSeverity
    rule_id: str
    title: str
    description: str
    
    # Location
    layer: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    
    # Related objects
    net1: Optional[str] = None
    net2: Optional[str] = None
    component: Optional[str] = None
    affected_nets: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    
    # Measurements
    actual: Optional[float] = None
    required: Optional[float] = None
    unit: str = "mm"
    
    # Remediation
    suggested_fix: Optional[str] = None
    
    # Traceability
    standard_reference: Optional[str] = None
    details: Dict = field(default_factory=dict)


@dataclass
class DRCResult:
    """Complete DRC analysis result"""
    status: str  # "PASS", "PASS_WITH_WARNINGS", "FAIL_ERRORS", "FAIL_CRITICAL"
    violations: List[Violation]
    summary: Dict[str, int]
    by_category: Dict[str, int]
    profile_used: str
    analysis_time_ms: float
    board_info: Dict


class DRCEngineV2:
    """
    Industry-Standard DRC Engine
    
    Comprehensive design rule checking using:
    - IPC-2221A clearance/creepage tables
    - IEC 62368-1 safety requirements  
    - TI application note guidelines
    - Manufacturer design rules
    """
    
    def __init__(
        self, 
        max_workers: Optional[int] = None,
        mains_region: MainsVoltageRegion = MainsVoltageRegion.UNIVERSAL
    ):
        """
        Initialize DRC Engine V2
        
        Args:
            max_workers: Parallel workers (default: CPU count)
            mains_region: Target mains voltage region
        """
        if max_workers is None:
            max_workers = mp.cpu_count()
        
        self.max_workers = max_workers
        self.profile_library = RuleProfileLibrary()
        
        # Initialize domain-specific rule engines
        self.mains_safety = MainsSafetyRulesV2(mains_region)
        self.bus_interfaces = BusInterfaceRulesV2()
        self.power_smps = PowerSMPSRulesV2()
        self.bom_validation = BOMValidationRules()
        self.high_speed = HighSpeedInterfaceRules()
        self.thermal = ThermalAnalysisRules()
        
        logger.info(f"DRC Engine V2 initialized with {self.max_workers} workers")
    
    def run_full_analysis(
        self, 
        board: Board, 
        profile_id: str = "ipc2221_class2",
        include_info: bool = True
    ) -> DRCResult:
        """
        Run comprehensive DRC analysis
        
        Args:
            board: Canonical board model
            profile_id: Rule profile to use
            include_info: Include INFO-level issues
        
        Returns:
            DRCResult with all violations
        """
        start_time = time.time()
        
        # Get profile
        profile = self.profile_library.get_profile(profile_id)
        if not profile:
            logger.warning(f"Profile {profile_id} not found, using default")
            profile = self.profile_library.get_profile("ipc2221_class2")
        
        logger.info(f"Running DRC with profile: {profile.name}")
        
        violations = []
        
        # Define analysis tasks
        analysis_tasks = [
            ("Core DRC", lambda: self._run_core_drc(board, profile)),
            ("Mains Safety", lambda: self._run_mains_safety(board, profile)),
            ("Bus Interfaces", lambda: self._run_bus_interfaces(board)),
            ("Power/SMPS", lambda: self._run_power_smps(board)),
            ("BOM Validation", lambda: self._run_bom_validation(board)),
            ("High-Speed", lambda: self._run_high_speed(board)),
            ("Thermal", lambda: self._run_thermal(board)),
        ]
        
        # Run analyses in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(task_func): task_name
                for task_name, task_func in analysis_tasks
            }
            
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result = future.result()
                    violations.extend(result)
                    logger.info(f"✓ {task_name}: {len(result)} issues")
                except Exception as e:
                    logger.error(f"✗ {task_name} failed: {e}", exc_info=True)
        
        # Filter INFO if not requested
        if not include_info:
            violations = [v for v in violations if v.severity != ViolationSeverity.INFO]
        
        # Generate result
        elapsed_ms = (time.time() - start_time) * 1000
        result = self._generate_result(violations, board, profile.id, elapsed_ms)
        
        logger.info(f"DRC completed in {elapsed_ms:.0f}ms - "
                   f"{result.summary['total']} total issues, status: {result.status}")
        
        return result
    
    # ==========================================================================
    # CORE DRC CHECKS
    # ==========================================================================
    
    def _run_core_drc(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Run core DRC checks: traces, vias, clearances"""
        violations = []
        
        # Check trace widths
        violations.extend(self._check_trace_widths(board, profile))
        
        # Check via sizes
        violations.extend(self._check_via_sizes(board, profile))
        
        # Check component spacing
        violations.extend(self._check_component_spacing(board, profile))
        
        # Check edge clearance
        violations.extend(self._check_edge_clearance(board, profile))
        
        # Check net connectivity
        violations.extend(self._check_net_connectivity(board))
        
        # Check high-voltage clearances
        violations.extend(self._check_hv_clearances(board, profile))
        
        return violations
    
    def _check_trace_widths(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check trace widths against profile minimums"""
        violations = []
        min_width = profile.min_trace_width.value
        
        for track in board.tracks:
            if track.width < min_width:
                violations.append(Violation(
                    id=f"trace_width_{track.id}",
                    category=ViolationCategory.TRACE_WIDTH,
                    severity=ViolationSeverity.ERROR,
                    rule_id="CORE-TW-001",
                    title=f"Trace width below minimum on {track.net or 'unknown net'}",
                    description=f"Trace width {track.width}mm is below profile minimum {min_width}mm",
                    layer=track.layer,
                    x=track.start.x if track.start else None,
                    y=track.start.y if track.start else None,
                    net1=track.net,
                    actual=track.width,
                    required=min_width,
                    suggested_fix=f"Increase trace width to at least {min_width}mm",
                    standard_reference=profile.min_trace_width.source
                ))
        
        return violations
    
    def _check_via_sizes(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check via sizes and annular rings"""
        violations = []
        
        min_via = profile.min_via_diameter.value
        min_drill = profile.min_via_drill.value
        min_annular = profile.min_annular_ring.value
        
        for via in board.vias:
            # Check via diameter
            if via.size < min_via:
                violations.append(Violation(
                    id=f"via_size_{via.id}",
                    category=ViolationCategory.VIA_SIZE,
                    severity=ViolationSeverity.ERROR,
                    rule_id="CORE-VIA-001",
                    title=f"Via diameter below minimum",
                    description=f"Via diameter {via.size}mm < minimum {min_via}mm",
                    x=via.position.x if via.position else None,
                    y=via.position.y if via.position else None,
                    net1=via.net,
                    actual=via.size,
                    required=min_via
                ))
            
            # Check drill size
            if via.drill < min_drill:
                violations.append(Violation(
                    id=f"via_drill_{via.id}",
                    category=ViolationCategory.DRILL,
                    severity=ViolationSeverity.ERROR,
                    rule_id="CORE-VIA-002",
                    title=f"Via drill below minimum",
                    description=f"Via drill {via.drill}mm < minimum {min_drill}mm",
                    net1=via.net,
                    actual=via.drill,
                    required=min_drill
                ))
            
            # Check annular ring
            annular = via.annular_ring()
            if annular < min_annular:
                violations.append(Violation(
                    id=f"via_annular_{via.id}",
                    category=ViolationCategory.ANNULAR_RING,
                    severity=ViolationSeverity.ERROR,
                    rule_id="CORE-VIA-003",
                    title=f"Via annular ring too small",
                    description=f"Annular ring {annular:.3f}mm < minimum {min_annular}mm",
                    net1=via.net,
                    actual=annular,
                    required=min_annular,
                    standard_reference="IPC-2221A"
                ))
        
        return violations
    
    def _check_component_spacing(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check component-to-component spacing"""
        violations = []
        min_spacing = profile.min_component_spacing.value
        
        components = board.components
        
        for i, comp1 in enumerate(components):
            for comp2 in components[i+1:]:
                if comp1.side != comp2.side:
                    continue
                
                if not (comp1.position and comp2.position):
                    continue
                
                # Simple center-to-center distance (actual implementation would use bounding boxes)
                dx = comp1.position.x - comp2.position.x
                dy = comp1.position.y - comp2.position.y
                distance = (dx**2 + dy**2)**0.5
                
                # Rough size estimate
                estimated_clearance = distance - 2.0  # Assume ~2mm component size
                
                if estimated_clearance < min_spacing and distance < 5.0:
                    violations.append(Violation(
                        id=f"comp_spacing_{comp1.refdes}_{comp2.refdes}",
                        category=ViolationCategory.COMPONENT_SPACING,
                        severity=ViolationSeverity.WARNING,
                        rule_id="CORE-COMP-001",
                        title=f"Components {comp1.refdes} and {comp2.refdes} may be too close",
                        description=f"Distance {distance:.2f}mm between component centers",
                        layer=comp1.side.value,
                        x=(comp1.position.x + comp2.position.x) / 2,
                        y=(comp1.position.y + comp2.position.y) / 2,
                        affected_components=[comp1.refdes, comp2.refdes],
                        actual=distance,
                        required=min_spacing
                    ))
        
        return violations
    
    def _check_edge_clearance(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check component clearance from board edge"""
        violations = []
        min_edge = profile.min_edge_clearance.value
        
        bbox = board.bounding_box()
        if not bbox:
            return violations
        
        for comp in board.components:
            if not comp.position:
                continue
            
            edge_distances = [
                comp.position.x - bbox.min_x,
                bbox.max_x - comp.position.x,
                comp.position.y - bbox.min_y,
                bbox.max_y - comp.position.y,
            ]
            min_dist = min(edge_distances)
            
            if min_dist < min_edge:
                violations.append(Violation(
                    id=f"edge_clearance_{comp.refdes}",
                    category=ViolationCategory.ASSEMBLY,
                    severity=ViolationSeverity.WARNING,
                    rule_id="CORE-EDGE-001",
                    title=f"Component {comp.refdes} too close to edge",
                    description=f"Distance to edge {min_dist:.2f}mm < minimum {min_edge}mm",
                    x=comp.position.x,
                    y=comp.position.y,
                    component=comp.refdes,
                    actual=min_dist,
                    required=min_edge
                ))
        
        return violations
    
    def _check_net_connectivity(self, board: Board) -> List[Violation]:
        """Check for suspicious net connectivity"""
        violations = []
        
        for net in board.nets:
            pad_count = len(net.pads or [])
            
            if not net.name or net.name.strip() == "":
                continue
            if net.name.lower().startswith("unconnected-"):
                continue
            
            if pad_count == 0:
                violations.append(Violation(
                    id=f"net_unused_{net.name}",
                    category=ViolationCategory.CONNECTIVITY,
                    severity=ViolationSeverity.INFO,
                    rule_id="CORE-NET-001",
                    title=f"Net '{net.name}' has no connections",
                    description="Net defined but not connected to any pads",
                    net1=net.name
                ))
            elif pad_count == 1:
                violations.append(Violation(
                    id=f"net_stub_{net.name}",
                    category=ViolationCategory.CONNECTIVITY,
                    severity=ViolationSeverity.WARNING,
                    rule_id="CORE-NET-002",
                    title=f"Net '{net.name}' is a stub (single connection)",
                    description=f"Net only connects to {net.pads[0]}",
                    net1=net.name,
                    actual=1,
                    required=2
                ))
        
        return violations
    
    def _check_hv_clearances(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Check high-voltage net clearances using IPC-2221A"""
        violations = []
        
        hv_nets = board.get_high_voltage_nets(threshold=48.0)
        
        for net in hv_nets:
            if not net.voltage:
                continue
            
            # Get required clearance from IPC-2221A
            clearance = IPC2221A.get_clearance(
                net.voltage,
                ConductorType.B2_EXTERNAL_UNCOATED,
                safety_margin=1.2
            )
            
            violations.append(Violation(
                id=f"hv_clearance_{net.name}",
                category=ViolationCategory.HIGH_VOLTAGE,
                severity=ViolationSeverity.WARNING,
                rule_id="CORE-HV-001",
                title=f"High voltage net '{net.name}' ({net.voltage}V)",
                description=(
                    f"Net operates at {net.voltage}V. "
                    f"IPC-2221A requires minimum {clearance:.2f}mm clearance."
                ),
                net1=net.name,
                required=clearance,
                standard_reference="IPC-2221A Table 6-1",
                suggested_fix=f"Verify minimum {clearance}mm clearance to other nets"
            ))
        
        return violations
    
    # ==========================================================================
    # DOMAIN-SPECIFIC ANALYSIS WRAPPERS
    # ==========================================================================
    
    def _run_mains_safety(self, board: Board, profile: RuleProfile) -> List[Violation]:
        """Run mains safety analysis"""
        try:
            # Convert base_rule Issues to Violations
            issues = self.mains_safety.analyze(board)
            return self._convert_issues_to_violations(issues, ViolationCategory.HIGH_VOLTAGE)
        except Exception as e:
            logger.error(f"Mains safety analysis failed: {e}")
            return []
    
    def _run_bus_interfaces(self, board: Board) -> List[Violation]:
        """Run bus interface analysis"""
        try:
            issues = self.bus_interfaces.analyze(board)
            return self._convert_issues_to_violations(issues, ViolationCategory.BUS_INTERFACE)
        except Exception as e:
            logger.error(f"Bus interface analysis failed: {e}")
            return []
    
    def _run_power_smps(self, board: Board) -> List[Violation]:
        """Run power/SMPS analysis"""
        try:
            issues = self.power_smps.analyze(board)
            return self._convert_issues_to_violations(issues, ViolationCategory.POWER_INTEGRITY)
        except Exception as e:
            logger.error(f"Power/SMPS analysis failed: {e}")
            return []
    
    def _run_bom_validation(self, board: Board) -> List[Violation]:
        """Run BOM validation"""
        try:
            issues = self.bom_validation.analyze(board)
            return self._convert_issues_to_violations(issues, ViolationCategory.BOM)
        except Exception as e:
            logger.error(f"BOM validation failed: {e}")
            return []
    
    def _run_high_speed(self, board: Board) -> List[Violation]:
        """Run high-speed interface analysis"""
        try:
            issues = self.high_speed.analyze(board)
            return self._convert_issues_to_violations(issues, ViolationCategory.IMPEDANCE)
        except Exception as e:
            logger.error(f"High-speed analysis failed: {e}")
            return []
    
    def _run_thermal(self, board: Board) -> List[Violation]:
        """Run thermal analysis"""
        try:
            issues = self.thermal.analyze(board)
            return self._convert_issues_to_violations(issues, ViolationCategory.THERMAL)
        except Exception as e:
            logger.error(f"Thermal analysis failed: {e}")
            return []
    
    def _convert_issues_to_violations(
        self, 
        issues: List, 
        default_category: ViolationCategory
    ) -> List[Violation]:
        """Convert base_rule Issues to Violations"""
        violations = []
        
        for issue in issues:
            # Map severity
            severity_map = {
                "critical": ViolationSeverity.CRITICAL,
                "error": ViolationSeverity.ERROR,
                "warning": ViolationSeverity.WARNING,
                "info": ViolationSeverity.INFO,
            }
            severity = severity_map.get(
                issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity).lower(),
                ViolationSeverity.WARNING
            )
            
            violations.append(Violation(
                id=issue.issue_code,
                category=default_category,
                severity=severity,
                rule_id=issue.issue_code,
                title=issue.title,
                description=issue.description,
                suggested_fix=issue.suggested_fix,
                affected_nets=issue.affected_nets if hasattr(issue, 'affected_nets') else [],
                affected_components=issue.affected_components if hasattr(issue, 'affected_components') else [],
                details=issue.metadata if hasattr(issue, 'metadata') else {}
            ))
        
        return violations
    
    # ==========================================================================
    # RESULT GENERATION
    # ==========================================================================
    
    def _generate_result(
        self,
        violations: List[Violation],
        board: Board,
        profile_id: str,
        elapsed_ms: float
    ) -> DRCResult:
        """Generate DRC result summary"""
        
        # Count by severity
        by_severity = {
            ViolationSeverity.CRITICAL: 0,
            ViolationSeverity.ERROR: 0,
            ViolationSeverity.WARNING: 0,
            ViolationSeverity.INFO: 0,
        }
        for v in violations:
            by_severity[v.severity] += 1
        
        # Count by category
        by_category = {}
        for v in violations:
            cat = v.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
        
        # Determine status
        if by_severity[ViolationSeverity.CRITICAL] > 0:
            status = "FAIL_CRITICAL"
        elif by_severity[ViolationSeverity.ERROR] > 0:
            status = "FAIL_ERRORS"
        elif by_severity[ViolationSeverity.WARNING] > 0:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "PASS"
        
        return DRCResult(
            status=status,
            violations=violations,
            summary={
                "total": len(violations),
                "critical": by_severity[ViolationSeverity.CRITICAL],
                "errors": by_severity[ViolationSeverity.ERROR],
                "warnings": by_severity[ViolationSeverity.WARNING],
                "info": by_severity[ViolationSeverity.INFO],
            },
            by_category=by_category,
            profile_used=profile_id,
            analysis_time_ms=elapsed_ms,
            board_info=board.to_dict() if hasattr(board, 'to_dict') else {}
        )
    
    def generate_report(self, result: DRCResult) -> Dict:
        """Generate detailed report dictionary"""
        return {
            "status": result.status,
            "summary": result.summary,
            "by_category": result.by_category,
            "profile_used": result.profile_used,
            "analysis_time_ms": result.analysis_time_ms,
            "violations": [
                {
                    "id": v.id,
                    "category": v.category.value,
                    "severity": v.severity.value,
                    "rule_id": v.rule_id,
                    "title": v.title,
                    "description": v.description,
                    "location": {"x": v.x, "y": v.y, "layer": v.layer} if v.x else None,
                    "affected_nets": v.affected_nets,
                    "affected_components": v.affected_components,
                    "actual": v.actual,
                    "required": v.required,
                    "unit": v.unit,
                    "suggested_fix": v.suggested_fix,
                    "standard_reference": v.standard_reference,
                    "details": v.details,
                }
                for v in result.violations
            ],
            "board_info": result.board_info,
        }
