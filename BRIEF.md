# Tarot Engine BRIEF — 诚实占卜引擎（五层架构 + 共振层）

## 一、现状（What Exists）

项目根: `/home/ubuntu/kaka-portfolio/tarot-engine/`

```
data/cards/*.json            78张牌义JSON (arcanite全字段, 韦特能量学谱系):
                             card_id/card_name/card_number/suit/archetype
                             core_meanings{upright|reversed: essence/keywords/psychological/spiritual/practical/shadow}
                             position_interpretations{7类30+位义 × upright|reversed + keywords}
                             question_contexts{love|career|spiritual|financial|health × upright|reversed + keywords}
                             elemental_correspondences{element/zodiac/hebrew_letter/numerology/planet/season/time_of_day/colors/crystals/herbs}
                             symbols{象征物:释义} / affirmations / journaling_prompts / meditation_focus
                             card_relationships{amplifies|challenges|clarifies|similar_energy|opposite_energy|learning_sequence: {card_id:{interpretation,keywords}}}
data/tarot-spreads.json      牌阵定义 (含 layouts/spreads/categories):
                             每position: name/short_description/detailed_description/keywords/
                             rag_mapping("temporal_positions.present")/question_adaptations{love|career...}
data/tarotoo_cards.json      78张交叉校验数据 (Tarotoo: yes_no/love/career/mood/spiritual正逆位四维)
data/prompts/*.yaml          流派模板 (intuitive.yaml / kate-signature.yaml):
                             name/description/system/user (Jinja2模板, user模板用{cards[]}/{relationships}/{spread_name}等)
data/lenormand-spreads.json  雷诺曼牌阵 (本期不实现, 结构参考)
docs/plans/...-design.md     完整五层设计文档 (架构/数据流/清洗规则全在此)
```

**zodiac字段清洗规则**（实测三种脏数据必须处理）:
- `zodiac ∈ 12星座` → 保留
- `zodiac ∈ 行星名(uranus/moon/mercury/jupiter/pluto/mars/neptune/saturn/venus)` → 移入 `ruler_planet` 通道, zodiac置空
- `"sun in scorpio"` 混合文本 → 解析出 scorpio 填回
- 空值 `""` → 查 elemental.element 兜底（element 78/78实测无缺失）

## 二、规范（How to Build）

**架构五层（顺序严格执行，禁止跨层调用）**:
```
L1 DeckEngine     → seed洗牌+逆位独立掷骰 (random.Random(seed); shuffle; rng.random()<0.5)
L2 SpreadRegistry → 牌阵加载+position.rag_mapping (JSON读入, KeyError友好列出可用阵)
L3 Assembler      → 确定性RAG组装 (位置×正逆位×问题域三维牌义索引+牌际关系匹配+统计账本)
L5 Resonance      → 共振层 (QuerentSignature/Rapport/ResonanceScore, 方案B, 只影响解读不改随机)
L4 Synthesizer    → LLM合成 (问题分类temperature=0.1 + Jinja2解读temperature=0.7)
```

**核心铁律**:
1. LLM 禁止: 抽牌/选牌/改牌义/发明关键字/跳过影子面
2. 洗牌 reservoir: 任何Resonance信号不得进L1的rng
3. 逆位语义独立 (reversed 是独立影子叙事, 不是正位反转)
4. seed 可复现: 同seed同结果 (DrawnCard序列+orientation全可审计)
5. 组装fallback链: rag_mapping命中失败 → 降级core_meanings (不许报错崩溃)

**Resonance方案B具体公式** (照实现不许改):
```
signature = 生日→星座→{element, planet, resonant_suits, shadow_element}
   星座签名表(硬编码12条, 从arcanite牌义谱已验证):
   aries/fire+mars, taurus/earth+venus, gemini/air+mars, cancer/water+venus,
   leo/fire+sun, virgo/earth+mercury, libra/air+saturn, scorpio/water+pluto,
   sagittarius/fire+mars, capricorn/earth+saturn, aquarius/air+moon, pisces/water+neptune
每张drawn牌:
  score = 0
  +0.4  if card.elemental.element == signature.element
  +0.3  if elemental.planet == signature.planet
  +0.2  if suit ∈ resonant_suits (fire→wands, earth→pentacles, air→swords, water→cups)
  -0.2  if REVERSED 且上述任一命中 (能量拮抗)
分档: >=0.7 HOT / 0.3-0.7 WARM / <0.3 COLD
signature为null(生日没给) → 全跳过, 不影响解读
Rapport(共振强度0-1) = 0.4*question_depth_min(len(question)/20 cap 1)
                     + 0.3*centering_done(bool)
                     + 0.3*session_duration_z(秒/60 cap 1)
  只做展示用, 不进prompt (方案B定版)
```

**牌阵首发6个** (用现有tarot-spreads.json中的id, 附中文释义):
- single-card      单牌指引 · 今日能量
- three-card       三牌阵 · 身/心/灵
- past-present-future  时间流 · 过去/现在/未来
- celtic-cross     凯尔特十字 · 十位全面阵
- yes-no           是非阵 · 二元抉择
- love             爱情阵 · 关系能量场

**LLM接入** (L4, 走OpenAI兼容接口):
- 环境变量: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
- 草稿期 fail-with-no-llm 模式: 无key时 L4 返回"确定性上下文JSON + 提示未接LLM" (让数据流可测)
- 二调用: classify(temperature=0.1,max_tokens=20) / synthesize(temperature=0.7)

**目录结构** (src布局):
```
src/tarot_engine/
    __init__.py
    deck.py         L1 DeckEngine
    spread.py       L2 SpreadRegistry
    assembler.py    L3 Assembler + statistics
    resonance.py    L5 ResonanceLayer
    synthesizer.py  L4 LLMProvider + classifier + synthesizer (Jinja2)
    cleaner.py      zodiac清洗 (模块级, 在load时调用)
    loader.py       78张load+镜像验证
tests/
    test_deck.py    TDD: seed可复现/正逆位/越界抽牌
    test_spread.py  TDD: 加载6阵/rag_mapping字段存在/KeyError友好
    test_assembler.py  TDD: rag命中/fallback链/关系匹配/统计正确
    test_resonance.py  TDD: 签名生成/评分公式三档/null安全
    test_synthesizer.py TDD: no-llm模式/模板渲染
```

## 三、验收（Acceptance）

1. `pytest tests/ -v` 全绿 (零跳过)
2. 端到端冒烟: python -c 调 DeckEngine+SpreadRegistry+Assembler+Resonance 全链路, 打印 AssembledContext JSON (含stats/relationships/每张牌resonance_mark), 结构字段齐全
3. no-llm 模式: `LLM_API_KEY=` 空时跑 /readings 不崩, 返回完整确定性数据
4. 不精简纪律: 78张数据 + 六维关系 + 每张牌五维meaning + symbols/affirmations 全部进入AssembledContext; 任何一条被略过 = 实现失败
5. 代码风格: 类型标注(dict[str,Any]/list[...]), 每文件头部一行注释说明方向, 不要docstring口水话
```
