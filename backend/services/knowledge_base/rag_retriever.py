"""
RAG Retriever for PCB Analysis
Retrieves relevant knowledge for AI-powered analysis

Provides:
- Query-aware context retrieval
- Multi-source aggregation
- Image reference handling
- Context ranking and deduplication
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from .document_indexer import DocumentIndexer, DocumentChunk, DocumentType
from .vector_store import VectorStore, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """Retrieved context for AI analysis"""
    
    # Text context
    context_text: str
    
    # Source chunks
    chunks: List[DocumentChunk]
    
    # Related images
    images: List[str]
    
    # Metadata
    sources: List[str]
    topics_covered: List[str]
    standards_referenced: List[str]
    
    # Retrieval stats
    total_chunks: int
    avg_relevance_score: float


class RAGRetriever:
    """
    RAG Retriever for PCB Design Knowledge
    
    Retrieves relevant context from:
    - IPC/IEC standards
    - TI/NXP application notes
    - Design guides and tutorials
    - Component datasheets
    """
    
    # Knowledge base paths
    DEFAULT_KNOWLEDGE_BASES = [
        "ee_study_extracted_content.txt",
        "extracted_content/COMPILED_ALL_PDFS.txt",
        "extracted_content-1/COMPILED_ALL_PDFS.txt",
    ]
    
    DEFAULT_IMAGE_DIRS = [
        "extracted_content/images",
        "extracted_content-1/images",
    ]
    
    # Topic-specific query templates
    TOPIC_QUERIES = {
        'power_supply': [
            "SMPS switching power supply layout guidelines hot loop",
            "buck boost regulator capacitor placement TI application note",
            "LDO thermal design power dissipation",
            "decoupling capacitor placement bypass filtering",
        ],
        'safety': [
            "IEC 62368 clearance creepage mains voltage isolation",
            "IPC-2221 electrical spacing table high voltage",
            "reinforced insulation basic insulation pollution degree",
            "mains safety optocoupler transformer isolation",
        ],
        'bus_interface': [
            "I2C pull-up resistor calculation bus capacitance",
            "RS-485 termination resistor failsafe biasing",
            "CAN bus termination differential routing",
            "SPI layout guidelines trace length signal integrity",
        ],
        'high_speed': [
            "USB differential impedance routing guidelines",
            "PCIe HDMI differential pair length matching skew",
            "high speed signal integrity crosstalk 5W rule",
            "transmission line impedance microstrip stripline",
        ],
        'thermal': [
            "IPC-2152 trace current capacity temperature rise",
            "thermal via pattern exposed pad QFN",
            "power dissipation heat spreading copper pour",
            "via current carrying capacity calculation",
        ],
        'emc_emi': [
            "EMC EMI filtering grounding ground plane",
            "return current path impedance loop area",
            "decoupling bypass capacitor placement high frequency",
            "shielding and filtering techniques PCB",
        ],
        'components': [
            "E-series resistor capacitor standard values IEC 60063",
            "MLCC ceramic capacitor DC bias voltage derating",
            "tantalum capacitor voltage derating failure",
            "inductor selection saturation current DCR",
        ],
        'layout': [
            "PCB layout routing best practices component placement",
            "via placement trace width design rules",
            "ground plane power plane stackup layer",
            "analog digital mixed signal layout separation",
        ],
    }
    
    def __init__(
        self,
        project_root: Optional[str] = None,
        index_path: Optional[str] = None
    ):
        """
        Initialize RAG retriever
        
        Args:
            project_root: Root directory of the project
            index_path: Path to pre-built index
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            self.project_root = Path(__file__).parent.parent.parent.parent
        
        self.indexer = DocumentIndexer()
        self.vector_store = VectorStore()
        
        self.is_initialized = False
        
        # Try to load existing index
        if index_path and os.path.exists(index_path):
            if self.vector_store.load_index(index_path):
                self.is_initialized = True
                logger.info("Loaded pre-built index")
    
    def initialize(self, force_rebuild: bool = False) -> bool:
        """
        Initialize the knowledge base index
        
        Args:
            force_rebuild: Force rebuild even if index exists
        
        Returns:
            True if successful
        """
        if self.is_initialized and not force_rebuild:
            return True
        
        # Find knowledge base files
        kb_paths = []
        for kb in self.DEFAULT_KNOWLEDGE_BASES:
            full_path = self.project_root / kb
            if full_path.exists():
                kb_paths.append(str(full_path))
        
        if not kb_paths:
            logger.error("No knowledge base files found")
            return False
        
        # Find image directories
        image_dirs = []
        for img_dir in self.DEFAULT_IMAGE_DIRS:
            full_path = self.project_root / img_dir
            if full_path.exists():
                image_dirs.append(str(full_path))
        
        logger.info(f"Indexing {len(kb_paths)} knowledge bases...")
        
        try:
            # Index documents
            chunks = self.indexer.index_knowledge_base(kb_paths, image_dirs)
            
            # Build vector index
            self.vector_store.index_chunks(chunks)
            
            # Save index for future use
            index_path = self.project_root / "backend" / "cache" / "rag_index.pkl"
            index_path.parent.mkdir(parents=True, exist_ok=True)
            self.vector_store.save_index(str(index_path))
            
            self.is_initialized = True
            logger.info(f"RAG index initialized with {len(chunks)} chunks")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            return False
    
    def retrieve_for_analysis(
        self,
        pcb_context: Dict,
        detected_topics: List[str],
        max_chunks: int = 10,
        include_images: bool = True
    ) -> RetrievalContext:
        """
        Retrieve relevant context for PCB analysis
        
        Args:
            pcb_context: Context from PCB data (components, nets, etc.)
            detected_topics: Topics detected in the design
            max_chunks: Maximum chunks to retrieve
            include_images: Whether to include related images
        
        Returns:
            RetrievalContext with relevant knowledge
        """
        if not self.is_initialized:
            self.initialize()
        
        all_results: List[SearchResult] = []
        
        # Build queries based on PCB context
        queries = self._build_contextual_queries(pcb_context, detected_topics)
        
        # Retrieve for each query
        for query in queries:
            results = self.vector_store.hybrid_search(
                query,
                top_k=max_chunks // len(queries) + 1
            )
            all_results.extend(results)
        
        # Deduplicate and rank
        unique_results = self._deduplicate_results(all_results)
        top_results = sorted(unique_results, key=lambda r: r.score, reverse=True)[:max_chunks]
        
        # Build context
        return self._build_context(top_results, include_images)
    
    def retrieve_for_query(
        self,
        query: str,
        top_k: int = 5,
        filter_topics: Optional[List[str]] = None
    ) -> RetrievalContext:
        """
        Retrieve context for a specific query
        
        Args:
            query: Natural language query
            top_k: Number of results
            filter_topics: Optional topic filter
        
        Returns:
            RetrievalContext
        """
        if not self.is_initialized:
            self.initialize()
        
        results = self.vector_store.hybrid_search(query, top_k=top_k)
        
        if filter_topics:
            results = [r for r in results if any(t in r.chunk.topics for t in filter_topics)]
        
        return self._build_context(results, include_images=True)
    
    def retrieve_for_issue(
        self,
        issue_category: str,
        issue_description: str,
        affected_components: List[str] = None,
        affected_nets: List[str] = None
    ) -> RetrievalContext:
        """
        Retrieve context relevant to a specific issue
        
        Args:
            issue_category: Category of the issue
            issue_description: Description of the issue
            affected_components: Related components
            affected_nets: Related nets
        
        Returns:
            RetrievalContext with relevant solutions
        """
        if not self.is_initialized:
            self.initialize()
        
        # Build issue-specific query
        query_parts = [issue_description]
        
        # Add category-specific terms
        category_terms = {
            'power_supply': 'SMPS regulator capacitor inductor layout',
            'safety': 'clearance creepage isolation safety IEC IPC',
            'bus_interface': 'termination biasing pull-up interface',
            'high_speed': 'impedance differential routing signal integrity',
            'thermal': 'thermal via heat dissipation current capacity',
            'emc_emi': 'EMC filtering grounding shielding noise',
        }
        
        if issue_category in category_terms:
            query_parts.append(category_terms[issue_category])
        
        query = ' '.join(query_parts)
        
        results = self.vector_store.hybrid_search(query, top_k=5)
        
        return self._build_context(results, include_images=True)
    
    def _build_contextual_queries(
        self,
        pcb_context: Dict,
        detected_topics: List[str]
    ) -> List[str]:
        """Build queries based on PCB context"""
        queries = []
        
        # Add topic-specific queries
        for topic in detected_topics:
            if topic in self.TOPIC_QUERIES:
                queries.extend(self.TOPIC_QUERIES[topic][:2])
        
        # Add component-specific queries
        components = pcb_context.get('components', [])
        for comp in components[:10]:
            value = comp.get('value', '').lower()
            
            if any(kw in value for kw in ['ldo', 'regulator', '78', '117']):
                queries.append("LDO linear regulator thermal design capacitor selection")
            elif any(kw in value for kw in ['buck', 'boost', 'mp15', 'lm25', 'tps']):
                queries.append("switching regulator SMPS layout hot loop inductor")
            elif any(kw in value for kw in ['rs485', 'max485', 'sn65']):
                queries.append("RS-485 transceiver termination biasing ESD protection")
            elif any(kw in value for kw in ['can', 'mcp255', 'tja']):
                queries.append("CAN bus transceiver termination differential routing")
        
        # Add net-specific queries
        nets = pcb_context.get('nets', [])
        net_names = [n.get('name', '').lower() for n in nets]
        
        if any('mains' in n or '230v' in n or 'ac' in n for n in net_names):
            queries.append("mains voltage isolation clearance creepage IEC 62368")
        
        if any('usb' in n for n in net_names):
            queries.append("USB differential impedance routing ESD protection")
        
        if any('i2c' in n or 'sda' in n or 'scl' in n for n in net_names):
            queries.append("I2C pull-up resistor calculation bus capacitance speed")
        
        # Ensure at least some general queries
        if not queries:
            queries = [
                "PCB design best practices layout guidelines",
                "component placement routing techniques",
            ]
        
        return queries[:8]  # Limit total queries
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate chunks from results"""
        seen = set()
        unique = []
        
        for result in results:
            chunk_id = result.chunk.chunk_id
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique.append(result)
        
        return unique
    
    def _build_context(
        self,
        results: List[SearchResult],
        include_images: bool
    ) -> RetrievalContext:
        """Build retrieval context from results"""
        if not results:
            return RetrievalContext(
                context_text="",
                chunks=[],
                images=[],
                sources=[],
                topics_covered=[],
                standards_referenced=[],
                total_chunks=0,
                avg_relevance_score=0.0
            )
        
        chunks = [r.chunk for r in results]
        
        # Build context text
        context_parts = []
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            context_parts.append(f"--- Reference {i} (Source: {chunk.document_name}) ---")
            if chunk.section_title:
                context_parts.append(f"Section: {chunk.section_title}")
            context_parts.append(chunk.content)
            context_parts.append("")
        
        context_text = "\n".join(context_parts)
        
        # Collect images
        images = []
        if include_images:
            for chunk in chunks:
                images.extend(chunk.related_images[:2])
            images = images[:10]  # Limit total images
        
        # Collect sources
        sources = list(set(c.document_name for c in chunks))
        
        # Collect topics
        topics_covered = list(set(
            topic for c in chunks for topic in c.topics
        ))
        
        # Extract standards
        standards = []
        for chunk in chunks:
            for kw in chunk.keywords:
                if any(std in kw.upper() for std in ['IPC', 'IEC', 'UL', 'EN', 'MIL']):
                    standards.append(kw)
        standards_referenced = list(set(standards))
        
        # Calculate average score
        avg_score = sum(r.score for r in results) / len(results)
        
        return RetrievalContext(
            context_text=context_text,
            chunks=chunks,
            images=images,
            sources=sources,
            topics_covered=topics_covered,
            standards_referenced=standards_referenced,
            total_chunks=len(chunks),
            avg_relevance_score=avg_score
        )
    
    def get_standards_context(self, standards: List[str]) -> RetrievalContext:
        """Get context specifically from standards documents"""
        if not self.is_initialized:
            self.initialize()
        
        query = ' '.join(standards)
        
        results = self.vector_store.search(
            query,
            top_k=10,
            filter_doc_types=[DocumentType.STANDARD, DocumentType.REFERENCE]
        )
        
        return self._build_context(results, include_images=False)
