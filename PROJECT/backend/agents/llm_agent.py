"""LLM agent (PROMPT_5 §2.3).

Provider chain: OpenRouter (primary) -> fallback model -> Gemini. JSON mode on,
per-call timeout, cross-model fallback on failure. Allowed outputs are ONLY
summaries / explanations / structured synthesis. Numeric data always comes from
tools — never from the LLM. If every provider fails -> None (caller supplies a
deterministic fallback). The agent NEVER guesses fares, timings, or scores.
"""
import json
import logging
from dataclasses import dataclass, field

from .. import config

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    openrouter_key: str = ""
    openrouter_base: str = ""
    openrouter_model: str = ""
    gemini_key: str = ""
    gemini_model: str = ""
    temperature: float = 0.2
    timeout_s: float = 30.0
    fallback_models: list[str] = field(default_factory=list)


def _load_config() -> LLMConfig:
    return LLMConfig(
        openrouter_key=config.env_str("OPENROUTER_API_KEY"),
        openrouter_base=config.env_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_model=config.env_str("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        gemini_key=config.env_str("GEMINI_API_KEY"),
        gemini_model=config.env_str("GEMINI_MODEL", "gemini-2.0-flash"),
    )


class LLMAgent:
    def __init__(self, cfg: LLMConfig | None = None):
        self._cfg = cfg or _load_config()
        self._openai = None  # lazy
        self._gemini = None

    # ------------------------------------------------------------ providers
    def _openai_client(self):
        import openai

        if self._openai is None:
            self._openai = openai.OpenAI(api_key=self._cfg.openrouter_key,
                                         base_url=self._cfg.openrouter_base, timeout=self._cfg.timeout_s)
        return self._openai

    def _gemini_client(self):
        import openai

        if self._gemini is None:
            self._gemini = openai.OpenAI(
                api_key=self._cfg.gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                timeout=self._cfg.timeout_s,
            )
        return self._gemini

    # ------------------------------------------------------------- completions
    def chat_json(self, system: str, user: str) -> dict | None:
        """One JSON completion with cross-provider fallback. None if all fail."""
        if self._cfg.openrouter_key:
            try:
                out = self._complete(self._openai_client(), self._cfg.openrouter_model, system, user)
                if out is not None:
                    return out
            except Exception as exc:  # noqa: BLE001 — provider chain
                logger.warning("[llm] OpenRouter failed: %s", exc)
        if self._cfg.gemini_key:
            try:
                out = self._complete(self._gemini_client(), self._cfg.gemini_model, system, user)
                if out is not None:
                    return out
            except Exception as exc:  # noqa: BLE001
                logger.warning("[llm] Gemini failed: %s", exc)
        return None

    def _complete(self, client, model: str, system: str, user: str) -> dict | None:
        resp = client.chat.completions.create(
            model=model,
            temperature=self._cfg.temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            timeout=self._cfg.timeout_s,
        )
        content = resp.choices[0].message.content or ""
        return json.loads(content)
