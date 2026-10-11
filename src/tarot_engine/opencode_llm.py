"""opencode_llm.py — Zen-free LLM bridge: wraps `opencode run` as an OpenAI-ish provider.

Why: OpenCode zen free tier only answers inside the OpenCode CLI process (FreeTierError on
any external HTTP call). The only escape hatch is spawning `opencode run` as a subprocess
(skill-documented). This module is that hatch, exposed as a complete()-based provider.

Cost: zero go-quota (model prefixed opencode/*, e.g. mimo-v2.6-flash-free).
Latency: ~5-10s per call (CLI boot overhead) — acceptable for draft readings.
"""
from __future__ import annotations

import re
import tempfile
import subprocess
from pathlib import Path
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_HEADER_RE = re.compile(r"^> build · .*$")

_DEFAULT_MODEL = "opencode/mimo-v2.6-flash-free"


class OpenCodeFreeProvider:
    """Completes prompts by spawning `opencode run` with a zen-free model."""

    def __init__(self, model: str = _DEFAULT_MODEL, arena_dir: Path | None = None) -> None:
        self._model = model
        self._arena = arena_dir or Path(tempfile.mkdtemp(prefix="oc_llm_"))
        self._arena.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        try:
            subprocess.run(["/home/ubuntu/.local/bin/opencode", "--version"],
                           capture_output=True, timeout=20, check=True)
            return True
        except Exception:
            return False

    def complete(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1600) -> str:
        prompt_file = self._arena / "prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        cmd = [
            "/home/ubuntu/.local/bin/opencode", "run",
            "--model", self._model,
            f"Read the file {prompt_file} and follow its instructions exactly. Output only the requested content, no commentary.",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(self._arena))
        raw = proc.stdout or ""
        text = _ANSI_RE.sub("", raw)
        # strip "> build · <model>" banner line
        lines = [ln for ln in text.splitlines() if not _HEADER_RE.match(ln)]
        return "\n".join(lines).strip()
