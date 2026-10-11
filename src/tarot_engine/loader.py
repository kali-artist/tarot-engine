"""loader.py: load the 78-card deck, spread registry, and tradition prompts.

- Every card passes through cleaner.clean_card at load time (design §1.2).
- Image handling: data/images/{system}/{card_id}.{fmt} if present, else None.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cleaner import clean_card

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def data_dir() -> Path:
    return _DATA_DIR


def load_cards(cards_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load all card JSON files, cleaned. Sorted by (card_number, card_id) for stable order."""
    d = cards_dir or (_DATA_DIR / "cards")
    out: list[dict[str, Any]] = []
    for path in sorted(d.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        card = clean_card(raw)
        card["_image_filename"] = path.stem  # e.g. "m00", "w01"
        out.append(card)
    if len(out) != 78:
        raise ValueError(f"expected 78 cards, loaded {len(out)} from {d}")
    ids = [c.get("card_id") for c in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate card_id in deck: {sorted(dupes)}")
    out.sort(key=lambda c: (int(c.get("card_number") or 0), c.get("card_id") or ""))
    return out


def load_spreads(path: Path | None = None) -> dict[str, Any]:
    p = path or (_DATA_DIR / "tarot-spreads.json")
    return json.loads(p.read_text(encoding="utf-8"))


def load_traditions(prompts_dir: Path | None = None) -> dict[str, Any]:
    """Load all tradition prompt YAML files as {stem: parsed_dict (system/user/...)}."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML required for tradition prompts") from exc
    d = prompts_dir or (_DATA_DIR / "prompts")
    out: dict[str, str] = {}
    for path in sorted(d.glob("*.yaml")):
        out[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return out
