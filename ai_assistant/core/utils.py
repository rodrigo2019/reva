"""
Utility functions for the REVA AI Assistant — model initialization and memory management.

Based on the ai_engine architecture, adapted for the REVA fitness platform.
Uses ChatOpenAI with the Responses API (output_version="responses/v1").
"""

import logging
from typing import Any
from urllib.parse import urljoin

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("ai_assistant")

# Global in-memory saver instance (used for dev/SQLite environments)
_memory = MemorySaver()

# Reasoning models require temperature of 1.0
REASONING_MODELS = {"o3", "o4-mini"}

# Models where reasoning effort should be low
LOW_REASONING_MODELS = {"gpt-5", "gpt-5-mini", "gpt-5-nano"}

# Models that don't support output_version="responses/v1"
NO_RESPONSES_OUTPUT_MODELS = {"gpt-35-turbo", "model-router"}


def get_memory_saver() -> MemorySaver:
    """Get the global in-memory saver instance for conversation checkpointing.

    Returns:
        The global MemorySaver instance.
    """
    return _memory


def default_temperature(model_name: str) -> float:
    """Return the default temperature for a given model.

    Args:
        model_name: The model identifier.

    Returns:
        1.0 for reasoning models, 0.5 for others.
    """
    if model_name in REASONING_MODELS:
        return 1.0
    return 0.5


def _prepare_openai_model_options(model_name: str) -> tuple[str, dict[str, Any]]:
    """Return adjusted model name and extra kwargs for OpenAI deployments.

    Handles reasoning model configuration and Responses API output version.

    Args:
        model_name: The model identifier.

    Returns:
        Tuple of (normalized_model_name, extra_kwargs).
    """
    kwargs: dict[str, Any] = {}

    # Enable Responses API unless model doesn't support it
    if model_name not in NO_RESPONSES_OUTPUT_MODELS:
        kwargs["output_version"] = "responses/v1"

    if model_name in REASONING_MODELS:
        kwargs["reasoning"] = {"effort": "high", "summary": "detailed"}
        return model_name, kwargs

    if model_name in LOW_REASONING_MODELS:
        kwargs["reasoning"] = {"effort": "low", "summary": "detailed"}
        return model_name, kwargs

    return model_name, kwargs


def initialize_model(
    provider: str,
    api_key: str,
    model_name: str,
    base_url: str | None = None,
    temperature: float = 0.5,
):
    """Initialize the appropriate LangChain chat model based on the provider.

    Uses ChatOpenAI with the Responses API for the OpenAI provider
    (same pattern as ai_engine). No API version date is required — uses
    ``api-version: preview`` automatically.

    Args:
        provider: The provider type ("openai", "anthropic", "deepseek", "google").
        api_key: API key for the service.
        model_name: Model identifier used by the provider.
        base_url: Base URL for the API endpoint.
        temperature: Temperature setting (0.0 to 1.0).

    Returns:
        Initialized LangChain chat model instance.

    Raises:
        ValueError: If required parameters are missing or provider is unsupported.
    """
    if not api_key or not model_name:
        raise ValueError("Both 'api_key' and 'model_name' are required.")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            base_url=urljoin(base_url, "anthropic/") if base_url else None,
            api_key=api_key,
            temperature=temperature,
            max_tokens=64_000,
        )

    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=model_name,
            api_key=api_key,
            api_base=urljoin(base_url, "openai/v1") if base_url else None,
            temperature=temperature,
            stream_usage=True,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=None,
            timeout=None,
            max_retries=2,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not base_url:
            raise ValueError("Base URL is required for OpenAI models.")

        normalized_model, extra_kwargs = _prepare_openai_model_options(model_name)

        # Reasoning models must use temperature=1.0
        if model_name in REASONING_MODELS:
            temperature = 1.0

        return ChatOpenAI(
            base_url=urljoin(base_url, "openai/v1"),
            api_key=api_key,
            default_query={"api-version": "preview"},
            model=normalized_model,
            stream_usage=True,
            temperature=temperature,
            **extra_kwargs,
        )

    raise ValueError(f"Unsupported provider: {provider}")


def extract_content_and_reasoning(content) -> tuple[str, str]:
    """Extract both text content and reasoning from different content formats.

    Args:
        content: Content that can be a string, list of items, or dict.

    Returns:
        Tuple of (text_content, reasoning).
    """
    if isinstance(content, str):
        return content, ""

    if isinstance(content, list):
        text = ""
        reasoning = ""
        for item in content:
            if isinstance(item, dict):
                if "summary" in item and len(item["summary"]) > 0:
                    reasoning += item["summary"][0].get("text", "")
                else:
                    text += item.get("text", "")
            elif isinstance(item, str):
                text += item
        return text, reasoning

    if isinstance(content, dict):
        if "summary" in content and len(content["summary"]) > 0:
            return "", content["summary"][0].get("text", "")
        return content.get("text", ""), ""

    return str(content) if content else "", ""
