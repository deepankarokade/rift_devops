"""
OpenRouter AI Client

Client for interacting with OpenRouter AI API for AI-powered code analysis and fix generation.
OpenRouter provides free access to many LLM models.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default model - using free models
DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct"


def get_openrouter_api_key() -> Optional[str]:
    """Retrieve the OpenRouter API key from environment variables.

    Returns None if not configured so callers can fall back to a mock response.
    """
    return os.environ.get("OPENROUTER_API_KEY")


def call_ai(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Call the OpenRouter API with a system prompt and user prompt.
    
    Args:
        system_prompt: The system instructions that define the AI's role and behavior.
        user_prompt: The user's input/query.
        model: The OpenRouter model to use (default: meta-llama/llama-3.1-8b-instruct).
    
    Returns:
        The model's response as a string.
    
    Raises:
        ValueError: If the API key is not configured.
        Exception: If the API call fails.
    """
    try:
        import requests
        
        api_key = get_openrouter_api_key()

        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set — returning mock response")
            return f"Mock response to: {user_prompt[:100]}..."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/deepankarokade/autonomous-cicd-pipeline-healer",
            "X-Title": "CI/CD Pipeline Healer"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1024
        }
        
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        response.raise_for_status()
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        logger.info("OpenRouter AI API call successful")
        return content
        
    except ImportError:
        logger.warning("requests library not available, returning mock response")
        return f"Mock response to: {user_prompt[:100]}..."
    except Exception as exc:
        logger.error("OpenRouter AI API call failed: %s", exc)
        raise


# Backward compatibility - keep groq functions as aliases
def get_groq_api_key():
    """Backward compatibility - now uses OpenRouter"""
    return get_openrouter_api_key()


def call_groq(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Backward compatibility - now calls OpenRouter API
    """
    return call_ai(system_prompt, user_prompt, model)
