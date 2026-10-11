"""mmx_llm.py — MiniMax M3 provider via local mmx CLI (owner-preferred, per user directive).

Replaces OpenCode bridge for L4. mmx text chat --messages-file accepts a JSON array of
{role, content}; --output json gives parseable stdout.

Quota: MiniMax-M3 is MiniMax-M3's own generous weekly pool (not OpenCode go) — free for
draft readings. Model default MiniMax-M3, temperature passed through.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

_MMX = "/home/ubuntu/.local/bin/mmx"
_DEFAULT_MODEL = "MiniMax-M3"


class MMXProvider:
    """complete() adapter over `mmx text chat`; OpenAI-compatible shape for Synthesizer."""

    def __init__(self, model: str = _DEFAULT_MODEL, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key  # mmx reads its own auth; explicit key only overrides

    @property
    def available(self) -> bool:
        try:
            subprocess.run([_MMX, "auth", "status"], capture_output=True, timeout=20, check=True)
            return True
        except Exception:
            return False

    def complete(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1600) -> str:
        messages = [{"role": "user", "content": prompt}]
        payload = tempfile.mktemp(suffix=".json")
        Path(payload).write_text(json.dumps(messages, ensure_ascii=False), encoding="utf-8")
        cmd = [_MMX, "text", "chat",
               "--model", self._model,
               "--max-tokens", str(max_tokens),
               "--temperature", str(temperature),
               "--messages-file", payload,
               "--output", "json", "--quiet"]
        if self._api_key:
            cmd += ["--api-key", self._api_key]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"mmx chat failed rc={proc.returncode}: {proc.stderr[:200]}")
        stdout = proc.stdout.strip()
        try:
            return stdout  # --output json --quiet returns raw content text
        except Exception:
            return stdout
