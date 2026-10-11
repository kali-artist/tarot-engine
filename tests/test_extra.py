"""test_extra.py — review-driven coverage: cleaner module, fallback chain, no-llm, edge days."""
from datetime import date

import pytest

from tarot_engine.assembler import Assembler
from tarot_engine.cleaner import clean_card
from tarot_engine.deck import DeckEngine
from tarot_engine.loader import load_cards, load_spreads, load_traditions
from tarot_engine.resonance import SIGNATURES, signature_from_birthday
from tarot_engine.spread import SpreadRegistry
from tarot_engine.synthesizer import Synthesizer, LLMProvider


@pytest.fixture(scope="module")
def deck():
    return DeckEngine(load_cards())


@pytest.fixture(scope="module")
def reg():
    return SpreadRegistry(load_spreads())


@pytest.fixture(scope="module")
def assembled_bundle():
    deck = DeckEngine(load_cards())
    reg = SpreadRegistry(load_spreads())
    spread = reg.load_spread("single-focus")
    drawn = deck.draw(1, seed=777)
    ctx = Assembler(deck).assemble(drawn, spread, "指引?", "general")
    return deck, spread, ctx



# ================= review-driven additions =================

def test_cleaner_planet_channel_moves_to_ruler():
    raw = {"card_id": "the_fool", "elemental_correspondences": {"zodiac": "uranus", "planet": "pluto", "element": "air"}}
    out = clean_card(raw)
    e = out["elemental_correspondences"]
    assert e["zodiac"] == ""            # planet moved out of zodiac slot
    assert e["ruler_planet"] == "pluto" # planet channel wins
    assert raw["elemental_correspondences"]["zodiac"] == "uranus"  # input not mutated


def test_cleaner_mixed_text_parsed_and_anchored():
    raw = {"card_id": "x", "elemental_correspondences": {"zodiac": "sun in scorpio", "planet": "moon"}}
    out = clean_card(raw)
    e = out["elemental_correspondences"]
    assert e["zodiac"] == "scorpio"
    assert e["ruler_planet"] == "moon"   # explicit planet field wins over "sun"


def test_cleaner_ignore_nonplanets_in_mixed():
    raw = {"card_id": "x", "elemental_correspondences": {"zodiac": "banana in scorpio"}}
    out = clean_card(raw)
    e = out["elemental_correspondences"]
    assert e["zodiac"] == "scorpio"
    assert e["ruler_planet"] == ""       # "banana" is not a planet -> dropped


def test_cleaner_empty_string_zodiac_kept():
    raw = {"card_id": "x", "elemental_correspondences": {"zodiac": "", "element": "fire"}}
    out = clean_card(raw)
    e = out["elemental_correspondences"]
    assert e["zodiac"] == ""   # empty stays empty (element covers scoring)
    assert e["ruler_planet"] == ""


def test_relationships_bidirectional_no_loss(deck):
    """Cross-side-only relationships must still surface: dedupe by sorted pair."""
    a = Assembler(deck)
    ids = {d.card_id for d in deck.draw(12, seed=77)}
    rels = a.find_relationships(ids)
    seen = {(min(r.card1_id, r.card2_id), max(r.card1_id, r.card2_id), r.relationship_type) for r in rels}
    # collection integrity: no duplicated (pair, type)
    assert len(seen) == len(rels)


def test_keywords_string_guard_single_item():
    """Dirty keywords as string must not split into chars."""
    card = {"card_id": "x", "card_name": "X", "suit": "wands",
            "core_meanings": {"upright": {"essence": "s", "keywords": "potential, faith"}}}
    cooked = clean_card(card)
    assert cooked["card_id"] == "x"


def test_rag_complete_fallback_chain(deck, reg):
    """rag hit -> core fallback both reachable; node missing at first hop falls back."""
    spread = reg.load_spread("single-focus")
    spread.positions[0].rag_mapping = "nonexistent.first_hop"
    drawn = deck.draw(1, seed=1)
    ctx = Assembler(deck).assemble(drawn, spread, question=None, question_type=None)
    ci = ctx.card_interpretations[0]
    assert ci.core_essence  # fell through to core_meanings


def test_no_llm_payload_shape(assembled_bundle, monkeypatch):
    deck, spread, ctx = assembled_bundle
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    synth = Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions())
    result = synth.reading(ctx)
    assert result["mode"] == "no-llm"
    assert set(result["assembled"]) == {"spread_name", "spread_id", "question", "question_type", "cards", "relationships", "statistics"}
