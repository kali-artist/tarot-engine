"""main.py — FastAPI host for the 申派塔罗 single-page site. Wraps the five-layer tarot_engine.

Endpoints:
    GET  /               -> static/index.html
    GET  /api/spreads    -> 6 launch spreads (中文释义)
    POST /api/reading    -> full deterministic chain + MMX synthesis
    GET  /api/health     -> {"status": "ok"}

Engine is imported from ../src/tarot_engine via a sys.path shim; engine source is never modified.
Runtime temp files are pinned inside backend/.tmp so nothing lands in /tmp.
"""
from __future__ import annotations

import os
import sys
import zlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# keep every runtime temp artifact inside the project (MMXProvider writes a payload file)
_TMP_DIR = _BACKEND_DIR / ".tmp"
_TMP_DIR.mkdir(exist_ok=True)
os.environ.setdefault("TMPDIR", str(_TMP_DIR))

_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from tarot_engine.assembler import Assembler  # noqa: E402
from tarot_engine.deck import DeckEngine  # noqa: E402
from tarot_engine.loader import load_cards, load_spreads, load_traditions  # noqa: E402
from tarot_engine.mmx_llm import MMXProvider  # noqa: E402
from tarot_engine.resonance import ResonanceLayer, signature_from_birthday  # noqa: E402
from tarot_engine.spread import SpreadRegistry  # noqa: E402
from tarot_engine.synthesizer import Synthesizer  # noqa: E402

# --------------------------------------------------------------- launch spreads
LAUNCH_IDS: tuple[str, ...] = (
    "single-focus",
    "past-present-future",
    "mind-body-spirit",
    "celtic-cross",
    "four-card-decision",
    "relationship-spread",
)

LAUNCH_CN: dict[str, dict[str, str]] = {
    "single-focus": {
        "name": "单牌指引 · 今日能量",
        "description": "一张牌，回答你此刻最需要看见的那股能量。",
    },
    "past-present-future": {
        "name": "时间流 · 过去/现在/未来",
        "description": "经典三牌，看清事件的来路、当下与去向。",
    },
    "mind-body-spirit": {
        "name": "三牌阵 · 身/心/灵",
        "description": "从身、心、灵三个层面，照见你的整体状态。",
    },
    "celtic-cross": {
        "name": "凯尔特十字 · 十位全面阵",
        "description": "十张牌的全面洞察，深入一个议题的各个维度。",
    },
    "four-card-decision": {
        "name": "是非抉择阵 · 二元快手",
        "description": "四个位置，帮你在两条路之间看清取舍。",
    },
    "relationship-spread": {
        "name": "爱情阵 · 关系能量场",
        "description": "六张牌，拆解你与对方之间的能量流动。",
    },
}


class ReadingRequest(BaseModel):
    question: str = Field(default="", description="占卜问题")
    spread_id: str = Field(default="single-focus")
    birthday: str | None = Field(default=None, description="可选 YYYY-MM-DD，用于本命共振")
    allow_reversals: bool = True
    nonce: int | str | None = Field(default=None, description="改变种子以“再抽一次”")


def stable_seed(fingerprint: str, question: str, nonce: Any = None) -> int:
    """16-bit reproducible seed. Deterministic substitute for CPython's process-random hash()."""
    material = f"{fingerprint}|{question}|{nonce if nonce is not None else ''}".encode("utf-8")
    return zlib.crc32(material) & 0xFFFF


def _parse_birthday(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


_CARDS_STATIC_DIR = Path(__file__).parent / "static" / "cards"
_CARD_ID_TO_STEM: dict[str, str] = {}
_CARD_NAME_ZH: dict[str, str] = {}
_ORIENT_ZH = {"upright": "正位", "reversed": "逆位"}
_ELEM_ZH = {"fire": "火", "earth": "土", "air": "风", "water": "水"}


def _build_image_map(cards: list[dict[str, Any]] | None = None) -> None:
    """card_id -> arcanite image stem (m00/c07/p03/s14/w09...), from loader's _image_filename.

    Pass the already-loaded cards (from the app's DeckEngine) to avoid re-reading
    78 JSON files; falls back to a fresh load_cards() when called standalone.
    """
    if _CARD_ID_TO_STEM:
        return
    try:
        if cards is None:
            cards = load_cards()
        for c in cards:
            stem = c.get("_image_filename")
            if stem:
                _CARD_ID_TO_STEM[c["card_id"]] = stem
    except Exception:
        pass


def _load_names_zh() -> None:
    """78张中文牌名 (data/card_names_zh.json)."""
    if _CARD_NAME_ZH:
        return
    try:
        import json as _json
        p = Path(__file__).resolve().parent.parent / "data" / "card_names_zh.json"
        _CARD_NAME_ZH.update(_json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        pass


def _card_image_exists(card_id: str) -> str | None:
    """Return /cards/{stem}.jpg when the 78-image asset exists, else None."""
    _build_image_map()
    _load_names_zh()
    stem = _CARD_ID_TO_STEM.get(card_id)
    if stem and (_CARDS_STATIC_DIR / f"{stem}.jpg").is_file():
        return f"/cards/{stem}.jpg"
    return None


def _fallback_reading(assembled: Any, signature: Any) -> str:
    """Deterministic Chinese reading used when the LLM is unavailable/failed."""
    lines = [f"## {assembled.spread_name}", ""]
    if assembled.question:
        lines += [f"> 你的问题：{assembled.question}", ""]
    for ci in assembled.card_interpretations:
        lines.append(f"### {ci.position_name} · {ci.card_name}（{ci.orientation}）")
        lines.append(ci.position_interpretation or ci.core_essence or ci.position_description)
        lines.append("")
    lines.append("> 当前为演示模式（未接入语言模型），内容由确定性牌义引擎生成。")
    return "\n".join(lines)


def create_app(provider: Any | None = None, cards_dir: Path | None = None) -> FastAPI:
    cards = load_cards(cards_dir) if cards_dir else load_cards()
    deck = DeckEngine(cards)
    _build_image_map(cards)
    _load_names_zh()
    registry = SpreadRegistry(load_spreads())
    traditions = load_traditions()
    llm = provider if provider is not None else MMXProvider()
    synthesizer = Synthesizer(provider=llm, traditions=traditions, tradition="shen-mystic")

    app = FastAPI(title="申派塔罗", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:8600",
                       "http://127.0.0.1:8600"],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = _BACKEND_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.mount("/cards", StaticFiles(directory=str(static_dir / "cards")), name="cards")

    @app.get("/styles.css")
    def _styles_css() -> FileResponse:
        return FileResponse(static_dir / "styles.css", media_type="text/css")

    @app.get("/app.js")
    def _app_js() -> FileResponse:
        return FileResponse(static_dir / "app.js", media_type="application/javascript")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((static_dir / "index.html").read_text(encoding="utf-8"))

    @app.get("/api/spreads")
    def spreads() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for sid in LAUNCH_IDS:
            try:
                sp = registry.load_spread(sid)
            except KeyError:
                continue
            meta = LAUNCH_CN.get(sid, {})
            out.append({
                "id": sid,
                "name": meta.get("name", sp.name),
                "description": meta.get("description", sp.description),
                "position_count": sp.position_count,
                "difficulty": sp.difficulty,
                "category": sp.category,
            })
        return out

    @app.post("/api/reading")
    def reading(req: ReadingRequest) -> dict[str, Any]:
        try:
            spread = registry.load_spread(req.spread_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

        birthday = _parse_birthday(req.birthday)
        fingerprint = birthday.isoformat() if birthday else "anon"
        seed = stable_seed(fingerprint, req.question.strip(), req.nonce)

        drawn = deck.draw(spread.position_count, seed=seed, allow_reversals=req.allow_reversals)

        question_type = synthesizer.classify(req.question or "")
        assembled = Assembler(deck).assemble(
            drawn, spread, question=req.question or None, question_type=question_type
        )

        signature = signature_from_birthday(birthday) if birthday else None
        marks = ResonanceLayer(signature).for_reading(deck, drawn)
        mark_by_id = {m.card_id: m for m in marks}

        try:
            synth = synthesizer.reading(assembled, marks, signature)
        except Exception as exc:  # MMX quota / network / CLI failure -> graceful fallback
            synth = {"mode": "error", "error": str(exc)[:300]}

        if synth.get("mode") == "llm" and synth.get("reading"):
            reading_text = str(synth["reading"])
        else:
            reading_text = _fallback_reading(assembled, signature)

        cards_payload: list[dict[str, Any]] = []
        for ci in assembled.card_interpretations:
            mark = mark_by_id.get(ci.card_id)
            keywords = ci.position_keywords or ci.core_keywords
            cards_payload.append({
                "position_name": ci.position_name,
                "position_description": ci.position_description,
                "card_name": ci.card_name,
                "card_id": ci.card_id,
                "orientation": ci.orientation,
                "image_url": _card_image_exists(ci.card_id),
                "card_name_zh": _CARD_NAME_ZH.get(ci.card_id, ci.card_name),
                "orientation_zh": _ORIENT_ZH.get(ci.orientation, ci.orientation),
                "position_interpretation": ci.position_interpretation or ci.core_essence,
                "keywords": keywords,
                "element": ci.element,
                "resonance": (
                    {"level": mark.level, "score": mark.score, "reasons": mark.reasons}
                    if mark else None
                ),
            })

        relationships_payload = [
            {
                "relationship_type": r.relationship_type,
                "card1_name": r.card1_name,
                "card2_name": r.card2_name,
                "card1_zh": _CARD_NAME_ZH.get(r.card1_id, r.card1_name),
                "card2_zh": _CARD_NAME_ZH.get(r.card2_id, r.card2_name),
                "interpretation": r.interpretation,
                "keywords": r.keywords,
            }
            for r in assembled.relationships
        ]

        return {
            "cards": cards_payload,
            "relationships": relationships_payload,
            "statistics": {
                "elements_balance": assembled.statistics.elements_balance,
                "suits_balance": assembled.statistics.suits_balance,
                "major_ratio": assembled.statistics.major_ratio,
                "numerology_numbers": assembled.statistics.numerology_numbers,
                "majors": assembled.statistics.majors,
            },
            "reading": reading_text,
            "signature": (
                {
                    "element": signature.element,
                    "planet": signature.planet,
                    "resonant_suits": list(signature.resonant_suits),
                    "shadow_element": signature.shadow_element,
                    "sign": signature.sign,
                }
                if signature else None
            ),
            "question_type": question_type,
            "seed": seed,
            "mode": synth.get("mode"),
        }

    return app


app = create_app()
