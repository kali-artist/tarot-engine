"""test_deck.py — L1 TDD: seed reproducibility, orientation dice, bounds."""
import pytest

from tarot_engine.deck import DeckEngine, Orientation
from tarot_engine.loader import load_cards


@pytest.fixture(scope="module")
def deck():
    return DeckEngine(load_cards())


def test_deck_loads_78(deck):
    assert len(deck) == 78


def test_draw_count(deck):
    drawn = deck.draw(5, seed=42)
    assert len(drawn) == 5
    assert all(isinstance(d.card_id, str) for d in drawn)


def test_seed_reproducibility_full_sequence_and_orientation(deck):
    """Same seed -> same card ids AND same orientations, position order included."""
    a = deck.draw(10, seed=1234)
    b = deck.draw(10, seed=1234)
    assert [(d.card_id, d.orientation) for d in a] == [(d.card_id, d.orientation) for d in b]


def test_different_seeds_diverge(deck):
    a = deck.draw(10, seed=1)
    b = deck.draw(10, seed=2)
    assert [(d.card_id, d.orientation) for d in a] != [(d.card_id, d.orientation) for d in b]


def test_position_index_sequential(deck):
    drawn = deck.draw(3, seed=7)
    assert [d.position_index for d in drawn] == [0, 1, 2]


def test_reversals_toggle(deck):
    no_rev = deck.draw(20, seed=99, allow_reversals=False)
    assert all(d.orientation == Orientation.UPRIGHT for d in no_rev)
    with_rev = deck.draw(78, seed=99, allow_reversals=True)
    assert any(d.orientation == Orientation.REVERSED for d in with_rev)


def test_overdraw_raises(deck):
    with pytest.raises(ValueError):
        deck.draw(79, seed=1)


def test_unknown_card_id_raises(deck):
    with pytest.raises(KeyError):
        deck.get_card("nonexistent-card")


def test_big_draw_no_duplicates(deck):
    drawn = deck.draw(78, seed=888)
    ids = [d.card_id for d in drawn]
    assert len(set(ids)) == 78, "physical shuffle must not repeat a card within one draw"
