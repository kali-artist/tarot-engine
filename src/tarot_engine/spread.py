"""spread.py — L2 SpreadRegistry. Loads tarot-spreads.json; positions carry rag_mapping; friendly KeyError. Design §3."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import load_spreads


@dataclass
class SpreadPosition:
    name: str
    short_description: str
    detailed_description: str
    keywords: list[str]
    rag_mapping: str                     # e.g. "temporal_positions.present"
    question_adaptations: dict[str, str] = field(default_factory=dict)


@dataclass
class SpreadDefinition:
    id: str
    name: str
    description: str
    layout_id: str
    card_size: str
    aspect_ratio: float
    category: str
    difficulty: str
    positions: list[SpreadPosition]

    @property
    def position_count(self) -> int:
        return len(self.positions)


class SpreadRegistry:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        raw = data if data is not None else load_spreads()
        layouts: dict[str, Any] = raw.get("layouts", {})
        self._spreads: dict[str, SpreadDefinition] = {}
        for s in raw.get("spreads", []):
            positions = [
                SpreadPosition(
                    name=p["name"],
                    short_description=p.get("short_description", ""),
                    detailed_description=p.get("detailed_description", ""),
                    keywords=list(p.get("keywords", [])),
                    rag_mapping=p.get("rag_mapping", "temporal_positions.present"),
                    question_adaptations=dict(p.get("question_adaptations", {})),
                ) for p in s.get("positions", [])
            ]
            self._spreads[s["id"]] = SpreadDefinition(
                id=s["id"],
                name=s["name"],
                description=s.get("description", ""),
                layout_id=s.get("layout", ""),
                card_size=s.get("cardSize", "medium"),
                aspect_ratio=float(s.get("aspectRatio", 1.0)),
                category=s.get("category", "general"),
                difficulty=s.get("difficulty", "beginner"),
                positions=positions,
            )
        self._layouts = layouts

    def load_spread(self, spread_id: str) -> SpreadDefinition:
        try:
            return self._spreads[spread_id]
        except KeyError:
            available = ", ".join(sorted(self._spreads.keys()))
            raise KeyError(f"spread not found: {spread_id!r}. available: {available}") from None

    def list_spreads(self) -> list[str]:
        return sorted(self._spreads.keys())
