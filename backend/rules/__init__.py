"""
Rule Engine for PCB Analysis - Industry Standard Implementation

This package provides comprehensive DRC rule engines based on:
- IPC-2221A: PCB Design Standards
- IEC 62368-1: Safety Requirements  
- TI Application Notes: Power & Interface Layout
- NXP AN10216: I2C Design Guide
"""

# Base classes
from .base_rule import BaseRule, Issue, IssueSeverity

# Legacy rule engines (V1)
from .mains_safety import MainsSafetyRules
from .bus_interfaces import BusInterfaceRules
from .power_smps import PowerSMPSRules
from .bom_sanity import BOMSanityRules
from .assembly_test import AssemblyTestRules

# New industry-standard rule engines (V2)
from .mains_safety_v2 import MainsSafetyRulesV2, MainsVoltageRegion
from .bus_interfaces_v2 import BusInterfaceRulesV2
from .power_smps_v2 import PowerSMPSRulesV2
from .bom_validation import BOMValidationRules
from .high_speed_interfaces import HighSpeedInterfaceRules
from .thermal_analysis import ThermalAnalysisRules

__all__ = [
    # Base
    "BaseRule",
    "Issue",
    "IssueSeverity",
    
    # Legacy V1
    "MainsSafetyRules",
    "BusInterfaceRules",
    "PowerSMPSRules",
    "BOMSanityRules",
    "AssemblyTestRules",
    
    # Industry Standard V2
    "MainsSafetyRulesV2",
    "MainsVoltageRegion",
    "BusInterfaceRulesV2",
    "PowerSMPSRulesV2",
    "BOMValidationRules",
    "HighSpeedInterfaceRules",
    "ThermalAnalysisRules",
]
