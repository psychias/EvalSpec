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

  /* ---------- scoring modes ---------- */
  (function () {
    var ll = $("#mode-ll"), gen = $("#mode-gen"); if (!ll || !gen) { return; }
    var REF = "A";
    var badge = function (ok) { return '<span class="badge">' + (ok ? "right" : "wrong") + "</span> "; };
    function verdict(el, ok, html) { el.className = "outcome " + (ok ? "good" : "bad"); el.innerHTML = badge(ok) + html; }
    function updateLL() {
      var rows = $$(".optrow", ll), best = null, bestV = -1, tie = false;
      rows.forEach(function (r) {
        var v = parseFloat($("input", r).value);
        $(".lp", r).textContent = v;
        if (v > bestV) { bestV = v; best = r; tie = false; } else if (v === bestV) { tie = true; }
      });
      rows.forEach(function (r) { r.classList.toggle("pick", r === best && !tie); });
      var out = $(".outcome", ll);
      if (tie) { out.className = "outcome"; out.textContent = "Two options tie. Drag a handle to break the tie."; return; }
      var o = best.dataset.opt;
      verdict(out, o === REF, "The model picks <b>" + o + "</b>. The reference is " + REF + ".");
    }
    $$("input[type=range]", ll).forEach(function (i) { i.disabled = false; i.addEventListener("input", updateLL); });

    var OUTS = [
      "(A)",
      "One week after 3 March is 10 March. In MM/DD/YYYY that is 03/10/2021. The answer is (A).",
      "One week after 3 March is 10 March, so the date is 03/10/2021."
    ];
    var PAT = /\(([A-D])\)/, input = $("#gen-input"), tokens = $("#gen-tokens"), group = $(".btngroup", gen);
    function updateGen() {
      var text = input.value, m = PAT.exec(text), res = $(".outcome", gen), pos = 0;
      tokens.innerHTML = text.split(/(\s+)/).map(function (w) {
        var start = pos; pos += w.length;
        if (!w.trim()) { return ""; }
        var hit = m && m.index >= start && m.index < start + w.length;
        return "<span" + (hit ? ' class="hit"' : "") + ">" + esc(w) + "</span>";
      }).join("");
      if (m) { verdict(res, m[1] === REF, "The parser extracts <b>" + m[1] + "</b>. The reference is " + REF + "."); }
      else { verdict(res, false, "The parser finds no letter in brackets, so there is nothing to compare with the reference."); }
    }
    group.hidden = false;
    $$("button", group).forEach(function (b) {
      b.addEventListener("click", function () {
        var own = b.dataset.out === "own";
        press(group, b); input.hidden = !own;
        if (own) { input.focus(); input.select(); } else { input.value = OUTS[+b.dataset.out]; }
        updateGen();
      });
    });
    input.addEventListener("input", updateGen);
  })();

  /* ---------- rescaling: drag the measured accuracy ---------- */
  (function () {
    var fig = $("#fig-rescale"); if (!fig) { return; }
    reveal(fig);
    var svg = $("svg", fig), dot = $("#rs-draw"), hit = $("#rs-hit");
    var X0 = 46, X1 = 658, YT = 70, YB = 160, raw = 32.8859, k = 4, exact = true;   // exact: a starting value with more digits than its label shows
    var X = function (v) { return X0 + (X1 - X0) * v / 100; };
    var fmt = function (v) { return (Math.round(v * 100) / 100).toFixed(2).replace(/\.?0+$/, ""); };
    var fmt3 = function (v) { return exact ? (Math.round(v * 1000) / 1000).toFixed(3) : fmt(v); };
    var at = function (el, attrs) { Object.keys(attrs).forEach(function (a) { el.setAttribute(a, attrs[a]); }); };
    function draw() {
      var base = 100 / k, shown = Math.max(0, (raw - base) / (100 - base) * 100);
      at($("#rs-below"), { width: X(base) - X0 });
      at($("#rs-chance"), { x1: X(base), x2: X(base) });
      var ct = $("#rs-chancet"); at(ct, { x: X(base) }); ct.textContent = "chance " + fmt(base);
      $$("#rs-fan .fan", fig).forEach(function (l, t) { at(l, { x1: X(base + (100 - base) * t / 5), x2: X(100 * t / 5) }); });
      at($("#rs-map"), { x1: X(raw), x2: X(shown) });
      at(dot, { cx: X(raw), "aria-valuenow": fmt(raw), "aria-valuetext": "measured " + fmt(raw) + ", shown " + fmt(shown) });
      at($("#rs-dshown"), { cx: X(shown) });
      var tr = $("#rs-traw"), ts = $("#rs-tshown");
      at(tr, { x: X(raw) }); tr.textContent = (Math.round(raw * 100) / 100).toFixed(2);
      at(ts, { x: X(shown) }); ts.textContent = (Math.round(shown * 100) / 100).toFixed(2);
      $("#rs-formula").innerHTML = raw <= base
        ? fmt(raw) + " is at or below chance (" + fmt(base) + "), so the score shown is 0"
        : "(" + fmt3(raw) + " &minus; " + fmt(base) + ") / (100 &minus; " + fmt(base) + ") &times; 100 = " + fmt(shown);
    }
    var kGroup = $("#rs-k"), exGroup = $("#rs-ex");
    function setK(v) { k = v; $$("button", kGroup).forEach(function (b) { b.setAttribute("aria-pressed", +b.dataset.k === k ? "true" : "false"); }); }
    function setRaw(v) { raw = Math.max(0, Math.min(100, v)); exact = false; press(exGroup, null); draw(); }
    function fromPointer(e) {
      var p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
      var q = p.matrixTransform(svg.getScreenCTM().inverse());
      setRaw(Math.round((q.x - X0) / (X1 - X0) * 1000) / 10);
    }
    var dragging = false;
    [dot, hit].forEach(function (el) {
      el.addEventListener("pointerdown", function (e) { dragging = true; el.setPointerCapture(e.pointerId); fromPointer(e); e.preventDefault(); });
      el.addEventListener("pointermove", function (e) { if (dragging) { fromPointer(e); } });
      el.addEventListener("pointerup", function () { dragging = false; });
      el.addEventListener("pointercancel", function () { dragging = false; });
    });
    dot.addEventListener("keydown", function (e) {
      var d = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -10, PageUp: 10 }[e.key];
      if (e.key === "Home") { setRaw(0); } else if (e.key === "End") { setRaw(100); } else if (d) { setRaw(Math.round(raw) + d); } else { return; }
      e.preventDefault();
    });
    $$("button", kGroup).forEach(function (b) { b.addEventListener("click", function () { setK(+b.dataset.k); press(exGroup, null); draw(); }); });
    $$("button", exGroup).forEach(function (b) { b.addEventListener("click", function () { raw = parseFloat(b.dataset.raw); exact = true; setK(+b.dataset.k); press(exGroup, b); draw(); }); });
    draw();
  })();

  /* ---------- records: the sentence and the line point at each other ---------- */
  $$(".hl[data-part]").forEach(function (t) {
    var fig = t.closest("figure"), seg = fig && $('.seg[data-part="' + t.dataset.part + '"]', fig); if (!seg) { return; }
    var on = function () { seg.classList.add("is-hl"); t.classList.add("is-hl"); }, off = function () { seg.classList.remove("is-hl"); t.classList.remove("is-hl"); };
    [t, seg].forEach(function (el) { el.addEventListener("mouseenter", on); el.addEventListener("mouseleave", off); el.addEventListener("focus", on); el.addEventListener("blur", off); });
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
    if (btn.classList.contains("es-btn")) { return; }   // the site's own buttons are handled by site.js
    var target = document.getElementById(btn.dataset.copy); if (!target || !navigator.clipboard) { return; }
    var label = btn.textContent; btn.hidden = false;
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(target.textContent).then(function () { btn.textContent = "Copied"; }, function () { btn.textContent = "Select the text and copy"; })
        .then(function () { window.setTimeout(function () { btn.textContent = label; }, 1800); });
    });
  });
})();
