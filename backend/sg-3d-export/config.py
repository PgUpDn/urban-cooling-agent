"""
Configuration settings for SG 3D Export Backend
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings"""
    
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", os.getenv("API_KEY", ""))
    
    # File paths
    BASE_DIR: Path = Path(__file__).parent.parent
    STL_FILE_PATH: Path = BASE_DIR / "sg-building-binary.stl"
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS settings
    # Allow all origins in development, or specify production domains via CORS_ORIGINS env var
    _cors_origins_env = os.getenv("CORS_ORIGINS")
    if _cors_origins_env:
        CORS_ORIGINS: list = [origin.strip() for origin in _cors_origins_env.split(",")]
    else:
        # Default: allow localhost and all Vercel preview domains
        CORS_ORIGINS: list = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "https://*.vercel.app",  # All Vercel preview domains
            "*"  # Allow all for development and production
        ]


settings = Settings()
