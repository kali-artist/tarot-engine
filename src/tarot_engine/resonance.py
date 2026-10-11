"""resonance.py — L5 Resonance Layer (design B). Signatures, rapport, per-card marks. Never touches L1 rng. Design §5."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .deck import DrawnCard, Orientation

# element -> resonant suit (design §5.3)
_ELEMENT_SUIT: dict[str, str] = {
    "fire": "wands",
    "earth": "pentacles",
    "air": "swords",
    "water": "cups",
}

# element/ruler_planet per sign: extracted from arcanite major-arcana cards (each sign's
# dedicated major card carries the sign's element & planet) — anchored by test_resonance.py
SIGNATURES: dict[str, dict[str, str]] = {
    "aries":      {"element": "fire",  "planet": "mars",    "major_card": "the_emperor"},
    "taurus":     {"element": "earth", "planet": "venus",   "major_card": "the_hierophant"},
    "gemini":     {"element": "air",   "planet": "mercury", "major_card": "the_lovers"},
    "cancer":     {"element": "water", "planet": "moon",    "major_card": "the_chariot"},
    "leo":        {"element": "fire",  "planet": "sun",     "major_card": "the_sun"},
    "virgo":      {"element": "earth", "planet": "mercury", "major_card": "the_hermit"},
    "libra":      {"element": "earth", "planet": "venus",   "major_card": "the_empress"},
    "scorpio":    {"element": "water", "planet": "pluto",   "major_card": "death"},
    "sagittarius": {"element": "water", "planet": "jupiter", "major_card": "temperance"},
    "capricorn":  {"element": "earth", "planet": "saturn",  "major_card": "the_devil"},
    "aquarius":   {"element": "air",   "planet": "uranus",  "major_card": "the_star"},
    "pisces":     {"element": "water", "planet": "neptune", "major_card": "the_moon"},
}

# sun-sign date boundaries (month, day, sign), inclusive start of each sign span
_SIGN_BOUNDS: list[tuple[int, int, str]] = [
    (1, 1, "capricorn"), (1, 20, "aquarius"), (2, 19, "pisces"), (3, 21, "aries"),
    (4, 20, "taurus"), (5, 21, "gemini"), (6, 21, "cancer"), (7, 23, "leo"),
    (8, 23, "virgo"), (9, 23, "libra"), (10, 23, "scorpio"), (11, 22, "sagittarius"),
    (12, 22, "capricorn"),
]


@dataclass
class QuerentSignature:
    element: str
    planet: str
    resonant_suits: tuple[str, ...]
    shadow_element: str
    sign: str


def shadow_element_of(element: str) -> str:
    """Complementary element (fire↔water, air↔earth). Raises ValueError on unknown."""
    if element not in _ELEMENT_SUIT:
        raise ValueError(f"unknown element {element!r}; expected one of {sorted(_ELEMENT_SUIT)}")
    return {"fire": "water", "water": "fire", "air": "earth", "earth": "air"}[element]


def signature_from_birthday(birthday: date) -> QuerentSignature | None:
    """Map a Gregorian birthday to a sun-sign QuerentSignature.

    Sign span runs from its bound date (inclusive) up to the next sign's bound (exclusive);
    Jan 1 falls inside the year-start capricorn span.
    """
    if not isinstance(birthday, date):
        return None
    candidates = [i for i, (bm, bd, _) in enumerate(_SIGN_BOUNDS) if (birthday.month, birthday.day) >= (bm, bd)]
    idx = candidates[-1] if candidates else 0
    sign = _SIGN_BOUNDS[idx][2]
    info = SIGNATURES[sign]
    return QuerentSignature(
        element=info["element"],
        planet=info["planet"],
        resonant_suits=(_ELEMENT_SUIT[info["element"]],),
        shadow_element=shadow_element_of(info["element"]),
        sign=sign,
    )


@dataclass
class ResonanceMark:
    card_id: str
    orientation: str
    score: float
    level: str  # HOT / WARM / COLD
    reasons: list[str]


def rapport_score(question: str | None, centering_done: bool, session_seconds: float) -> float:
    """Design §5.2: 0.4*depth + 0.3*centering + 0.3*duration, clamped to [0,1]. Display-only."""
    depth = min(len((question or "").strip()) / 20.0, 1.0)
    duration = min(max(session_seconds, 0.0) / 60.0, 1.0)
    return round(0.4 * depth + 0.3 * (1.0 if centering_done else 0.0) + 0.3 * duration, 2)


def _level(score: float) -> str:
    """Classify on the same rounded score we expose to users (single source of truth)."""
    if score >= 0.7:
        return "HOT"
    if score >= 0.3:
        return "WARM"
    return "COLD"


def evaluate_card(
    card: dict[str, Any],
    orientation: Orientation,
    sig: QuerentSignature | None,
) -> ResonanceMark | None:
    if sig is None:
        return None
    ecal = card.get("elemental_correspondences") or {}
    element = (ecal.get("element") or "").lower().strip()
    planet = (ecal.get("ruler_planet") or "").lower().strip()

    score = 0.0
    reasons: list[str] = []
    if element and element == sig.element:
        score += 0.4
        reasons.append(f"element match: {element}")
    if planet and planet == sig.planet:
        score += 0.3
        reasons.append(f"ruler planet match: {planet}")
    if card.get("suit") and str(card["suit"]) in sig.resonant_suits:
        score += 0.2
        reasons.append(f"suit resonance: {card['suit']}")
    # Design note (confirmed §5.3): antiphase applies ONLY when there is at least one positive
    # hit — a reversed card with zero native resonance is neutral (0.0), not negative.
    if reasons and orientation == Orientation.REVERSED:
        score -= 0.2
        reasons.append("reversed antiphase (-0.2)")

    score = round(score, 2)
    return ResonanceMark(
        card_id=card["card_id"],
        orientation=orientation.value,
        score=score,
        level=_level(score),
        reasons=reasons,
    )


def evaluate(
    drawn: list[DrawnCard],
    deck: Any,
    sig: QuerentSignature | None,
) -> list[ResonanceMark]:
    marks: list[ResonanceMark] = []
    for d in drawn:
        card = deck.get_card(d.card_id)
        mark = evaluate_card(card, d.orientation, sig)
        if mark is not None:
            marks.append(mark)
    return marks


class ResonanceLayer:
    """Facade: wraps signature generation + per-card evaluation. Never touches L1 rng (design §5.5)."""

    def __init__(self, signature: QuerentSignature | None) -> None:
        self.signature = signature

    def for_reading(self, deck: Any, drawn: list[DrawnCard]) -> list[ResonanceMark]:
        return evaluate(drawn, deck, self.signature)

    def rapport(self, question: str | None, centering_done: bool, session_seconds: float) -> float:
        return rapport_score(question, centering_done, session_seconds)
