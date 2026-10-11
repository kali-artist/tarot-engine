"""test_synthesizer.py — L4 TDD: no-llm mode, classifier fallback, jinja rendering."""
import pytest
from datetime import date

from tarot_engine.assembler import Assembler
from tarot_engine.deck import DeckEngine
from tarot_engine.loader import load_cards, load_spreads, load_traditions
from tarot_engine.spread import SpreadRegistry
from tarot_engine.synthesizer import Synthesizer, LLMProvider


@pytest.fixture(scope="module")
def assembled_bundle():
    deck = DeckEngine(load_cards())
    reg = SpreadRegistry(load_spreads())
    spread = reg.load_spread("single-focus")
    drawn = deck.draw(1, seed=777)
    ctx = Assembler(deck).assemble(drawn, spread, "今日指引?", "general")
    return deck, spread, ctx


def test_no_llm_key_returns_deterministic_payload(assembled_bundle, monkeypatch):
    deck, spread, ctx = assembled_bundle
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    synth = Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions())
    result = synth.reading(ctx)
    assert result["mode"] == "no-llm"
    assert result["assembled"]["cards"]
    assert result["assembled"]["statistics"]


def test_classify_no_llm_defaults_general(assembled_bundle, monkeypatch):
    deck, spread, ctx = assembled_bundle
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    synth = Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions())
    assert synth.classify("任何问题") == "general"


def test_unknown_tradition_raises():
    with pytest.raises(KeyError, match="available"):
        Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions(), tradition="nope")


def test_traditions_load_nonempty():
    tr = load_traditions()
    assert {"intuitive", "kate-signature"} <= set(tr)
    for name, doc in tr.items():
        assert doc.get("system"), f"{name}.yaml missing system prompt"
        assert doc.get("user"), f"{name}.yaml missing user template"
        assert "{% for card in cards %}" in doc["user"], f"{name}.yaml must render cards list"


def test_jinja_render_contains_cards(assembled_bundle, monkeypatch):
    deck, spread, ctx = assembled_bundle
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    synth = Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions())
    rendered = synth._render_user(ctx, [])
    assert spread.name in rendered
    assert ctx.card_interpretations[0].card_name in rendered


def test_resonance_marks_rendered_into_prompt(assembled_bundle, monkeypatch):
    from tarot_engine.resonance import evaluate, signature_from_birthday
    deck, spread, ctx = assembled_bundle
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    synth = Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions())
    sig = signature_from_birthday(date(1990, 4, 15)) if False else None
    # build exactly one mark for the single drawn card
    card = deck.get_card(ctx.card_interpretations[0].card_id)
    from tarot_engine.deck import Orientation
    from tarot_engine.resonance import ResonanceMark, evaluate_card
    mark = evaluate_card(card, Orientation.UPRIGHT, signature_from_birthday(date(1990, 4, 15)))
    sig = signature_from_birthday(date(1990, 4, 15))
    synth_r = Synthesizer(provider=LLMProvider(api_key=""), traditions=load_traditions(), tradition="resonance-b")
    rendered = synth_r._render_user(ctx, [mark], sig)
    low = rendered.lower()
    assert ("resonance" in low) and any(k in rendered for k in ("HOT","WARM","COLD")), "resonance-b must render marks"
