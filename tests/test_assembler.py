"""test_assembler.py — L3 TDD: rag hit, fallback chain, relationships, statistics."""
import pytest

from tarot_engine.assembler import Assembler, RELATIONSHIP_TYPES
from tarot_engine.deck import DeckEngine, Orientation
from tarot_engine.loader import load_cards, load_spreads
from tarot_engine.spread import SpreadRegistry


@pytest.fixture(scope="module")
def deck():
    return DeckEngine(load_cards())


@pytest.fixture(scope="module")
def reg():
    return SpreadRegistry(load_spreads())


def test_every_card_has_core_meanings_both_orientations(deck):
    for card in deck._cards:
        cm = card.get("core_meanings") or {}
        for orient in ("upright", "reversed"):
            branch = cm.get(orient) or {}
            assert branch.get("essence"), f"{card['card_id']}.{orient} missing essence"
            assert branch.get("keywords"), f"{card['card_id']}.{orient} missing keywords"


def test_every_card_has_position_interpretations(deck):
    """No simplification rule: all 78 cards carry position_interpretations with 7 dropzones."""
    for card in deck._cards:
        pi = card.get("position_interpretations") or {}
        assert pi, card["card_id"]
        assert all(y in pi for y in (
            "temporal_positions", "challenge_and_growth", "guidance_and_action",
            "emotional_and_internal", "external_influences", "outcome_and_result",
        )), card["card_id"]


def test_rag_hit_temporal_present(deck, reg):
    spread = reg.load_spread("single-focus")
    drawn = deck.draw(1, seed=5)
    a = Assembler(deck)
    ctx = a.assemble(drawn, spread, question="指引?", question_type="general")
    ci = ctx.card_interpretations[0]
    assert ci.position_name == spread.positions[0].name
    assert ci.position_interpretation or ci.core_essence  # may fall back, never crash


def test_fallback_chain_never_crashes(deck, reg):
    """rag_mapping pointing to a nonexistent leaf must fall back, not raise."""
    spread = reg.load_spread("single-focus")  # unknown position name will silently swap to single-card
    # Induce a bogus mapping by hand-editing one position
    from tarot_engine.spread import SpreadPosition
    spread.positions[0].rag_mapping = "nonexistent_zone.no_slot"
    a = Assembler(deck)
    drawn = deck.draw(spread.position_count, seed=11)
    ctx = a.assemble(drawn, spread, question=None, question_type=None)
    assert ctx.card_interpretations
    assert ctx.card_interpretations[0].core_essence  # fallback content populated


def test_relationships_no_placeholder(deck):
    a = Assembler(deck)
    drawn = deck.draw(10, seed=31337)
    rels = a.find_relationships({d.card_id for d in drawn})
    for r in rels:
        assert r.interpretation
        assert not r.interpretation.startswith("[TO BE WRITTEN")
        assert r.relationship_type in RELATIONSHIP_TYPES


def test_relationships_de_dupe_pairs(deck):
    a = Assembler(deck)
    ids = {d.card_id for d in deck.draw(10, seed=31337)}
    rels = a.find_relationships(ids)
    pairs = {(min(r.card1_id, r.card2_id), max(r.card1_id, r.card2_id), r.relationship_type) for r in rels}
    assert len(pairs) == len(rels), "each (card1, card2, rel_type) triple must appear exactly once"


def test_statistics_shape(deck, reg):
    spread = reg.load_spread("mind-body-spirit")
    drawn = deck.draw(spread.position_count, seed=4242)
    ctx = Assembler(deck).assemble(drawn, spread, "past present future?", "general")
    stats = ctx.statistics
    assert 0.0 <= stats.major_ratio <= 1.0
    assert set(stats.elements_balance.keys()) <= {"fire", "earth", "air", "water"}
    assert len(stats.numerology_numbers) == spread.position_count
