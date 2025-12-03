"""
Cache Service
Provides caching for analysis results to avoid recomputation
Supports both Redis (production) and in-memory (dev) backends
"""
import json
import hashlib
import logging
from typing import Optional, Any
from functools import lru_cache
from datetime import datetime
from config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Caching service with fallback from Redis to in-memory
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.use_redis = False
        
        # Try to initialize Redis if enabled
        if self.settings.enable_caching:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=False  # We'll handle encoding
                )
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logger.info("✅ Cache: Using Redis backend")
            except (ImportError, Exception) as e:
                logger.warning(f"Redis unavailable, falling back to in-memory cache: {e}")
                self.use_redis = False
        else:
            logger.info("Caching disabled in config")
    
    def compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA256 hash of a file
        
        Args:
            file_path: Path to file
        
        Returns:
            Hex digest of file hash
        """
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return ""
    
    def get_cache_key(self, project_id: str, file_hash: str, profile: str = "auto") -> str:
        """
        Generate cache key
        
        Format: analysis:{project_id}:{file_hash}:{profile}
        """
        return f"analysis:{project_id}:{file_hash}:{profile}"
    
    def get(self, cache_key: str) -> Optional[dict]:
        """
        Get cached analysis result
        
        Args:
            cache_key: Cache key
        
        Returns:
            Cached data as dict, or None if not found
        """
        if not self.settings.enable_caching:
            return None
        
        try:
            if self.use_redis and self.redis_client:
                # Get from Redis
                data = self.redis_client.get(cache_key)
                if data:
                    logger.info(f"✅ Cache HIT: {cache_key[:50]}...")
                    return json.loads(data.decode('utf-8'))
                else:
                    logger.info(f"❌ Cache MISS: {cache_key[:50]}...")
                    return None
            else:
                # Use in-memory cache
                return self._get_from_memory(cache_key)
                
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None
    
    def set(self, cache_key: str, data: dict, ttl: Optional[int] = None) -> bool:
        """
        Store analysis result in cache
        
        Args:
            cache_key: Cache key
            data: Data to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (default from config)
        
        Returns:
            True if successful
        """
        if not self.settings.enable_caching:
            return False
        
        if ttl is None:
            ttl = self.settings.cache_ttl
        
        try:
            # Add metadata
            cache_data = {
                'data': data,
                'cached_at': datetime.utcnow().isoformat(),
                'ttl': ttl
            }
            
            if self.use_redis and self.redis_client:
                # Store in Redis
                json_data = json.dumps(cache_data)
                self.redis_client.setex(cache_key, ttl, json_data)
                logger.info(f"💾 Cached: {cache_key[:50]}... (TTL: {ttl}s)")
                return True
            else:
                # Store in memory
                return self._set_in_memory(cache_key, cache_data, ttl)
                
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False
    
    def delete(self, cache_key: str) -> bool:
        """
        Delete cached entry
        
        Args:
            cache_key: Cache key
        
        Returns:
            True if deleted
        """
        try:
            if self.use_redis and self.redis_client:
                result = self.redis_client.delete(cache_key)
                return result > 0
            else:
                return self._delete_from_memory(cache_key)
        except Exception as e:
            logger.error(f"Cache delete failed: {e}")
            return False
    
    def clear_project_cache(self, project_id: str) -> int:
        """
        Clear all cache entries for a project
        
        Args:
            project_id: Project ID
        
        Returns:
            Number of entries deleted
        """
        try:
            if self.use_redis and self.redis_client:
                # Find all keys matching pattern
                pattern = f"analysis:{project_id}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    logger.info(f"🗑️ Cleared {deleted} cache entries for project {project_id}")
                    return deleted
                return 0
            else:
                # Clear from memory cache
                return self._clear_memory_pattern(f"analysis:{project_id}:")
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return 0
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics
        
        Returns:
            Dict with cache stats
        """
        stats = {
            'backend': 'redis' if self.use_redis else 'memory',
            'enabled': self.settings.enable_caching,
            'ttl': self.settings.cache_ttl
        }
        
        try:
            if self.use_redis and self.redis_client:
                info = self.redis_client.info()
                stats['redis_keys'] = self.redis_client.dbsize()
                stats['redis_memory'] = info.get('used_memory_human', 'N/A')
            else:
                stats['memory_keys'] = len(self._memory_cache)
        except:
            pass
        
        return stats
    
    # In-memory cache fallback (LRU with max size)
    _memory_cache = {}
    _cache_max_size = 100
    
    @classmethod
    def _get_from_memory(cls, key: str) -> Optional[dict]:
        """Get from in-memory cache"""
        if key in cls._memory_cache:
            entry = cls._memory_cache[key]
            # Check TTL
            cached_at = datetime.fromisoformat(entry['cached_at'])
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age < entry['ttl']:
                logger.info(f"✅ Memory cache HIT: {key[:50]}...")
                return entry['data']
            else:
                # Expired
                del cls._memory_cache[key]
                logger.info(f"⏰ Memory cache EXPIRED: {key[:50]}...")
                return None
        else:
            logger.info(f"❌ Memory cache MISS: {key[:50]}...")
            return None
    
    @classmethod
    def _set_in_memory(cls, key: str, data: dict, ttl: int) -> bool:
        """Store in memory cache"""
        # Implement simple LRU: remove oldest if at capacity
        if len(cls._memory_cache) >= cls._cache_max_size:
            # Remove first (oldest) item
            oldest_key = next(iter(cls._memory_cache))
            del cls._memory_cache[oldest_key]
        
        cls._memory_cache[key] = data
        logger.info(f"💾 Memory cached: {key[:50]}... (TTL: {ttl}s)")
        return True
    
    @classmethod
    def _delete_from_memory(cls, key: str) -> bool:
        """Delete from memory cache"""
        if key in cls._memory_cache:
            del cls._memory_cache[key]
            return True
        return False
    
    @classmethod
    def _clear_memory_pattern(cls, pattern: str) -> int:
        """Clear memory cache entries matching pattern"""
        keys_to_delete = [k for k in cls._memory_cache.keys() if k.startswith(pattern)]
        for key in keys_to_delete:
            del cls._memory_cache[key]
        if keys_to_delete:
            logger.info(f"🗑️ Cleared {len(keys_to_delete)} memory cache entries")
        return len(keys_to_delete)


# Global cache instance
_cache_instance = None


def get_cache() -> CacheService:
    """Get or create global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance
