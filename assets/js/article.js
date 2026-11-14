/* The article is complete as static HTML. This file adds:
   hover boxes for footnotes and citations, and the behaviour of the interactive figures. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (t) { return String(t).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); };
  function press(group, btn) { $$("button", group).forEach(function (b) { b.setAttribute("aria-pressed", b === btn ? "true" : "false"); }); }
  function reveal(root) { $$("[hidden]", root).forEach(function (el) { el.hidden = false; }); }

  /* ---------- footnote and citation hover boxes ---------- */
  (function () {
    var box = $("#hover-box"); if (!box) { return; }
    var panel = $(".panel", box), timer = null;
    function content(a) {
      if (a.dataset.fn) {
        var li = document.getElementById("fn-" + a.dataset.fn); if (!li) { return ""; }
        var c = li.cloneNode(true); $$(".backlink", c).forEach(function (b) { b.remove(); }); return c.innerHTML;
      }
      return (a.dataset.refs || "").split(",").map(function (n) {
        var li = document.getElementById("ref-" + n); return li ? '<div class="ref">' + li.innerHTML + "</div>" : "";
      }).join("");
    }
    function show(a) {
      window.clearTimeout(timer);
      panel.innerHTML = content(a);
      var r = a.getBoundingClientRect();
      box.style.top = (window.pageYOffset + r.bottom + 10) + "px";
      box.classList.add("on");
    }
    function hideSoon(ms) { window.clearTimeout(timer); timer = window.setTimeout(function () { box.classList.remove("on"); }, ms); }
    $$(".fn-ref, .cite-ref").forEach(function (a) {
      a.addEventListener("mouseenter", function () { show(a); });
      a.addEventListener("focus", function () { show(a); });
      a.addEventListener("mouseleave", function () { hideSoon(300); });
      a.addEventListener("blur", function () { hideSoon(300); });
    });
    box.addEventListener("mouseenter", function () { window.clearTimeout(timer); });
    box.addEventListener("mouseleave", function () { hideSoon(500); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { box.classList.remove("on"); } });
  })();

  /* ---------- opening figure: follow a score, or a step, along its paths ---------- */
  (function () {
    var fig = $("#fig-paths"); if (!fig) { return; }
    var svg = $("svg", fig), pinned = null;
    var has = function (el, set) { return (el.dataset.paths || el.dataset.p).split(" ").some(function (p) { return set.indexOf(p) >= 0; }); };
    function show(set) {
      svg.classList.toggle("sel", !!set);
      $$(".rib, .chip, .score", svg).forEach(function (el) {
        var on = !!set && has(el, set);
        el.classList.toggle("on", on);
        if (el.classList.contains("rib")) {
          var mine = el.dataset.paths.split(" ");
          el.classList.toggle("p1", on && mine.indexOf("1") >= 0);
          el.classList.toggle("p2", on && mine.indexOf("1") < 0);
        }
      });
    }
    $$(".chip, .score", svg).forEach(function (g) {
      var set = (g.dataset.paths || g.dataset.p).split(" ");
      var toggle = function () { pinned = pinned === set ? null : set; show(pinned); };
      g.addEventListener("mouseenter", function () { show(set); });
      g.addEventListener("mouseleave", function () { show(pinned); });
      g.addEventListener("focus", function () { show(set); });
      g.addEventListener("blur", function () { show(pinned); });
      g.addEventListener("click", toggle);
      g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    });
  })();

  /* ---------- pipeline: what happens at each step ---------- */
  (function () {
    var fig = $("#fig-pipeline"); if (!fig) { return; }
    var panel = $("#pipe-panel"), stages = $$(".stage", fig), pinned = "mode";
    var SAME = '<span class="solidtag">shared step</span>', GAP = '<span class="hollow">not recorded</span>';
    var TEXT = {
      item: ["Question", "One question from BIG-Bench Hard, with its reference answer. Both sources name the benchmark.", SAME + " The benchmark name is published with both scores."],
      prompt: ["Prompt", "The text the model is given. The leaderboard's harness, a fork of lm-evaluation-harness, puts three worked examples before the question. The developers' own pipeline also uses three examples and asks the model to reason step by step.", GAP + " Neither score comes with the prompt or the harness as a field."],
      model: ["Model", "Gemma-2-9B in both cases.", SAME + " The model name is published with both scores."],
      mode: ["Scoring mode", "How an answer is obtained from the model and checked. The leaderboard ranks the answer options it is given by likelihood. The report lets the model generate its reasoning and extracts the answer from the text.", GAP + " Neither source has a field for it."],
      mark: ["Right or wrong", "The answer is compared with the reference, and the question gets one mark.", SAME + " The way the answer was obtained differs, the comparison does not."],
      avg: ["Average", "The marks are averaged over the questions and over the subtasks of the benchmark.", SAME + " We know of no difference between the two sources here."],
      rescale: ["Rescale", "The leaderboard subtracts the score that guessing would get and stretches the rest to 0 to 100. Its harness measured 53.77, and it shows 34.10. The report publishes its accuracy as measured.", '<span class="hollow">recorded by one source</span>' + " The leaderboard documents the rule and lists both values in its data. The report has no field for the scale."],
      pub: ["Published score", "34.10 on the leaderboard and 68.20 in the Gemma 2 report, for the same model and the same benchmark.", '<span class="solidtag">published</span>' + " A reader of either number sees the model and the benchmark, and none of the three steps where the lines split."]
    };
    function show(k) {
      $$(".stage, .colbg", fig).forEach(function (g) { g.classList.toggle("on", g.dataset.k === k); });
      var t = TEXT[k]; panel.innerHTML = "<h4>" + t[0] + "</h4><p>" + t[1] + '</p><p class="rec">' + t[2] + "</p>";
    }
    stages.forEach(function (g) {
      var k = g.dataset.k;
      g.addEventListener("mouseenter", function () { show(k); });
      g.addEventListener("focus", function () { show(k); });
      g.addEventListener("click", function () { pinned = k; show(k); });
      g.addEventListener("mouseleave", function () { show(pinned); });
      g.addEventListener("blur", function () { show(pinned); });
      g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pinned = k; show(k); } });
    });
  })();

  /* ---------- one question, marked two ways ---------- */
  (function () {
    var ll = $("#mode-ll"), gen = $("#mode-gen"); if (!ll || !gen) { return; }
    var REF = "A", MIN = 3;
    function mark(el, ok, text) { el.className = "mark " + (ok ? "good" : "bad"); el.innerHTML = "<b>" + (ok ? "✓" : "✗") + "</b> " + text; }

    /* likelihood ranking: one bar of probability, three dividers */
    var bar = $("#ll-mass"), segs = $$(".sg", bar), grips = $$(".grip", bar), cuts = [31, 83, 94];
    function drawBar() {
      var edges = [0].concat(cuts, [100]), best = -1, bestI = -1, tie = false;
      segs.forEach(function (sg, i) {
        var w = edges[i + 1] - edges[i];
        sg.style.left = edges[i] + "%"; sg.style.width = w + "%"; $("i", sg).textContent = w;
        if (w > best) { best = w; bestI = i; tie = false; } else if (w === best) { tie = true; }
      });
      segs.forEach(function (sg, i) { sg.classList.toggle("pick", !tie && i === bestI); });
      grips.forEach(function (g, i) { g.style.left = cuts[i] + "%"; g.setAttribute("aria-valuenow", cuts[i]); });
      var out = $(".mark", ll);
      if (tie) { out.className = "mark"; out.textContent = "Two options have the same share. Move a divider to break the tie."; return; }
      var o = segs[bestI].dataset.opt;
      mark(out, o === REF, o + " has the largest share, so " + o + " is the answer. Marked " + (o === REF ? "right." : "wrong."));
    }
    function setCut(i, v) {
      var lo = (i === 0 ? 0 : cuts[i - 1]) + MIN, hi = (i === 2 ? 100 : cuts[i + 1]) - MIN;
      cuts[i] = Math.max(lo, Math.min(hi, Math.round(v))); drawBar();
    }
    grips.forEach(function (g, i) {
      g.hidden = false;
      var drag = false;
      var move = function (e) { var r = bar.getBoundingClientRect(); setCut(i, (e.clientX - r.left) / r.width * 100); };
      g.addEventListener("pointerdown", function (e) { drag = true; g.setPointerCapture(e.pointerId); e.preventDefault(); g.focus(); });
      g.addEventListener("pointermove", function (e) { if (drag) { move(e); } });
      g.addEventListener("pointerup", function () { drag = false; });
      g.addEventListener("pointercancel", function () { drag = false; });
      g.addEventListener("keydown", function (e) {
        var d = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -10, PageUp: 10 }[e.key];
        if (d) { setCut(i, cuts[i] + d); e.preventDefault(); }
      });
    });

    /* generation: what the model writes, and the little of it the parser sees */
    var OUTS = [
      "(A)",
      "One week after 3 March is 10 March. In MM/DD/YYYY that is 03/10/2021. The answer is (A).",
      "One week after 3 March is 10 March, so the date is 03/10/2021."
    ];
    var PAT = /\(([A-D])\)/, input = $("#gen-input"), seen = $("#gen-seen"), links = $$(".try .inl", gen);
    var bars = function (t) { return t.split(/(\s+)/).map(function (w) { return !w || /^\s+$/.test(w) ? w : '<span class="bar">' + esc(w) + "</span>"; }).join(""); };
    function drawGen() {
      var text = input.value, m = PAT.exec(text), res = $(".mark", gen);
      input.style.height = "auto"; input.style.height = input.scrollHeight + "px";
      if (m) {
        seen.innerHTML = bars(text.slice(0, m.index)) + '<span class="found">' + esc(m[0]) + "</span>" + bars(text.slice(m.index + m[0].length));
        mark(res, m[1] === REF, "The parser finds " + m[1] + ". Marked " + (m[1] === REF ? "right." : "wrong."));
      } else {
        seen.innerHTML = bars(text) || "&nbsp;";
        mark(res, false, "The parser finds no letter. Marked wrong" + (text.indexOf("03/10/2021") >= 0 ? ", with the right date written in the answer." : "."));
      }
    }
    $(".try", gen).hidden = false; input.readOnly = false; input.rows = 1;
    links.forEach(function (b) {
      b.addEventListener("click", function () {
        links.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        input.value = OUTS[+b.dataset.out]; drawGen();
      });
    });
    input.addEventListener("input", function () { links.forEach(function (x) { x.setAttribute("aria-pressed", "false"); }); drawGen(); });
    window.addEventListener("resize", drawGen);
    drawGen();
  })();

  /* ---------- rescaling: a second ruler that starts at chance ---------- */
  (function () {
    var fig = $("#fig-rescale"); if (!fig) { return; }
    reveal(fig);
    var svg = $("svg", fig), cursor = $("#rs-cursor"), hit = $("#rs-hit"), lower = $("#rs-lower");
    var NS = "http://www.w3.org/2000/svg", X0 = 44, X1 = 660, raw = 32.8859, k = 4, base = 25, exact = true;   // exact: a value with more digits than its label shows
    var X = function (v) { return X0 + (X1 - X0) * v / 100; };
    var fmt = function (v) { return (Math.round(v * 100) / 100).toFixed(2).replace(/\.?0+$/, ""); };
    var fmt3 = function (v) { return exact ? (Math.round(v * 1000) / 1000).toFixed(3) : fmt(v); };
    var el = function (name, attrs, text) { var n = document.createElementNS(NS, name); Object.keys(attrs).forEach(function (a) { n.setAttribute(a, attrs[a]); }); if (text !== undefined) { n.textContent = text; } return n; };
    function drawLower() {
      var XL = function (v) { return X(base + (100 - base) * v / 100); }, step = (XL(1) - XL(0)) >= 3.6 ? 1 : 5;
      lower.textContent = "";
      lower.appendChild(el("rect", { "class": "ruler low", x: X(base) - 12, y: 94, width: 672 - X(base) + 12, height: 42 }));
      for (var v = 0; v <= 100; v += step) {
        lower.appendChild(el("line", { "class": "rt", x1: XL(v), y1: 94, x2: XL(v), y2: 94 + (v % 10 === 0 ? 14 : v % 5 === 0 ? 9 : 5) }));
        if (v % 10 === 0) { lower.appendChild(el("text", { "class": "rn", x: XL(v), y: 123, "text-anchor": "middle" }, v)); }
      }
      lower.appendChild(el("text", { "class": "rchance", x: X(base) - 18, y: 119, "text-anchor": "end" }, "chance " + fmt(Math.round(base * 10) / 10)));
    }
    function drawCursor() {
      var shown = Math.max(0, (raw - base) / (100 - base) * 100);
      cursor.setAttribute("transform", "translate(" + X(raw) + ",0)");
      cursor.setAttribute("aria-valuenow", fmt(raw)); cursor.setAttribute("aria-valuetext", "measured " + fmt(raw) + ", shown " + fmt(shown));
      $("#rs-traw").textContent = (Math.round(raw * 100) / 100).toFixed(2);
      $("#rs-tshown").textContent = (Math.round(shown * 100) / 100).toFixed(2);
      var chance = 100 / k;
      $("#rs-formula").innerHTML = raw <= chance
        ? fmt(raw) + " is at or below chance (" + fmt(chance) + "), so the score shown is 0"
        : "(" + fmt3(raw) + " &minus; " + fmt(chance) + ") / (100 &minus; " + fmt(chance) + ") &times; 100 = " + fmt(Math.max(0, (raw - chance) / (100 - chance) * 100));
    }
    var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches, anim = null;
    function slideTo(target) {   // the lower ruler slides to its new zero
      window.cancelAnimationFrame(anim);
      if (still) { base = target; drawLower(); drawCursor(); return; }
      var from = base, t0 = null;
      anim = window.requestAnimationFrame(function tick(t) {
        if (t0 === null) { t0 = t; }
        var p = Math.min(1, (t - t0) / 280), e = 1 - Math.pow(1 - p, 3);
        base = from + (target - from) * e; drawLower(); drawCursor();
        if (p < 1) { anim = window.requestAnimationFrame(tick); } else { base = target; drawLower(); drawCursor(); }
      });
    }
    var kBtns = $$("#rs-k .inl", fig), exBtns = $$("#rs-ex .inl", fig);
    var pressOnly = function (list, test) { list.forEach(function (b) { b.setAttribute("aria-pressed", test(b) ? "true" : "false"); }); };
    function setK(v) { k = v; pressOnly(kBtns, function (b) { return +b.dataset.k === k; }); slideTo(100 / k); }
    function setRaw(v) { raw = Math.max(0, Math.min(100, v)); exact = false; pressOnly(exBtns, function () { return false; }); drawCursor(); }
    function fromPointer(e) {
      var p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
      var q = p.matrixTransform(svg.getScreenCTM().inverse());
      setRaw(Math.round((q.x - X0) / (X1 - X0) * 1000) / 10);
    }
    var dragging = false;
    [cursor, hit].forEach(function (t) {
      t.addEventListener("pointerdown", function (e) { dragging = true; t.setPointerCapture(e.pointerId); fromPointer(e); e.preventDefault(); });
      t.addEventListener("pointermove", function (e) { if (dragging) { fromPointer(e); } });
      t.addEventListener("pointerup", function () { dragging = false; });
      t.addEventListener("pointercancel", function () { dragging = false; });
    });
    cursor.addEventListener("keydown", function (e) {
      var d = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -10, PageUp: 10 }[e.key];
      if (e.key === "Home") { setRaw(0); } else if (e.key === "End") { setRaw(100); } else if (d) { setRaw(Math.round(raw) + d); } else { return; }
      e.preventDefault();
    });
    kBtns.forEach(function (b) { b.addEventListener("click", function () { pressOnly(exBtns, function () { return false; }); setK(+b.dataset.k); }); });
    exBtns.forEach(function (b) { b.addEventListener("click", function () { raw = parseFloat(b.dataset.raw); exact = true; pressOnly(exBtns, function (x) { return x === b; }); setK(+b.dataset.k); }); });
    drawLower(); drawCursor();
  })();

  /* ---------- protocol variants: a difference and its counterpart ---------- */
  $$(".pcol, .pflow").forEach(function (col) {
    var parts = $$(".df", col);
    function show(k) { parts.forEach(function (p) { p.classList.toggle("on", !!k && p.dataset.d === k); }); }
    parts.forEach(function (p) {
      p.addEventListener("mouseenter", function () { show(p.dataset.d); }); p.addEventListener("mouseleave", function () { show(null); });
      p.addEventListener("focus", function () { show(p.dataset.d); }); p.addEventListener("blur", function () { show(null); });
    });
  });

  /* ---------- 291 pairs: pick out one band ---------- */
  (function () {
    var fig = $("#fig-overlap"); if (!fig) { return; }
    var grid = $(".waffle", fig), cells = $$("i", grid), rows = $$(".bands li", fig);
    function show(b) {
      grid.classList.toggle("sel", !!b);
      cells.forEach(function (c) { c.classList.toggle("on", c.dataset.b === b); });
      rows.forEach(function (r) { r.classList.toggle("on", r.dataset.b === b); });
    }
    rows.forEach(function (r) {
      r.addEventListener("mouseenter", function () { show(r.dataset.b); }); r.addEventListener("focus", function () { show(r.dataset.b); });
      r.addEventListener("mouseleave", function () { show(null); }); r.addEventListener("blur", function () { show(null); });
    });
    grid.addEventListener("mouseover", function (e) { if (e.target.dataset && e.target.dataset.b) { show(e.target.dataset.b); } });
    grid.addEventListener("mouseleave", function () { show(null); });
  })();

  /* ---------- answer parser ---------- */
  (function () {
    var fig = $("#fig-parser"); if (!fig) { return; }
    reveal(fig);
    var REFERENCE = "18", mode = "strict";
    var norm = function (a) { return a.replace(/[$,]/g, "").replace(/\.+$/, ""); };
    function extract(text) {
      if (mode === "strict") { var m = /####\s+(\S+)/.exec(text); return m ? m[1] : null; }
      var all = text.match(/-?\d[\d,]*(?:\.\d+)?/g); return all ? all[all.length - 1] : null;
    }
    function verdict(text) {
      var got = extract(text);
      if (got === null) { return '<b class="wrong">No match</b><br>response recorded as invalid<br>exact_match = 0'; }
      var ok = norm(got) === REFERENCE;
      return '<b class="' + (ok ? "right" : "wrong") + '">Match: \'' + esc(got) + "'</b><br>reference: 18<br>exact_match = " + (ok ? 1 : 0);
    }
    var runs = $$(".run[data-run]", fig).map(function (run) {
      var area = $("textarea", run), v = $(".verdict", run), restore = $(".linkbtn", run), acc = $(".acc", run), original = area.dataset.original, timer;
      function update() {
        v.innerHTML = verdict(area.value);
        restore.hidden = area.value === original;
        acc.innerHTML = mode === "strict" ? acc.dataset.strict + "<small>accuracy over 200 problems</small>" : "<small>accuracy under this parser was not measured</small>";
      }
      area.addEventListener("input", function () { window.clearTimeout(timer); timer = window.setTimeout(update, 200); });
      restore.addEventListener("click", function () { area.value = original; update(); area.focus(); });
      $("label", run).textContent += " (editable)";
      return update;
    });
    var group = $(".btngroup", fig);
    $$("button", group).forEach(function (b) {
      b.addEventListener("click", function () {
        mode = b.dataset.parser; press(group, b);
        $("#parser-pattern").textContent = mode === "strict" ? "re.search(r'####\\s+(\\S+)', output)" : "last number found in the output";
        runs.forEach(function (u) { u(); });
      });
    });
    runs.forEach(function (u) { u(); });
  })();

  /* ---------- heat table: read a cell as a sentence ---------- */
  (function () {
    var fig = $("#fig-heat"); if (!fig) { return; }
    var status = $("#heat-status"), heads = $$("thead th", fig), initial = status.innerHTML;
    $$("td.c", fig).forEach(function (td) {
      if (td.classList.contains("na")) { return; }
      var tr = td.parentNode, col = td.cellIndex, f = heads[col].dataset.f, b = tr.dataset.b, v = td.textContent.replace("*", "");
      function on() {
        $$(".x", fig).forEach(function (el) { el.classList.remove("x"); }); td.classList.add("x");
        var s = "On " + b + ", runs that differ only in " + f + " are " + v + " pp apart on average.";
        if (f !== "two random seeds" && tr.dataset.seed) { s += " Two seeds differ by " + tr.dataset.seed + " pp there."; }
        if (td.dataset.note) { s += " " + td.dataset.note; }
        status.textContent = s;
      }
      td.addEventListener("mouseenter", on); td.addEventListener("focus", on); td.addEventListener("click", on);
    });
    $("table", fig).addEventListener("mouseleave", function () { $$(".x", fig).forEach(function (el) { el.classList.remove("x"); }); status.innerHTML = initial; });
  })();

  /* ---------- judges ---------- */
  (function () {
    var fig = $("#fig-judges"); if (!fig) { return; }
    var status = $("#judges-status"), models = $$("g.model", fig), overlay = $(".overlay", fig), pinned = "Ministral-8B";
    var NS = "http://www.w3.org/2000/svg";
    function set(name) {
      models.forEach(function (g) {
        var on = g.dataset.m === name; g.classList.toggle("on", on); if (!on) { return; }
        var v = g.dataset.v.split(","), r = g.dataset.ranks.split(",");
        // draw the chosen model again on top, so nothing paints over it; the original stays where it is
        overlay.textContent = "";
        overlay.appendChild($(".jl", g).cloneNode(false));
        $$(".jd", g).forEach(function (c, idx) {
          overlay.appendChild(c.cloneNode(false));
          var t = document.createElementNS(NS, "text");
          t.setAttribute("class", "jv"); t.setAttribute("x", c.getAttribute("cx")); t.setAttribute("y", parseFloat(c.getAttribute("cy")) - 10); t.setAttribute("text-anchor", "middle");
          t.textContent = v[idx]; overlay.appendChild(t);
        });
        status.textContent = name + " is rated " + v.slice(0, 3).join(", ") + " and " + v[3] + ", which ranks it " + r.slice(0, 3).join(", ") + " and " + r[3] + " of the five.";
      });
    }
    models.forEach(function (g) {
      var n = g.dataset.m;
      g.addEventListener("mouseenter", function () { set(n); });
      g.addEventListener("focus", function () { set(n); });
      g.addEventListener("click", function () { pinned = n; set(n); });
      g.addEventListener("mouseleave", function () { set(pinned); });
      g.addEventListener("blur", function () { set(pinned); });
    });
  })();

  /* ---------- worked example: released or filled in ---------- */
  (function () {
    var fig = $("#fig-worked"); if (!fig) { return; }
    var group = $(".btngroup", fig); group.hidden = false;
    $$("button", group).forEach(function (b) {
      b.addEventListener("click", function () { press(group, b); fig.classList.toggle("released", b.dataset.view === "released"); });
    });
  })();

  /* ---------- copy ---------- */
  $$("[data-copy]").forEach(function (btn) {
    var target = document.getElementById(btn.dataset.copy); if (!target || !navigator.clipboard) { return; }
    var label = btn.textContent; btn.hidden = false;
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(target.textContent).then(function () { btn.textContent = "Copied"; }, function () { btn.textContent = "Select the text and copy"; })
        .then(function () { window.setTimeout(function () { btn.textContent = label; }, 1800); });
    });
  });
})();
