"""
Business Logic Services for PCB Analysis

This package provides:
- File upload and extraction
- PCB analysis orchestration
- AI-powered analysis (V1 and V2)
- RAG-based knowledge retrieval
- Export and reporting
"""

# Core services
from .upload_service import UploadService
from .analysis_service import AnalysisService
from .export_service import ExportService

# AI Services (V1 - Legacy)
from .ai_service import AIAnalysisService
from .gpt_extractor import GPTExtractor

# AI Services (V2 - RAG-Powered)
from .ai_service_v2 import AIAnalysisServiceV2
from .gpt_extractor_v2 import GPTExtractorV2

# Rule Profiles
from .rule_profiles import RuleProfileLibrary, RuleProfile
from .rule_profiles_v2 import RuleProfileLibrary as RuleProfileLibraryV2

# DRC Engine
from .drc_engine import DRCEngine
from .drc_engine_v2 import DRCEngineV2

# Knowledge Base
from .knowledge_base import (
    DocumentIndexer,
    DocumentChunk,
    VectorStore,
    SearchResult,
    RAGRetriever,
    RetrievalContext,
)

__all__ = [
    # Core
    "UploadService",
    "AnalysisService", 
    "ExportService",
    
    # AI V1 (Legacy)
    "AIAnalysisService",
    "GPTExtractor",
    
    # AI V2 (RAG-Powered)
    "AIAnalysisServiceV2",
    "GPTExtractorV2",
    
    # Rule Profiles
    "RuleProfileLibrary",
    "RuleProfile",
    "RuleProfileLibraryV2",
    
    # DRC Engine
    "DRCEngine",
    "DRCEngineV2",
    
    # Knowledge Base
    "DocumentIndexer",
    "DocumentChunk",
    "VectorStore",
    "SearchResult",
    "RAGRetriever",
    "RetrievalContext",
]
