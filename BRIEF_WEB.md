# Tarot Web BRIEF v2 — 申派占卜站 · 商用级豪华简约 (big-pickle task)

## 一、现状（What Exists）

引擎已全部就位（50 pytest green, commit 130a37f），目录 `/home/ubuntu/kaka-portfolio/tarot-engine/`：

```
src/tarot_engine/
    loader.py       load_cards/load_spreads/load_traditions
    cleaner.py      zodiac脏数据清洗
    deck.py         DeckEngine.draw(count, seed, allow_reversals)
    spread.py       SpreadRegistry.load_spread/list_spreads
    assembler.py    Assembler.assemble(drawn, spread, question, question_type) → AssembledContext
    resonance.py    ResonanceLayer(sig).for_reading(deck, drawn); signature_from_birthday(date)
    synthesizer.py  Synthesizer(provider, traditions, tradition="shen-mystic")
                    .classify(question) → 六域; .reading(ctx, marks, sig) → {"mode":"llm","reading":str}
    mmx_llm.py      MMXProvidererry (默认 MiniMax-M3, 本机 mmx CLI, 免费周池)
```

llm.py doctring complete(prompt, temperature, max_tokens) 接口统一。

launch 6牌阵 ids (data/tarot-spreads.json): single-focus / past-present-future / mind-body-spirit / celtic-cross / four-card-decision / relationship-spread
中文释义 + 難易度 (见 tests/test_spread.py LAUNCH_CN)。

shen-mystic 流派 prompt: 简体中文咨询体 (不做决定/影子直说/共振分类法/结尾小动作+自查问题)。

## 二、要建什么（Scope)

单页商用级占卜站 (1 个 index.html + 资源), served by the Python FastAPI backend。

### 后端 (FastAPI) — `backend/`
- `main.py` — FastAPI app, 三个端点:
  - `GET  /`                    → index.html
  - `GET  /api/spreads`         → 6 牌阵 {id,name, Beschreibung中文,position_count, difficulty,category}
  - `POST /api/reading`         → body {question, spread_id, birthday(optional "YYYY-MM-DD"), allow_reversals}
                                  流程: seed=hash(user_fingerprint+question) → draw → assemble → resonance → classify → mmx synthesize
                                  返回 {cards:[{position_name, card_name, orientation, image_url, position_interpretation, keywords, resonance}], relationships:[...], statistics:{...}, reading: str, signature:{...}, seed}
  - `GET  /api/health`
- engine calls imported from `../src/tarot_engine` (add `sys.path` shim or package it properly). Use `MMXProvider`.
- seed 规范: `seed = hash(fingerprint + question) & 0xffff` (16bit, 便于前端重抽复现)
- Birthday optional → signature=None path still works.
- CORS: allow localhost for dev, prod domain后配.
- 依赖: fastapi + uvicorn + jinja2 + pyyaml. requirements.txt.

### 前端 (单页) — `backend/static/`
`index.html + styles.css + app.js`. 零 build 依赖 (hand-rolled), 移动端优先设计.

**视觉 — 简约奢华 × 星空仪式感 (设计语言须照抄)**:
- 色板: 
  - 背景 `#050810` (近黑夜空) + 顶部径向微光 `radial-gradient(1200px at 50% -10%, #141a2e 0%, #050810 70%)`
  - 主金 `#d4af37` (香槟金), 辅金 `#f4d97b`, 亮金 `#ffe8a3`
  - 星尘白 `#f5f3ee`, 灰阶 `#8a8a9a`
- 字体: display 标题 `Cormorant Garamond, serif` (西文) / `Noto Serif SC, serif` (中文) — Google Fonts CDN
- body: `Inter, sans-serif`
- 卡牌: 玻璃拟态 `backdrop-filter: blur(20px); background: rgba(212,175,55,0.06); border: 1px solid rgba(212,175,55,0.25)`
- 金色渐变字标题: `background: linear-gradient(135deg,#f4d97b,#d4af37,#8a6d1f); -webkit-background-clip:text`
- 按钮: 金边主按钮 hover 发光 `box-shadow: 0 0 30px rgba(212,175,55,.35)`
- 星空粒子背景: 纯CSS (3层 opacity 不同 box-shadow 星点 + 缓慢 drift keyframes), 不引three.js
- 正逆位视觉: 正位牌框金渐变, 逆位牌 `transform: rotate(180deg) + border-color: #6a5aaa (紫影)`

**页面流程 (四屏)**
1. **Landing 首屏**: 全屏星空中央一颗发光的牌背 (CSS 星阵图) + 标题「申派塔罗」 + 副标题「真实牌义 · 诚实抽牌 · 仪式感占位」 + 「开始占卜」按钮 (滚入第二屏)
2. **设置屏**: 问题输入框 (textarea, 香焦金边) / 生日输入 (可选, 说明"用于本命共振, 不填跳过") / 牌阵选择 (6卡横滑 or grid, 每卡显示中文释义+张数) / 「开始抽牌」
3. **抽牌动画屏**: 牌背锻炼旋出 (CSS transform 3D flip + glow), 逐张翻开, 每张显示卡名+正/逆位 (逆位旋转180°) + 位置名; 骨架期间显示「抽牌中」计数.
4. **解读屏**: 
   - 顶部: 综合解读 markdown (简单格式渲染: 段落/标题/引用块)
   - 牌位网格: 每卡一张迷你卡 (卡名+位置+正逆位+关键词)
   - 牌际关系: 8组关系卡片列表 (Amplifies/Challenges 中文标签)
   - 统计能量账本: 元素分布条形图 (CSS bar, 金色) + 大小阿卡纳比例 + 数字命理
   - 共振标记: 每卡 HOT/WARM/COLD 徽章 (HOT金/COLD紫/WARM灰) + tone tooltip
   - 「再抽一次」按钮 (同问题 different seed)

**无后端可跑 (dev fallback)**: 若 fetch /api/reading 失败, JS 内置三张 mock card 数据继续渲染 (带 "演示模式" 徽章), 保证非后端主机也能打开看UI.

## 三、验收（Acceptance)

1. `cd backend && uvicorn main:app --port 8600` 起服务, curl /api/health 返回 {"status":"ok"}
2. POST /api/reading 用真实 question 返回 JSON 含完整 cards/reading 字段, reading 为中文 (MMXProvider 实调)
3. 浏览器开 http://localhost:8600 : landing→设置→动画→解读 四屏全走通, 移动端 (375px 宽) 无横向滚动
4. 视觉: 截图三张 (landing / animation mid / result) 存 backend/static/preview/ 方便审查
5. engine 侧 `pytest` 依旧 50 green (不得动 src/tarot_engine 除非必要接口微调)
6. 代码: 无 console 报错; 深色模式适配 (prefers-color-scheme 不变, 因为站点本然深色)
7. 交付: git commit 一次全部
```
