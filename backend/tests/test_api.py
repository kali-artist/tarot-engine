"""test_api.py — offline API tests. LLM is stubbed; no MMX / network is touched."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main


class StubProvider:
    """Deterministic offline stand-in for MMXProvider (same complete() shape)."""

    def __init__(self, *, available: bool = True, reading: str | None = None) -> None:
        self._available = available
        self._reading = reading or "## 测试解读\n\n这是离线桩返回的中文解读，用于验证接口形状。"
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return self._available

    def complete(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1600) -> str:
        self.calls.append({"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens})
        if "Classify this tarot question" in prompt:
            low = prompt.lower()
            if any(w in low for w in ("love", "relationship", "感情", "关系", "爱情")):
                return "love"
            if any(w in low for w in ("career", "job", "工作", "事业")):
                return "career"
            return "general"
        return self._reading


@pytest.fixture
def stub() -> StubProvider:
    return StubProvider()


@pytest.fixture
def client(stub: StubProvider) -> TestClient:
    return TestClient(main.create_app(provider=stub))


# ------------------------------------------------------------------ health / index
def test_health_ok(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_served(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "申派塔罗" in r.text
    assert "app.js" in r.text  # root-relative ref now (works on CF Pages + backend routes)


# ------------------------------------------------------------------ spreads
def test_spreads_returns_six_launch_spreads(client: TestClient):
    r = client.get("/api/spreads")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 6
    ids = {s["id"] for s in data}
    assert ids == set(main.LAUNCH_IDS)
    for s in data:
        assert set(s) >= {"id", "name", "description", "position_count", "difficulty", "category"}
        assert s["position_count"] >= 1
        assert any("\u4e00" <= ch <= "\u9fff" for ch in s["name"]), "spread name must carry 中文"


def test_celtic_cross_position_count(client: TestClient):
    data = client.get("/api/spreads").json()
    cc = next(s for s in data if s["id"] == "celtic-cross")
    assert cc["position_count"] == 10


# ------------------------------------------------------------------ reading happy path
def test_reading_shape_and_cards(client: TestClient, stub: StubProvider):
    r = client.post("/api/reading", json={
        "question": "这段关系接下来会怎样?",
        "spread_id": "past-present-future",
        "allow_reversals": True,
    })
    assert r.status_code == 200
    data = r.json()

    assert len(data["cards"]) == 3
    card = data["cards"][0]
    assert set(card) >= {
        "position_name", "card_name", "orientation", "image_url",
        "position_interpretation", "keywords", "resonance",
    }
    assert data["reading"] == stub._reading
    assert data["mode"] == "llm"
    assert data["question_type"] == "love"
    assert isinstance(data["seed"], int)
    assert 0 <= data["seed"] <= 0xFFFF
    assert isinstance(data["relationships"], list)
    assert set(data["statistics"]) == {
        "elements_balance", "suits_balance", "major_ratio",
        "numerology_numbers", "majors",
    }
    # stub got exactly two calls: classifier (0.1) then synthesis (0.7)
    temps = sorted(c["temperature"] for c in stub.calls)
    assert temps == [0.1, 0.7]


def test_celtic_cross_ten_cards(client: TestClient):
    data = client.post("/api/reading", json={"question": "综合看看", "spread_id": "celtic-cross"}).json()
    assert len(data["cards"]) == 10


def test_no_reversals_all_upright(client: TestClient):
    data = client.post("/api/reading", json={
        "question": "今日指引", "spread_id": "mind-body-spirit", "allow_reversals": False,
    }).json()
    assert all(c["orientation"] == "upright" for c in data["cards"])


# ------------------------------------------------------------------ signature
def test_birthday_produces_signature(client: TestClient):
    data = client.post("/api/reading", json={
        "question": "事业走向", "spread_id": "single-focus", "birthday": "1990-04-15",
    }).json()
    assert data["signature"] is not None
    assert data["signature"]["sign"] == "aries"
    assert set(data["signature"]) == {"element", "planet", "resonant_suits", "shadow_element", "sign"}
    assert data["cards"][0]["resonance"] is not None
    assert data["cards"][0]["resonance"]["level"] in {"HOT", "WARM", "COLD"}


def test_without_birthday_signature_none_and_resonance_none(client: TestClient):
    data = client.post("/api/reading", json={
        "question": "事业走向", "spread_id": "single-focus",
    }).json()
    assert data["signature"] is None
    assert data["cards"][0]["resonance"] is None


# ------------------------------------------------------------------ determinism
def test_same_payload_same_seed_and_cards(client: TestClient):
    payload = {"question": "同一个问题", "spread_id": "past-present-future", "nonce": 42}
    a = client.post("/api/reading", json=payload).json()
    b = client.post("/api/reading", json=payload).json()
    assert a["seed"] == b["seed"]
    assert [c["card_name"] for c in a["cards"]] == [c["card_name"] for c in b["cards"]]
    assert [c["orientation"] for c in a["cards"]] == [c["orientation"] for c in b["cards"]]


def test_different_nonce_changes_draw(client: TestClient):
    base = {"question": "同一个问题", "spread_id": "celtic-cross"}
    a = client.post("/api/reading", json={**base, "nonce": 1}).json()
    b = client.post("/api/reading", json={**base, "nonce": 2}).json()
    assert a["seed"] != b["seed"]


# ------------------------------------------------------------------ errors / fallback
def test_unknown_spread_friendly_404(client: TestClient):
    r = client.post("/api/reading", json={"question": "x", "spread_id": "nope"})
    assert r.status_code == 404
    assert "available" in r.json()["detail"].lower()


def test_offline_provider_falls_back_to_deterministic_reading():
    app = main.create_app(provider=StubProvider(available=False))
    c = TestClient(app)
    data = c.post("/api/reading", json={"question": "无 key 时", "spread_id": "single-focus"}).json()
    assert data["mode"] == "no-llm"
    assert isinstance(data["reading"], str) and len(data["reading"]) > 0
    assert len(data["cards"]) == 1


def test_seed_is_stable_across_calls():
    assert main.stable_seed("anon", "你好", 1) == main.stable_seed("anon", "你好", 1)
    assert main.stable_seed("anon", "你好", 1) != main.stable_seed("anon", "你好", 2)
    assert 0 <= main.stable_seed("anon", "边界", None) <= 0xFFFF
