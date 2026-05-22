"""
Provider info endpoint — lets the frontend know which providers/models are available.
"""
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(prefix="/providers", tags=["providers"])

PROVIDER_CATALOG = {
    "groq": {
        "name": "Groq",
        "description": "Ultra-fast inference — free tier available",
        "free": True,
        "models": [
            {"id": "llama-3.1-8b-instant", "name": "LLaMA 3.1 8B Instant", "context": 131072},
            {"id": "llama-3.3-70b-versatile", "name": "LLaMA 3.3 70B Versatile", "context": 131072},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "context": 32768},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B", "context": 8192},
        ],
    },
    "ollama": {
        "name": "Ollama (Local)",
        "description": "Fully local open-source models — no API key needed",
        "free": True,
        "models": [
            {"id": "llama3", "name": "LLaMA 3 8B (local)", "context": 8192},
            {"id": "mistral", "name": "Mistral 7B (local)", "context": 8192},
            {"id": "phi3", "name": "Phi-3 Mini (local)", "context": 4096},
            {"id": "gemma2", "name": "Gemma 2 9B (local)", "context": 8192},
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Access to many models — free tier available",
        "free": True,
        "models": [
            {"id": "mistralai/mistral-7b-instruct:free", "name": "Mistral 7B (free)", "context": 32768},
            {"id": "meta-llama/llama-3-8b-instruct:free", "name": "LLaMA 3 8B (free)", "context": 8192},
            {"id": "google/gemma-7b-it:free", "name": "Gemma 7B (free)", "context": 8192},
        ],
    },
    "openai": {
        "name": "OpenAI",
        "description": "GPT models — requires API key",
        "free": False,
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context": 128000},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context": 16385},
        ],
    },
}


@router.get("")
async def list_providers():
    return PROVIDER_CATALOG


@router.get("/default")
async def get_default():
    return {
        "provider": settings.DEFAULT_PROVIDER,
        "model": settings.DEFAULT_MODEL,
    }
