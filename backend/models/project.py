"""
Project model - represents uploaded PCB projects
"""
from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    eda_tool = Column(String(50), nullable=False)  # kicad, altium, easyleda, gerber
    
    # File paths
    zip_path = Column(String(500), nullable=False)
    extracted_path = Column(String(500))
    
    # Status
    status = Column(String(50), default="uploaded")  # uploaded, analyzing, completed, failed
    
    # Metadata
    board_size_x = Column(Integer)  # mm
    board_size_y = Column(Integer)  # mm
    layer_count = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    analysis_jobs = relationship("AnalysisJob", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project {self.name} ({self.eda_tool})>"
