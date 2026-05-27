import os
import json
import re
import logging
from core.llm_engine import _call_llm_silent, _stream_request

logger = logging.getLogger("jellyfish.base_orchestrator")

def _parse_plan_safe(text: str) -> list[dict]:
    """Robust multi-format JSON parser for orchestration plans."""
    md_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    candidate = md_match.group(1).strip() if md_match else text.strip()

    for attempt in [candidate, text.strip()]:
        try:
            data = json.loads(attempt)
            if isinstance(data, list):
                return [s for s in data if isinstance(s, dict) and "query" in s]
            if isinstance(data, dict):
                for key in ("steps", "plan", "queries", "tasks", "searches"):
                    if key in data and isinstance(data[key], list):
                        return [s for s in data[key] if isinstance(s, dict) and "query" in s]
        except (json.JSONDecodeError, ValueError):
            pass

    array_match = re.search(r"\[[\s\S]*?\]", candidate)
    if array_match:
        try:
            data = json.loads(array_match.group(0))
            if isinstance(data, list):
                return [s for s in data if isinstance(s, dict) and "query" in s]
        except (json.JSONDecodeError, ValueError):
            pass

    logger.debug("Could not parse orchestration plan. Text: %.200s", text)
    return []

class BaseOrchestrator:
    """Base orchestrator class containing shared utility methods for LLM interactions and parsing."""
    
    def __init__(self, state):
        self.state = state

    def _generate_silent(self, system_prompt: str, user_prompt: str, provider=None, model=None) -> str:
        """Call the LLM silently without streaming output to the TUI."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        prov = provider or self.state.subagent_provider
        mod = model or self.state.subagent_model
        response = _call_llm_silent(self.state, messages, provider=prov, model=mod)
        return response if response else ""

    def _generate_visible(self, system_prompt: str, user_prompt: str, label: str) -> str:
        """Call the LLM with streaming output visible on the TUI."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = _stream_request(self.state, messages, label)
        return response if response else ""

    def _parse_plan_safe(self, text: str) -> list[dict]:
        return _parse_plan_safe(text)
