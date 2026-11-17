/* Shared by every page: helpers, loading of the data files, the model lookup, tooltips and
   copy buttons, and the pieces that draw a record (its fields, and who filled each one in).
   Needs data/spec.js. Defines window.ES. */
(function () {
  "use strict";
  var SPEC = window.EVALSPEC_SPEC, SITE = window.EVALSPEC_SITE;
  if (!SPEC || !SITE) { return; }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var ENTITY = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(t) { return String(t).replace(/[&<>"']/g, function (c) { return ENTITY[c]; }); }
  function num(n) { return Number(n).toLocaleString("en-US"); }
  function share(part, whole) { return whole ? 100 * part / whole : 0; }
  function pct(part, whole) {            // no decimals, but never "0%" or "100%" for a value that is not exactly that
    var v = share(part, whole);
    return v > 0 && v < 1 ? "under 1%" : v > 99 && v < 100 ? "over 99%" : Math.round(v) + "%";
  }
  function plural(n, one, many) { return num(n) + " " + (n === 1 ? one : (many || one + "s")); }
  function score(v, hi) {               // two decimals on a 0 to 100 scale, three on a 0 to 1 scale
    if (v === null || v === undefined) { return "n/a"; }
    if (hi !== null && hi !== undefined && hi <= 1.5) { return v.toFixed(3); }
    return (hi === null || hi === undefined) && Number.isInteger(v) ? String(v) : v.toFixed(2);
  }

  /* ---------- names: the same normalisation as source/ingest.py ---------- */
  function flat(text) { return String(text).toLowerCase().replace(/\+/g, "plus").replace(/[^a-z0-9]/g, ""); }
  function modelKey(id) {
    var tail = String(id).trim().split("/").pop(), key = flat(tail) || tail.toLowerCase();
    return SITE.model_aliases[key] || key;
  }
  function shardOf(key) {               // which per-model file holds a model
    var h = 5381;
    Array.from(key).forEach(function (ch) { h = (Math.imul(h, 33) + ch.codePointAt(0)) >>> 0; });
    return h % SITE.shards;
  }

  /* ---------- data files ---------- */
  var pending = {};
  function load(src) {                  // a data file, loaded once, as a script so that it also works from disk
    if (!pending[src]) {
      pending[src] = new Promise(function (resolve, reject) {
        var s = document.createElement("script");
        s.src = src + "?v=" + SITE.build;
        s.onload = resolve;
        s.onerror = function () { delete pending[src]; reject(new Error("could not load " + src)); };
        document.head.appendChild(s);
      });
    }
    return pending[src];
  }
  function loadModels() {               // [{id, n, sources, benches, names, key}]
    return load("data/models.js").then(function () {
      var raw = window.EVALSPEC_MODELS;
      if (!raw.ready) {
        raw.ready = raw.map(function (m) {
          return { id: m[0], n: m[1], sources: m[2], benches: m[3], names: m[4], key: modelKey(m[0]),
                   hay: [m[0]].concat(m[4]).map(flat) };
        });
      }
      return raw.ready;
    });
  }
  function loadShard(key) {
    var n = shardOf(key);
    return load("data/model/" + n + ".js").then(function () { return decode(window.EVALSPEC_SHARDS[n]); });
  }
  function searchModels(models, query, limit) {
    var q = flat(query), tail = flat(String(query).split("/").pop());
    if (!q) { return []; }
    return models.filter(function (m) { return m.hay.some(function (h) { return h.indexOf(q) >= 0; }) || (tail.length > 2 && m.key.indexOf(tail) >= 0); })
      .sort(function (a, b) {
        return (b.key === modelKey(query)) - (a.key === modelKey(query)) || (b.key.indexOf(tail) === 0) - (a.key.indexOf(tail) === 0) ||
               b.sources - a.sources || b.n - a.n || a.id.localeCompare(b.id);
      }).slice(0, limit || 8);
  }

  /* The registry arrives column by column, with repeated texts stored once. record(i) puts one record back together. */
  var KEY_FIELDS = ["scoring_mode", "harness_name", "harness_version", "n_shot", "benchmark_variant", "judge_model", "evaluation_timestamp"];
  var NAMES = SPEC.fields.map(function (f) { return f.name; });
  function decode(p) {
    if (p.record) { return p; }
    var S = p.strings, C = p.cols;
    p.record = function (i) {
      var values = { model_id: S[C.mid[i]], benchmark_id: S[C.bname[i]] }, prov = {}, status = {};
      KEY_FIELDS.forEach(function (k) { if (C[k][i]) { values[k] = S[C[k][i]]; } });
      if (C.more[i]) { var more = JSON.parse(S[C.more[i]]); Object.keys(more).forEach(function (k) { values[k] = more[k]; }); }
      var tag = S[C.tag[i]], over = C.tags[i] ? JSON.parse(S[C.tags[i]]) : {}, sig = S[C.sig[i]];
      NAMES.forEach(function (n, j) {
        status[n] = +sig.charAt(j);
        if (Object.prototype.hasOwnProperty.call(values, n)) { prov[n] = over[n] || tag; }
      });
      return {
        i: i, model: p.models[C.model[i]], bench: p.benches[C.bench[i]], source: p.sources[C.source[i]],
        score: C.score[i], pct: C.pct[i], lo: C.lo[i], hi: C.hi[i], metric: S[C.metric[i]], raw: S[C.raw[i]], note: S[C.note[i]],
        author: C.track[i] === 1, superseded: C.sup[i] === 1, tag: tag, tier: C.tier[i], ok: C.ok[i] === 1,
        have: C.have[i], of: C.of[i], first: C.first[i], llm: C.llm[i], rec: C.rec[i], full: C.full[i],
        values: values, prov: prov, status: status, file: S[C.file[i]], errors: C.errors[i] ? JSON.parse(S[C.errors[i]]) : []
      };
    };
    return p;
  }

  /* ---------- drawing a record ---------- */
  // status of a field: 0 not on record, 1 first-hand, 2 read by an LLM, 3 inferred, 4 not valid, 5 does not apply
  var MARK = ["is-missing", "is-first", "is-llm", "is-inferred", "is-invalid", "is-na"];
  var WORD = ["not on record", "reported first-hand", "read from the source by an LLM", "inferred by a pipeline", "not valid", "does not apply"];
  var TIER = ["Below Required", "Required", "Recommended", "Full"];
  var APPLIES = { generation: "applies when scoring_mode is generation", judge: "applies when a judge produces the score" };

  function mark(status) { return '<span class="es-mark ' + MARK[status] + '" title="' + WORD[status] + '" aria-hidden="true"></span>'; }
  function shown(f, v) {
    if (v === null) { return "none"; }
    if (Array.isArray(v)) { return esc(v.join(", ")); }
    v = String(v);
    if (f.type === "sha256" && v.length > 30) { return '<span title="' + esc(v) + '">' + esc(v.slice(0, 19)) + "…</span>"; }
    if (f.type === "url" && /^https?:\/\//.test(v)) { return '<a href="' + esc(v) + '">' + esc(v) + "</a>"; }
    return esc(v);
  }
  function fieldRow(f, rec) {            // mark, name, value, and who filled the value in
    var st = rec.status[f.name], body, by = "";
    if (st >= 1 && st <= 3) { body = shown(f, rec.values[f.name]); by = esc(rec.prov[f.name]); }
    else if (st === 0) { body = '<span class="es-hollow">not on record</span>'; }
    else if (st === 4) {
      var why = rec.errors.filter(function (e) { return e.indexOf(f.name + ":") === 0; })[0];
      body = "not valid"; by = why ? esc(why.slice(f.name.length + 2)) : "";
    } else { body = "does not apply"; by = APPLIES[f.applies]; }
    return '<div class="es-field ' + MARK[st] + '"><dt>' + mark(st) + "<span>" + esc(f.name) + "</span></dt><dd>" + body + '</dd><dd class="es-by">' + by + "</dd></div>";
  }
  // fields(rec, {tiers: ["required"], skipNA: true, stacked: true}) -> the field list, tier by tier
  function fields(rec, opts) {
    opts = opts || {};
    var tiers = SPEC.tiers.filter(function (t) { return !opts.tiers || opts.tiers.indexOf(t.id) >= 0; });
    return '<div class="es-fields' + (opts.stacked ? " is-stacked" : "") + '">' + tiers.map(function (t) {
      var rows = SPEC.fields.filter(function (f) { return f.tier === t.id && !(opts.skipNA && rec.status[f.name] === 5); });
      return (tiers.length > 1 ? '<p class="es-grouplabel">' + esc(t.label) + "</p>" : "") + "<dl>" + rows.map(function (f) { return fieldRow(f, rec); }).join("") + "</dl>";
    }).join("") + "</div>";
  }
  // coverage as a stacked bar: first-hand, read by an LLM, inferred; the empty rest is not on record
  function meter(cov, thin) {
    var parts = [["is-first", cov.first_hand, "first-hand"], ["is-llm", cov.llm, "read by an LLM"], ["is-inferred", cov.inferred, "inferred"]];
    var label = parts.filter(function (p) { return p[1]; }).map(function (p) { return pct(p[1], cov.of) + " " + p[2]; }).join(", ") || "nothing on record";
    var tip = parts.map(function (p) { return p[2] + ": " + num(p[1]) + " of " + num(cov.of); }).join("; ") +
              "; not on record: " + num(cov.of - cov.have) + " of " + num(cov.of);
    return '<span class="es-meter' + (thin ? " is-thin" : "") + '" role="img" tabindex="0" aria-label="' + esc(label) + '" data-tip="' + esc(tip) + '">' +
      parts.filter(function (p) { return p[1]; }).map(function (p) { return '<i class="' + p[0] + '" style="width:' + share(p[1], cov.of).toFixed(2) + '%"></i>'; }).join("") + "</span>";
  }
  function recordCoverage(rec) { return { of: rec.of, have: rec.have, first_hand: rec.first, llm: rec.llm, inferred: rec.have - rec.first - rec.llm }; }
  function trackLabel(rec) {
    return rec.author ? '<span class="es-track is-author">Author-reported</span>' : '<span class="es-track is-predicted">Predicted</span>';
  }
  function modeLabel(mode) {
    return mode ? '<span class="es-mode is-' + esc(mode) + '">' + esc(mode) + "</span>" : '<span class="es-hollow">not on record</span>';
  }
  function sourceLine(s) {
    var name = s.url ? '<a href="' + esc(s.url) + '">' + esc(s.label) + "</a>" : esc(s.label);
    return name + ' <span class="es-kind">' + esc(s.kind) + (s.ref ? ", " + esc(s.ref) : "") + "</span>";
  }
  function fileUrl(rec) { return SITE.datastore.file_base + rec.file.split("/").map(encodeURIComponent).join("/"); }
  function modelUrl(id, bench) { return "model.html?id=" + encodeURIComponent(id).replace(/%2F/g, "/") + (bench ? "#b-" + bench : ""); }
  // the record as the flat JSON object the Submit page reads, for "Correct this record"
  function flatRecord(rec) {
    var out = { model_id: rec.model.id, benchmark_id: rec.values.benchmark_id, score: rec.score };
    if (rec.metric) { out.metric_name = rec.metric; }
    if (rec.lo !== null && rec.hi !== null) { out.min_score = rec.lo; out.max_score = rec.hi; }
    SPEC.fields.forEach(function (f) {
      if (f.name === "model_id" || f.name === "benchmark_id" || !Object.prototype.hasOwnProperty.call(rec.values, f.name)) { return; }
      var v = rec.values[f.name];
      if (f.name === "judge_model" && v === "none") { v = null; }
      else if ((f.type === "integer" || f.type === "number") && typeof v === "string" && isFinite(v)) { v = Number(v); }
      out[f.name] = v;
    });
    out.source_name = rec.source.label; out.source_kind = rec.source.kind;
    if (rec.source.url) { out.source_url = rec.source.url; }
    return out;
  }
  function correctUrl(rec) { return "submit.html?record=" + encodeURIComponent(JSON.stringify(flatRecord(rec))) + "#build"; }
  // everything about one record: where it comes from, every field, and what can be done with it
  function recordDetail(rec, opts) {
    opts = opts || {};
    var cov = recordCoverage(rec), scale = rec.lo !== null && rec.hi !== null ? ", on a scale from " + rec.lo + " to " + rec.hi : ", scale not stated";
    var facts = [
      "<b>" + score(rec.score, rec.hi) + "</b>" + (rec.metric && rec.metric !== "unspecified" ? " " + esc(rec.metric) : "") + scale + ".",
      "Published by " + sourceLine(rec.source) + ".",
      trackLabel(rec) + " Values are tagged <b>" + esc(rec.tag) + "</b> unless a field says otherwise."
    ];
    if (rec.values.model_id !== rec.model.id) { facts.push("The source writes the model as <code>" + esc(rec.values.model_id) + "</code>."); }
    if (rec.raw) { facts.push("Measured value before rescaling: <b>" + esc(rec.raw) + "</b>."); }
    if (rec.note) { facts.push(esc(rec.note)); }
    if (rec.superseded) { facts.push("Superseded: the same source has since reported this model and benchmark itself."); }
    if (!rec.ok) { facts.push('<span style="color:var(--bad)">Not well formed: ' + esc(rec.errors.join("; ")) + ".</span>"); }
    var links = ['<a href="' + esc(fileUrl(rec)) + '">Datastore file</a>'];
    if (!rec.author) { links.push('<a href="' + esc(correctUrl(rec)) + '">Correct this record</a>'); }
    if (opts.modelLink) { links.push('<a href="' + esc(modelUrl(rec.model.id, rec.bench.key)) + '">All reports for this model</a>'); }
    return '<div class="es-rec"><div class="es-rec-meta">' + facts.map(function (t) { return "<div>" + t + "</div>"; }).join("") + "</div>" +
      fields(rec) +
      '<div class="es-rec-foot"><span>' + rec.have + " of " + rec.of + " Required fields on record, " + rec.first + " first-hand. " + TIER[rec.tier] +
      " tier.</span><span class=\"es-actions\">" + links.join(" ") + "</span></div></div>";
  }

  /* ---------- two verdicts on a model and benchmark pair with several records ---------- */
  function names(list, max) {
    var shown = list.slice(0, max).map(function (n) { return "<code>" + esc(n) + "</code>"; }).join(", ");
    return shown + (list.length > max ? " and " + (list.length - max) + " more" : "");
  }
  function sameWay(c) {
    if (c.procedure === "different") { return '<span class="es-verdict is-no"><b>No</b><span>differs in ' + names(c.differs, 3) + "</span></span>"; }
    if (c.procedure === "same") { return '<span class="es-verdict is-yes"><b>Yes</b><span>every procedure field is on record and equal</span></span>'; }
    var why = c.missing.length ? "missing " + names(c.missing, 3) : c.soft.length ? "inferred values differ in " + names(c.soft, 3) : "some values were inferred";
    return '<span class="es-verdict is-unknown"><b>Not on record</b><span>' + why + "</span></span>";
  }
  function independent(c) {
    if (c.independent === "yes") { return '<span class="es-verdict is-yes"><b>Yes</b><span>separate evaluation dates</span></span>'; }
    if (c.independent === "twins") { return '<span class="es-verdict is-no"><b>Possibly not</b><span>equal scores, no evaluation dates</span></span>'; }
    return '<span class="es-verdict is-unknown"><b>Not on record</b><span>no evaluation dates</span></span>';
  }
  /* ---------- tables ---------- */
  // sortable(table, state, redraw): header buttons with data-sort set state.sort and state.dir
  function sortable(table, state, redraw) {
    function paint() {
      $$("thead th", table).forEach(function (th) {
        var b = $("button[data-sort]", th);
        if (b && b.dataset.sort === state.sort) { th.setAttribute("aria-sort", state.dir > 0 ? "ascending" : "descending"); }
        else { th.removeAttribute("aria-sort"); }
      });
    }
    $$("thead button[data-sort]", table).forEach(function (b) {
      b.addEventListener("click", function () {
        if (state.sort === b.dataset.sort) { state.dir = -state.dir; }
        else { state.sort = b.dataset.sort; state.dir = b.closest("th").classList.contains("es-num") ? -1 : 1; }
        paint(); redraw();
      });
    });
    paint();
    return paint;
  }
  // pager(box, total, state, redraw): "Showing 1 to 50 of 122" with previous and next
  function pager(box, total, state, redraw) {
    var pages = Math.max(1, Math.ceil(total / state.size));
    state.page = Math.min(Math.max(1, state.page), pages);
    var from = total ? (state.page - 1) * state.size + 1 : 0, to = Math.min(total, state.page * state.size);
    box.innerHTML = "<span>" + (total ? "Showing " + num(from) + " to " + num(to) + " of " + num(total) : "Nothing to show") + "</span>" +
      (pages > 1 ? '<button class="es-btn is-plain is-small" type="button" data-go="-1"' + (state.page === 1 ? " disabled" : "") + ">Previous</button>" +
                   '<button class="es-btn is-plain is-small" type="button" data-go="1"' + (state.page === pages ? " disabled" : "") + ">Next</button>" : "");
    $$("button[data-go]", box).forEach(function (b) {
      b.addEventListener("click", function () { state.page += +b.dataset.go; redraw(); });
    });
  }
  // Rows that open a detail row underneath. Each row ends with the button from toggleCell(); a click anywhere on the row does the same.
  function toggleCell(what) {
    return '<td class="es-toggle"><button type="button" class="es-expander" aria-expanded="false"><span>Show</span><span class="sr"> ' + esc(what) + "</span></button></td>";
  }
  function expandable(tbody, detail) {
    function toggle(tr) {
      var open = tr.classList.contains("is-open"), next = tr.nextElementSibling, button = $(".es-toggle button", tr);
      if (open) { if (next && next.classList.contains("es-detail")) { next.remove(); } }
      else {
        var row = document.createElement("tr");
        row.className = "es-detail";
        row.innerHTML = '<td colspan="' + tr.children.length + '">' + detail(tr) + "</td>";
        tr.after(row);
      }
      tr.classList.toggle("is-open", !open);
      if (button) { button.setAttribute("aria-expanded", String(!open)); button.firstChild.textContent = open ? "Show" : "Hide"; }
    }
    tbody.addEventListener("click", function (e) {
      var tr = e.target.closest("tr.es-click");
      if (tr && (e.target.closest(".es-toggle button") || !e.target.closest("a, button"))) { toggle(tr); }
    });
    return toggle;
  }

  /* ---------- the model lookup: suggestions from the registry while typing ---------- */
  function lookup(form, n) {
    var input = $('input[name="id"]', form), list = document.createElement("ul"), models = null, found = [], active = -1;
    list.className = "es-suggest"; list.id = "suggest-" + n; list.hidden = true; list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Models in the registry");
    ($(".es-lookup-row", form) || form).appendChild(list);     // directly under the input
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id); input.setAttribute("aria-expanded", "false");
    function close() { list.hidden = true; active = -1; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); }
    function paint() {
      $$("li", list).forEach(function (li, i) { li.setAttribute("aria-selected", String(i === active)); });
      if (active >= 0) { input.setAttribute("aria-activedescendant", list.id + "-" + active); } else { input.removeAttribute("aria-activedescendant"); }
    }
    function update() {
      found = models && input.value.trim() ? searchModels(models, input.value, 8) : [];
      active = -1;
      if (!found.length) { close(); return; }
      list.innerHTML = found.map(function (m, i) {
        return '<li role="option" id="' + list.id + "-" + i + '" data-i="' + i + '"><span>' + esc(m.id) + "</span><small>" +
               plural(m.sources, "source") + ", " + plural(m.n, "record") + "</small></li>";
      }).join("");
      list.hidden = false; input.setAttribute("aria-expanded", "true"); paint();
    }
    function go(m) { window.location.href = modelUrl(m.id); }
    input.addEventListener("focus", function () { if (!models) { loadModels().then(function (m) { models = m; update(); }, function () {}); } });
    input.addEventListener("input", update);
    input.addEventListener("keydown", function (e) {
      if (list.hidden) { return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        active = (active + (e.key === "ArrowDown" ? 1 : -1) + found.length + 1) % (found.length + 1);
        if (active === found.length) { active = -1; }
        paint();
      } else if (e.key === "Enter" && active >= 0) { e.preventDefault(); go(found[active]); }
      else if (e.key === "Escape") { close(); }
    });
    list.addEventListener("mousedown", function (e) {      // before the input loses focus
      var li = e.target.closest("li"); if (li) { e.preventDefault(); go(found[+li.dataset.i]); }
    });
    input.addEventListener("blur", function () { window.setTimeout(close, 120); });
    form.addEventListener("submit", function (e) { if (!input.value.trim()) { e.preventDefault(); input.focus(); } });
  }
  $$("form[data-lookup]").forEach(lookup);

  /* ---------- tooltips for anything with data-tip ---------- */
  (function () {
    var tip = null;
    function show(el) {
      if (!tip) { tip = document.createElement("div"); tip.className = "es-tip"; tip.setAttribute("role", "tooltip"); document.body.appendChild(tip); }
      tip.textContent = el.dataset.tip; tip.hidden = false;
      var r = el.getBoundingClientRect(), w = tip.offsetWidth;
      tip.style.left = Math.max(8, Math.min(window.pageXOffset + r.left, window.pageXOffset + document.documentElement.clientWidth - w - 8)) + "px";
      tip.style.top = (window.pageYOffset + r.bottom + 6) + "px";
    }
    function hide() { if (tip) { tip.hidden = true; } }
    document.addEventListener("mouseover", function (e) { var el = e.target.closest && e.target.closest("[data-tip]"); if (el) { show(el); } else { hide(); } });
    document.addEventListener("focusin", function (e) { var el = e.target.closest && e.target.closest("[data-tip]"); if (el) { show(el); } });
    document.addEventListener("focusout", hide);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { hide(); } });
  })();

  /* ---------- copy buttons: <button class="es-btn" data-copy="id of the element to copy"> ---------- */
  $$(".es-btn[data-copy]").forEach(function (btn) {
    var target = document.getElementById(btn.dataset.copy);
    if (!target || !navigator.clipboard) { return; }
    var label = btn.textContent;
    btn.hidden = false;
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(target.textContent).then(function () { btn.textContent = "Copied"; }, function () { btn.textContent = "Select the text and copy"; })
        .then(function () { window.setTimeout(function () { btn.textContent = label; }, 1800); });
    });
  });

  /* ---------- a group of buttons that shows one of several panels: data-show on the button, data-stat on the panel ---------- */
  $$(".es-seg").forEach(function (group) {
    var buttons = $$("button[data-show]", group);
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        buttons.forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        $$("[data-stat]", group.parentNode).forEach(function (panel) { panel.hidden = panel.dataset.stat !== b.dataset.show; });
      });
    });
  });

  window.ES = {
    spec: SPEC, site: SITE, $: $, $$: $$, esc: esc, num: num, share: share, pct: pct, plural: plural, score: score,
    flat: flat, modelKey: modelKey, load: load, loadModels: loadModels, loadShard: loadShard, searchModels: searchModels, decode: decode,
    TIER: TIER, mark: mark, fields: fields, meter: meter, recordCoverage: recordCoverage, trackLabel: trackLabel, modeLabel: modeLabel,
    sourceLine: sourceLine, fileUrl: fileUrl, modelUrl: modelUrl, flatRecord: flatRecord, correctUrl: correctUrl, recordDetail: recordDetail,
    sameWay: sameWay, independent: independent, sortable: sortable, pager: pager, toggleCell: toggleCell, expandable: expandable, lookup: lookup
  };
})();
