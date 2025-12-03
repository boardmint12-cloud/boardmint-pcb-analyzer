"""
Cost Estimation Service
Provides rough cost estimates for PCB manufacturing, components, and assembly
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from models.canonical import Board

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Cost estimate breakdown"""
    pcb_cost: float  # PCB fabrication
    component_cost: float  # Components BOM
    assembly_cost: float  # SMD assembly
    total_cost: float  # Total
    currency: str = "USD"
    notes: List[str] = None
    
    def __post_init__(self):
        if self.notes is None:
            self.notes = []


class CostEstimator:
    """
    Cost estimation engine
    
    Provides rough estimates - not quotes!
    Useful for budgeting and design decisions
    """
    
    def __init__(self):
        # PCB cost per cm² by layer count (USD)
        self.pcb_base_cost = {
            2: 0.50,   # 2-layer: $0.50/cm²
            4: 1.25,   # 4-layer: $1.25/cm²
            6: 2.00,   # 6-layer: $2.00/cm²
            8: 3.00,   # 8-layer: $3.00/cm²
        }
        
        # Component cost estimates by category (USD)
        self.component_costs = {
            # Passives
            'resistor': 0.01,
            'capacitor': 0.02,
            'inductor': 0.05,
            'ferrite': 0.10,
            
            # Discretes
            'diode': 0.05,
            'led': 0.10,
            'transistor': 0.15,
            'mosfet': 0.30,
            
            # ICs
            'opamp': 0.50,
            'regulator': 0.80,
            'mcu': 2.00,
            'microcontroller': 2.00,
            'processor': 5.00,
            
            # Connectivity
            'connector': 0.50,
            'usb': 0.30,
            'header': 0.20,
            'terminal': 0.40,
            
            # Power
            'transformer': 3.00,
            'relay': 1.50,
            'fuse': 0.20,
            
            # Misc
            'crystal': 0.30,
            'oscillator': 0.80,
            'switch': 0.25,
            'button': 0.15,
            'buzzer': 0.50,
            
            # Default
            'unknown': 0.50,
        }
        
        # Assembly cost per component (USD)
        self.assembly_costs = {
            'smd': 0.10,      # SMD placement
            'through_hole': 0.20,  # Through-hole (more expensive)
            'bga': 0.50,      # BGA (requires X-ray)
            'qfn': 0.15,      # QFN (slightly more than regular SMD)
        }
    
    def estimate(self, board: Board, bom: Optional[List[Dict]] = None) -> CostBreakdown:
        """
        Estimate total project cost
        
        Args:
            board: Canonical board model
            bom: Optional BOM data (list of dicts with 'mpn', 'quantity', 'value')
        
        Returns:
            CostBreakdown with cost estimates
        """
        notes = []
        
        # 1. PCB Fabrication Cost
        pcb_cost = self._estimate_pcb_cost(board)
        notes.append(f"PCB: {board.outline.polygon.bounding_box().width:.1f} × {board.outline.polygon.bounding_box().height:.1f} mm, {board.layer_count()} layers")
        
        # 2. Component Cost
        component_cost = self._estimate_component_cost(board, bom)
        notes.append(f"Components: {board.component_count()} parts")
        
        # 3. Assembly Cost
        assembly_cost = self._estimate_assembly_cost(board)
        notes.append(f"Assembly: ~{self._count_smd_components(board)} SMD placements")
        
        # Total
        total_cost = pcb_cost + component_cost + assembly_cost
        
        notes.append("⚠️ Rough estimate only - not a quote!")
        notes.append("Actual costs vary by supplier and volume")
        
        return CostBreakdown(
            pcb_cost=round(pcb_cost, 2),
            component_cost=round(component_cost, 2),
            assembly_cost=round(assembly_cost, 2),
            total_cost=round(total_cost, 2),
            currency="USD",
            notes=notes
        )
    
    def _estimate_pcb_cost(self, board: Board) -> float:
        """
        Estimate PCB fabrication cost
        
        Based on:
        - Board area (cm²)
        - Layer count
        - Quantity (assume prototype qty=5)
        """
        if not board.outline:
            return 0.0
        
        bbox = board.outline.polygon.bounding_box()
        area_mm2 = bbox.width * bbox.height
        area_cm2 = area_mm2 / 100
        
        # Get cost per cm² for layer count
        layer_count = board.layer_count()
        if layer_count <= 2:
            cost_per_cm2 = self.pcb_base_cost[2]
        elif layer_count <= 4:
            cost_per_cm2 = self.pcb_base_cost[4]
        elif layer_count <= 6:
            cost_per_cm2 = self.pcb_base_cost[6]
        else:
            cost_per_cm2 = self.pcb_base_cost[8]
        
        # Base cost for 5 boards (typical prototype)
        base_cost = area_cm2 * cost_per_cm2 * 5
        
        # Add setup fee for small orders
        setup_fee = 10.0
        
        total_pcb_cost = base_cost + setup_fee
        
        logger.debug(f"PCB cost: {area_cm2:.1f} cm² × ${cost_per_cm2} × 5 boards + ${setup_fee} setup = ${total_pcb_cost:.2f}")
        
        return total_pcb_cost
    
    def _estimate_component_cost(self, board: Board, bom: Optional[List[Dict]] = None) -> float:
        """
        Estimate component cost
        
        If BOM provided with MPNs, could look up real prices
        For now, use heuristics based on component types
        """
        total_cost = 0.0
        
        for component in board.components:
            # Try to categorize component
            category = self._categorize_component(component.refdes, component.value, component.footprint)
            
            # Get cost estimate for category
            cost = self.component_costs.get(category, self.component_costs['unknown'])
            
            total_cost += cost
            
            logger.debug(f"{component.refdes} ({category}): ${cost:.2f}")
        
        return total_cost
    
    def _estimate_assembly_cost(self, board: Board) -> float:
        """
        Estimate assembly cost
        
        Based on:
        - Number of SMD components
        - Number of through-hole components
        - Special packages (BGA, QFN)
        """
        smd_count = 0
        th_count = 0
        bga_count = 0
        qfn_count = 0
        
        for component in board.components:
            footprint = (component.footprint or "").lower()
            
            if 'bga' in footprint:
                bga_count += 1
            elif 'qfn' in footprint or 'dfn' in footprint:
                qfn_count += 1
            elif 'th' in footprint or 'through' in footprint or 'dip' in footprint:
                th_count += 1
            else:
                # Assume SMD by default
                smd_count += 1
        
        # Calculate costs
        cost = 0.0
        cost += smd_count * self.assembly_costs['smd']
        cost += th_count * self.assembly_costs['through_hole']
        cost += bga_count * self.assembly_costs['bga']
        cost += qfn_count * self.assembly_costs['qfn']
        
        # Add stencil cost for SMD boards
        if smd_count > 0:
            cost += 15.0  # Stencil cost
        
        logger.debug(f"Assembly: {smd_count} SMD (${smd_count * self.assembly_costs['smd']:.2f}) + " +
                     f"{th_count} TH (${th_count * self.assembly_costs['through_hole']:.2f}) + " +
                     f"{bga_count} BGA (${bga_count * self.assembly_costs['bga']:.2f}) + " +
                     f"{qfn_count} QFN (${qfn_count * self.assembly_costs['qfn']:.2f}) + " +
                     f"$15 stencil = ${cost:.2f}")
        
        return cost
    
    def _categorize_component(self, refdes: str, value: Optional[str], footprint: Optional[str]) -> str:
        """
        Categorize component for cost estimation
        
        Uses reference designator, value, and footprint hints
        """
        refdes_lower = refdes.lower()
        value_lower = (value or "").lower()
        footprint_lower = (footprint or "").lower()
        
        # By reference designator
        if refdes_lower.startswith('r'):
            return 'resistor'
        elif refdes_lower.startswith('c'):
            return 'capacitor'
        elif refdes_lower.startswith('l'):
            return 'inductor'
        elif refdes_lower.startswith('d'):
            if 'led' in value_lower:
                return 'led'
            return 'diode'
        elif refdes_lower.startswith('q') or refdes_lower.startswith('t'):
            if 'mosfet' in value_lower or 'fet' in value_lower:
                return 'mosfet'
            return 'transistor'
        elif refdes_lower.startswith('u') or refdes_lower.startswith('ic'):
            # Try to identify IC type
            if 'mcu' in value_lower or 'micro' in value_lower or 'stm32' in value_lower or 'esp' in value_lower:
                return 'microcontroller'
            elif 'regulator' in value_lower or 'ldo' in value_lower or 'buck' in value_lower:
                return 'regulator'
            elif 'opamp' in value_lower or 'op-amp' in value_lower:
                return 'opamp'
            elif 'processor' in value_lower or 'cpu' in value_lower:
                return 'processor'
            return 'unknown'  # Generic IC
        elif refdes_lower.startswith('j') or refdes_lower.startswith('p') or refdes_lower.startswith('con'):
            if 'usb' in value_lower or 'usb' in footprint_lower:
                return 'usb'
            elif 'header' in footprint_lower:
                return 'header'
            elif 'terminal' in footprint_lower:
                return 'terminal'
            return 'connector'
        elif refdes_lower.startswith('k') or refdes_lower.startswith('rly'):
            return 'relay'
        elif refdes_lower.startswith('f'):
            return 'fuse'
        elif refdes_lower.startswith('y') or refdes_lower.startswith('x'):
            if 'oscillator' in value_lower:
                return 'oscillator'
            return 'crystal'
        elif refdes_lower.startswith('s') or refdes_lower.startswith('sw'):
            if 'button' in value_lower or 'push' in value_lower:
                return 'button'
            return 'switch'
        elif refdes_lower.startswith('bz') or refdes_lower.startswith('ls'):
            return 'buzzer'
        elif refdes_lower.startswith('t') and 'transformer' in value_lower:
            return 'transformer'
        elif refdes_lower.startswith('fb'):
            return 'ferrite'
        
        return 'unknown'
    
    def _count_smd_components(self, board: Board) -> int:
        """Count SMD components (excluding through-hole)"""
        count = 0
        for component in board.components:
            footprint = (component.footprint or "").lower()
            if 'th' not in footprint and 'dip' not in footprint and 'through' not in footprint:
                count += 1
        return count
