"""LLM provider configuration. All providers speak the OpenAI chat-completions API."""

from dataclasses import dataclass

from openai import OpenAI

from cs_agent.config import Settings

TIMEOUT_SECONDS = 30
MAX_RETRIES = 2


class ConfigError(Exception):
    """The environment cannot produce a working LLM client. The message says how to fix it."""


@dataclass(frozen=True)
class Provider:
    base_url: str | None  # None: the SDK default (OpenAI) or Settings.ollama_base_url
    key_setting: str | None  # Settings field holding the API key; None: no key needed
    default_model: str
    missing_key_help: str


# One place to add or change a provider.
PROVIDERS: dict[str, Provider] = {
    "gemini": Provider(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_setting="gemini_api_key",
        default_model="gemini-2.5-flash",
        missing_key_help=(
            "Set GEMINI_API_KEY in .env (free key at aistudio.google.com). "
            "To run locally instead, install Ollama and set LLM_PROVIDER=ollama."
        ),
    ),
    "ollama": Provider(
        base_url=None,
        key_setting=None,
        default_model="qwen2.5:7b",
        missing_key_help="",
    ),
    "openai": Provider(
        base_url=None,
        key_setting="openai_api_key",
        default_model="gpt-4o-mini",
        missing_key_help="Set OPENAI_API_KEY in .env.",
    ),
}


@dataclass(frozen=True)
class LLM:
    client: OpenAI
    model: str
    provider: str


def create_llm(settings: Settings) -> LLM:
    """Build the client for `settings.llm_provider`; LLM_MODEL overrides the default model."""
    name = settings.llm_provider
    provider = PROVIDERS.get(name)
    if provider is None:
        raise ConfigError(
            f"Unknown LLM_PROVIDER {name!r}. Options: {', '.join(sorted(PROVIDERS))}."
        )

    if provider.key_setting is None:
        api_key = "ollama"  # Ollama ignores the key, the SDK requires one
    else:
        api_key = getattr(settings, provider.key_setting)
        if not api_key:
            raise ConfigError(f"LLM_PROVIDER={name} needs an API key. {provider.missing_key_help}")

    base_url = settings.ollama_base_url if name == "ollama" else provider.base_url
    client = OpenAI(
        api_key=api_key, base_url=base_url, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES
    )
    return LLM(client, settings.llm_model or provider.default_model, name)
