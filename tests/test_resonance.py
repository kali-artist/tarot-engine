"""test_resonance.py — L5 (scheme B) TDD: signature table, scoring formula, null-safety."""
from datetime import date

import pytest

from tarot_engine.deck import DeckEngine, Orientation
from tarot_engine.loader import load_cards
from tarot_engine.resonance import (
    SIGNATURES, evaluate, evaluate_card,
    rapport_score, signature_from_birthday,
)


@pytest.fixture(scope="module")
def deck():
    return DeckEngine(load_cards())


def test_signature_table_12_signs():
    assert set(SIGNATURES) == {
        "aries", "taurus", "gemini", "cancer", "leo", "virgo",
        "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
    }
    for sign, info in SIGNATURES.items():
        assert info["element"] in {"fire", "earth", "air", "water"}, sign
        assert info["planet"], sign


def test_birthday_mapping_known_boundaries():
    assert signature_from_birthday(date(1990, 4, 15)).sign == "aries"
    assert signature_from_birthday(date(1990, 12, 25)).sign == "capricorn"
    assert signature_from_birthday(date(1990, 1, 1)).sign == "capricorn"
    assert signature_from_birthday(date(1990, 11, 1)).sign == "scorpio"


def test_scoring_element_plus_suit_warm(deck):
    sig = signature_from_birthday(date(1990, 4, 15))  # aries: fire/mars, resonant suit=wands
    card = {"card_id": "x", "suit": "wands",
            "elemental_correspondences": {"element": "fire", "ruler_planet": "venus"}}
    mark = evaluate_card(card, Orientation.UPRIGHT, sig)
    assert mark.score == pytest.approx(0.6)  # element 0.4 + suit 0.2
    assert mark.level == "WARM"
    assert not any("ruler planet match" in r for r in mark.reasons)


def test_scoring_full_stack_hot(deck):
    sig = signature_from_birthday(date(1990, 4, 15))  # fire/mars, resonant suit=wands
    card = {"card_id": "x", "suit": "wands",
            "elemental_correspondences": {"element": "fire", "ruler_planet": "mars"}}
    mark = evaluate_card(card, Orientation.UPRIGHT, sig)
    assert mark.score == pytest.approx(0.4 + 0.3 + 0.2)
    assert mark.level == "HOT"


def test_scoring_reversed_antiphase(deck):
    sig = signature_from_birthday(date(1990, 4, 15))
    card = {"card_id": "x", "suit": "wands",
            "elemental_correspondences": {"element": "fire", "ruler_planet": "mars"}}
    mark = evaluate_card(card, Orientation.REVERSED, sig)
    assert mark.score == pytest.approx(0.4 + 0.3 + 0.2 - 0.2)
    assert mark.level == "HOT"


def test_scoring_cold_no_overlap(deck):
    sig = signature_from_birthday(date(1990, 4, 15))  # fire/mars
    card = {"card_id": "x", "suit": "pentacles",
            "elemental_correspondences": {"element": "earth", "ruler_planet": "venus"}}
    mark = evaluate_card(card, Orientation.UPRIGHT, sig)
    assert mark.score == 0.0
    assert mark.level == "COLD"


def test_null_signature_skips_marks(deck):
    drawn = deck.draw(3, seed=4)
    marks = evaluate(drawn, deck, sig=None)
    assert marks == []


def test_rapport_score_bounds():
    short = rapport_score("hi", centering_done=False, session_seconds=0)
    assert 0.0 <= short <= 1.0
    long_q = rapport_score("这是一个足够长的提问超过20个字符就满分了", centering_done=True, session_seconds=600)
    assert long_q == pytest.approx(1.0)


def test_birthday_boundary_24_edges():
    """24 boundary days covering the year — each sign's first/last valid date."""
    cases = [
        (date(2000, 1, 1), "capricorn"), (date(2000, 1, 19), "capricorn"), (date(2000, 1, 20), "aquarius"), (date(2000, 2, 18), "aquarius"),
        (date(2000, 2, 19), "pisces"), (date(2000, 3, 20), "pisces"), (date(2000, 3, 21), "aries"), (date(2000, 4, 19), "aries"),
        (date(2000, 4, 20), "taurus"), (date(2000, 5, 20), "taurus"), (date(2000, 5, 21), "gemini"), (date(2000, 6, 20), "gemini"),
        (date(2000, 6, 21), "cancer"), (date(2000, 7, 22), "cancer"), (date(2000, 7, 23), "leo"), (date(2000, 8, 22), "leo"),
        (date(2000, 8, 23), "virgo"), (date(2000, 9, 22), "virgo"), (date(2000, 9, 23), "libra"), (date(2000, 10, 22), "libra"),
        (date(2000, 10, 23), "scorpio"), (date(2000, 11, 21), "scorpio"), (date(2000, 11, 22), "sagittarius"), (date(2000, 12, 21), "sagittarius"),
        (date(2000, 12, 22), "capricorn"), (date(2000, 12, 31), "capricorn"),
    ]
    for bd, expected in cases:
        assert signature_from_birthday(bd).sign == expected, f"{bd} -> {expected}"


def test_shadow_element_unknown_raises():
    import pytest
    from tarot_engine.resonance import shadow_element_of
    with pytest.raises(ValueError):
        shadow_element_of("plasma")


def test_signature_truth_from_major_arcana_anchored():
    """SIGNATURES truth: each sign's major anchor card carries the claimed element/planet."""
    from tarot_engine.loader import load_cards
    cards = {c["card_id"]: c for c in load_cards()}
    for sign, info in SIGNATURES.items():
        anchor = cards[info["major_card"]]
        ecal = anchor.get("elemental_correspondences", {})
        assert (ecal.get("element") or "").lower() == info["element"], f"{sign} element mismatch"
        assert (ecal.get("ruler_planet") or "").lower() == info["planet"], f"{sign} planet mismatch"
