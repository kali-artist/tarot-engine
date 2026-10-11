"""assembler.py — L3 deterministic assembly. rag-mapping lookup + fallback chain + relationships + statistics. Design §4."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any

from .deck import DeckEngine, DrawnCard, Orientation
from .spread import SpreadDefinition, SpreadRegistry


def _clean_keywords(value: Any) -> list[str]:
    """Guard against dirty-data keywords (string / single token / None)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(k) for k in value if str(k).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]

RELATIONSHIP_TYPES: tuple[str, ...] = (
    "amplifies", "challenges", "clarifies",
    "similar_energy", "opposite_energy", "learning_sequence",
)

_QUESTION_TYPES: tuple[str, ...] = ("love", "career", "spiritual", "financial", "health")


@dataclass
class CardInterpretation:
    card_id: str
    card_name: str
    position_index: int
    position_name: str
    position_description: str
    orientation: str
    position_interpretation: str
    position_keywords: list[str]
    question_context: str | None
    question_keywords: list[str]
    core_essence: str
    core_keywords: list[str]
    archetype: str
    psychological: str
    spiritual: str
    practical: str
    shadow: str
    symbols: dict[str, str]
    affirmations: list[str]
    element: str | None
    zodiac: str | None
    ruler_planet: str | None
    suit: str
    card_number: int


@dataclass
class CardRelationshipMatch:
    card1_id: str
    card1_name: str
    card2_id: str
    card2_name: str
    relationship_type: str
    interpretation: str
    keywords: list[str]


@dataclass
class EnergyStatistics:
    elements_balance: dict[str, int]
    suits_balance: dict[str, int]
    major_ratio: float
    numerology_numbers: list[int]
    majors: list[str]


@dataclass
class AssembledContext:
    spread_name: str
    spread_id: str
    question: str | None
    question_type: str | None
    card_interpretations: list[CardInterpretation]
    relationships: list[CardRelationshipMatch]
    statistics: EnergyStatistics


class Assembler:
    """No LLM here. Raises nothing for missing RAG paths - falls back to core_meanings."""

    def __init__(self, deck: DeckEngine) -> None:
        self._deck = deck

    # ---------------------------------------------------------------- rag lookup
    @staticmethod
    def _resolve_rag(card: dict[str, Any], rag_mapping: str, reversed_: bool) -> dict[str, Any]:
        """Navigate position_interpretations[parts...] then pick orientation dict.
        Fallback chain (design §2 rule 5): rag miss -> core_meanings of same orientation.
        Returns {"interpretation": str, "keywords": [...]}  (empty strings allowed)."""
        position_interps: dict[str, Any] = card.get("position_interpretations") or {}
        node: Any = position_interps
        for part in rag_mapping.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                node = None
                break

        if isinstance(node, dict):
            orient = "reversed" if reversed_ else "upright"
            inner = node.get(orient)
            if isinstance(inner, dict):
                return {
                    "interpretation": str(inner.get("interpretation") or inner.get("essence") or ""),
                    "keywords": _clean_keywords(inner.get("keywords", [])),
                }
            # some cards store text directly
            if isinstance(inner, str):
                return {"interpretation": inner, "keywords": []}

        return Assembler._core_fallback(card, reversed_)

    @staticmethod
    def _core_fallback(card: dict[str, Any], reversed_: bool) -> dict[str, Any]:
        core = (card.get("core_meanings") or {}).get("reversed" if reversed_ else "upright") or {}
        return {
            "interpretation": str(core.get("essence") or ""),
            "keywords": _clean_keywords(core.get("keywords", [])),
        }

    def _question_context(self, card: dict[str, Any], question_type: str | None, reversed_: bool) -> tuple[str | None, list[str]]:
        if not question_type or question_type not in _QUESTION_TYPES:
            return None, []
        qc = card.get("question_contexts") or {}
        branch = qc.get(question_type)
        if not isinstance(branch, dict):
            return None, []
        orient = "reversed" if reversed_ else "upright"
        return str(branch.get(orient) or ""), _clean_keywords(branch.get("keywords", []))

    # ---------------------------------------------------------------- relationships
    def find_relationships(self, drawn_ids: set[str]) -> list[CardRelationshipMatch]:
        """Scan every drawn card's outgoing relationships; dedupe by sorted (pair, type).

        Relationships can be recorded on either side of a pair — we scan all sources and
        dedupe on (min_id, max_id, type) so nothing is silently dropped (review fix #4).
        """
        out: list[CardRelationshipMatch] = []
        seen: set[tuple[str, str, str]] = set()
        # sorted() so output order is deterministic across processes (set iteration
        # order varies with hash randomization) — same seed must yield same payload order.
        for a_id in sorted(drawn_ids):
            card = self._deck.get_card(a_id)
            rels = card.get("card_relationships") or {}
            for rel_type in RELATIONSHIP_TYPES:
                targets = rels.get(rel_type)
                if not isinstance(targets, dict):
                    continue
                for other_id, rel_data in targets.items():
                    if other_id not in drawn_ids or other_id == a_id:
                        continue
                    if not isinstance(rel_data, dict):
                        continue
                    interp = str(rel_data.get("interpretation") or "").strip()
                    if not interp or interp.startswith("[TO BE WRITTEN"):
                        continue
                    lo, hi = sorted([a_id, other_id])
                    key = (lo, hi, rel_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(CardRelationshipMatch(
                        card1_id=lo,
                        card1_name=self._deck.get_card(lo)["card_name"],
                        card2_id=hi,
                        card2_name=self._deck.get_card(hi)["card_name"],
                        relationship_type=rel_type,
                        interpretation=interp,
                        keywords=_clean_keywords(rel_data.get("keywords", [])),
                    ))
        return out

    # ---------------------------------------------------------------- statistics
    @staticmethod
    def compute_statistics(cards: list[dict[str, Any]]) -> EnergyStatistics:
        elements: collections.Counter[str] = collections.Counter()
        suits: collections.Counter[str] = collections.Counter()
        numbers: list[int] = []
        majors: list[str] = []
        for c in cards:
            e = c.get("elemental_correspondences") or {}
            if e.get("element"):
                elements[str(e["element"])] += 1
            s = c.get("suit") or ""
            suits[s if s != "major_arcana" else "major"] += 1
            n = int(c.get("card_number") or 0)
            numbers.append(n)
            if s == "major_arcana":
                majors.append(c["card_name"])
        return EnergyStatistics(
            elements_balance=dict(elements),
            suits_balance=dict(suits),
            major_ratio=len(majors) / len(cards) if cards else 0.0,
            numerology_numbers=numbers,
            majors=majors,
        )

    # ---------------------------------------------------------------- main entry
    def assemble(
        self,
        drawn: list[DrawnCard],
        spread: SpreadDefinition,
        question: str | None = None,
        question_type: str | None = None,
    ) -> AssembledContext:
        if len(drawn) != spread.position_count:
            raise ValueError(
                f"drew {len(drawn)} cards but spread {spread.id!r} has {spread.position_count} positions"
            )

        card_interps: list[CardInterpretation] = []
        raw_cards: list[dict[str, Any]] = []

        for drawn_card, position in zip(drawn, spread.positions):
            card = self._deck.get_card(drawn_card.card_id)
            reversed_ = drawn_card.orientation == Orientation.REVERSED
            interp = self._resolve_rag(card, position.rag_mapping, reversed_)
            qctx, qkw = self._question_context(card, question_type, reversed_)
            core = (card.get("core_meanings") or {}).get("reversed" if reversed_ else "upright") or {}
            ecal = card.get("elemental_correspondences") or {}

            ci = CardInterpretation(
                card_id=card["card_id"],
                card_name=card["card_name"],
                position_index=drawn_card.position_index,
                position_name=position.name,
                position_description=position.detailed_description or position.short_description,
                orientation=drawn_card.orientation.value,
                position_interpretation=interp["interpretation"],
                position_keywords=interp["keywords"],
                question_context=qctx,
                question_keywords=qkw,
                core_essence=str(core.get("essence") or ""),
                core_keywords=_clean_keywords(core.get("keywords", [])),
                archetype=str(card.get("archetype") or ""),
                psychological=str(core.get("psychological") or ""),
                spiritual=str(core.get("spiritual") or ""),
                practical=str(core.get("practical") or ""),
                shadow=str(core.get("shadow") or ""),
                symbols={str(k): str(v) for k, v in (card.get("symbols") or {}).items()},
                affirmations=[str(a) for a in (card.get("affirmations") or []) if isinstance(a, (str,))],
                element=(ecal.get("element") and str(ecal["element"])) or None,
                zodiac=(ecal.get("zodiac") and str(ecal["zodiac"])) or None,
                ruler_planet=(ecal.get("ruler_planet") and str(ecal["ruler_planet"])) or None,
                suit=str(card.get("suit") or ""),
                card_number=int(card.get("card_number") or 0),
            )
            card_interps.append(ci)
            raw_cards.append(card)

        relationships = self.find_relationships({d.card_id for d in drawn})
        stats = self.compute_statistics(raw_cards)

        return AssembledContext(
            spread_name=spread.name,
            spread_id=spread.id,
            question=question,
            question_type=question_type,
            card_interpretations=card_interps,
            relationships=relationships,
            statistics=stats,
        )
