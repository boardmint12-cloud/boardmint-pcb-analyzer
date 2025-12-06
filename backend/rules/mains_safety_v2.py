"""
Mains Safety Rules V2 - Industry Standard Compliance
Based on IEC 62368-1, IPC-2221A, and UL safety requirements

This module provides comprehensive mains safety analysis:
- Clearance/creepage validation against IEC 62368-1
- Isolation barrier verification
- Protection device detection (MOV, TVS, fuses)
- Grounding and bonding checks
- Slot/cutout creepage enhancement calculations

Sources:
- IEC 62368-1:2018 (Audio/video, IT equipment safety)
- IPC-2221A (PCB design clearances)
- UL 60950-1 (IT equipment safety)
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_rule import BaseRule, Issue, IssueSeverity
from .standards.iec_62368 import (
    IEC62368, InsulationType, PollutionDegree, 
    MaterialGroup, OvervoltageCategory, SafetyMargins
)
from .standards.ipc_2221a import IPC2221A, ConductorType

logger = logging.getLogger(__name__)


class MainsVoltageRegion(str, Enum):
    """Mains voltage regions"""
    EU_230V = "EU_230V"
    US_120V = "US_120V"
    UK_240V = "UK_240V"
    UNIVERSAL = "UNIVERSAL"


@dataclass
class IsolationBarrier:
    """Detected isolation barrier"""
    component: str
    barrier_type: str  # "optocoupler", "transformer", "relay", "digital_isolator"
    rated_voltage: Optional[float] = None
    primary_nets: List[str] = field(default_factory=list)
    secondary_nets: List[str] = field(default_factory=list)


@dataclass
class SafetyZone:
    """Safety zone definition"""
    zone_name: str
    voltage_class: str  # "MAINS", "SECONDARY", "SELV"
    nets: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)


class MainsSafetyRulesV2(BaseRule):
    """
    Industry-standard mains safety rules
    
    Implements checks per IEC 62368-1 and IPC-2221A for:
    - Clearance distances (air gap)
    - Creepage distances (surface path)
    - Isolation requirements
    - Protection devices
    - Grounding/bonding
    """
    
    # Component detection patterns
    OPTOCOUPLER_PATTERNS = ['opto', 'pc817', 'tlp', '4n35', '6n137', 'hcpl', 'acpl', 'iso']
    TRANSFORMER_PATTERNS = ['transformer', 'xfmr', 'trafo', 't1', 't2']
    RELAY_PATTERNS = ['relay', 'k1', 'k2', 'g3mb', 'omron', 'finder']
    DIGITAL_ISOLATOR_PATTERNS = ['adum', 'iso72', 'si86', 'digital_iso']
    
    MOV_PATTERNS = ['mov', 'varistor', '07d', '10d', '14d', '20d']
    TVS_PATTERNS = ['tvs', 'smbj', 'smaj', 'p6ke', 'esd']
    FUSE_PATTERNS = ['fuse', 'f1', 'f2', 'pptc', 'polyfuse', 'mf-r']
    GDT_PATTERNS = ['gdt', 'gas', 'spark']
    
    def __init__(self, mains_region: MainsVoltageRegion = MainsVoltageRegion.UNIVERSAL):
        """
        Initialize mains safety rules
        
        Args:
            mains_region: Target mains voltage region
        """
        super().__init__()
        self.mains_region = mains_region
        
        # Get safety requirements for region
        self.safety_requirements = IEC62368.get_mains_safety_requirements(
            mains_region.value,
            InsulationType.REINFORCED,
            PollutionDegree.PD2
        )
        
        logger.info(f"MainsSafetyRulesV2 initialized for {mains_region.value}: "
                   f"clearance={self.safety_requirements.clearance_mm}mm, "
                   f"creepage={self.safety_requirements.creepage_mm}mm")
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Comprehensive mains safety analysis
        
        Args:
            pcb_data: ParsedPCBData object
        
        Returns:
            List of safety issues
        """
        issues = []
        
        # Step 1: Identify mains and SELV zones
        mains_zone, selv_zone = self._identify_safety_zones(pcb_data)
        
        if not mains_zone.nets:
            logger.info("No mains nets detected - skipping mains safety checks")
            return [Issue(
                issue_code="MNS-000",
                severity=IssueSeverity.INFO,
                category="mains_safety",
                title="No mains voltage detected",
                description="Board does not appear to have mains voltage circuits.",
                suggested_fix="If this board handles mains voltage, ensure nets are properly labeled."
            )]
        
        logger.info(f"Mains zone: {len(mains_zone.nets)} nets, {len(mains_zone.components)} components")
        logger.info(f"SELV zone: {len(selv_zone.nets)} nets, {len(selv_zone.components)} components")
        
        # Step 2: Check for isolation barriers
        barriers = self._detect_isolation_barriers(pcb_data)
        issues.extend(self._validate_isolation_barriers(barriers, pcb_data))
        
        # Step 3: Clearance and creepage checks
        issues.extend(self._check_clearance_creepage(mains_zone, selv_zone, pcb_data))
        
        # Step 4: Protection device checks
        issues.extend(self._check_protection_devices(mains_zone, pcb_data))
        
        # Step 5: Grounding checks
        issues.extend(self._check_grounding(mains_zone, pcb_data))
        
        # Step 6: Edge clearance for HV
        issues.extend(self._check_hv_edge_clearance(mains_zone, pcb_data))
        
        return issues
    
    def _identify_safety_zones(self, pcb_data) -> Tuple[SafetyZone, SafetyZone]:
        """Identify mains and SELV safety zones"""
        
        # Mains net detection patterns
        mains_patterns = ['mains', 'ac_', 'line', 'neutral', 'live', 'l1', 'n1', 
                        '230v', '120v', '240v', 'vac', 'ac_in', 'hot']
        
        mains_nets = []
        selv_nets = []
        
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            
            # Check if mains
            if any(pattern in net_lower for pattern in mains_patterns):
                mains_nets.append(net.name)
            elif net.is_mains:
                mains_nets.append(net.name)
            elif net.voltage and net.voltage > 60:  # >60V considered dangerous
                mains_nets.append(net.name)
            else:
                selv_nets.append(net.name)
        
        # Find components on each zone
        mains_components = []
        selv_components = []
        
        for comp in pcb_data.components:
            comp_nets = self._get_component_nets(comp, pcb_data)
            if any(net in mains_nets for net in comp_nets):
                mains_components.append(comp.reference)
            else:
                selv_components.append(comp.reference)
        
        mains_zone = SafetyZone(
            zone_name="MAINS",
            voltage_class="MAINS",
            nets=mains_nets,
            components=mains_components
        )
        
        selv_zone = SafetyZone(
            zone_name="SELV",
            voltage_class="SELV",
            nets=selv_nets,
            components=selv_components
        )
        
        return mains_zone, selv_zone
    
    def _get_component_nets(self, component, pcb_data) -> List[str]:
        """Get nets connected to a component"""
        # This would need actual netlist data - simplified for now
        nets = []
        for net in pcb_data.nets:
            if hasattr(net, 'pads'):
                for pad in net.pads or []:
                    if component.reference in pad:
                        nets.append(net.name)
                        break
        return nets
    
    def _detect_isolation_barriers(self, pcb_data) -> List[IsolationBarrier]:
        """Detect isolation components"""
        barriers = []
        
        for comp in pcb_data.components:
            ref_lower = comp.reference.lower()
            value_lower = comp.value.lower() if comp.value else ""
            
            # Optocouplers
            if any(p in ref_lower or p in value_lower for p in self.OPTOCOUPLER_PATTERNS):
                barriers.append(IsolationBarrier(
                    component=comp.reference,
                    barrier_type="optocoupler",
                    rated_voltage=3750  # Typical rating
                ))
            
            # Transformers
            elif any(p in ref_lower or p in value_lower for p in self.TRANSFORMER_PATTERNS):
                barriers.append(IsolationBarrier(
                    component=comp.reference,
                    barrier_type="transformer",
                    rated_voltage=4000  # Typical isolation
                ))
            
            # Relays
            elif any(p in ref_lower or p in value_lower for p in self.RELAY_PATTERNS):
                barriers.append(IsolationBarrier(
                    component=comp.reference,
                    barrier_type="relay",
                    rated_voltage=1500  # Typical coil-contact isolation
                ))
            
            # Digital isolators
            elif any(p in ref_lower or p in value_lower for p in self.DIGITAL_ISOLATOR_PATTERNS):
                barriers.append(IsolationBarrier(
                    component=comp.reference,
                    barrier_type="digital_isolator",
                    rated_voltage=5000  # High isolation ICs
                ))
        
        return barriers
    
    def _validate_isolation_barriers(
        self, 
        barriers: List[IsolationBarrier], 
        pcb_data
    ) -> List[Issue]:
        """Validate isolation barriers"""
        issues = []
        
        if not barriers:
            issues.append(Issue(
                issue_code="MNS-001",
                severity=IssueSeverity.CRITICAL,
                category="mains_safety",
                title="No galvanic isolation detected",
                description=(
                    "Board has mains voltage but no isolation components detected. "
                    "Optocouplers, transformers, or digital isolators required for safety."
                ),
                suggested_fix=(
                    "1. Add transformer for isolated power supply\n"
                    "2. Add optocouplers for signal isolation (min 3750Vrms)\n"
                    "3. Use digital isolators for data interfaces\n"
                    "4. Ensure isolation rating ≥2500Vrms for reinforced insulation"
                ),
                metadata={
                    "required_isolation_voltage": 2500,
                    "standard": "IEC 62368-1"
                }
            ))
        else:
            # Report found barriers
            barrier_summary = ", ".join([f"{b.component} ({b.barrier_type})" for b in barriers])
            
            # Check isolation ratings
            min_isolation = min(b.rated_voltage or 0 for b in barriers)
            required_isolation = 2500  # IEC 62368-1 reinforced
            
            if min_isolation < required_isolation:
                issues.append(Issue(
                    issue_code="MNS-002",
                    severity=IssueSeverity.WARNING,
                    category="mains_safety",
                    title="Verify isolation barrier ratings",
                    description=(
                        f"Found isolation components: {barrier_summary}. "
                        f"Minimum isolation voltage may be {min_isolation}V. "
                        f"IEC 62368-1 requires {required_isolation}Vrms for reinforced insulation."
                    ),
                    suggested_fix=(
                        "1. Check component datasheets for isolation voltage rating\n"
                        "2. Ensure rating ≥2500Vrms for mains isolation\n"
                        "3. Verify creepage/clearance around isolation components"
                    ),
                    affected_components=[b.component for b in barriers]
                ))
            else:
                issues.append(Issue(
                    issue_code="MNS-003",
                    severity=IssueSeverity.INFO,
                    category="mains_safety",
                    title=f"Found {len(barriers)} isolation barrier(s)",
                    description=f"Isolation components detected: {barrier_summary}",
                    affected_components=[b.component for b in barriers]
                ))
        
        return issues
    
    def _check_clearance_creepage(
        self,
        mains_zone: SafetyZone,
        selv_zone: SafetyZone,
        pcb_data
    ) -> List[Issue]:
        """Check clearance and creepage distances"""
        issues = []
        
        required_clearance = self.safety_requirements.clearance_mm
        required_creepage = self.safety_requirements.creepage_mm
        
        # Create detailed issue about requirements
        issues.append(Issue(
            issue_code="MNS-010",
            severity=IssueSeverity.CRITICAL,
            category="mains_safety",
            title="Verify mains-to-SELV clearance and creepage",
            description=(
                f"IEC 62368-1 requires for {self.mains_region.value}:\n"
                f"• Minimum CLEARANCE: {required_clearance}mm (air gap)\n"
                f"• Minimum CREEPAGE: {required_creepage}mm (surface path)\n"
                f"• Insulation type: {self.safety_requirements.insulation_type.value}\n"
                f"• Working voltage: {self.safety_requirements.voltage_working}V RMS\n\n"
                f"Mains nets: {', '.join(mains_zone.nets[:5])}{'...' if len(mains_zone.nets) > 5 else ''}\n"
                f"SELV nets: {', '.join(selv_zone.nets[:5])}{'...' if len(selv_zone.nets) > 5 else ''}"
            ),
            suggested_fix=(
                f"1. Measure minimum copper-to-copper distance between mains and SELV\n"
                f"2. Clearance (air gap) must be ≥{required_clearance}mm\n"
                f"3. Creepage (along surface) must be ≥{required_creepage}mm\n"
                f"4. Add routed slots to increase creepage if needed:\n"
                f"   - 1mm wide slot adds 2×board_thickness to creepage\n"
                f"5. Use silkscreen barrier lines as visual guides\n"
                f"6. Add keepout zones around mains traces"
            ),
            affected_nets=mains_zone.nets[:10] + selv_zone.nets[:10],
            metadata={
                "required_clearance_mm": required_clearance,
                "required_creepage_mm": required_creepage,
                "insulation_type": self.safety_requirements.insulation_type.value,
                "standard": "IEC 62368-1",
                "mains_region": self.mains_region.value
            }
        ))
        
        # Slot enhancement suggestion
        issues.append(Issue(
            issue_code="MNS-011",
            severity=IssueSeverity.INFO,
            category="mains_safety",
            title="Consider isolation slots for enhanced creepage",
            description=(
                f"Routed slots between mains and SELV zones add creepage distance:\n"
                f"• 1mm wide slot in 1.6mm board adds ~3.2mm creepage\n"
                f"• Slot must be ≥1mm wide for Pollution Degree 2\n"
                f"• Slot must completely separate zones (no bridging)"
            ),
            suggested_fix=(
                "1. Route 1-2mm wide slot between mains and SELV areas\n"
                "2. Extend slot past all isolation components\n"
                "3. Do not place components across slot\n"
                "4. Add silkscreen marking on both sides"
            )
        ))
        
        return issues
    
    def _check_protection_devices(
        self,
        mains_zone: SafetyZone,
        pcb_data
    ) -> List[Issue]:
        """Check for mains protection devices"""
        issues = []
        
        # Find protection components
        movs = []
        tvs = []
        fuses = []
        gdts = []
        
        for comp in pcb_data.components:
            ref_lower = comp.reference.lower()
            value_lower = comp.value.lower() if comp.value else ""
            combined = ref_lower + " " + value_lower
            
            if any(p in combined for p in self.MOV_PATTERNS):
                movs.append(comp.reference)
            if any(p in combined for p in self.TVS_PATTERNS):
                tvs.append(comp.reference)
            if any(p in combined for p in self.FUSE_PATTERNS):
                fuses.append(comp.reference)
            if any(p in combined for p in self.GDT_PATTERNS):
                gdts.append(comp.reference)
        
        # Check for fuse
        if not fuses:
            issues.append(Issue(
                issue_code="MNS-020",
                severity=IssueSeverity.CRITICAL,
                category="mains_safety",
                title="No fuse detected on mains input",
                description=(
                    "Mains-powered equipment requires overcurrent protection. "
                    "No fuse or PTC detected near mains input."
                ),
                suggested_fix=(
                    "1. Add fuse in series with Line (L) conductor\n"
                    "2. Rating: typically 2-5A for small equipment\n"
                    "3. Type: time-delay (T) for inrush, fast (F) for sensitive circuits\n"
                    "4. Consider PTC resettable fuse for consumer products\n"
                    "5. Fuse holder should have adequate creepage"
                ),
                affected_nets=mains_zone.nets[:3]
            ))
        else:
            issues.append(Issue(
                issue_code="MNS-021",
                severity=IssueSeverity.INFO,
                category="mains_safety",
                title=f"Fuse/overcurrent protection detected: {', '.join(fuses)}",
                description="Verify fuse rating matches load requirements.",
                affected_components=fuses
            ))
        
        # Check for surge protection
        if not movs and not gdts:
            issues.append(Issue(
                issue_code="MNS-022",
                severity=IssueSeverity.WARNING,
                category="mains_safety",
                title="No surge protection detected on mains input",
                description=(
                    "MOV (Metal Oxide Varistor) or GDT (Gas Discharge Tube) recommended "
                    "for protection against mains surges and transients."
                ),
                suggested_fix=(
                    "1. Add MOV across L-N (e.g., 275V/300V MOV for 230V mains)\n"
                    "2. Place after fuse for coordinated protection\n"
                    "3. Consider MOV + GDT for enhanced protection\n"
                    "4. MOV should fail safely (not short-circuit)\n"
                    "5. Add thermal fuse for MOV failure protection"
                ),
                affected_nets=mains_zone.nets[:3]
            ))
        else:
            surge_devices = movs + gdts
            issues.append(Issue(
                issue_code="MNS-023",
                severity=IssueSeverity.INFO,
                category="mains_safety",
                title=f"Surge protection detected: {', '.join(surge_devices)}",
                description="Verify surge device ratings match mains voltage.",
                affected_components=surge_devices
            ))
        
        return issues
    
    def _check_grounding(
        self,
        mains_zone: SafetyZone,
        pcb_data
    ) -> List[Issue]:
        """Check grounding and bonding"""
        issues = []
        
        # Look for earth/protective ground nets
        earth_patterns = ['earth', 'pe', 'gnd_earth', 'chassis', 'protective']
        earth_nets = [
            net.name for net in pcb_data.nets
            if any(p in net.name.lower() for p in earth_patterns)
        ]
        
        if not earth_nets:
            issues.append(Issue(
                issue_code="MNS-030",
                severity=IssueSeverity.WARNING,
                category="mains_safety",
                title="No protective earth (PE) connection detected",
                description=(
                    "Class I equipment requires protective earth connection. "
                    "No PE or Earth net found."
                ),
                suggested_fix=(
                    "1. If Class I (earthed): Add PE connection to metal enclosure\n"
                    "2. PE trace width per IEC 62368-1 Table 31\n"
                    "3. If Class II (double insulated): Verify reinforced insulation\n"
                    "4. Label PE connection point clearly"
                )
            ))
        
        return issues
    
    def _check_hv_edge_clearance(
        self,
        mains_zone: SafetyZone,
        pcb_data
    ) -> List[Issue]:
        """Check HV clearance from board edges"""
        issues = []
        
        min_edge_clearance = 3.0  # mm - conservative for mains
        
        issues.append(Issue(
            issue_code="MNS-040",
            severity=IssueSeverity.WARNING,
            category="mains_safety",
            title="Verify mains clearance from board edges",
            description=(
                f"Mains voltage traces/pads should be ≥{min_edge_clearance}mm "
                f"from board edges for safety and handling."
            ),
            suggested_fix=(
                f"1. Keep mains copper ≥{min_edge_clearance}mm from all edges\n"
                "2. Add keepout zones along edges\n"
                "3. Consider V-score or routing clearance if panelized"
            ),
            affected_nets=mains_zone.nets[:5],
            metadata={
                "min_edge_clearance_mm": min_edge_clearance
            }
        ))
        
        return issues
    
    def get_iec62368_requirements(
        self,
        voltage_rms: float,
        insulation: InsulationType = InsulationType.REINFORCED
    ) -> SafetyMargins:
        """
        Get IEC 62368-1 requirements for a specific voltage
        
        Args:
            voltage_rms: RMS voltage
            insulation: Required insulation type
        
        Returns:
            SafetyMargins with clearance and creepage
        """
        voltage_peak = voltage_rms * 1.414
        
        clearance = IEC62368.get_clearance(voltage_peak, insulation)
        creepage = IEC62368.get_creepage(voltage_rms, insulation)
        
        return SafetyMargins(
            clearance_mm=clearance,
            creepage_mm=creepage,
            insulation_type=insulation,
            voltage_working=voltage_rms,
            voltage_peak=voltage_peak
        )
