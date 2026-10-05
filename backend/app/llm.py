"""Groq chat model factory."""

from langchain_groq import ChatGroq

from app.config import get_settings


def get_llm(role, max_tokens, effort=None):
    """Return a ChatGroq model for the "router" or "answer" role.

    The model name and reasoning effort come from .env, so a retired
    model can be swapped without a code change. gpt-oss models are
    reasoning models and their thinking tokens count toward max_tokens,
    so callers must leave headroom. Pass effort to override the
    configured reasoning effort for one call.
    """
    settings = get_settings()
    if role == "router":
        model = settings.router_model
        effort = effort or settings.router_reasoning_effort
    else:
        model = settings.llm_model
        effort = effort or settings.llm_reasoning_effort
    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        reasoning_effort=effort,
        max_tokens=max_tokens,
        temperature=0,
    )
