/* Model page: model.html?id=<Hugging Face id>. Every record the registry holds for one model,
   benchmark by benchmark, with what each source says about how its score was produced. */
(function () {
  "use strict";
  var ES = window.ES, root = document.getElementById("model-root");
  if (!ES || !root) { return; }
  var $ = ES.$, $$ = ES.$$, esc = ES.esc, num = ES.num, plural = ES.plural;
  var asked = (new URLSearchParams(window.location.search).get("id") || "").trim();
  var LOOKUP = '<form class="es-lookup" action="model.html" method="get" role="search" aria-label="Evaluation reports for a model" style="margin:20px 0 0">' +
    '<label class="es-label" for="lookup">Find the evaluation reports for a model</label><div class="es-lookup-row">' +
    '<input class="es-input" id="lookup" name="id" type="search" placeholder="Hugging Face id, for example google/gemma-2-9b" autocomplete="off" spellcheck="false">' +
    '<button class="es-btn" type="submit">Find reports</button></div></form>';
  function withLookup() { ES.lookup($("form.es-lookup", root), "page"); }
  function hubSearch(name) { return "https://huggingface.co/models?search=" + encodeURIComponent(String(name).split("/").pop()); }
  function submitUrl(id) { return "submit.html?record=" + encodeURIComponent(JSON.stringify({ model_id: id })) + "#build"; }

  /* ---------- no id given, or nothing found ---------- */
  function start() {
    root.innerHTML = '<header class="es-modelhead"><h1 style="font-family:var(--sans)">Evaluation reports for a model</h1>' +
      '<p class="es-lead">Enter the Hugging Face id of a model to see every published score the registry holds for it, and what each source says about how the score was produced.</p></header>' +
      LOOKUP + '<div id="known" style="margin-top:28px"></div>';
    withLookup();
    ES.loadModels().then(function (models) {
      var top = models.slice().sort(function (a, b) { return b.sources - a.sources || b.n - a.n || a.id.localeCompare(b.id); }).slice(0, 24);
      $("#known").innerHTML = '<h2 style="font-size:20px">Models with the most sources</h2><div class="es-scroll"><table class="es-table"><thead><tr><th scope="col">Model</th>' +
        '<th scope="col" class="es-num">Sources</th><th scope="col" class="es-num">Records</th><th scope="col" class="es-num">Benchmarks</th></tr></thead><tbody>' +
        top.map(function (m) {
          return '<tr><td class="es-id"><a href="' + esc(ES.modelUrl(m.id)) + '">' + esc(m.id) + '</a></td><td class="es-num">' + num(m.sources) +
                 '</td><td class="es-num">' + num(m.n) + '</td><td class="es-num">' + num(m.benches) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }, function () {});
  }
  function notFound() {
    document.title = asked + ": no evaluation reports yet";
    root.innerHTML = '<header class="es-modelhead"><p class="es-small">Evaluation reports for</p><h1>' + esc(asked) + "</h1></header>" +
      '<div class="es-empty"><h2 class="es-h3">No report for this model yet</h2>' +
      "<p>The registry holds no record under this name. Reports are matched by the name of the model without the organisation, " +
      "so <code>organisation/name</code> and <code>name</code> find the same model.</p>" +
      '<p id="similar"></p>' +
      '<p class="es-actions"><a class="es-btn" href="' + esc(submitUrl(asked)) + '">Submit the first report</a> ' +
      '<a class="es-btn is-plain" href="' + esc(hubSearch(asked)) + '">Look it up on Hugging Face</a></p></div>' + LOOKUP;
    withLookup();
    ES.loadModels().then(function (models) {
      var q = ES.modelKey(asked), seen = {};
      var near = ES.searchModels(models, asked, 6).concat(models.filter(function (m) { return m.key.length >= 4 && q.indexOf(m.key) >= 0; }))
        .filter(function (m) { if (seen[m.id]) { return false; } seen[m.id] = true; return true; }).slice(0, 6);
      if (near.length) {
        $("#similar").innerHTML = "Models in the registry with a similar name: " +
          near.map(function (m) { return '<a class="es-code" href="' + esc(ES.modelUrl(m.id)) + '">' + esc(m.id) + "</a>"; }).join(", ") + ".";
      }
    }, function () {});
  }
  function failed() {
    root.innerHTML = '<header class="es-modelhead"><h1 style="font-family:var(--sans)">The registry could not be loaded</h1></header>' +
      '<p class="es-note">The data file for this model did not load. Reload the page, or get the records as <a href="data/records.csv">CSV</a>.</p>';
  }

  /* ---------- one benchmark ---------- */
  function strip(recs) {          // every score of the pair on one 0 to 100 line
    var on = recs.filter(function (r) { return r.pct !== null; });
    if (on.length < 2 || on.length !== recs.length) { return ""; }
    var lo = Math.min.apply(null, on.map(function (r) { return r.pct; })), hi = Math.max.apply(null, on.map(function (r) { return r.pct; }));
    var ticks = [0, 25, 50, 75, 100].map(function (t) { return '<i class="es-tick" style="left:' + t + '%"><span>' + t + "</span></i>"; }).join("");
    // scores that fall on the same spot are stacked, so that each one can be seen and selected
    var level = {}, start = null, k = 0;
    on.slice().sort(function (a, b) { return a.pct - b.pct; }).forEach(function (r) {
      if (start !== null && r.pct - start < 0.6) { k = Math.min(k + 1, 2); } else { start = r.pct; k = 0; }
      level[r.i] = k;
    });
    var dots = on.map(function (r) {
      var text = ES.score(r.score, r.hi) + ", " + r.source.label + (r.author ? ", author-reported" : ", predicted");
      return '<button type="button" class="es-dot' + (r.author ? "" : " is-predicted") + '" style="left:' + r.pct.toFixed(2) + "%;top:" + (41 - 11 * level[r.i]) +
             'px" data-i="' + r.i + '" data-tip="' + esc(text) + '" aria-label="' + esc(text) + '"></button>';
    }).join("");
    var labels = hi - lo < 9 ? '<span class="es-val" style="left:' + ((lo + hi) / 2).toFixed(2) + '%">' + (hi - lo < 0.005 ? lo.toFixed(2) : lo.toFixed(2) + " to " + hi.toFixed(2)) + "</span>"
      : '<span class="es-val" style="left:' + lo.toFixed(2) + '%">' + lo.toFixed(2) + '</span><span class="es-val" style="left:' + hi.toFixed(2) + '%">' + hi.toFixed(2) + "</span>";
    return '<div class="es-strip" role="group" aria-label="Scores from ' + lo.toFixed(2) + " to " + hi.toFixed(2) + ' on a scale from 0 to 100">' + ticks +
      '<i class="es-gap" style="left:' + lo.toFixed(2) + "%;width:" + (hi - lo).toFixed(2) + '%"></i>' + labels + dots + "</div>";
  }
  function row(r) {
    var v = r.values, harness = v.harness_name ? esc(v.harness_name) + (v.harness_version ? " " + esc(v.harness_version) : "") : '<span class="es-hollow">not on record</span>';
    return '<tr class="es-click" data-i="' + r.i + '">' +
      '<td class="es-num"><b>' + ES.score(r.score, r.hi) + "</b></td>" +
      "<td>" + esc(r.source.label) + '<span class="es-sub">' + esc(r.source.kind) + (r.source.ref ? ", " + esc(r.source.ref) : "") + (r.superseded ? ", superseded" : "") + "</span></td>" +
      "<td>" + ES.trackLabel(r) + "</td>" +
      "<td>" + ES.modeLabel(v.scoring_mode) + "</td>" +
      "<td>" + harness + "</td>" +
      '<td class="es-num">' + (v.n_shot !== undefined ? esc(v.n_shot) : '<span class="es-hollow">?</span>') + "</td>" +
      '<td><span class="es-cov">' + ES.meter(ES.recordCoverage(r), true) + "<span>" + r.have + " of " + r.of + "</span></span></td>" +
      ES.toggleCell("the record with the score " + ES.score(r.score, r.hi) + " from " + r.source.label) + "</tr>";
  }
  function section(group) {
    var recs = group.recs, c = group.cell, sources = {};
    recs.forEach(function (r) { sources[r.source.key] = true; });
    var count = plural(recs.length, "record") + " from " + plural(Object.keys(sources).length, "source");
    var verdicts = c ? '<ul class="es-verdicts"><li><span class="es-q">Were the scores produced the same way?</span>' + ES.sameWay(c) +
      '</li><li><span class="es-q">Are they independent measurements?</span>' + ES.independent(c) + "</li></ul>"
      : '<p class="es-small" style="margin:2px 0 10px">One record only, so there is nothing to check this score against.</p>';
    return '<section class="es-cell" id="b-' + esc(group.bench.key) + '"><div class="es-cell-head"><h2>' + esc(group.bench.label) + "</h2><span>" + count + "</span></div>" +
      verdicts + strip(recs) +
      '<div class="es-scroll"><table class="es-table"><thead><tr><th scope="col" class="es-num">Score</th><th scope="col">Source</th><th scope="col">Track</th>' +
      '<th scope="col">Scoring mode</th><th scope="col">Harness</th><th scope="col" class="es-num">Shots</th><th scope="col">Required fields</th><th scope="col"><span class="sr">Record</span></th></tr></thead><tbody>' +
      recs.map(row).join("") + "</tbody></table></div></section>";
  }

  /* ---------- the page ---------- */
  function csv(recs) {
    var names = ES.spec.fields.map(function (f) { return f.name; }).filter(function (n) { return n !== "model_id" && n !== "benchmark_id"; });
    var head = ["model", "model_as_reported", "benchmark", "score", "min_score", "max_score", "metric_name", "source", "source_kind", "track", "evidence_source"]
      .concat(names, ["required_reported", "required_applicable", "file"]);
    var cell = function (x) { x = x === null || x === undefined ? "" : String(x); return /[",\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; };
    var lines = recs.map(function (r) {
      return [r.model.id, r.values.model_id, r.bench.label, r.score, r.lo, r.hi, r.metric, r.source.label, r.source.kind,
              r.author ? "author-reported" : "predicted", r.tag]
        .concat(names.map(function (n) { var v = r.values[n]; return Array.isArray(v) ? JSON.stringify(v) : v; }), [r.have, r.of, r.file]).map(cell).join(",");
    });
    return head.join(",") + "\n" + lines.join("\n") + "\n";
  }
  function render(p, mi) {
    var model = p.models[mi], all = [], track = "all", words = "";
    for (var i = 0; i < p.n; i++) { if (p.cols.model[i] === mi) { all.push(p.record(i)); } }
    var cells = {};
    p.cells.forEach(function (c) { if (c.model === mi) { cells[p.benches[c.bench].key] = c; } });
    document.title = model.id + ": evaluation reports";
    var canonical = $('link[rel="canonical"]');                 // each model is a page of its own
    if (canonical) { canonical.href = canonical.href.split("?")[0] + "?id=" + encodeURIComponent(model.id).replace(/%2F/g, "/"); }
    var authors = all.filter(function (r) { return r.author; }).length, benches = {};
    all.forEach(function (r) { benches[r.bench.key] = true; });
    var nBench = Object.keys(benches).length;
    var also = model.names.length ? '<p class="es-also">Written as ' + model.names.map(function (n) { return "<code>" + esc(n) + "</code>"; }).join(", ") +
      " in some sources. Reports are matched by the name of the model, without the organisation.</p>" : "";
    var other = ES.flat(asked) !== ES.flat(model.id) && model.names.map(ES.flat).indexOf(ES.flat(asked)) < 0
      ? '<p class="es-also">You asked for <code>' + esc(asked) + "</code>. The registry lists this model as <code>" + esc(model.id) + "</code>.</p>" : "";

    root.innerHTML = '<header class="es-modelhead"><p class="es-small">Evaluation reports for</p><h1>' + esc(model.id) + "</h1>" + other + also +
      "<p>" + plural(all.length, "record") + " from " + plural(model.sources, "source") + " on " + plural(nBench, "benchmark") + ". " +
      num(authors) + (authors === 1 ? " is" : " are") + " author-reported, " + num(all.length - authors) + (all.length - authors === 1 ? " is" : " are") + " predicted.</p>" +
      '<p class="es-actions"><a class="es-btn" href="' + esc(submitUrl(model.id)) + '">Submit a report for this model</a>' +
      '<button class="es-btn is-plain" type="button" id="download">Download these records</button>' +
      '<a class="es-btn is-plain" href="' + esc(hubSearch(model.id)) + '">Look it up on Hugging Face</a></p></header>' +
      '<div class="es-toolbar" style="margin-top:18px"><div><span class="es-label" id="track-label">Records shown</span>' +
      '<div class="es-seg" role="group" aria-labelledby="track-label" id="track">' +
      '<button type="button" data-track="all" aria-pressed="true">All</button><button type="button" data-track="author" aria-pressed="false">Author-reported</button>' +
      '<button type="button" data-track="predicted" aria-pressed="false">Predicted</button></div></div>' +
      (nBench > 8 ? '<div class="es-grow"><label class="es-label" for="bq">Benchmark</label><input class="es-input" id="bq" type="search" placeholder="Filter the ' +
                    nBench + ' benchmarks" autocomplete="off" spellcheck="false"></div>' : "") + "</div>" +
      '<div id="cells"></div>';

    function draw() {
      var groups = {}, order = [];
      all.forEach(function (r) {
        if (track !== "all" && (track === "author") !== r.author) { return; }
        if (words && ES.flat(r.bench.label + " " + r.values.benchmark_id).indexOf(words) < 0) { return; }
        if (!groups[r.bench.key]) { groups[r.bench.key] = { bench: r.bench, recs: [], cell: track === "all" ? cells[r.bench.key] : null }; order.push(groups[r.bench.key]); }
        groups[r.bench.key].recs.push(r);
      });
      order.forEach(function (g) {        // author-reported first, superseded last, then by how much the source reports itself
        g.recs.sort(function (a, b) { return a.superseded - b.superseded || b.author - a.author || a.source.rank - b.source.rank || a.score - b.score; });
        g.sources = Object.keys(g.recs.reduce(function (o, r) { o[r.source.key] = true; return o; }, {})).length;
      });
      order.sort(function (a, b) { return b.sources - a.sources || b.recs.length - a.recs.length || a.bench.label.toLowerCase().localeCompare(b.bench.label.toLowerCase()); });
      $("#cells").innerHTML = order.map(section).join("") ||
        '<div class="es-empty" style="margin-top:8px"><p class="es-emptyhead">Nothing to show</p><p>' + (track === "author"
          ? 'No source has reported its own results for this model yet. <a href="' + esc(submitUrl(model.id)) + '">Submit a report</a>.'
          : "No record matches.") + "</p></div>";
      $$("#cells tbody").forEach(function (body) {
        ES.expandable(body, function (tr) { return '<div class="es-detail-in">' + ES.recordDetail(p.record(+tr.dataset.i)) + "</div>"; });
      });
    }
    draw();

    $$("#track button").forEach(function (b) {
      b.addEventListener("click", function () {
        track = b.dataset.track;
        $$("#track button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        draw();
      });
    });
    if ($("#bq")) { $("#bq").addEventListener("input", function () { words = ES.flat($("#bq").value); draw(); }); }
    $("#cells").addEventListener("click", function (e) {         // a dot on the score line opens its record
      var dot = e.target.closest(".es-dot");
      if (!dot) { return; }
      var tr = $('tr.es-click[data-i="' + dot.dataset.i + '"]', $("#cells"));
      if (tr) { if (!tr.classList.contains("is-open")) { tr.click(); } tr.scrollIntoView({ block: "nearest" }); $(".es-toggle button", tr).focus(); }
    });
    $("#download").addEventListener("click", function () {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([csv(all)], { type: "text/csv" }));
      a.download = model.id.replace(/[^A-Za-z0-9._-]+/g, "_") + "-evalspec-records.csv";
      document.body.appendChild(a); a.click(); a.remove();
      window.setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    });
    if (window.location.hash.length > 1) {
      var target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      if (target) { target.scrollIntoView(); }
    }
  }

  if (!asked) { start(); return; }
  var key = ES.modelKey(asked);
  ES.loadShard(key).then(function (p) {
    var mi = p.models.findIndex(function (m) { return m.key === key; });
    if (mi < 0) { notFound(); } else { render(p, mi); }
  }, failed);
})();
