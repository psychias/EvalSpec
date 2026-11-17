/* Registry page: the transparency board, the records explorer, and the model and benchmark pairs
   that have more than one record. Everything is computed in the browser from data/registry.js,
   so the three views always agree with each other and with the track switch.
   The state of the page is kept in the address: registry.html#records?q=gemma&track=author */
(function () {
  "use strict";
  var ES = window.ES, P = window.EVALSPEC_REGISTRY;
  if (!ES || !P) { return; }
  ES.decode(P);
  var $ = ES.$, $$ = ES.$$, esc = ES.esc, num = ES.num, C = P.cols, S = P.strings;
  var TABS = ["board", "records", "cells"];
  var state = { tab: "board", track: "all", q: "", mode: "", source: "",
                board: { sort: "rank", dir: 1 }, records: { sort: "have", dir: -1, page: 1, size: 50 }, cells: { sort: "", dir: -1, page: 1, size: 50 } };
  // the Required fields that describe the procedure: all but the two that name the model and the benchmark
  var PROCEDURE = ES.spec.fields.map(function (f, j) { return { name: f.name, j: j, tier: f.tier }; })
    .filter(function (f) { return f.tier === "required" && f.name !== "model_id" && f.name !== "benchmark_id"; });
  var CLASS = [null, "first_hand", "llm", "inferred"];

  function inTrack(i) { return state.track === "all" || (state.track === "author") === (C.track[i] === 1); }

  /* ---------- the address ---------- */
  function readAddress() {
    var parts = window.location.hash.slice(1).split("?"), q = new URLSearchParams(parts[1] || "");
    state.tab = TABS.indexOf(parts[0]) >= 0 ? parts[0] : "board";
    state.track = ["author", "predicted"].indexOf(q.get("track")) >= 0 ? q.get("track") : "all";
    state.q = q.get("q") || ""; state.mode = q.get("mode") || "";
    state.source = P.sources.some(function (s) { return s.key === q.get("source"); }) ? q.get("source") : "";
    state.records.page = +q.get("page") || 1;
  }
  function writeAddress() {
    var q = new URLSearchParams();
    if (state.track !== "all") { q.set("track", state.track); }
    if (state.tab === "records") {
      if (state.q) { q.set("q", state.q); }
      if (state.mode) { q.set("mode", state.mode); }
      if (state.source) { q.set("source", state.source); }
      if (state.records.page > 1) { q.set("page", state.records.page); }
    }
    var text = q.toString(), hash = "#" + state.tab + (text ? "?" + text : "");
    if (hash !== window.location.hash && !(hash === "#board" && !window.location.hash)) { window.history.replaceState(null, "", hash); }
  }

  /* ---------- transparency board ---------- */
  function boardRows() {
    var rows = P.sources.map(function (s) {
      var fields = {};
      PROCEDURE.forEach(function (f) { fields[f.name] = { of: 0, have: 0, first_hand: 0, llm: 0, inferred: 0 }; });
      return { s: s, n: 0, author: 0, superseded: 0, models: {}, cov: { of: 0, have: 0, first_hand: 0, llm: 0, inferred: 0 }, fields: fields };
    });
    for (var i = 0; i < P.n; i++) {
      if (!inTrack(i)) { continue; }
      var row = rows[C.source[i]], sig = S[C.sig[i]];
      row.n++; row.author += C.track[i]; row.models[C.model[i]] = true;
      if (C.sup[i]) { row.superseded++; continue; }           // listed, but no longer counted
      for (var k = 0; k < PROCEDURE.length; k++) {
        var code = +sig.charAt(PROCEDURE[k].j), f = row.fields[PROCEDURE[k].name];
        if (code === 5) { continue; }
        f.of++; row.cov.of++;
        if (code >= 1 && code <= 3) { f.have++; f[CLASS[code]]++; row.cov.have++; row.cov[CLASS[code]]++; }
      }
    }
    rows = rows.filter(function (r) { return r.n > 0; });
    rows.forEach(function (r) {
      r.models = Object.keys(r.models).length;
      r.shares = ["first_hand", "llm", "inferred"].map(function (k) { return r.cov.of ? Math.round(1e6 * r.cov[k] / r.cov.of) / 1e6 : 0; });
    });
    // most first-hand first; then what a language model could read from the source; then what a pipeline inferred
    rows.sort(function (a, b) {
      var x = a.s.label.toLowerCase(), y = b.s.label.toLowerCase();       // plain comparison, as the build does
      return b.shares[0] - a.shares[0] || b.shares[1] - a.shares[1] || b.shares[2] - a.shares[2] || b.n - a.n || (x < y ? -1 : x > y ? 1 : 0);
    });
    rows.forEach(function (r, i) {
      var prev = rows[i - 1];
      r.rank = prev && prev.shares.join() === r.shares.join() ? prev.rank : i + 1;
    });
    return rows;
  }
  function boardDetail(r) {
    var grid = PROCEDURE.filter(function (f) { return r.fields[f.name].of; }).map(function (f) {
      var c = r.fields[f.name];
      return "<li><code>" + esc(f.name) + '</code><span class="es-cov">' + ES.meter(c, true) + "<span>" + num(c.have) + " of " + num(c.of) + "</span></span></li>";
    }).join("");
    var predicted = r.n - r.author, what = [];
    if (r.author) { what.push(ES.plural(r.author, "author-reported record")); }
    if (predicted) { what.push(ES.plural(predicted, "predicted record")); }
    var text = what.join(" and ") + (r.superseded ? ", of which " + num(r.superseded) + " superseded by the source's own" : "") + ".";
    var nudge = !r.author ? " Nothing here was reported by the source itself. If these are your results, open a record and choose Correct this record, or " +
                            '<a href="submit.html">submit your own</a>: the source then moves up the board.' : "";
    return '<div class="es-detail-in"><p class="es-small" style="margin-bottom:10px">' + text + nudge + "</p>" +
      '<ul class="es-grid">' + grid + "</ul>" +
      '<p class="es-small" style="margin:12px 0 0"><button class="es-expander" type="button" data-source="' + esc(r.s.key) + '">Show the records of this source</button>' +
      (r.s.url ? ' <a href="' + esc(r.s.url) + '" style="margin-left:14px">Open the source</a>' : "") + "</p></div>";
  }
  var board = [];
  function drawBoard() {
    board = boardRows();
    var st = state.board, get = {
      rank: function (r) { return r.rank; }, label: function (r) { return r.s.label.toLowerCase(); }, n: function (r) { return r.n; },
      models: function (r) { return r.models; }, first: function (r) { return r.shares[0]; }, have: function (r) { return r.cov.of ? r.cov.have / r.cov.of : 0; }
    }[st.sort];
    var rows = board.slice();
    if (st.sort !== "rank" || st.dir < 0) {
      rows.sort(function (a, b) { var x = get(a), y = get(b); return (x < y ? -1 : x > y ? 1 : 0) * st.dir || a.rank - b.rank; });
    }
    var body = $("#board tbody");
    body.innerHTML = rows.map(function (r) {
      return '<tr class="es-click" data-key="' + esc(r.s.key) + '">' +
        '<td class="es-rank">' + r.rank + "</td>" +
        "<td>" + esc(r.s.label) + '<span class="es-sub">' + esc(r.s.kind) + (r.s.ref ? ", " + esc(r.s.ref) : "") + "</span></td>" +
        '<td class="es-num">' + num(r.n) + '</td><td class="es-num">' + num(r.models) + "</td>" +
        "<td>" + ES.meter(r.cov) + "</td>" +
        '<td class="es-num">' + ES.pct(r.cov.first_hand, r.cov.of) + '</td><td class="es-num">' + ES.pct(r.cov.have, r.cov.of) + "</td>" +
        ES.toggleCell("the fields reported by " + r.s.label) + "</tr>";
    }).join("") || '<tr><td colspan="8"><div class="es-empty"><p class="es-emptyhead">No ' + (state.track === "author" ? "author-reported" : "predicted") +
      ' records yet</p><p>The first source to report its own evaluation procedure will be listed here. <a href="submit.html">Submit a report</a>.</p></div></td></tr>';
    $("#count-board").textContent = num(board.length);
  }

  /* ---------- records ---------- */
  var hay = null, matched = [];
  function haystack() {
    if (!hay) {
      hay = new Array(P.n);
      for (var i = 0; i < P.n; i++) {
        hay[i] = ES.flat(P.models[C.model[i]].id + " " + S[C.mid[i]]) + " " + ES.flat(P.benches[C.bench[i]].label + " " + S[C.bname[i]]) + " " +
                 ES.flat(P.sources[C.source[i]].label);
      }
    }
    return hay;
  }
  function filterRecords() {
    var words = state.q.split(/\s+/).map(ES.flat).filter(Boolean), h = words.length ? haystack() : null;
    var source = state.source ? P.sources.findIndex(function (s) { return s.key === state.source; }) : -1;
    matched = [];
    for (var i = 0; i < P.n; i++) {
      if (!inTrack(i) || (source >= 0 && C.source[i] !== source)) { continue; }
      if (state.mode && (S[C.scoring_mode[i]] || "not recorded") !== state.mode) { continue; }
      if (h && !words.every(function (w) { return h[i].indexOf(w) >= 0; })) { continue; }
      matched.push(i);
    }
    var st = state.records, get = {
      model: function (i) { return P.models[C.model[i]].id.toLowerCase(); }, bench: function (i) { return P.benches[C.bench[i]].label.toLowerCase(); },
      score: function (i) { return C.pct[i] === null ? C.score[i] : C.pct[i]; }, source: function (i) { return P.sources[C.source[i]].label.toLowerCase(); },
      have: function (i) { return C.first[i] / C.of[i] + C.have[i] / C.of[i] / 1000; }
    }[st.sort];
    matched.sort(function (a, b) { var x = get(a), y = get(b); return (x < y ? -1 : x > y ? 1 : 0) * st.dir || a - b; });
  }
  function drawRecords() {
    filterRecords();
    var st = state.records, total = 0;
    for (var i = 0; i < P.n; i++) { if (inTrack(i)) { total++; } }
    ES.pager($("#records-pager"), matched.length, st, function () { drawRecords(); writeAddress(); $("#records").scrollIntoView({ block: "nearest" }); });
    var rows = matched.slice((st.page - 1) * st.size, st.page * st.size);
    $("#records tbody").innerHTML = rows.map(function (i) {
      var m = P.models[C.model[i]], cov = { of: C.of[i], have: C.have[i], first_hand: C.first[i], llm: C.llm[i], inferred: C.have[i] - C.first[i] - C.llm[i] };
      var harness = S[C.harness_name[i]], version = S[C.harness_version[i]], shots = S[C.n_shot[i]];
      return '<tr class="es-click" data-i="' + i + '">' +
        '<td class="es-id"><a href="' + esc(ES.modelUrl(m.id)) + '">' + esc(m.id) + "</a></td>" +
        "<td>" + esc(P.benches[C.bench[i]].label) + "</td>" +
        '<td class="es-num">' + ES.score(C.score[i], C.hi[i]) + "</td>" +
        "<td>" + ES.modeLabel(S[C.scoring_mode[i]]) + "</td>" +
        "<td>" + (harness ? esc(harness) + (version ? " " + esc(version) : "") : '<span class="es-hollow">not on record</span>') + "</td>" +
        '<td class="es-num">' + (shots ? esc(shots) : '<span class="es-hollow">?</span>') + "</td>" +
        "<td>" + esc(P.sources[C.source[i]].label) + '<span class="es-sub">' + (C.track[i] ? "author-reported" : "predicted") + (C.sup[i] ? ", superseded" : "") + "</span></td>" +
        '<td><span class="es-cov">' + ES.meter(cov, true) + "<span>" + C.have[i] + " of " + C.of[i] + "</span></span></td>" +
        ES.toggleCell("the record of " + m.id + " on " + P.benches[C.bench[i]].label + " from " + P.sources[C.source[i]].label) + "</tr>";
    }).join("") || '<tr><td colspan="9"><div class="es-empty"><p class="es-emptyhead">No record matches</p><p>Change the filter, or look a model up by its Hugging Face id.</p></div></td></tr>';
    $("#records-status").textContent = matched.length === total ? ES.plural(total, "record") : num(matched.length) + " of " + ES.plural(total, "record") + " match";
    $("#count-records").textContent = num(total);
  }

  /* ---------- same model, same benchmark ---------- */
  function drawCells() {
    var st = state.cells, cells = P.cells.filter(function (c) {
      return state.track === "all" || (state.track === "author" ? c.author > 0 : c.n - c.author > 0);
    });
    if (st.sort) {
      var get = { model: function (c) { return P.models[c.model].id.toLowerCase(); }, bench: function (c) { return P.benches[c.bench].label.toLowerCase(); },
                  sources: function (c) { return c.sources; }, spread: function (c) { return c.spread === null ? -1 : c.spread; } }[st.sort];
      cells = cells.slice().sort(function (a, b) { var x = get(a), y = get(b); return (x < y ? -1 : x > y ? 1 : 0) * st.dir; });
    }
    ES.pager($("#cells-pager"), cells.length, st, function () { drawCells(); $("#cells").scrollIntoView({ block: "nearest" }); });
    $("#cells tbody").innerHTML = cells.slice((st.page - 1) * st.size, st.page * st.size).map(function (c) {
      var m = P.models[c.model], b = P.benches[c.bench];
      return '<tr><td class="es-id"><a href="' + esc(ES.modelUrl(m.id, b.key)) + '">' + esc(m.id) + "</a></td><td>" + esc(b.label) + "</td>" +
        '<td class="es-num">' + c.sources + '<span class="es-sub">' + ES.plural(c.n, "record") + "</span></td>" +
        '<td class="es-num">' + (c.spread === null ? '<span class="es-hollow">scales differ</span>' : c.spread.toFixed(2) + " pp") + "</td>" +
        "<td>" + ES.sameWay(c) + "</td><td>" + ES.independent(c) + "</td></tr>";
    }).join("") || '<tr><td colspan="6"><div class="es-empty"><p>No model and benchmark pair has more than one record in this track.</p></div></td></tr>';
    var multi = cells.filter(function (c) { return c.sources > 1; }).length;
    $("#cells-status").textContent = ES.plural(cells.length, "pair") + " with more than one record, " + num(multi) + " of them reported by more than one source.";
    $("#count-cells").textContent = num(cells.length);
  }

  /* ---------- wiring ---------- */
  function draw() {
    TABS.forEach(function (t) {
      var on = t === state.tab;
      $("#tab-" + t).setAttribute("aria-selected", String(on));
      $("#tab-" + t).tabIndex = on ? 0 : -1;
      $("#view-" + t).hidden = !on;
    });
    $$("#track button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.track === state.track)); });
    $("#q").value = state.q; $("#f-mode").value = state.mode; $("#f-source").value = state.source;
    drawBoard(); drawRecords(); drawCells();
    writeAddress();
  }

  Object.keys(P.stats.modes).forEach(function (m) { $("#f-mode").insertAdjacentHTML("beforeend", '<option value="' + esc(m) + '">' + esc(m) + "</option>"); });
  P.sources.slice().sort(function (a, b) { return a.label.toLowerCase().localeCompare(b.label.toLowerCase()); }).forEach(function (s) {
    $("#f-source").insertAdjacentHTML("beforeend", '<option value="' + esc(s.key) + '">' + esc(s.label.length > 60 ? s.label.slice(0, 58) + "…" : s.label) + "</option>");
  });

  TABS.forEach(function (t, n) {
    var tab = $("#tab-" + t);
    tab.addEventListener("click", function () { state.tab = t; draw(); });
    tab.addEventListener("keydown", function (e) {            // arrow keys move between tabs
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") { return; }
      state.tab = TABS[(n + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
      draw(); $("#tab-" + state.tab).focus();
    });
  });
  $$("#track button").forEach(function (b) {
    b.addEventListener("click", function () { state.track = b.dataset.track; state.records.page = state.cells.page = 1; draw(); });
  });
  var typing = null;
  $("#q").addEventListener("input", function () {
    window.clearTimeout(typing);
    typing = window.setTimeout(function () { state.q = $("#q").value.trim(); state.records.page = 1; drawRecords(); writeAddress(); }, 120);
  });
  $("#f-mode").addEventListener("change", function () { state.mode = $("#f-mode").value; state.records.page = 1; drawRecords(); writeAddress(); });
  $("#f-source").addEventListener("change", function () { state.source = $("#f-source").value; state.records.page = 1; drawRecords(); writeAddress(); });

  ES.sortable($("#board"), state.board, drawBoard);
  ES.sortable($("#records"), state.records, function () { state.records.page = 1; drawRecords(); });
  ES.sortable($("#cells"), state.cells, function () { state.cells.page = 1; drawCells(); });
  ES.expandable($("#board tbody"), function (tr) {
    return boardDetail(board.filter(function (r) { return r.s.key === tr.dataset.key; })[0]);
  });
  ES.expandable($("#records tbody"), function (tr) {
    return '<div class="es-detail-in">' + ES.recordDetail(P.record(+tr.dataset.i), { modelLink: true }) + "</div>";
  });
  $("#board").addEventListener("click", function (e) {         // from a source on the board to its records
    var b = e.target.closest("button[data-source]");
    if (!b) { return; }
    state.tab = "records"; state.source = b.dataset.source; state.q = ""; state.mode = ""; state.records.page = 1;
    draw(); $("#tab-records").focus();
  });

  window.addEventListener("hashchange", function () { readAddress(); draw(); });
  readAddress(); draw();
})();
