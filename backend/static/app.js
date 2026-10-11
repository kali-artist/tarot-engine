/* app.js — 申派塔罗 single-page controller. No build step, no deps.
   Four screens: landing -> setup -> animation -> reading.
   If the backend is unreachable, a built-in 演示模式 (mock) keeps the UI alive. */
(function () {
  "use strict";

  // ------------------------------------------------------------- starfield
  function buildStars(el, count, size, alpha) {
    if (!el) return;
    var w = Math.max(window.innerWidth, 360) * 2;
    var h = Math.max(window.innerHeight, 640) * 2;
    var parts = [];
    for (var i = 0; i < count; i++) {
      var x = Math.round(Math.random() * w);
      var y = Math.round(Math.random() * h);
      var c = Math.random() < 0.24
        ? "rgba(244,217,123," + alpha + ")"
        : "rgba(245,243,238," + alpha + ")";
      parts.push(x + "px " + y + "px 0 " + size + "px " + c);
    }
    el.style.boxShadow = parts.join(",");
  }
  buildStars(document.getElementById("starsFar"), 220, 0, 0.5);
  buildStars(document.getElementById("starsMid"), 130, 0, 0.75);
  buildStars(document.getElementById("starsNear"), 60, 1, 0.95);

  // dedicated twinkling stars (box-shadow dots can't animate individually)
  (function buildTwinkles() {
    var box = document.getElementById("twinkles");
    if (!box) return;
    for (var i = 0; i < 16; i++) {
      var s = document.createElement("span");
      s.className = "twinkle";
      s.style.left = (Math.random() * 100).toFixed(2) + "%";
      s.style.top = (Math.random() * 100).toFixed(2) + "%";
      s.style.animationDelay = (Math.random() * 4).toFixed(2) + "s";
      s.style.animationDuration = (2.2 + Math.random() * 2.6).toFixed(2) + "s";
      var big = Math.random() < 0.3;
      s.style.width = s.style.height = big ? "3px" : "2px";
      box.appendChild(s);
    }
  })();

  // ------------------------------------------------------------- constants
  var SIGIL_SVG =
    '<svg viewBox="0 0 100 100" aria-hidden="true">' +
    '<circle cx="50" cy="50" r="34" class="sigil-ring"/>' +
    '<circle cx="50" cy="50" r="22" class="sigil-ring sigil-ring--thin"/>' +
    '<path d="M50 16 L58 42 L84 50 L58 58 L50 84 L42 58 L16 50 L42 42 Z" class="sigil-star"/>' +
    '<circle cx="50" cy="50" r="3.4" class="sigil-core"/></svg>';

  var SPREAD_FALLBACK = [
    { id: "single-focus", name: "单牌指引 · 今日能量", description: "一张牌，回答你此刻最需要看见的那股能量。", position_count: 1, difficulty: "beginner", category: "simple" },
    { id: "past-present-future", name: "时间流 · 过去/现在/未来", description: "经典三牌，看清事件的来路、当下与去向。", position_count: 3, difficulty: "beginner", category: "timeline" },
    { id: "mind-body-spirit", name: "三牌阵 · 身/心/灵", description: "从身、心、灵三个层面，照见你的整体状态。", position_count: 3, difficulty: "beginner", category: "wellness" },
    { id: "celtic-cross", name: "凯尔特十字 · 十位全面阵", description: "十张牌的全面洞察，深入一个议题的各个维度。", position_count: 10, difficulty: "advanced", category: "comprehensive" },
    { id: "four-card-decision", name: "是非抉择阵 · 二元快手", description: "四个位置，帮你在两条路之间看清取舍。", position_count: 4, difficulty: "intermediate", category: "decision" },
    { id: "relationship-spread", name: "爱情阵 · 关系能量场", description: "六张牌，拆解你与对方之间的能量流动。", position_count: 6, difficulty: "intermediate", category: "relationship" }
  ];

  var REL_CN = {
    amplifies: "增强", challenges: "挑战", clarifies: "澄清",
    similar_energy: "同频", opposite_energy: "对立", learning_sequence: "进阶"
  };
  var REL_CLASS = {
    amplifies: "t-amp", challenges: "t-cha", clarifies: "t-clr",
    similar_energy: "t-sim", opposite_energy: "t-opp", learning_sequence: "t-seq"
  };
  var POS_CN = { "Past":"过去", "Present":"现在", "Future":"未来", "Focus":"焦点", "Challenge":"挑战",
    "Outer":"外部", "Advice":"建议", "Foundation":"根基", "Crown":"目标", "Cross":"核心",
    "Mind":"理智", "Body":"身体", "Spirit":"灵魂", "Situation":"现状", "Action":"行动", "Outcome":"结果" };
  var SUIT_CN = { wands:"权杖", cups:"圣杯", pentacles:"星币", swords:"宝剑" };
  var KEY_CN = { courage:"勇气", new_start:"新的开始", innocence:"初心", clarity:"清明", release:"放下",
    intuition:"直觉", subconscious:"潜意识", fear:"恐惧", anxiety:"不安", wisdom:"智慧",
    mystery:"神秘", selfishness:"自我", imbalance:"失衡", neglect:"忽视", overindulgence:"放纵",
    abundance:"丰盛", stability:"稳定", patience:"耐心", love:"爱", passion:"热忱", conflict:"冲突",
    focus:"聚焦", delay:"延迟", defeat:"挫败", endings:"终结", transformation:"蜕变",
    choice:"抉择", harmony:"和谐", willpower:"意志", retreat:"退省", guidance:"指引", renewal:"更新",
    isolation:"孤立", reflection:"内省", planning:"规划", opportunity:"机会", vision:"远见",
    leadership:"引领", authority:"权威", tradition:"传统", rebellion:"反叛", awakening:"觉醒",
    celebration:"庆祝", exchange:"交换", rest:"休息", reward:"回报", burden:"重担",
    success:"成功", illusion:"幻象", truth:"真相", deception:"蒙蔽", movement:"行动",
    boundaries:"边界", generosity:"慷慨", grounding:"落地", nurture:"滋养", control:"掌控",
    surrender:"放手", hope:"希望", faith:"信念" };
  var SIGN_CN = { aries:"白羊", taurus:"金牛", gemini:"双子", cancer:"巨蟹", leo:"狮子", virgo:"处女", libra:"天秤", scorpio:"天蝎", sagittarius:"射手", capricorn:"摩羯", aquarius:"水瓶", pisces:"双鱼" };
  var PLANET_CN = { mars:"火星", venus:"金星", mercury:"水星", moon:"月亮", sun:"太阳", saturn:"土星", jupiter:"木星", pluto:"冥王星", uranus:"天王星", neptune:"海王星" };
  var TYPE_CN = {
    love: "感情", career: "事业", spiritual: "灵性",
    financial: "财务", health: "健康", general: "综合"
  };
  var DIFF_CN = { beginner: "入门", intermediate: "进阶", advanced: "高阶" };
  var ELEMENT_CN = { fire: "火", earth: "土", air: "风", water: "水" };
  var ELEMENT_ICON = { fire: "🔥", earth: "⛰️", air: "💨", water: "💧" };
  var SPREAD_ICON = {
    "single-focus": "✦", "past-present-future": "☽", "mind-body-spirit": "❖",
    "celtic-cross": "✠", "four-card-decision": "⚖", "relationship-spread": "♥"
  };

  var MOCK_DATA = {
    cards: [
      { position_name: "过去", card_name: "The Fool", card_name_zh: "愚者", orientation: "upright", orientation_zh: "正位", image_url: "cards/m00.jpg",
        position_interpretation: "过去一个毫无保留的跃入，塑造了你此刻的处境。",
        keywords: ["courage","new_start","innocence"], element: "air",
        resonance: { level: "WARM", score: 0.4, reasons: ["element match: air"] } },
      { position_name: "现在", card_name: "The Moon", card_name_zh: "月亮", orientation: "reversed", orientation_zh: "逆位", image_url: "cards/m18.jpg",
        position_interpretation: "迷雾正在散去，你开始看清自己真正在意的东西。",
        keywords: ["intuition","fear","release"], element: "water",
        resonance: { level: "COLD", score: 0.0, reasons: [] } },
      { position_name: "未来", card_name: "The Star", card_name_zh: "星星", orientation: "upright", orientation_zh: "正位", image_url: "cards/m17.jpg",
        position_interpretation: "一条安静的希望之路正在展开，慢，但方向是对的。",
        keywords: ["hope", "renewal", "guidance"], element: "air",
        resonance: { level: "HOT", score: 0.7, reasons: ["element match: air", "ruler planet match: uranus"] } }
    ],
    relationships: [
      { relationship_type: "amplifies", card1_name: "The Fool", card2_name: "The Star",
        interpretation: "初心与希望彼此放大，让你更愿意相信前路。", keywords: ["trust", "flow"] }
    ],
    statistics: {
      elements_balance: { air: 2, water: 1 }, suits_balance: { major: 3 },
      major_ratio: 1.0, numerology_numbers: [0, 18, 17], majors: ["The Fool", "The Moon", "The Star"]
    },
    reading: "## 演示模式\n\n当前未连接到后端，展示的是内置示例数据。\n\n" +
      "> 你在过去敢于跃入未知，这份勇气此刻仍在支撑你。\n\n" +
      "### 现在的功课\n迷雾正在散去，请允许自己慢一点，**先看清，再行动**。\n\n" +
      "### 一个今晚可以做的小动作\n写下三件你此刻仍然相信的事，哪怕很小。\n\n" +
      "### 一个值得带走的自查问题\n如果没有人会评价你，你此刻最想做出的那个选择是什么？",
    signature: { sign: "aries", element: "fire", planet: "mars", resonant_suits: ["wands"], shadow_element: "water" },
    question_type: "general", seed: 20261, mode: "mock"
  };

  // ------------------------------------------------------------- state
  var state = {
    spreads: SPREAD_FALLBACK.slice(),
    selectedSpread: SPREAD_FALLBACK[0],
    question: "",
    birthday: "",
    allowReversals: true,
    lastResult: null,
    lastSpread: null,
    demo: false,
    pending: false
  };

  var $ = function (id) { return document.getElementById(id); };

  // ------------------------------------------------------------- navigation
  function showScreen(name) {
    var screens = document.querySelectorAll(".screen");
    for (var i = 0; i < screens.length; i++) {
      screens[i].classList.toggle("is-active", screens[i].getAttribute("data-screen") === name);
    }
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function setDemo(on) {
    state.demo = !!on;
    $("demoBadge").hidden = !on;
  }

  // ------------------------------------------------------------- spreads
  function renderSpreads() {
    var grid = $("spreadGrid");
    grid.innerHTML = "";
    state.spreads.forEach(function (sp) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "spread" + (sp.id === state.selectedSpread.id ? " is-selected" : "");
      btn.setAttribute("role", "radio");
      btn.setAttribute("aria-checked", sp.id === state.selectedSpread.id ? "true" : "false");
      btn.setAttribute("data-id", sp.id);

      var top = document.createElement("div");
      top.className = "spread__top";
      var nm = document.createElement("span");
      nm.className = "spread__name";
      var icon = document.createElement("span");
      icon.className = "spread__icon";
      icon.textContent = SPREAD_ICON[sp.id] || "✦";
      nm.appendChild(icon);
      nm.appendChild(document.createTextNode(sp.name));
      var cnt = document.createElement("span");
      cnt.className = "spread__count";
      cnt.textContent = sp.position_count + " 张";
      top.appendChild(nm); top.appendChild(cnt);

      var desc = document.createElement("p");
      desc.className = "spread__desc";
      desc.textContent = sp.description;

      var meta = document.createElement("div");
      meta.className = "spread__meta";
      meta.textContent = (DIFF_CN[sp.difficulty] || sp.difficulty) + " · " + (sp.category || "");

      btn.appendChild(top); btn.appendChild(desc); btn.appendChild(meta);
      btn.addEventListener("click", function () {
        state.selectedSpread = sp;
        renderSpreads();
      });
      grid.appendChild(btn);
    });
  }

  function loadSpreads() {
    return fetch("/api/spreads")
      .then(function (r) {
        if (!r.ok) throw new Error("spreads " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (Array.isArray(data) && data.length) {
          state.spreads = data;
          state.selectedSpread = data[0];
        }
      })
      .catch(function () {
        state.spreads = SPREAD_FALLBACK.slice();
        state.selectedSpread = state.spreads[0];
      })
      .then(renderSpreads);
  }

  // ------------------------------------------------------------- animation
  function makeFlip(card, index, total) {
    var flip = document.createElement("div");
    flip.className = "flip";
    flip.style.animationDelay = (index * 90) + "ms";
    flip.innerHTML =
      '<div class="flip__inner">' +
      '<div class="flat-glow"></div>' +
      '<div class="flip__face flip__back">' + SIGIL_SVG + "</div>" +
      '<div class="flip__face flip__front"></div>' +
      "</div>";
    return flip;
  }

  function renderFront(flip, card) {
    var front = flip.querySelector(".flip__front");
    if (card.orientation === "reversed") front.classList.add("is-reversed");
    var imgTag = card.image_url
      ? '<img class="flip__img' + (card.orientation === "reversed" ? " is-rev" : "") + '" src="' + esc(card.image_url) + '" alt="' + esc(card.card_name_zh || card.card_name) + '"/>'
      : '<div class="flip__ph">✦</div>';
    front.innerHTML =
      imgTag +
      '<div class="flip__pos">' + esc(POS_CN[card.position_name] || card.position_name || "") + "</div>" +
      '<div class="flip__name">' + esc(card.card_name_zh || card.card_name) + '</div><div class="flip__en">' + esc(card.card_name) + " · " + (card.orientation_zh || card.orientation) + "</div>" +
      '<div class="flip__orient ' + (card.orientation === "reversed" ? "rev" : "up") + '">' +
      (card.orientation === "reversed" ? "逆位" : "正位") + "</div>";
  }

  function runAnimation(cards) {
    var fan = $("fan");
    fan.innerHTML = "";
    $("animTitle").textContent = "抽牌中";
    $("revealDoneBtn").hidden = true;

    // small spreads lay out as a real arc fan (pivot at bottom center);
    // larger spreads (celtic cross etc.) fall back to the wrapped grid.
    var arc = cards.length <= 6;
    fan.classList.toggle("fan--arc", arc);
    var center = (cards.length - 1) / 2;

    cards.forEach(function (card, i) {
      var flip = makeFlip(card, i, cards.length);
      if (arc) {
        var slot = document.createElement("div");
        slot.className = "flip-slot";
        var off = i - center;
        slot.style.transform = "rotate(" + (off * 8).toFixed(2) + "deg) translateY(" + (off * off * 7).toFixed(1) + "px)";
        slot.appendChild(flip);
        fan.appendChild(slot);
      } else {
        fan.appendChild(flip);
      }
    });

    var flips = fan.querySelectorAll(".flip");
    var total = cards.length;
    var revealAt = 620; // let the deal-in settle first

    cards.forEach(function (card, i) {
      window.setTimeout(function () {
        renderFront(flips[i], card);
        flips[i].classList.add("is-flipped");
        $("animCount").textContent = "已翻开 " + (i + 1) + " / " + total;
        if (i === total - 1) {
          $("animTitle").textContent = "牌面已现";
          $("animCount").textContent = "共 " + total + " 张牌，静候你的解读。";
          $("revealDoneBtn").hidden = false;
        }
      }, revealAt + i * 460);
    });
  }

  // ------------------------------------------------------------- fetch reading
  function fetchReading(payload) {
    return fetch("/api/reading", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (r) {
      if (!r.ok) throw new Error("reading " + r.status);
      return r.json();
    });
  }

  // ------------------------------------------------------------- markdown
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function inline(s) {
    return s
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  }
  function renderMarkdown(md) {
    var lines = esc(md || "").split(/\r?\n/);
    var out = [];
    var mode = null; // 'p' | 'ul' | 'bq'
    function close() {
      if (mode === "ul") out.push("</ul>");
      if (mode === "bq") out.push("</blockquote>");
      if (mode === "p") out.push("</p>");
      mode = null;
    }
    var para = [];
    function flushPara() {
      if (para.length) { out.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; }
    }
    lines.forEach(function (raw) {
      var line = raw.trim();
      if (!line) { flushPara(); close(); return; }
      var h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        flushPara(); close();
        var lvl = Math.min(h[1].length + 1, 4);
        out.push("<h" + lvl + ">" + inline(h[2]) + "</h" + lvl + ">");
        return;
      }
      if (/^(-{3,}|\*{3,})$/.test(line)) { flushPara(); close(); out.push("<hr/>"); return; }
      var li = line.match(/^[-*]\s+(.*)$/);
      if (li) {
        flushPara();
        if (mode !== "ul") { close(); out.push("<ul>"); mode = "ul"; }
        out.push("<li>" + inline(li[1]) + "</li>");
        return;
      }
      var bq = line.match(/^>\s?(.*)$/);
      if (bq) {
        flushPara();
        if (mode !== "bq") { close(); out.push("<blockquote>"); mode = "bq"; }
        out.push("<p>" + inline(bq[1]) + "</p>");
        return;
      }
      if (mode === "p" || mode === null) { mode = "p"; para.push(line); }
      else { para.push(line); }
    });
    flushPara(); close();
    return out.join("");
  }

  // ------------------------------------------------------------- render reading
  function renderMiniCard(card) {
    var rev = card.orientation === "reversed";
    var el = document.createElement("div");
    el.className = "mini" + (rev ? " is-reversed" : "");
    var keys = (card.keywords || []).slice(0, 4).map(function (k) {
      var zh = KEY_CN[k];
      return zh ? '<span class="key">' + esc(zh) + "</span>" : "";
    }).join("");
    var badge = card.resonance
      ? '<span class="badge badge--' + esc(card.resonance.level) + '" data-lv="' + esc(card.resonance.level) + '" title="' +
        esc((card.resonance.reasons || []).join("; ") || "本命共振") + '">' +
        (({HOT:"共振·本命", WARM:"共鸣·温和", COLD:"对峙·回避"})[card.resonance.level] || card.resonance.level) + "</span>"
      : "";
    var imgTag = card.image_url
      ? '<div class="mini__imgwrap"><img class="mini__img' + (rev ? " is-rev" : "") + '" src="' + esc(card.image_url) + '" alt="' + esc(card.card_name) + '" loading="lazy"/></div>'
      : '<div class="mini__imgwrap mini__imgwrap--ph">✦</div>';
    el.innerHTML =
      badge +
      '<div class="mini__pos">' + esc(card.position_name) + "</div>" +
      imgTag +
      '<div class="mini__name">' + esc(card.card_name_zh || card.card_name) + '</div><div class="mini__en">' + esc(card.card_name) + " · " + (card.orientation_zh || card.orientation) + "</div>" +
      '' +
      (keys ? '<div class="mini__keys">' + keys + "</div>" : "") +
      '';
    return el;
  }

  function renderStats(stats) {
    var box = $("statsBox");
    box.innerHTML = '<div class="stat__hint">能量账本：整副牌阵里四种元素的分布。哪种元素多，就说明这次问题被哪种"行动风格"的能量主导——火=行动/冲劲，土=现实/金钱，风=思维/沟通，水=情感/直觉。</div>';
    var elements = stats.elements_balance || {};
    var total = 0;
    Object.keys(elements).forEach(function (k) { total += elements[k]; });
    if (total === 0) total = 1;
    // always render all four elements so a missing element shows an explicit 0%
    ["fire", "earth", "air", "water"].forEach(function (k) {
      var n = elements[k] || 0;
      var pct = Math.round((n / total) * 100);
      var row = document.createElement("div");
      row.className = "stat__row";
      row.innerHTML =
        '<div class="stat__label"><span class="stat__elname">' + (ELEMENT_ICON[k] || "") + " " +
        esc(ELEMENT_CN[k] || k) + " 元素</span><span>" + n + " · " + pct + '%</span></div>' +
        '<div class="bar"><div class="bar__fill" data-el="' + k + '" style="width:0%"></div></div>';
      box.appendChild(row);
      requestAnimationFrame(function () {
        row.querySelector(".bar__fill").style.width = pct + "%";
      });
    });

    var majorPct = Math.round((stats.major_ratio || 0) * 100);
    var mrow = document.createElement("div");
    mrow.className = "stat__row";
    mrow.innerHTML =
      '<div class="stat__label"><span>大阿卡纳占比</span><span>' + majorPct + '%</span></div>' +
      '<div class="bar"><div class="bar__fill" style="width:0%"></div></div>';
    box.appendChild(mrow);
    requestAnimationFrame(function () {
      mrow.querySelector(".bar__fill").style.width = majorPct + "%";
    });

    if (stats.majors && stats.majors.length) {
      var mm = document.createElement("div");
      mm.className = "stat__muted";
      mm.style.margin = "-6px 0 18px";
      mm.textContent = "大牌：" + stats.majors.join(" · ");
      box.appendChild(mm);
    }

    var nums = stats.numerology_numbers || [];
    if (nums.length) {
      var nrow = document.createElement("div");
      nrow.className = "stat__row";
      nrow.innerHTML = '<div class="stat__hint">数字命理：大牌在塔罗序列中的编号（愚者0~世界21，圣杯Ace=1…）。相同或相邻的数字暗示同一条"课题线"。</div>' +
        '<div class="stat__label"><span>数字命理</span></div>' +
        '<div class="numline">' + nums.map(function (n) {
          return '<span class="num">' + esc(n) + "</span>";
        }).join("") + "</div>";
      box.appendChild(nrow);
    }
  }

  function renderSignature(sig) {
    var block = $("sigBlock");
    if (!sig) { block.hidden = true; return; }
    block.hidden = false;
    $("sigBox").innerHTML =
      "<div>星座：<b>" + esc(SIGN_CN[sig.sign] || sig.sign) + "</b> · 本命元素：<b>" + esc(ELEMENT_CN[sig.element] || sig.element) +
      '</b> · 主星：<b>' + esc(PLANET_CN[sig.planet] || sig.planet) + "</b></div>" +
      "<div>共振花色：<b>" + esc((sig.resonant_suits || []).map(function(s){return SUIT_CN[s] || s;}).join(" / ")) +
      "</b> · 影子元素：<b>" + esc(ELEMENT_CN[sig.shadow_element] || sig.shadow_element) + "</b></div>";
  }

  function renderReading(data) {
    state.lastResult = data;
    $("readingMeta").textContent =
      (state.lastSpread ? state.lastSpread.name : "") + " · 共 " + data.cards.length + " 张牌";
    $("seedChip").textContent = "seed " + data.seed;
    $("domainChip").textContent = "问题域 " + (TYPE_CN[data.question_type] || data.question_type || "综合");

    $("readingText").innerHTML = renderMarkdown(data.reading);

    var grid = $("miniGrid");
    grid.innerHTML = "";
    data.cards.forEach(function (c) { grid.appendChild(renderMiniCard(c)); });

    var rels = data.relationships || [];
    $("relBlock").hidden = rels.length === 0;
    var rl = $("relList");
    rl.innerHTML = "";
    rels.forEach(function (r) {
      var el = document.createElement("div");
      el.className = "rel";
      el.innerHTML =
        '<div class="rel__head"><span class="rel__pair">' + esc(r.card1_zh || r.card1_name) + " ✕ " + esc(r.card2_zh || r.card2_name) +
        '</span><span class="rel__tag ' + (REL_CLASS[r.relationship_type] || "") + '">' +
        esc(REL_CN[r.relationship_type] || r.relationship_type) + "</span></div>" +
        '<div class="rel__interp">' + esc(r.interpretation) + "</div>";
      rl.appendChild(el);
    });

    renderStats(data.statistics || {});
    renderSignature(data.signature);
  }

  // ------------------------------------------------------------- flow
  function startReading(payload, cardsHint) {
    if (state.pending) return; // guard against double-submit / Enter mashing
    state.pending = true;
    var drawBtn = $("drawBtn");
    if (drawBtn) { drawBtn.disabled = true; drawBtn.classList.add("is-loading"); }
    var done = function () {
      state.pending = false;
      if (drawBtn) { drawBtn.disabled = false; drawBtn.classList.remove("is-loading"); }
    };

    var count = (state.selectedSpread && state.selectedSpread.position_count) || 3;
    setDemo(false);
    showScreen("anim");
    $("fan").innerHTML = "";
    $("animCount").textContent = "正在为你的问题抽出 " + count + " 张牌…";

    fetchReading(payload)
      .then(function (data) {
        done();
        state.lastSpread = state.selectedSpread;
        runAnimation(data.cards);
        // pre-render the reading so the button is instant
        var btn = $("revealDoneBtn");
        btn.onclick = function () { renderReading(data); showScreen("reading"); };
      })
      .catch(function () {
        done();
        setDemo(true);
        state.lastSpread = { name: "演示牌阵" };
        runAnimation(MOCK_DATA.cards);
        $("revealDoneBtn").onclick = function () {
          renderReading(MOCK_DATA);
          showScreen("reading");
        };
      });
  }

  // ------------------------------------------------------------- events
  $("startBtn").addEventListener("click", function () {
    showScreen("setup");
    $("question").focus();
  });

  $("setupForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var q = $("question").value.trim();
    var err = $("setupError");
    if (!q) {
      err.textContent = "请先在心里明确一个问题，并写下来。";
      err.hidden = false;
      return;
    }
    err.hidden = true;
    state.question = q;
    state.birthday = $("birthday").value || "";
    startReading({
      question: q,
      spread_id: state.selectedSpread.id,
      birthday: state.birthday || null,
      allow_reversals: true,
      nonce: Date.now()
    });
  });

  $("revealDoneBtn").addEventListener("click", function () {
    // handled per-run; fallback guard
  });

  $("againBtn").addEventListener("click", function () {
    if (!state.question) { showScreen("setup"); return; }
    startReading({
      question: state.question,
      spread_id: state.selectedSpread.id,
      birthday: state.birthday || null,
      allow_reversals: true,
      nonce: Date.now()
    });
  });

  $("resetBtn").addEventListener("click", function () {
    showScreen("setup");
    $("question").value = "";
    $("question").focus();
  });

  // ------------------------------------------------------------- init
  loadSpreads();
})();
