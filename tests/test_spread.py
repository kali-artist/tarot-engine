"""test_spread.py — L2 TDD: all six launch spreads load, carry rag_mapping, and fail friendly.

Launch mapping (design §3): data ids as stored in tarot-spreads.json, 中文释义 for UI selection.
"""
import pytest

from tarot_engine.spread import SpreadRegistry

# id -> 中文释义 (design launch list)
LAUNCH = {
    "single-focus":          "单牌指引 · 今日能量",
    "past-present-future":   "时间流 · 过去/现在/未来",
    "mind-body-spirit":      "三牌阵 · 身/心/灵",
    "celtic-cross":          "凯尔特十字 · 十位全面阵",
    "yes-no":                "是非阵 · 二元抉择",
    "love":                  "爱情阵 · 关系能量场",
}
# note: yes-no maps to the binary-decision spread present in the data; love -> relationship-spread
LAUNCH_IDS = ["single-focus", "past-present-future", "mind-body-spirit", "celtic-cross", "four-card-decision", "relationship-spread"]
LAUNCH_CN = {
    "single-focus":          "单牌指引 · 今日能量",
    "past-present-future":   "时间流 · 过去/现在/未来",
    "mind-body-spirit":      "三牌阵 · 身/心/灵",
    "celtic-cross":          "凯尔特十字 · 十位全面阵",
    "four-card-decision":    "是非抉择阵 · 二元快手",
    "relationship-spread":   "爱情阵 · 关系能量场",
}


@pytest.fixture(scope="module")
def reg():
    return SpreadRegistry()


def test_launch_ids_present(reg):
    have = set(reg.list_spreads())
    for spread_id in LAUNCH_IDS:
        assert spread_id in have, f"missing launch spread {spread_id!r}; available: {sorted(have)}"


@pytest.mark.parametrize("spread_id", LAUNCH_IDS)
def test_positions_have_required_fields(reg, spread_id):
    spread = reg.load_spread(spread_id)
    assert spread.position_count == len(spread.positions)
    assert spread.position_count >= 1
    for pos in spread.positions:
        assert pos.name, "each position must be named"
        assert pos.rag_mapping, "each position must declare rag_mapping for deterministic lookup"
        assert "." in pos.rag_mapping, "rag_mapping is dot-path into position_interpretations"


def test_celtic_cross_is_ten_positions(reg):
    assert reg.load_spread("celtic-cross").position_count == 10


def test_unknown_spread_friendly_error(reg):
    with pytest.raises(KeyError, match="available"):
        reg.load_spread("definitely-not-a-spread")
