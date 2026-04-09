"""
Configuration for Intelligent Building Analysis Agent

Instructions:
  1. Copy this file:  cp config_template.py config.py
  2. Replace the placeholder values below with your actual API keys
  3. Do NOT commit config.py to version control
"""

# OpenAI API Key (required)
OPENAI_API_KEY = "sk-your-openai-api-key-here"

# LangSmith Observability (optional — leave empty strings to disable tracing)
LANGSMITH_API_KEY = ""
LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"
LANGSMITH_PROJECT = "IntelligentBuildingAgent"

# Model Configuration
DEFAULT_MODEL = "gpt-4o"

# Temperature for LLM responses (lower = more deterministic)
TEMPERATURE = 0.1
