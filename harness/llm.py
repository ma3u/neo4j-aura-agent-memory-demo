"""
Chat generator for the Haystack side (agents and the LLM judge).

  AZURE_OPENAI_ENDPOINT set -> Azure OpenAI (AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION)
  otherwise                 -> OpenAI (OPENAI_API_KEY, OPENAI_MODEL)
"""
import os

from dotenv import load_dotenv
from haystack.components.generators.chat import AzureOpenAIChatGenerator, OpenAIChatGenerator

load_dotenv()


def chat_generator(**kwargs):
    """kwargs pass through (e.g. generation_kwargs, max_retries)."""
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        return AzureOpenAIChatGenerator(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            **kwargs,
        )
    return OpenAIChatGenerator(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"), **kwargs)
