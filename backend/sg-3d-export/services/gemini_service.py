"""
Gemini AI Service for Urban Planning Insights
"""
import google.generativeai as genai
from config import settings


# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)


async def get_urban_insight(district_name: str) -> str:
    """
    Get urban planning insight for a specific Singapore district using Gemini AI.
    
    Args:
        district_name: Name of the Singapore district
        
    Returns:
        A brief architectural and urban planning context
    """
    if not settings.GEMINI_API_KEY:
        return "AI insights unavailable. Please configure GEMINI_API_KEY."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""Provide a very brief (2 sentence) architectural and urban planning context 
        for the {district_name} area of Singapore. Mention common building types or historical significance."""
        
        response = await model.generate_content_async(prompt)
        
        if response.text:
            return response.text.strip()
        return "Unable to generate insight at this time."
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return f"Error generating insight: {str(e)}"


async def get_building_analysis(district_name: str, building_count: int) -> str:
    """
    Get detailed building analysis for export preparation.
    
    Args:
        district_name: Name of the Singapore district
        building_count: Number of buildings in selection
        
    Returns:
        Analysis text for the selected buildings
    """
    if not settings.GEMINI_API_KEY:
        return "AI analysis unavailable."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""For a 3D model export of {building_count} buildings in {district_name}, Singapore:
        Provide a one-sentence summary of what architectural styles and building heights to expect."""
        
        response = await model.generate_content_async(prompt)
        
        if response.text:
            return response.text.strip()
        return "Analysis unavailable."
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Error generating analysis."
