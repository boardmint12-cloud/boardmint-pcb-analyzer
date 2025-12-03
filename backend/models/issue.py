"""
Issue model - represents individual analysis findings
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class Issue(Base):
    __tablename__ = "issues"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False)
    
    # Issue identification
    issue_code = Column(String(50))  # e.g., MNS-001, BUS-003
    severity = Column(String(20), nullable=False)  # critical, warning, info
    category = Column(String(50), nullable=False)  # mains_safety, bus_interfaces, power, bom, assembly
    
    # Content
    title = Column(String(500), nullable=False)
    description = Column(Text)
    suggested_fix = Column(Text)
    
    # Affected items
    affected_nets = Column(JSON)  # List of net names
    affected_components = Column(JSON)  # List of component refs
    
    # Location (if applicable)
    location_x = Column(Float)
    location_y = Column(Float)
    layer = Column(String(50))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("AnalysisJob", back_populates="issues")
    
    def __repr__(self):
        return f"<Issue {self.issue_code}: {self.title}>"
