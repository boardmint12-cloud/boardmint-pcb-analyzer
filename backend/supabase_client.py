"""
Supabase Client Configuration
Handles connection to Supabase for auth, database, and storage
"""
import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client"""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance"""
        if cls._instance is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")
            
            if not url or not key:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
                )
            
            cls._instance = create_client(url, key)
            logger.info("✓ Supabase client initialized")
        
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset client instance (for testing)"""
        cls._instance = None


# Convenience function
def get_supabase() -> Client:
    """Get Supabase client instance"""
    return SupabaseClient.get_client()
