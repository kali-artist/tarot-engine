"""deck.py — L1 DeckEngine. seed-shuffle plus independent reversed-dice. Zero LLM. Design §2."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .loader import load_cards


class Orientation(str, Enum):
    UPRIGHT = "upright"
    REVERSED = "reversed"


@dataclass
class DrawnCard:
    card_id: str
    card_name: str
    position_index: int
    position_name: str  # filled by SpreadRegistry/Assembler when laid into a spread
    orientation: Orientation
    image_path: str | None = None


class DeckEngine:
    """Seeded deck. Same seed -> same card sequence AND same orientations (auditable)."""

    def __init__(self, cards: list[dict[str, Any]] | None = None, images_base: Path | None = None) -> None:
        self._cards: list[dict[str, Any]] = cards if cards is not None else load_cards()
        self._by_id: dict[str, dict[str, Any]] = {c["card_id"]: c for c in self._cards}
        self._images_base = images_base

    def __len__(self) -> int:
        return len(self._cards)

    def get_card(self, card_id: str) -> dict[str, Any]:
        try:
            return self._by_id[card_id]
        except KeyError:
            raise KeyError(f"unknown card_id {card_id!r}; known: {len(self._by_id)}") from None

    def draw(self, count: int, seed: int | None = None, allow_reversals: bool = True) -> list[DrawnCard]:
        if count > len(self._cards):
            raise ValueError(f"cannot draw {count} from a {len(self._cards)}-card deck")
        if count < 0:
            raise ValueError("count must be >= 0")

        rng = random.Random(seed)
        shuffled = list(self._cards)
        # Fisher-Yates via rng.shuffle; note: not GSR riffle (design keeps single-stripe with
        # documented simplification; hermeticai GSR upgrade is a drop-in later per design).
        rng.shuffle(shuffled)

        drawn: list[DrawnCard] = []
        for i, card in enumerate(shuffled[:count]):
            orientation = (
                Orientation.REVERSED if rng.random() < 0.5 else Orientation.UPRIGHT
            ) if allow_reversals else Orientation.UPRIGHT
            drawn.append(DrawnCard(
                card_id=card["card_id"],
                card_name=card["card_name"],
                position_index=i,
                position_name="",
                orientation=orientation,
                image_path=self._image_path(card),
            ))
        return drawn

    def _image_path(self, card: dict[str, Any]) -> str | None:
        if not self._images_base:
            return None
        candidate = self._images_base / f"{card['_image_filename']}.jpg"
        return str(candidate) if candidate.is_file() else None
