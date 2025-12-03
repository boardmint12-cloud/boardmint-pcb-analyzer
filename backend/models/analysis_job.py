"""
Analysis Job model - represents analysis runs on projects
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Configuration
    fab_profile = Column(String(100), default="cheap_cn_8mil")
    
    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(String(100))  # Current step description
    
    # Results summary
    risk_level = Column(String(50))  # low, moderate, high
    critical_count = Column(String, default="0")
    warning_count = Column(String, default="0")
    info_count = Column(String, default="0")
    
    # Raw results (normalized JSON)
    raw_results = Column(JSON)
    
    # Error info (if failed)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    project = relationship("Project", back_populates="analysis_jobs")
    issues = relationship("Issue", back_populates="job", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AnalysisJob {self.id} - {self.status}>"
