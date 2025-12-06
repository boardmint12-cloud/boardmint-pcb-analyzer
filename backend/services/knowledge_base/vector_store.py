"""
Vector Store for PCB Knowledge Base
Semantic search using OpenAI embeddings

Provides:
- Document embedding generation
- Similarity search
- Hybrid search (semantic + keyword)
- Caching for performance
"""

import os
import json
import pickle
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from openai import OpenAI
from config import get_settings

from .document_indexer import DocumentChunk, DocumentType

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result with relevance score"""
    chunk: DocumentChunk
    score: float
    match_type: str  # "semantic", "keyword", "hybrid"


class VectorStore:
    """
    Vector store for semantic search over PCB knowledge base
    
    Uses OpenAI text-embedding-3-small for cost-effective embeddings
    Supports hybrid search combining semantic and keyword matching
    """
    
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Initialize vector store
        
        Args:
            cache_dir: Directory for caching embeddings
            use_cache: Whether to use cached embeddings
        """
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        
        self.use_cache = use_cache
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).parent.parent.parent / "cache" / "embeddings"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory index
        self.chunks: List[DocumentChunk] = []
        self.embeddings: Optional[np.ndarray] = None
        
        # Keyword index for hybrid search
        self.keyword_index: Dict[str, List[int]] = {}
        
        logger.info(f"Vector store initialized, cache: {self.cache_dir}")
    
    def index_chunks(
        self,
        chunks: List[DocumentChunk],
        batch_size: int = 100
    ) -> None:
        """
        Index document chunks by generating embeddings
        
        Args:
            chunks: Document chunks to index
            batch_size: Batch size for embedding API calls
        """
        logger.info(f"Indexing {len(chunks)} chunks...")
        
        self.chunks = chunks
        
        # Check cache
        cache_key = self._get_cache_key(chunks)
        cached = self._load_cache(cache_key)
        
        if cached is not None:
            logger.info("Loaded embeddings from cache")
            self.embeddings = cached
            self._build_keyword_index()
            return
        
        # Generate embeddings in batches
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [self._prepare_text_for_embedding(c) for c in batch]
            
            try:
                response = self.client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input=texts
                )
                
                batch_embeddings = [e.embedding for e in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.info(f"Embedded batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Embedding failed for batch {i}: {e}")
                # Fill with zeros for failed batch
                all_embeddings.extend([[0.0] * self.EMBEDDING_DIMENSIONS] * len(batch))
        
        self.embeddings = np.array(all_embeddings)
        
        # Cache embeddings
        self._save_cache(cache_key, self.embeddings)
        
        # Build keyword index
        self._build_keyword_index()
        
        logger.info(f"Indexing complete: {len(self.chunks)} chunks, shape {self.embeddings.shape}")
    
    def _prepare_text_for_embedding(self, chunk: DocumentChunk) -> str:
        """Prepare chunk text for embedding with metadata"""
        parts = []
        
        # Add document context
        if chunk.document_name:
            parts.append(f"Document: {chunk.document_name}")
        
        if chunk.section_title:
            parts.append(f"Section: {chunk.section_title}")
        
        if chunk.topics:
            parts.append(f"Topics: {', '.join(chunk.topics)}")
        
        # Main content
        parts.append(chunk.content)
        
        return "\n".join(parts)
    
    def _build_keyword_index(self) -> None:
        """Build inverted index for keyword search"""
        self.keyword_index = {}
        
        # Key technical terms to index
        key_terms = [
            # Standards
            'ipc-2221', 'ipc-2152', 'iec-62368', 'iec-60601',
            # Topics
            'clearance', 'creepage', 'impedance', 'termination',
            'pull-up', 'decoupling', 'bypass', 'thermal', 'via',
            # Interfaces
            'i2c', 'spi', 'rs-485', 'rs485', 'can', 'usb', 'pcie', 'hdmi',
            # Power
            'buck', 'boost', 'ldo', 'smps', 'regulator', 'capacitor',
            # Components
            'mlcc', 'tantalum', 'electrolytic', 'inductor', 'resistor',
        ]
        
        for idx, chunk in enumerate(self.chunks):
            content_lower = chunk.content.lower()
            
            for term in key_terms:
                if term in content_lower:
                    if term not in self.keyword_index:
                        self.keyword_index[term] = []
                    self.keyword_index[term].append(idx)
            
            # Also index document type
            doc_type = chunk.document_type.value
            if doc_type not in self.keyword_index:
                self.keyword_index[doc_type] = []
            self.keyword_index[doc_type].append(idx)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_topics: Optional[List[str]] = None,
        filter_doc_types: Optional[List[DocumentType]] = None,
        min_score: float = 0.3
    ) -> List[SearchResult]:
        """
        Search for relevant chunks
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_topics: Filter by topic
            filter_doc_types: Filter by document type
            min_score: Minimum similarity score
        
        Returns:
            List of search results
        """
        if self.embeddings is None or len(self.chunks) == 0:
            logger.warning("Vector store is empty")
            return []
        
        # Get query embedding
        try:
            response = self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=query
            )
            query_embedding = np.array(response.data[0].embedding)
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            return []
        
        # Compute cosine similarity
        similarities = self._cosine_similarity(query_embedding, self.embeddings)
        
        # Apply filters
        mask = np.ones(len(self.chunks), dtype=bool)
        
        if filter_topics:
            topic_mask = np.zeros(len(self.chunks), dtype=bool)
            for idx, chunk in enumerate(self.chunks):
                if any(t in chunk.topics for t in filter_topics):
                    topic_mask[idx] = True
            mask &= topic_mask
        
        if filter_doc_types:
            type_mask = np.zeros(len(self.chunks), dtype=bool)
            for idx, chunk in enumerate(self.chunks):
                if chunk.document_type in filter_doc_types:
                    type_mask[idx] = True
            mask &= type_mask
        
        # Apply mask
        similarities = np.where(mask, similarities, -1)
        
        # Get top results
        top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # Get more for filtering
        
        results = []
        for idx in top_indices:
            score = similarities[idx]
            if score < min_score:
                continue
            
            results.append(SearchResult(
                chunk=self.chunks[idx],
                score=float(score),
                match_type="semantic"
            ))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[SearchResult]:
        """
        Hybrid search combining semantic and keyword matching
        
        Args:
            query: Search query
            top_k: Number of results
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
        
        Returns:
            List of search results
        """
        # Semantic search
        semantic_results = self.search(query, top_k=top_k * 2)
        
        # Keyword search
        keyword_results = self._keyword_search(query, top_k=top_k * 2)
        
        # Combine results
        combined_scores: Dict[str, Tuple[float, DocumentChunk]] = {}
        
        for result in semantic_results:
            chunk_id = result.chunk.chunk_id
            combined_scores[chunk_id] = (
                result.score * semantic_weight,
                result.chunk
            )
        
        for result in keyword_results:
            chunk_id = result.chunk.chunk_id
            if chunk_id in combined_scores:
                combined_scores[chunk_id] = (
                    combined_scores[chunk_id][0] + result.score * keyword_weight,
                    result.chunk
                )
            else:
                combined_scores[chunk_id] = (
                    result.score * keyword_weight,
                    result.chunk
                )
        
        # Sort by combined score
        sorted_results = sorted(
            combined_scores.items(),
            key=lambda x: x[1][0],
            reverse=True
        )
        
        return [
            SearchResult(
                chunk=chunk,
                score=score,
                match_type="hybrid"
            )
            for _, (score, chunk) in sorted_results[:top_k]
        ]
    
    def _keyword_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Simple keyword-based search"""
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        # Find chunks matching query terms
        matching_chunks: Dict[int, int] = {}  # chunk_idx -> match_count
        
        for term in query_terms:
            # Check exact term
            if term in self.keyword_index:
                for idx in self.keyword_index[term]:
                    matching_chunks[idx] = matching_chunks.get(idx, 0) + 1
            
            # Check partial matches
            for indexed_term, indices in self.keyword_index.items():
                if term in indexed_term or indexed_term in term:
                    for idx in indices:
                        matching_chunks[idx] = matching_chunks.get(idx, 0) + 0.5
        
        # Sort by match count
        sorted_matches = sorted(
            matching_chunks.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for idx, count in sorted_matches[:top_k]:
            score = min(count / len(query_terms), 1.0)
            results.append(SearchResult(
                chunk=self.chunks[idx],
                score=score,
                match_type="keyword"
            ))
        
        return results
    
    def _cosine_similarity(
        self,
        query: np.ndarray,
        embeddings: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between query and all embeddings"""
        # Normalize
        query_norm = query / (np.linalg.norm(query) + 1e-8)
        embeddings_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
        
        # Dot product
        return np.dot(embeddings_norm, query_norm)
    
    def _get_cache_key(self, chunks: List[DocumentChunk]) -> str:
        """Generate cache key from chunks"""
        content_hash = hashlib.md5()
        for chunk in chunks[:100]:  # Sample for performance
            content_hash.update(chunk.content[:100].encode())
        return f"embeddings_{len(chunks)}_{content_hash.hexdigest()[:8]}"
    
    def _load_cache(self, cache_key: str) -> Optional[np.ndarray]:
        """Load cached embeddings"""
        if not self.use_cache:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.npy"
        if cache_file.exists():
            try:
                return np.load(cache_file)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        return None
    
    def _save_cache(self, cache_key: str, embeddings: np.ndarray) -> None:
        """Save embeddings to cache"""
        if not self.use_cache:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.npy"
        try:
            np.save(cache_file, embeddings)
            logger.info(f"Saved embeddings cache: {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def save_index(self, path: str) -> None:
        """Save full index to disk"""
        data = {
            'chunks': self.chunks,
            'embeddings': self.embeddings,
            'keyword_index': self.keyword_index
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"Saved index to {path}")
    
    def load_index(self, path: str) -> bool:
        """Load index from disk"""
        if not os.path.exists(path):
            return False
        
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            
            self.chunks = data['chunks']
            self.embeddings = data['embeddings']
            self.keyword_index = data['keyword_index']
            
            logger.info(f"Loaded index from {path}: {len(self.chunks)} chunks")
            return True
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False
