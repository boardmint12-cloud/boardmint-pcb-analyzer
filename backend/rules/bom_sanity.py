"""
BOM sanity checks
Verifies completeness, detects missing MPNs, placeholder parts
"""
import logging
import re
from typing import List
from .base_rule import BaseRule, Issue, IssueSeverity

logger = logging.getLogger(__name__)


class BOMSanityRules(BaseRule):
    """Rules for BOM quality and completeness"""
    
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Analyze BOM quality
        
        Args:
            pcb_data: ParsedPCBData object
            
        Returns:
            List of BOM issues
        """
        issues = []
        
        if not pcb_data.components:
            issue = Issue(
                issue_code="BOM-001",
                severity=IssueSeverity.CRITICAL,
                category="bom",
                title="No components found",
                description="No components were extracted from the project files.",
                suggested_fix="Ensure BOM file or layout file with component data is included."
            )
            issues.append(issue)
            return issues
        
        # Check for missing MPNs
        issues.extend(self._check_missing_mpns(pcb_data))
        
        # Check for placeholder parts
        issues.extend(self._check_placeholder_parts(pcb_data))
        
        # Check for potential duplicates
        issues.extend(self._check_duplicate_values(pcb_data))
        
        # Check for key components
        issues.extend(self._check_key_components(pcb_data))
        
        return issues
    
    def _check_missing_mpns(self, pcb_data) -> List[Issue]:
        """Check for components without manufacturer part numbers"""
        issues = []
        
        # Focus on active components (ICs, transistors, etc.)
        active_prefixes = ['U', 'Q', 'IC', 'T']
        connector_prefixes = ['J', 'P', 'CON']
        critical_prefixes = active_prefixes + connector_prefixes + ['K', 'RLY']  # Include relays
        
        missing_mpn = [
            comp for comp in pcb_data.components
            if not comp.mpn and any(comp.reference.startswith(prefix) for prefix in critical_prefixes)
        ]
        
        if missing_mpn:
            missing_refs = [c.reference for c in missing_mpn[:10]]  # Show first 10
            
            issue = Issue(
                issue_code="BOM-002",
                severity=IssueSeverity.WARNING,
                category="bom",
                title=f"{len(missing_mpn)} critical components missing MPN",
                description=(
                    f"Found {len(missing_mpn)} active/critical components without "
                    f"manufacturer part numbers. Examples: {', '.join(missing_refs)}. "
                    "This creates ambiguity for procurement and assembly."
                ),
                suggested_fix=(
                    "1. Add MPN column to BOM with exact part numbers\n"
                    "2. Include manufacturer name for clarity\n"
                    "3. Verify parts are available from distributors (Digikey, Mouser, etc.)\n"
                    "4. Consider alternates for long-lead items"
                ),
                affected_components=missing_refs,
                metadata={'missing_count': len(missing_mpn)}
            )
            issues.append(issue)
        
        return issues
    
    def _check_placeholder_parts(self, pcb_data) -> List[Issue]:
        """Check for placeholder/dummy parts"""
        issues = []
        
        placeholder_keywords = ['tbd', 'tbc', 'xxx', 'test', 'sample', 'placeholder', 'dnp', 'do not place']
        
        placeholders = [
            comp for comp in pcb_data.components
            if comp.mpn and any(kw in comp.mpn.lower() for kw in placeholder_keywords)
            or comp.value and any(kw in comp.value.lower() for kw in placeholder_keywords)
        ]
        
        if placeholders:
            placeholder_refs = [c.reference for c in placeholders[:5]]
            
            issue = Issue(
                issue_code="BOM-003",
                severity=IssueSeverity.WARNING,
                category="bom",
                title=f"{len(placeholders)} placeholder components detected",
                description=(
                    f"Found components with placeholder values like 'TBD', 'TEST', etc. "
                    f"Examples: {', '.join(placeholder_refs)}. These must be resolved before production."
                ),
                suggested_fix=(
                    "1. Replace placeholder parts with actual MPNs\n"
                    "2. If truly optional (DNP), mark clearly in BOM notes\n"
                    "3. For test points, ensure they're intentional"
                ),
                affected_components=placeholder_refs
            )
            issues.append(issue)
        
        return issues
    
    def _check_duplicate_values(self, pcb_data) -> List[Issue]:
        """Check for potentially redundant duplicate parts"""
        issues = []
        
        # Group resistors by value
        resistors = [c for c in pcb_data.components if c.reference.startswith('R')]
        
        if len(resistors) > 20:
            # Count unique values
            unique_values = set(r.value for r in resistors if r.value)
            
            if len(unique_values) > 15:
                issue = Issue(
                    issue_code="BOM-004",
                    severity=IssueSeverity.INFO,
                    category="bom",
                    title=f"High resistor value diversity: {len(unique_values)} unique values",
                    description=(
                        f"Board has {len(resistors)} resistors with {len(unique_values)} different values. "
                        "Consider consolidating to reduce BOM line items and improve assembly efficiency."
                    ),
                    suggested_fix=(
                        "1. Review if similar values can be standardized (e.g., 1k vs 1.2k)\n"
                        "2. Use E12 or E24 series values for consistency\n"
                        "3. Reduces assembly errors and simplifies inventory\n"
                        "4. Common building automation practice: stick to ~10 resistor values"
                    ),
                    metadata={'resistor_count': len(resistors), 'unique_values': len(unique_values)}
                )
                issues.append(issue)
        
        return issues
    
    def _check_key_components(self, pcb_data) -> List[Issue]:
        """Check for presence of key component types"""
        issues = []
        
        # Check for MCU/processor
        mcu_keywords = ['stm32', 'atmega', 'pic', 'esp', 'nrf', 'mcu', 'cpu']
        mcus = [
            comp for comp in pcb_data.components
            if any(kw in comp.value.lower() or kw in comp.reference.lower() 
                   for kw in mcu_keywords)
        ]
        
        if not mcus:
            issue = Issue(
                issue_code="BOM-005",
                severity=IssueSeverity.INFO,
                category="bom",
                title="No microcontroller detected",
                description=(
                    "Could not identify a microcontroller/processor. Most building automation "
                    "boards need an MCU for control logic."
                ),
                suggested_fix=(
                    "If design includes MCU, ensure it's labeled clearly in BOM. "
                    "If design is passive (e.g., breakout board), this is expected."
                )
            )
            issues.append(issue)
        else:
            issue = Issue(
                issue_code="BOM-006",
                severity=IssueSeverity.INFO,
                category="bom",
                title=f"Microcontroller detected: {mcus[0].reference}",
                description=(
                    f"Found MCU: {mcus[0].value}. Verify programming interface (SWD/JTAG/UART) "
                    "is accessible for firmware updates."
                ),
                suggested_fix=(
                    "1. Ensure programming header is present\n"
                    "2. Add test points for critical signals (RESET, BOOT, etc.)\n"
                    "3. Document programming procedure in assembly docs"
                ),
                affected_components=[mcus[0].reference]
            )
            issues.append(issue)
        
        return issues
