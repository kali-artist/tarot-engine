"""synthesizer.py — L4. Two-LLM-call design: classifier (temp 0.1) + reading synthesis (temp 0.7).

Fail-with-no-llm: when LLM_API_KEY is empty, reading() returns the assembled context wrapped in
{"mode": "no-llm", "assembled": {...}} so the deterministic chain is fully testable without a key.
"""
from __future__ import annotations

import json
import os
from typing import Any

try:
    import jinja2
    _HAS_JINJA = True
except ImportError:
    _HAS_JINJA = False


CLASSIFY_PROMPT = """Classify this tarot question into exactly ONE of these categories:

- love (relationships, romance, partnership, dating, marriage, breakups)
- career (work, profession, business, job, promotion)
- spiritual (growth, purpose, meaning, path, meditation)
- financial (money, resources, wealth, investments, debt)
- health (physical, mental, wellness, healing, energy)
- general (none of the above, or multiple equally)

Question: "{question}"

Respond with ONLY the category name. One word."""


class LLMProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("LLM_API_KEY", "").strip()
        self._base_url = (base_url or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self._model = model or os.environ.get("LLM_MODEL") or "gpt-4o-mini"

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def complete(self, prompt: str, temperature: float, max_tokens: int) -> str:
        if not self.available:
            raise RuntimeError("LLM_API_KEY not set")
        import urllib.request
        body = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"]).strip()


class Synthesizer:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        traditions: dict[str, Any] | None = None,
        tradition: str = "intuitive",
    ) -> None:
        from .loader import load_traditions
        self._provider = provider or LLMProvider()
        self._traditions = traditions if traditions is not None else load_traditions()
        if tradition not in self._traditions:
            raise KeyError(f"unknown tradition {tradition!r}; available: {sorted(self._traditions)}")
        self._tradition = self._traditions[tradition]

    # ------------------------------------------------------- call 1: classifier
    def classify(self, question: str) -> str:
        if not self._provider.available:
            return "general"
        raw = self._provider.complete(
            CLASSIFY_PROMPT.format(question=question.strip()),
            temperature=0.1,
            max_tokens=20,
        )
        word = raw.lower().strip().strip('.,')
        known = {"love", "career", "spiritual", "financial", "health", "general"}
        return word if word in known else "general"

    # ------------------------------------------------------- call 2: synthesis
    def reading(self, assembled: Any, resonance_marks: list[Any] | None = None,
                signature: Any = None) -> dict[str, Any]:
        """Return either mode=llm (rendered prompt -> provider -> text) or mode=no-llm payload."""
        if not self._provider.available:
            return {
                "mode": "no-llm",
                "assembled": _serialize(assembled),
                "resonance": [m.__dict__ for m in (resonance_marks or [])],
                "signature": signature.__dict__ if signature else None,
                "note": "LLM_API_KEY 空置: 已返回确定性占卜数据; 接入LLM后此数据直接作为Prompt上下文",
            }

        system = str(self._tradition.get("system") or "")
        user = self._render_user(assembled, resonance_marks or [], signature)
        text = self._provider.complete(f"{system}\n\n---\n\n{user}", temperature=0.7, max_tokens=1600)
        return {"mode": "llm", "tradition": self._tradition.get("name", self._tradition), "reading": text}

    def _render_user(self, assembled: Any, marks: list[Any], signature: Any = None) -> str:
        sys_template = str(self._tradition.get("user") or "")
        if not _HAS_JINJA:
            # graceful degradation: hand-render minimal facts without jinja
            cards_txt = "\n".join(
                f"### {c.position_name}: {c.card_name} ({c.orientation})\n"
                f"essence: {c.core_essence}\nposition interp: {c.position_interpretation}\nshadow: {c.shadow}"
                for c in assembled.card_interpretations
            )
            return f"## Reading Context\nQuestion: {assembled.question or ''}\n\n## Cards\n{cards_txt}"

        template = jinja2.Template(sys_template)
        cards_payload = []
        mark_by_id = {m.card_id: m for m in marks if hasattr(m, "card_id")}
        for ci in assembled.card_interpretations:
            c = ci.__dict__.copy()
            if ci.card_id in mark_by_id:
                m = mark_by_id[ci.card_id]
                c["resonance_mark"] = m.level
                c["resonance_score"] = m.score
                c["resonance_reasons"] = m.reasons
            else:
                c["resonance_mark"] = None
                c["resonance_score"] = None
                c["resonance_reasons"] = None
            cards_payload.append(c)

        rel_payload = [
            {
                "type": r.relationship_type,
                "card1": r.card1_name,
                "card2": r.card2_name,
                "interpretation": r.interpretation,
                "keywords": r.keywords,
            }
            for r in assembled.relationships
        ]
        # tolerate empty relationships in template: provide list always (Jinja else-branch)
        stats_payload = assembled.statistics.__dict__.copy()

        sig_payload = None
        if signature is not None:
            sig_payload = signature.__dict__

        return template.render(
            spread_name=assembled.spread_name,
            question=assembled.question,
            question_type=assembled.question_type,
            cards=cards_payload,
            relationships=rel_payload,
            statistics=stats_payload,
            resonance_context=sig_payload,
            resonance_marks=[m.__dict__ for m in (marks or []) if hasattr(m, "card_id")],
        )


def _serialize(assembled: Any) -> dict[str, Any]:
    return {
        "spread_name": assembled.spread_name,
        "spread_id": assembled.spread_id,
        "question": assembled.question,
        "question_type": assembled.question_type,
        "cards": [c.__dict__ for c in assembled.card_interpretations],
        "relationships": [r.__dict__ for r in assembled.relationships],
        "statistics": assembled.statistics.__dict__,
    }
