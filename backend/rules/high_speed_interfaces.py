"""
High-Speed Interface Rules - USB, PCIe, HDMI, SATA, Ethernet
Based on TI SPRAAR7J High-Speed Interface Layout Guidelines

This module provides comprehensive high-speed signal analysis:
- Differential pair routing rules (5W spacing rule)
- Trace length matching requirements
- Via discontinuity mitigation
- Reference plane guidelines
- Fiber weave skew mitigation
- ESD/EMI considerations

Sources:
- TI SPRAAR7J: High-Speed Interface Layout Guidelines
- USB-IF USB 2.0/3.0 Specifications
- PCI-SIG PCIe Specifications
- HDMI Specification
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_rule import BaseRule, Issue, IssueSeverity

logger = logging.getLogger(__name__)


class HighSpeedInterface(str, Enum):
    """High-speed interface types"""
    USB2 = "usb2"
    USB3 = "usb3"
    PCIE = "pcie"
    SATA = "sata"
    HDMI = "hdmi"
    ETHERNET_RGMII = "ethernet_rgmii"
    ETHERNET_SGMII = "ethernet_sgmii"
    MIPI_CSI = "mipi_csi"
    MIPI_DSI = "mipi_dsi"
    LVDS = "lvds"


@dataclass
class DifferentialPairSpec:
    """Differential pair specifications"""
    interface: HighSpeedInterface
    impedance_ohm: float
    impedance_tolerance_percent: float
    trace_width_mm: float
    trace_spacing_mm: float
    max_length_mm: float
    max_skew_mm: float
    min_pair_to_pair_spacing_mm: float


@dataclass
class DetectedHighSpeedInterface:
    """Detected high-speed interface"""
    interface_type: HighSpeedInterface
    signal_nets: List[str]
    positive_nets: List[str]
    negative_nets: List[str]
    clock_nets: List[str]
    connectors: List[str]


class HighSpeedInterfaceRules(BaseRule):
    """
    High-speed interface layout rules
    
    Based on TI SPRAAR7J and interface specifications:
    - Differential impedance control
    - 5W spacing rule for crosstalk
    - Length matching within pairs
    - Reference plane continuity
    """
    
    # ==========================================================================
    # INTERFACE SPECIFICATIONS (from TI SPRAAR7J)
    # ==========================================================================
    
    INTERFACE_SPECS: Dict[HighSpeedInterface, DifferentialPairSpec] = {
        HighSpeedInterface.USB2: DifferentialPairSpec(
            interface=HighSpeedInterface.USB2,
            impedance_ohm=90,
            impedance_tolerance_percent=10,
            trace_width_mm=0.15,  # 6 mil typical
            trace_spacing_mm=0.2,  # 8 mil typical
            max_length_mm=150,
            max_skew_mm=0.125,  # 5 mil
            min_pair_to_pair_spacing_mm=0.75  # 30 mil
        ),
        HighSpeedInterface.USB3: DifferentialPairSpec(
            interface=HighSpeedInterface.USB3,
            impedance_ohm=85,
            impedance_tolerance_percent=15,
            trace_width_mm=0.1,
            trace_spacing_mm=0.15,
            max_length_mm=100,
            max_skew_mm=0.075,
            min_pair_to_pair_spacing_mm=0.75
        ),
        HighSpeedInterface.PCIE: DifferentialPairSpec(
            interface=HighSpeedInterface.PCIE,
            impedance_ohm=85,
            impedance_tolerance_percent=15,
            trace_width_mm=0.1,
            trace_spacing_mm=0.15,
            max_length_mm=200,  # Gen3
            max_skew_mm=0.125,
            min_pair_to_pair_spacing_mm=0.5
        ),
        HighSpeedInterface.SATA: DifferentialPairSpec(
            interface=HighSpeedInterface.SATA,
            impedance_ohm=85,
            impedance_tolerance_percent=15,
            trace_width_mm=0.1,
            trace_spacing_mm=0.15,
            max_length_mm=150,
            max_skew_mm=0.125,
            min_pair_to_pair_spacing_mm=0.5
        ),
        HighSpeedInterface.HDMI: DifferentialPairSpec(
            interface=HighSpeedInterface.HDMI,
            impedance_ohm=100,
            impedance_tolerance_percent=10,
            trace_width_mm=0.1,
            trace_spacing_mm=0.15,
            max_length_mm=100,
            max_skew_mm=0.075,
            min_pair_to_pair_spacing_mm=0.5
        ),
        HighSpeedInterface.ETHERNET_RGMII: DifferentialPairSpec(
            interface=HighSpeedInterface.ETHERNET_RGMII,
            impedance_ohm=50,  # Single-ended
            impedance_tolerance_percent=10,
            trace_width_mm=0.2,
            trace_spacing_mm=0.2,
            max_length_mm=75,
            max_skew_mm=0.5,
            min_pair_to_pair_spacing_mm=0.5
        ),
        HighSpeedInterface.MIPI_CSI: DifferentialPairSpec(
            interface=HighSpeedInterface.MIPI_CSI,
            impedance_ohm=100,
            impedance_tolerance_percent=10,
            trace_width_mm=0.1,
            trace_spacing_mm=0.15,
            max_length_mm=100,
            max_skew_mm=0.05,
            min_pair_to_pair_spacing_mm=0.5
        ),
    }
    
    # ==========================================================================
    # SIGNAL DETECTION PATTERNS
    # ==========================================================================
    
    USB_PATTERNS = {
        'data': ['dp', 'dm', 'd+', 'd-', 'usb_d', 'usbdp', 'usbdm'],
        'ss': ['sstx', 'ssrx', 'ss_tx', 'ss_rx', 'usb3'],
        'power': ['vbus', 'usb_vcc', 'usb_5v']
    }
    
    PCIE_PATTERNS = {
        'tx': ['pcie_tx', 'pex_tx', 'pcie_txp', 'pcie_txn'],
        'rx': ['pcie_rx', 'pex_rx', 'pcie_rxp', 'pcie_rxn'],
        'clock': ['pcie_clk', 'refclk']
    }
    
    SATA_PATTERNS = {
        'tx': ['sata_tx', 'sata_txp', 'sata_txn'],
        'rx': ['sata_rx', 'sata_rxp', 'sata_rxn']
    }
    
    HDMI_PATTERNS = {
        'data': ['hdmi_d', 'tmds', 'hdmi_data'],
        'clock': ['hdmi_clk', 'tmds_clk']
    }
    
    ETHERNET_PATTERNS = {
        'rgmii': ['rgmii', 'txd', 'rxd', 'tx_clk', 'rx_clk', 'tx_ctl', 'rx_ctl'],
        'mdio': ['mdc', 'mdio']
    }
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Comprehensive high-speed interface analysis
        
        Args:
            pcb_data: ParsedPCBData object
        
        Returns:
            List of high-speed interface issues
        """
        issues = []
        
        # Detect interfaces
        detected = self._detect_interfaces(pcb_data)
        
        if not detected:
            return [Issue(
                issue_code="HS-000",
                severity=IssueSeverity.INFO,
                category="high_speed",
                title="No high-speed interfaces detected",
                description="No USB, PCIe, SATA, HDMI, or high-speed Ethernet signals found.",
                suggested_fix="If board has high-speed signals, ensure nets are properly labeled."
            )]
        
        logger.info(f"Detected high-speed interfaces: {[d.interface_type.value for d in detected]}")
        
        # Analyze each interface
        for interface in detected:
            issues.extend(self._check_interface(interface, pcb_data))
        
        # General high-speed guidelines
        issues.extend(self._create_general_guidelines())
        
        return issues
    
    def _detect_interfaces(self, pcb_data) -> List[DetectedHighSpeedInterface]:
        """Detect high-speed interfaces from nets"""
        detected = []
        
        # Check USB
        usb2_nets = []
        usb3_nets = []
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            if any(p in net_lower for p in self.USB_PATTERNS['data']):
                usb2_nets.append(net.name)
            if any(p in net_lower for p in self.USB_PATTERNS['ss']):
                usb3_nets.append(net.name)
        
        if usb2_nets:
            detected.append(DetectedHighSpeedInterface(
                interface_type=HighSpeedInterface.USB2,
                signal_nets=usb2_nets,
                positive_nets=[n for n in usb2_nets if 'p' in n.lower() or '+' in n],
                negative_nets=[n for n in usb2_nets if 'm' in n.lower() or '-' in n],
                clock_nets=[],
                connectors=[]
            ))
        
        if usb3_nets:
            detected.append(DetectedHighSpeedInterface(
                interface_type=HighSpeedInterface.USB3,
                signal_nets=usb3_nets,
                positive_nets=[n for n in usb3_nets if 'p' in n.lower()],
                negative_nets=[n for n in usb3_nets if 'n' in n.lower()],
                clock_nets=[],
                connectors=[]
            ))
        
        # Check PCIe
        pcie_nets = []
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            if any(p in net_lower for p in self.PCIE_PATTERNS['tx'] + self.PCIE_PATTERNS['rx']):
                pcie_nets.append(net.name)
        
        if pcie_nets:
            detected.append(DetectedHighSpeedInterface(
                interface_type=HighSpeedInterface.PCIE,
                signal_nets=pcie_nets,
                positive_nets=[n for n in pcie_nets if 'p' in n.lower()],
                negative_nets=[n for n in pcie_nets if 'n' in n.lower()],
                clock_nets=[n.name for n in pcb_data.nets 
                           if any(p in n.name.lower() for p in self.PCIE_PATTERNS['clock'])],
                connectors=[]
            ))
        
        # Check SATA
        sata_nets = []
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            if any(p in net_lower for p in self.SATA_PATTERNS['tx'] + self.SATA_PATTERNS['rx']):
                sata_nets.append(net.name)
        
        if sata_nets:
            detected.append(DetectedHighSpeedInterface(
                interface_type=HighSpeedInterface.SATA,
                signal_nets=sata_nets,
                positive_nets=[n for n in sata_nets if 'p' in n.lower()],
                negative_nets=[n for n in sata_nets if 'n' in n.lower()],
                clock_nets=[],
                connectors=[]
            ))
        
        # Check HDMI
        hdmi_nets = []
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            if any(p in net_lower for p in self.HDMI_PATTERNS['data']):
                hdmi_nets.append(net.name)
        
        if hdmi_nets:
            detected.append(DetectedHighSpeedInterface(
                interface_type=HighSpeedInterface.HDMI,
                signal_nets=hdmi_nets,
                positive_nets=[n for n in hdmi_nets if 'p' in n.lower()],
                negative_nets=[n for n in hdmi_nets if 'n' in n.lower()],
                clock_nets=[n.name for n in pcb_data.nets 
                           if any(p in n.name.lower() for p in self.HDMI_PATTERNS['clock'])],
                connectors=[]
            ))
        
        # Check Ethernet RGMII
        rgmii_nets = []
        for net in pcb_data.nets:
            net_lower = net.name.lower()
            if any(p in net_lower for p in self.ETHERNET_PATTERNS['rgmii']):
                rgmii_nets.append(net.name)
        
        if rgmii_nets:
            detected.append(DetectedHighSpeedInterface(
                interface_type=HighSpeedInterface.ETHERNET_RGMII,
                signal_nets=rgmii_nets,
                positive_nets=[],
                negative_nets=[],
                clock_nets=[n for n in rgmii_nets if 'clk' in n.lower()],
                connectors=[]
            ))
        
        return detected
    
    def _check_interface(
        self, 
        interface: DetectedHighSpeedInterface,
        pcb_data
    ) -> List[Issue]:
        """Check specific interface implementation"""
        issues = []
        
        spec = self.INTERFACE_SPECS.get(interface.interface_type)
        if not spec:
            return issues
        
        interface_name = interface.interface_type.value.upper()
        
        # Issue 1: Impedance control
        issues.append(Issue(
            issue_code=f"HS-{interface_name}-001",
            severity=IssueSeverity.WARNING,
            category="high_speed",
            title=f"{interface_name} differential impedance requirements",
            description=(
                f"Per TI SPRAAR7J, {interface_name} requires:\n"
                f"• Differential impedance: {spec.impedance_ohm}Ω ±{spec.impedance_tolerance_percent}%\n"
                f"• Trace width: ~{spec.trace_width_mm}mm ({spec.trace_width_mm/0.0254:.0f} mils)\n"
                f"• Pair spacing: ~{spec.trace_spacing_mm}mm ({spec.trace_spacing_mm/0.0254:.0f} mils)\n"
                f"• Max trace length: {spec.max_length_mm}mm"
            ),
            suggested_fix=(
                "1. Use impedance calculator to determine trace geometry\n"
                "2. Specify controlled impedance in fab notes\n"
                "3. Request impedance test coupon\n"
                f"4. Maintain {spec.impedance_ohm}Ω ±{spec.impedance_tolerance_percent}% throughout route"
            ),
            affected_nets=interface.signal_nets[:10],
            metadata={
                "impedance_ohm": spec.impedance_ohm,
                "tolerance_percent": spec.impedance_tolerance_percent,
                "max_length_mm": spec.max_length_mm
            }
        ))
        
        # Issue 2: Length matching
        issues.append(Issue(
            issue_code=f"HS-{interface_name}-002",
            severity=IssueSeverity.WARNING,
            category="high_speed",
            title=f"{interface_name} trace length matching",
            description=(
                f"Differential pair length matching requirements:\n"
                f"• Max intra-pair skew: {spec.max_skew_mm}mm ({spec.max_skew_mm/0.0254:.0f} mils)\n"
                f"• Match P and N traces of each pair\n"
                f"• Add serpentine at MISMATCHED end (not matched end)"
            ),
            suggested_fix=(
                "1. Route P and N traces together as differential pair\n"
                "2. Use EDA tool's diff pair routing mode\n"
                "3. Add length tuning serpentines where traces diverge\n"
                "4. Serpentine amplitude should be ≥3× trace width"
            ),
            affected_nets=interface.positive_nets[:5] + interface.negative_nets[:5]
        ))
        
        # Issue 3: 5W spacing rule
        issues.append(Issue(
            issue_code=f"HS-{interface_name}-003",
            severity=IssueSeverity.INFO,
            category="high_speed",
            title=f"{interface_name} crosstalk isolation (5W rule)",
            description=(
                f"Per TI SPRAAR7J '5W Rule':\n"
                f"• Minimum spacing between diff pairs: 5× trace width\n"
                f"• For {spec.trace_width_mm}mm traces: {spec.trace_width_mm * 5}mm minimum\n"
                f"• Keep 30 mil (0.75mm) minimum to any other signal\n"
                f"• 50 mil (1.25mm) minimum to clocks/periodic signals"
            ),
            suggested_fix=(
                f"1. Maintain ≥{spec.min_pair_to_pair_spacing_mm}mm between diff pairs\n"
                "2. Use ground plane between pairs if spacing tight\n"
                "3. Route high-speed signals first in layout\n"
                "4. Use via stitching along routes for isolation"
            ),
            affected_nets=interface.signal_nets[:10]
        ))
        
        # Issue 4: Reference planes
        issues.append(Issue(
            issue_code=f"HS-{interface_name}-004",
            severity=IssueSeverity.WARNING,
            category="high_speed",
            title=f"{interface_name} reference plane guidelines",
            description=(
                "Per TI SPRAAR7J, high-speed signals need solid reference:\n"
                "• Route over continuous GND plane\n"
                "• Do NOT cross plane splits or voids\n"
                "• Avoid routing over power plane islands\n"
                "• Maintain same reference from source to destination"
            ),
            suggested_fix=(
                "1. Verify solid GND plane under entire route\n"
                "2. If crossing split unavoidable: add stitching caps\n"
                "3. Use stitching vias within 200 mils of signal vias\n"
                "4. Place stitching vias symmetrically around signal vias"
            ),
            affected_nets=interface.signal_nets[:10]
        ))
        
        # Issue 5: Via discontinuities
        issues.append(Issue(
            issue_code=f"HS-{interface_name}-005",
            severity=IssueSeverity.INFO,
            category="high_speed",
            title=f"{interface_name} via discontinuity mitigation",
            description=(
                "Via stubs cause impedance discontinuities:\n"
                "• Via stub resonates at f = c/(4×stub_length×√εr)\n"
                "• 1.6mm board with 0.3mm via = ~7GHz resonance\n"
                "• Problem for USB3, PCIe Gen3+, high-speed SerDes"
            ),
            suggested_fix=(
                "1. Route on layers close to component side\n"
                "2. For high-speed: consider back-drilled vias\n"
                "3. Use blind/buried vias if available\n"
                "4. Equalize via count in P and N traces"
            ),
            affected_nets=interface.signal_nets[:10]
        ))
        
        # Interface-specific issues
        if interface.interface_type == HighSpeedInterface.USB2:
            issues.extend(self._check_usb2_specific(interface))
        elif interface.interface_type == HighSpeedInterface.USB3:
            issues.extend(self._check_usb3_specific(interface))
        elif interface.interface_type == HighSpeedInterface.ETHERNET_RGMII:
            issues.extend(self._check_rgmii_specific(interface))
        
        return issues
    
    def _check_usb2_specific(
        self, 
        interface: DetectedHighSpeedInterface
    ) -> List[Issue]:
        """USB 2.0 specific checks"""
        issues = []
        
        issues.append(Issue(
            issue_code="HS-USB2-ESD",
            severity=IssueSeverity.WARNING,
            category="high_speed",
            title="USB 2.0 ESD protection",
            description=(
                "USB ports are exposed to ESD from user contact:\n"
                "• Required: TVS diode array at connector\n"
                "• Common parts: PRTR5V0U2X, TPD2E001\n"
                "• Place within 10mm of connector"
            ),
            suggested_fix=(
                "1. Add TVS array on D+/D- near connector\n"
                "2. Add TVS on VBUS for surge protection\n"
                "3. Keep ESD trace length minimal\n"
                "4. Consider ESD on ID pin for OTG"
            ),
            affected_nets=interface.signal_nets
        ))
        
        return issues
    
    def _check_usb3_specific(
        self, 
        interface: DetectedHighSpeedInterface
    ) -> List[Issue]:
        """USB 3.0 specific checks"""
        issues = []
        
        issues.append(Issue(
            issue_code="HS-USB3-REDRIVER",
            severity=IssueSeverity.INFO,
            category="high_speed",
            title="USB 3.0 signal integrity considerations",
            description=(
                "USB 3.0 SuperSpeed operates at 5 Gbps:\n"
                "• Very sensitive to impedance discontinuities\n"
                "• Consider redriver/repeater for long traces\n"
                "• AC coupling caps typically integrated in connector"
            ),
            suggested_fix=(
                "1. Minimize via count on SS lanes\n"
                "2. Use consistent trace geometry throughout\n"
                "3. Consider redriver if route >100mm\n"
                "4. Verify connector has proper AC coupling"
            ),
            affected_nets=interface.signal_nets
        ))
        
        return issues
    
    def _check_rgmii_specific(
        self, 
        interface: DetectedHighSpeedInterface
    ) -> List[Issue]:
        """RGMII Ethernet specific checks"""
        issues = []
        
        issues.append(Issue(
            issue_code="HS-RGMII-TIMING",
            severity=IssueSeverity.WARNING,
            category="high_speed",
            title="RGMII timing and length matching",
            description=(
                "RGMII operates at 125 MHz (1000Base-T):\n"
                "• TX/RX data must be matched within 50 mils\n"
                "• Clock-to-data skew is critical\n"
                "• Internal vs external delay mode affects routing"
            ),
            suggested_fix=(
                "1. Match TXD[0:3], TX_CTL to TX_CLK within 50 mils\n"
                "2. Match RXD[0:3], RX_CTL to RX_CLK within 50 mils\n"
                "3. Check PHY datasheet for internal delay support\n"
                "4. May need ~2ns clock delay (PCB or IC)"
            ),
            affected_nets=interface.signal_nets
        ))
        
        return issues
    
    def _create_general_guidelines(self) -> List[Issue]:
        """Create general high-speed layout guidelines"""
        issues = []
        
        # Fiber weave mitigation
        issues.append(Issue(
            issue_code="HS-GENERAL-001",
            severity=IssueSeverity.INFO,
            category="high_speed",
            title="PCB fiber weave skew mitigation",
            description=(
                "Per TI SPRAAR7J, fiber weave causes differential skew:\n"
                "• FR4 weave has varying εr (glass ~6, epoxy ~3)\n"
                "• Can cause intra-pair skew and common-mode noise\n"
                "• Especially problematic for long routes"
            ),
            suggested_fix=(
                "Mitigation strategies:\n"
                "1. Rotate PCB image 5-15° to diagonal weave pattern\n"
                "2. Route diff pairs at angle to weave (10-35°)\n"
                "3. Use zig-zag routing pattern\n"
                "4. Specify tighter weave fabric (1080, 2116 vs 7628)"
            )
        ))
        
        # Stackup recommendations
        issues.append(Issue(
            issue_code="HS-GENERAL-002",
            severity=IssueSeverity.INFO,
            category="high_speed",
            title="Recommended PCB stackup for high-speed",
            description=(
                "Example 4-layer stackup for high-speed signals:\n"
                "• L1 (Top): Signal + Components\n"
                "• L2: GND plane (continuous)\n"
                "• L3: Power plane\n"
                "• L4 (Bottom): Signal\n\n"
                "Route high-speed on L1 referenced to L2 GND."
            ),
            suggested_fix=(
                "1. Place GND plane adjacent to high-speed signal layer\n"
                "2. Avoid routing high-speed on power-referenced layers\n"
                "3. Use asymmetric stackup if needed for impedance\n"
                "4. Request stackup from fab early in design"
            )
        ))
        
        return issues
