"""
Document Indexer for PCB Knowledge Base
Chunks and indexes documents for RAG retrieval

Handles:
- Large text files (compiled PDFs)
- Document structure detection
- Metadata extraction
- Image reference linking
"""

import os
import re
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Document type classification"""
    STANDARD = "standard"           # IPC, IEC, etc.
    APPLICATION_NOTE = "app_note"   # TI, NXP app notes
    DESIGN_GUIDE = "design_guide"   # Design guidelines
    DATASHEET = "datasheet"         # Component datasheets
    TUTORIAL = "tutorial"           # Educational content
    REFERENCE = "reference"         # Tables, formulas
    UNKNOWN = "unknown"


@dataclass
class DocumentChunk:
    """A chunk of document for indexing"""
    chunk_id: str
    content: str
    source_file: str
    document_name: str
    document_type: DocumentType
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    
    # Metadata for retrieval
    topics: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # Related images
    related_images: List[str] = field(default_factory=list)
    
    # Position in source
    start_line: int = 0
    end_line: int = 0
    
    # Embedding (populated by vector store)
    embedding: Optional[List[float]] = None


class DocumentIndexer:
    """
    Indexes PCB knowledge base documents for RAG retrieval
    
    Optimized for:
    - IPC/IEC standards
    - TI/NXP application notes
    - Design guides and tutorials
    """
    
    # Document detection patterns
    DOCUMENT_PATTERNS = {
        DocumentType.STANDARD: [
            r'IPC-\d+', r'IEC \d+', r'UL \d+', r'EN \d+',
            r'MIL-STD', r'JEDEC', r'ISO \d+'
        ],
        DocumentType.APPLICATION_NOTE: [
            r'AN-?\d+', r'Application Note', r'App Note',
            r'SLOA\d+', r'SNVA\d+', r'SPRAAR', r'SLLA\d+'
        ],
        DocumentType.DESIGN_GUIDE: [
            r'Design Guide', r'Layout Guide', r'PCB Guidelines',
            r'Best Practices', r'Design Rules'
        ],
        DocumentType.DATASHEET: [
            r'Datasheet', r'Data Sheet', r'Specifications',
            r'Electrical Characteristics'
        ],
        DocumentType.TUTORIAL: [
            r'Tutorial', r'Introduction to', r'Getting Started',
            r'How to', r'Guide to'
        ],
    }
    
    # Topic detection for semantic categorization
    TOPIC_PATTERNS = {
        'power_supply': [
            r'buck', r'boost', r'LDO', r'regulator', r'SMPS', r'switching',
            r'power supply', r'voltage rail', r'decoupling', r'capacitor'
        ],
        'high_speed': [
            r'USB', r'PCIe', r'HDMI', r'differential', r'impedance',
            r'transmission line', r'signal integrity', r'crosstalk'
        ],
        'safety': [
            r'clearance', r'creepage', r'isolation', r'mains', r'high voltage',
            r'IEC 62368', r'safety', r'reinforced', r'insulation'
        ],
        'bus_interface': [
            r'I2C', r'SPI', r'RS-?485', r'CAN', r'UART', r'Modbus',
            r'termination', r'pull-?up', r'failsafe'
        ],
        'emc_emi': [
            r'EMC', r'EMI', r'shielding', r'filtering', r'noise',
            r'grounding', r'ground plane', r'return path'
        ],
        'thermal': [
            r'thermal', r'heat', r'temperature', r'dissipation',
            r'cooling', r'derating', r'via'
        ],
        'layout': [
            r'layout', r'routing', r'placement', r'trace', r'via',
            r'stackup', r'layer', r'copper'
        ],
        'components': [
            r'resistor', r'capacitor', r'inductor', r'MLCC',
            r'tantalum', r'electrolytic', r'E-?series'
        ],
    }
    
    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        """
        Initialize document indexer
        
        Args:
            chunk_size: Target size for each chunk (characters)
            chunk_overlap: Overlap between chunks for context
            min_chunk_size: Minimum chunk size to keep
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def index_knowledge_base(
        self,
        knowledge_base_paths: List[str],
        image_dirs: Optional[List[str]] = None
    ) -> List[DocumentChunk]:
        """
        Index all documents in knowledge base
        
        Args:
            knowledge_base_paths: Paths to text files
            image_dirs: Paths to image directories
        
        Returns:
            List of document chunks
        """
        all_chunks = []
        
        for kb_path in knowledge_base_paths:
            if not os.path.exists(kb_path):
                logger.warning(f"Knowledge base not found: {kb_path}")
                continue
            
            logger.info(f"Indexing: {kb_path}")
            
            # Read content
            with open(kb_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Detect and split by documents
            documents = self._split_into_documents(content, kb_path)
            
            logger.info(f"Found {len(documents)} documents in {kb_path}")
            
            # Chunk each document
            for doc_name, doc_content, doc_type in documents:
                chunks = self._chunk_document(
                    doc_content, 
                    kb_path, 
                    doc_name, 
                    doc_type
                )
                
                # Link related images
                if image_dirs:
                    chunks = self._link_images(chunks, doc_name, image_dirs)
                
                all_chunks.extend(chunks)
        
        logger.info(f"Total chunks created: {len(all_chunks)}")
        return all_chunks
    
    def _split_into_documents(
        self, 
        content: str,
        source_file: str
    ) -> List[Tuple[str, str, DocumentType]]:
        """Split compiled content into individual documents"""
        documents = []
        
        # Pattern to detect document boundaries
        # Matches: "DOCUMENT N: filename.pdf" or "=== filename ==="
        doc_pattern = r'(?:DOCUMENT\s+\d+:\s*([^\n]+\.pdf)|={3,}\s*FILE:\s*([^\n]+)|={40,}\s*\n\s*([^\n]+\.pdf))'
        
        splits = re.split(doc_pattern, content, flags=re.IGNORECASE)
        
        current_doc_name = Path(source_file).stem
        current_content = []
        
        i = 0
        while i < len(splits):
            part = splits[i]
            
            if part is None:
                i += 1
                continue
            
            # Check if this is a document name marker
            if part.endswith('.pdf') or part.endswith('.PDF'):
                # Save previous document
                if current_content:
                    doc_content = '\n'.join(current_content)
                    if len(doc_content) > self.min_chunk_size:
                        doc_type = self._detect_document_type(doc_content, current_doc_name)
                        documents.append((current_doc_name, doc_content, doc_type))
                
                current_doc_name = part.strip()
                current_content = []
            else:
                current_content.append(part)
            
            i += 1
        
        # Don't forget last document
        if current_content:
            doc_content = '\n'.join(current_content)
            if len(doc_content) > self.min_chunk_size:
                doc_type = self._detect_document_type(doc_content, current_doc_name)
                documents.append((current_doc_name, doc_content, doc_type))
        
        # If no documents detected, treat whole content as one document
        if not documents and len(content) > self.min_chunk_size:
            doc_type = self._detect_document_type(content, current_doc_name)
            documents.append((current_doc_name, content, doc_type))
        
        return documents
    
    def _detect_document_type(self, content: str, name: str) -> DocumentType:
        """Detect document type from content and name"""
        combined = content[:5000] + " " + name
        
        for doc_type, patterns in self.DOCUMENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return doc_type
        
        return DocumentType.UNKNOWN
    
    def _chunk_document(
        self,
        content: str,
        source_file: str,
        doc_name: str,
        doc_type: DocumentType
    ) -> List[DocumentChunk]:
        """Chunk a document with intelligent splitting"""
        chunks = []
        
        # Try to split by sections first
        sections = self._split_by_sections(content)
        
        if len(sections) > 1:
            # Process each section
            for section_title, section_content in sections:
                section_chunks = self._chunk_text(
                    section_content,
                    source_file,
                    doc_name,
                    doc_type,
                    section_title
                )
                chunks.extend(section_chunks)
        else:
            # No clear sections, chunk the whole content
            chunks = self._chunk_text(content, source_file, doc_name, doc_type)
        
        return chunks
    
    def _split_by_sections(self, content: str) -> List[Tuple[str, str]]:
        """Split content by section headers"""
        # Common section header patterns
        header_patterns = [
            r'^(?:#{1,3}|(?:\d+\.)+\d*)\s+(.+)$',  # Markdown or numbered
            r'^([A-Z][A-Z\s]+)$',  # ALL CAPS headers
            r'^(?:Section|Chapter|Part)\s+\d+[:\s]+(.+)$',  # Explicit sections
        ]
        
        lines = content.split('\n')
        sections = []
        current_title = None
        current_content = []
        
        for line in lines:
            is_header = False
            
            for pattern in header_patterns:
                match = re.match(pattern, line.strip())
                if match and len(line.strip()) < 100:  # Headers shouldn't be too long
                    is_header = True
                    
                    # Save previous section
                    if current_content:
                        section_text = '\n'.join(current_content)
                        if len(section_text) > self.min_chunk_size:
                            sections.append((current_title, section_text))
                    
                    current_title = line.strip()
                    current_content = []
                    break
            
            if not is_header:
                current_content.append(line)
        
        # Don't forget last section
        if current_content:
            section_text = '\n'.join(current_content)
            if len(section_text) > self.min_chunk_size:
                sections.append((current_title, section_text))
        
        return sections
    
    def _chunk_text(
        self,
        content: str,
        source_file: str,
        doc_name: str,
        doc_type: DocumentType,
        section_title: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Chunk text with overlap"""
        chunks = []
        
        # Split by paragraphs first
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk = []
        current_size = 0
        start_line = 0
        line_count = 0
        
        for para in paragraphs:
            para_size = len(para)
            para_lines = para.count('\n') + 1
            
            if current_size + para_size > self.chunk_size and current_chunk:
                # Create chunk
                chunk_content = '\n\n'.join(current_chunk)
                
                if len(chunk_content) >= self.min_chunk_size:
                    chunk = self._create_chunk(
                        chunk_content,
                        source_file,
                        doc_name,
                        doc_type,
                        section_title,
                        start_line,
                        line_count
                    )
                    chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_paras = []
                overlap_size = 0
                for p in reversed(current_chunk):
                    if overlap_size + len(p) <= self.chunk_overlap:
                        overlap_paras.insert(0, p)
                        overlap_size += len(p)
                    else:
                        break
                
                current_chunk = overlap_paras
                current_size = overlap_size
                start_line = line_count - sum(p.count('\n') + 1 for p in overlap_paras)
            
            current_chunk.append(para)
            current_size += para_size
            line_count += para_lines
        
        # Final chunk
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            if len(chunk_content) >= self.min_chunk_size:
                chunk = self._create_chunk(
                    chunk_content,
                    source_file,
                    doc_name,
                    doc_type,
                    section_title,
                    start_line,
                    line_count
                )
                chunks.append(chunk)
        
        return chunks
    
    def _create_chunk(
        self,
        content: str,
        source_file: str,
        doc_name: str,
        doc_type: DocumentType,
        section_title: Optional[str],
        start_line: int,
        end_line: int
    ) -> DocumentChunk:
        """Create a document chunk with metadata"""
        # Generate unique ID
        chunk_id = hashlib.md5(
            f"{source_file}:{doc_name}:{start_line}:{content[:100]}".encode()
        ).hexdigest()[:12]
        
        # Detect topics
        topics = self._detect_topics(content)
        
        # Extract keywords
        keywords = self._extract_keywords(content)
        
        return DocumentChunk(
            chunk_id=chunk_id,
            content=content,
            source_file=source_file,
            document_name=doc_name,
            document_type=doc_type,
            section_title=section_title,
            topics=topics,
            keywords=keywords,
            start_line=start_line,
            end_line=end_line
        )
    
    def _detect_topics(self, content: str) -> List[str]:
        """Detect relevant topics in content"""
        topics = []
        content_lower = content.lower()
        
        for topic, patterns in self.TOPIC_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    topics.append(topic)
                    break
        
        return topics
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extract key technical terms"""
        keywords = []
        
        # Technical term patterns
        patterns = [
            r'\b(IPC-\d+[A-Z]*)\b',           # IPC standards
            r'\b(IEC\s*\d+(?:-\d+)*)\b',      # IEC standards
            r'\b([A-Z]{2,}(?:\d+)?[A-Z]*)\b', # Acronyms
            r'\b(\d+(?:\.\d+)?(?:mm|mil|oz|V|A|Ω|µF|nF|pF|µH|MHz|GHz))\b',  # Values with units
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            keywords.extend(matches[:10])  # Limit per pattern
        
        return list(set(keywords))[:20]  # Dedupe and limit
    
    def _link_images(
        self,
        chunks: List[DocumentChunk],
        doc_name: str,
        image_dirs: List[str]
    ) -> List[DocumentChunk]:
        """Link related images to chunks"""
        # Create image directory name from document name
        doc_dir_name = doc_name.replace('.pdf', '').replace(' ', '_').replace('-', '_')
        
        for chunk in chunks:
            # Look for image references in content
            image_refs = re.findall(
                r'(?:Figure|Fig\.?|Image|Table)\s*(\d+(?:\.\d+)?)',
                chunk.content,
                re.IGNORECASE
            )
            
            # Try to find matching images
            for image_dir in image_dirs:
                # Look for directory matching document
                doc_image_dir = None
                for subdir in os.listdir(image_dir) if os.path.exists(image_dir) else []:
                    if doc_dir_name.lower() in subdir.lower():
                        doc_image_dir = os.path.join(image_dir, subdir)
                        break
                
                if doc_image_dir and os.path.exists(doc_image_dir):
                    images = os.listdir(doc_image_dir)
                    # Link first few images from the document
                    chunk.related_images = [
                        os.path.join(doc_image_dir, img)
                        for img in images[:5]
                        if img.lower().endswith(('.png', '.jpg', '.jpeg'))
                    ]
                    break
        
        return chunks
