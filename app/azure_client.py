"""
Azure AI Foundry client — placeholder for LLM completion calls.
Fill in AZURE_ENDPOINT, AZURE_API_KEY, and AZURE_MODEL in your .env when ready.
"""
import requests
try:
    from app.config import AZURE_ENDPOINT, AZURE_API_KEY, AZURE_MODEL
except ImportError:
    from config import AZURE_ENDPOINT, AZURE_API_KEY, AZURE_MODEL


def call_azure_complete(prompt: str, model: str = None,
                        endpoint: str = None, api_key: str = None) -> str:
    """Call Azure AI Foundry chat completion endpoint.

    Args:
        prompt: The full prompt text to send.
        model: Model deployment name (defaults to config).
        endpoint: Azure endpoint URL (defaults to config).
        api_key: API key (defaults to config).

    Returns:
        The LLM response text.
    """
    endpoint = endpoint or AZURE_ENDPOINT
    api_key = api_key or AZURE_API_KEY
    model = model or AZURE_MODEL

    if not endpoint or not api_key:
        raise ValueError(
            "Azure AI Foundry is not configured. "
            "Set AZURE_ENDPOINT and AZURE_API_KEY in your .env file."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    response = requests.post(
        f"{endpoint.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
