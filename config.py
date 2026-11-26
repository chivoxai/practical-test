"""Application settings, read from environment variables (or a local .env file).

No secrets live in code. Copy .env.example to .env and fill in your own keys.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # ---- LLM ---------------------------------------------------------------
    # Provider order: the first one with a key is used; the next is the fallback.
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "anthropic"))
    llm_fallback_provider: str = field(default_factory=lambda: os.getenv("LLM_FALLBACK_PROVIDER", "gemini"))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    llm_timeout_s: float = field(default_factory=lambda: _float("LLM_TIMEOUT_S", 20.0))
    # Use the LLM for a single batched relevance pass over borderline candidates.
    llm_relevance_enabled: bool = field(default_factory=lambda: _bool("LLM_RELEVANCE_ENABLED", True))

    # ---- Search / platform APIs ---------------------------------------------
    search_backend: str = field(default_factory=lambda: os.getenv("SEARCH_BACKEND", "serper"))  # serper | brave
    serper_api_key: str = field(default_factory=lambda: os.getenv("SERPER_API_KEY", ""))
    brave_api_key: str = field(default_factory=lambda: os.getenv("BRAVE_API_KEY", ""))
    youtube_api_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    results_per_query: int = field(default_factory=lambda: _int("RESULTS_PER_QUERY", 10))
    queries_per_platform: int = field(default_factory=lambda: _int("QUERIES_PER_PLATFORM", 2))

    # ---- Website enrichment (public contact pages of discovered websites) ---
    enrich_websites: bool = field(default_factory=lambda: _bool("ENRICH_WEBSITES", True))
    max_sites_to_enrich: int = field(default_factory=lambda: _int("MAX_SITES_TO_ENRICH", 8))
    user_agent: str = field(
        default_factory=lambda: os.getenv(
            "USER_AGENT", "ProspectDiscoveryBot/1.0 (+https://github.com/your-username/ai-prospect-discovery)"
        )
    )

    # ---- Timeouts, concurrency, caching -------------------------------------
    http_timeout_s: float = field(default_factory=lambda: _float("HTTP_TIMEOUT_S", 10.0))
    platform_timeout_s: float = field(default_factory=lambda: _float("PLATFORM_TIMEOUT_S", 25.0))
    max_concurrent_requests: int = field(default_factory=lambda: _int("MAX_CONCURRENT_REQUESTS", 6))
    cache_ttl_s: int = field(default_factory=lambda: _int("CACHE_TTL_S", 6 * 3600))

    # ---- Output -------------------------------------------------------------
    max_prospects: int = field(default_factory=lambda: _int("MAX_PROSPECTS", 25))
    include_possible_matches: bool = field(default_factory=lambda: _bool("INCLUDE_POSSIBLE_MATCHES", False))

    # ---- Inbound rate limit (per client IP) ---------------------------------
    rate_limit_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_PER_MINUTE", 10))

    port: int = field(default_factory=lambda: _int("PORT", 4000))


settings = Settings()
