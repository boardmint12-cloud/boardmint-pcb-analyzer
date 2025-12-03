"""
Base rule class and issue definitions
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod


class IssueSeverity(str, Enum):
    """Issue severity levels"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """Represents an analysis issue/finding"""
    issue_code: str
    severity: IssueSeverity
    category: str
    title: str
    description: str
    suggested_fix: str
    affected_nets: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    location_x: Optional[float] = None
    location_y: Optional[float] = None
    layer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRule(ABC):
    """Base class for rule modules"""
    
    def __init__(self, fab_profile: str = "cheap_cn_8mil"):
        """
        Initialize rule module
        
        Args:
            fab_profile: Fabrication profile to use for rules
        """
        self.fab_profile = fab_profile
        self.fab_rules = self._get_fab_rules(fab_profile)
    
    @abstractmethod
    def analyze(self, pcb_data) -> List[Issue]:
        """
        Run analysis rules
        
        Args:
            pcb_data: ParsedPCBData object
            
        Returns:
            List of Issue objects
        """
        pass
    
    def _get_fab_rules(self, profile: str) -> Dict[str, Any]:
        """Get fabrication rules for profile"""
        profiles = {
            "cheap_cn_8mil": {
                "min_track_width": 0.15,  # 6 mil ≈ 0.15mm
                "min_spacing": 0.15,
                "min_drill": 0.3,
                "mains_clearance": 3.0,  # mm
                "creepage_distance": 4.0,  # mm
            },
            "local_fab_8mil": {
                "min_track_width": 0.2,  # 8 mil ≈ 0.2mm
                "min_spacing": 0.2,
                "min_drill": 0.35,
                "mains_clearance": 3.0,
                "creepage_distance": 4.0,
            },
            "hdi_4mil": {
                "min_track_width": 0.1,  # 4 mil ≈ 0.1mm
                "min_spacing": 0.1,
                "min_drill": 0.2,
                "mains_clearance": 3.0,
                "creepage_distance": 4.0,
            }
        }
        
        return profiles.get(profile, profiles["cheap_cn_8mil"])
