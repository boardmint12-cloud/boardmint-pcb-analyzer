from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from supabase_client import get_supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class QuoteRequest(BaseModel):
    companyName: str
    fullName: str
    email: EmailStr
    phone: Optional[str] = None
    projectType: str
    boardComplexity: str
    timeline: str
    message: Optional[str] = None

@router.post("/api/quotes")
async def create_quote_request(quote: QuoteRequest):
    """
    Handle quote request submission.
    Saves to Supabase database for tracking and follow-up.
    """
    try:
        logger.info(f"📧 Quote request received from {quote.companyName} ({quote.email})")
        
        # Get Supabase client (uses service role key for full access)
        supabase = get_supabase()
        
        # Prepare data for database
        quote_data = {
            "company_name": quote.companyName,
            "full_name": quote.fullName,
            "email": quote.email,
            "phone": quote.phone,
            "project_type": quote.projectType,
            "board_complexity": quote.boardComplexity,
            "timeline": quote.timeline,
            "message": quote.message,
            "status": "new",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Save to Supabase
        result = supabase.table('quotes').insert(quote_data).execute()
        
        if result.data and len(result.data) > 0:
            quote_id = result.data[0].get('id')
            logger.info(f"✅ Quote saved to Supabase with ID: {quote_id}")
            logger.info(f"📊 Quote details: {quote.companyName} | {quote.projectType} | {quote.boardComplexity}")
        else:
            logger.warning("⚠️ Quote saved but no ID returned")
        
        # TODO: Send email notification
        # await send_email(
        #     to="pranavchahal@boardmint.io",
        #     subject=f"New Quote Request from {quote.companyName}",
        #     body=format_quote_email(quote_data)
        # )
        
        return {
            "success": True,
            "message": "Quote request received successfully",
            "quote_id": result.data[0].get('id') if result.data else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing quote request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process quote request: {str(e)}")
