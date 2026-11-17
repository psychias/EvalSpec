/* Submit page: the form that writes a record, the check, and the conversion into datastore files.
   Everything runs in the browser with assets/js/evalspec.js; nothing is sent anywhere.
     submit.html?record=<JSON>#build     opens the form with a record (used by "Correct this record")
     submit.html?example=<file>#check    opens a worked example in the check                           */
(function () {
  "use strict";
  var ES = window.ES, E = window.EvalSpec, EXAMPLES = window.EVALSPEC_EXAMPLES || {};
  if (!ES || !E) { return; }
  var $ = ES.$, $$ = ES.$$, esc = ES.esc, SPEC = ES.spec;
  var NUMBER = /^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$/;
  var NO_JUDGE = ["log-likelihood", "generation", "execution"];
  var MAX_SHOWN = 40;
  var form = $("#builder");

  /* ---------- 1. the form, generated from the field list ---------- */
  function control(f) {
    var id = "f-" + f.name, hint = esc(f.description) + ". " + esc(f.form_hint || f.guidance), input;
    if (f.type === "enum") {
      input = '<select class="es-select" id="' + id + '" data-field="' + f.name + '"><option value="">Not on record</option>' +
        f.enum.map(function (v) { return "<option>" + esc(v) + "</option>"; }).join("") + "</select>";
    } else {
      var example = f.name === "judge_model" ? "none" : f.type === "sha256" ? "sha256: and 64 hexadecimal digits" : f.example === null || f.example === undefined ? "" : String(f.example);
      var mode = f.type === "integer" ? ' inputmode="numeric"' : f.type === "number" ? ' inputmode="decimal"' : "";
      input = '<input class="es-input is-mono" id="' + id + '" data-field="' + f.name + '" type="' + (f.type === "url" ? "url" : "text") + '"' + mode +
              ' placeholder="' + esc(example) + '" aria-describedby="' + id + '-hint">';
    }
    var hash = f.type === "sha256" ? '<details class="es-hashhelp"><summary>Compute it from the prompt text</summary>' +
      '<label class="sr" for="' + id + '-text">Prompt text for ' + f.name + '</label><textarea class="es-textarea is-mono" id="' + id + '-text" rows="4" spellcheck="false" ' +
      'placeholder="Paste the fully rendered prompt: system instruction, chat template and task template"></textarea>' +
      '<button class="es-btn is-plain is-small" type="button" data-hash="' + id + '">Fill in the hash</button></details>' : "";
    return '<div data-applies="' + f.applies + '"' + (f.type === "sha256" || f.type === "url" ? ' class="is-wide"' : "") + '><label class="es-label es-code" for="' + id + '">' + f.name +
           "</label>" + input + '<span class="es-hint" id="' + id + '-hint">' + hint + "</span>" + hash + "</div>";
  }
  function buildForm() {
    var by = { result: "", required: "", recommended: "", full: "" };
    SPEC.fields.forEach(function (f) { by[f.name === "model_id" || f.name === "benchmark_id" ? "result" : f.tier] += control(f); });
    $("#form-result").insertAdjacentHTML("afterbegin", by.result);
    $("#form-required").innerHTML = by.required; $("#form-recommended").innerHTML = by.recommended; $("#form-full").innerHTML = by.full;
  }
  function typed(f, raw) {              // the text of an input as the value a record carries
    if (f.type === "integer" || f.type === "number") { return NUMBER.test(raw) ? Number(raw) : raw; }
    if (f.type === "integer_or_list") {
      var parts = raw.replace(/^\[|\]$/g, "").split(/[,\s]+/).filter(Boolean);
      return parts.every(function (x) { return NUMBER.test(x); }) ? (parts.length === 1 ? Number(parts[0]) : parts.map(Number)) : raw;
    }
    if (f.name === "judge_model" && /^(none|null|n\/a)$/i.test(raw)) { return null; }
    return raw;
  }
  function readForm() {
    var rec = {}, val = function (id) { var el = $("#" + id); return el ? el.value.trim() : ""; };
    ["model_id", "benchmark_id"].forEach(function (n) { if (val("f-" + n)) { rec[n] = val("f-" + n); } });
    if (val("f-score")) { rec.score = NUMBER.test(val("f-score")) ? Number(val("f-score")) : val("f-score"); }
    if (val("f-metric_name")) { rec.metric_name = val("f-metric_name"); }
    var scale = val("f-scale");
    if (scale === "0-100") { rec.min_score = 0; rec.max_score = 100; }
    else if (scale === "0-1") { rec.min_score = 0; rec.max_score = 1; }
    else if (scale === "other") {
      ["min_score", "max_score"].forEach(function (k) { var x = val("f-" + k); if (x) { rec[k] = NUMBER.test(x) ? Number(x) : x; } });
    }
    SPEC.fields.forEach(function (f) {
      var raw = val("f-" + f.name);
      if (raw && !(f.name in rec)) { rec[f.name] = typed(f, raw); }
    });
    if (!("judge_model" in rec) && NO_JUDGE.indexOf(rec.scoring_mode) >= 0) { rec.judge_model = null; }   // no judge: say so
    var author = form.elements.who.value === "author";
    rec.evidence_source = author ? "source-reported" : val("f-tag");
    if (!author && val("f-tag") === "LLM-extracted" && val("f-extractor_model")) { rec.extractor_model = val("f-extractor_model"); }
    ["source_name", "source_kind", "source_url", "evaluator_relationship"].forEach(function (k) { if (val("f-" + k)) { rec[k] = val("f-" + k); } });
    return rec;
  }
  function clearForm() {
    $$("input:not([type=radio]), textarea", form).forEach(function (el) { el.value = ""; });
    $$("select", form).forEach(function (el) { el.selectedIndex = 0; });
    form.elements.who.value = "author";
  }
  function fillForm(rec) {              // a record into the form; what the form has no place for is dropped
    clearForm();
    var set = function (id, v) { var el = $("#" + id); if (el && v !== undefined && v !== null) { el.value = Array.isArray(v) ? v.join(", ") : String(v); } };
    SPEC.fields.forEach(function (f) { set("f-" + f.name, rec[f.name] === null && f.name === "judge_model" ? "none" : rec[f.name]); });
    if (rec.benchmark && !rec.benchmark_id) { set("f-benchmark_id", rec.benchmark); }
    ["score", "metric_name", "source_name", "source_url", "extractor_model"].forEach(function (k) { set("f-" + k, rec[k]); });
    ["source_kind", "evaluator_relationship"].forEach(function (k) { if ($$("#f-" + k + " option").some(function (o) { return o.value === rec[k]; })) { set("f-" + k, rec[k]); } });
    var lo = rec.min_score, hi = rec.max_score;
    set("f-scale", lo === 0 && hi === 100 ? "0-100" : lo === 0 && hi === 1 ? "0-1" : lo === undefined || lo === null ? (rec.score === undefined ? "0-100" : "none") : "other");
    set("f-min_score", lo); set("f-max_score", hi);
    var tag = rec.evidence_source && typeof rec.evidence_source === "object" ? rec.evidence_source["default"] : rec.evidence_source;
    if (tag && tag !== "source-reported" && $$("#f-tag option").some(function (o) { return o.value === tag; })) { form.elements.who.value = "other"; set("f-tag", tag); }
    ["recommended", "full"].forEach(function (t) {
      $("#more-" + t).open = SPEC.fields.some(function (f) { return f.tier === t && rec[f.name] !== undefined && rec[f.name] !== null; });
    });
    live();
  }

  /* ---------- the panel next to the form ---------- */
  function live() {
    var rec = readForm(), report = E.check(E.viewFromFlat(rec)), cov = report.coverage.required;
    var author = form.elements.who.value === "author", mode = rec.scoring_mode, judged = mode === "preference" || typeof rec.judge_model === "string";
    $("#who-other").hidden = author;
    $("#extractor-wrap").hidden = $("#f-tag").value !== "LLM-extracted";
    $("#range-wrap").hidden = $("#f-scale").value !== "other";
    $$("[data-applies]", form).forEach(function (el) {
      var a = el.dataset.applies;
      el.classList.toggle("es-field-off", (a === "generation" && mode !== "generation") || (a === "judge" && !judged));
    });
    // three things any record needs; then the Required fields; then values that are not valid
    var needed = ["model_id", "benchmark_id", "score"].filter(function (k) { return rec[k] === undefined; });
    var missing = report.fields.filter(function (f) { return f.tier === "required" && f.status === "missing" && needed.indexOf(f.name) < 0; });
    var problems = report.errors.filter(function (e) { return needed.indexOf(e.field) < 0; });
    var item = function (cls, html) { return '<li><span class="es-mark ' + cls + '"></span><span>' + html + "</span></li>"; };
    var tier = report.tier === "none" ? "Below the Required tier" : "Reaches the " + ES.TIER[SPEC.tiers.map(function (t) { return t.id; }).indexOf(report.tier) + 1] + " tier";
    $("#live").innerHTML = "<h3>The record so far</h3>" +
      "<p><b>" + cov.have + " of " + cov.of + "</b> Required fields that apply</p>" +
      ES.meter(cov) + "<p>" + tier + ". Listed as " + (author ? "author-reported" : "predicted") + ".</p>" +
      (problems.length ? '<p class="es-small" style="margin:8px 0 0">Not valid:</p><ul>' + problems.map(function (e) {
        return item("is-invalid", "<code>" + esc(e.field) + "</code> " + esc(e.message)); }).join("") + "</ul>" : "") +
      (needed.length ? '<p class="es-small" style="margin:8px 0 0">Every record needs:</p><ul>' + needed.map(function (k) { return item("is-missing", "<code>" + k + "</code>"); }).join("") + "</ul>" : "") +
      (missing.length ? '<p class="es-small" style="margin:8px 0 0">Required and not on record:</p><ul>' + missing.map(function (f) {
        return item("is-missing", "<code>" + f.name + "</code>"); }).join("") + "</ul>" : "") +
      "<details><summary>As JSON</summary><pre>" + esc(JSON.stringify(rec, null, 2)) + "</pre></details>";
  }

  /* ---------- 2. the check ---------- */
  function parse(text) {                // JSON, or one JSON object per line
    try { return JSON.parse(text); }
    catch (first) {
      var lines = text.split(/\r?\n/).filter(function (l) { return l.trim(); });
      try { if (lines.length > 1) { return lines.map(function (l) { return JSON.parse(l); }); } } catch (ignore) { /* report the first error */ }
      throw first;
    }
  }
  function asRecord(report) {           // a check report in the form ES.fields draws
    var out = { status: {}, values: {}, prov: {}, errors: report.errors.map(function (e) { return e.field + ": " + e.message; }) };
    var code = { "first-hand": 1, llm: 2, inferred: 3 };
    report.fields.forEach(function (f) {
      if (f.status === "reported") {
        out.status[f.name] = code[E.tagClass[String(f.provenance).toLowerCase()]] || 3;
        out.values[f.name] = f.value; out.prov[f.name] = f.provenance;
      } else { out.status[f.name] = { missing: 0, invalid: 4, not_applicable: 5 }[f.status]; }
    });
    return out;
  }
  function verdict(r) {
    var cov = r.coverage.required;
    if (!r.well_formed) { return '<span class="es-result is-bad">Not well formed: ' + ES.plural(r.errors.length, "error") + "</span>"; }
    if (r.tier !== "none") { return '<span class="es-result is-ok">Well formed. Reaches the ' + r.tier.charAt(0).toUpperCase() + r.tier.slice(1) + " tier.</span>"; }
    return '<span class="es-result">Well formed. ' + cov.have + " of " + cov.of + " Required fields that apply.</span>";
  }
  function reportItem(r) {
    var msgs = r.errors.map(function (e) { return '<li class="is-error"><b>Error</b><span><code>' + esc(e.field) + "</code> " + esc(e.message) + "</span></li>"; })
      .concat(r.warnings.map(function (w) { return '<li class="is-warning"><b>Note</b><span><code>' + esc(w.field) + "</code> " + esc(w.message) + "</span></li>"; }));
    var missing = r.fields.filter(function (f) { return f.tier === "required" && f.status === "missing"; }).map(function (f) { return "<code>" + f.name + "</code>"; });
    if (!r.fields.length) {             // not a record at all
      return '<div class="es-report-item"><div class="es-report-head"><b>Not a record</b>' + verdict(r) + '</div><ul class="es-msgs">' + msgs.join("") + "</ul></div>";
    }
    return '<div class="es-report-item"><div class="es-report-head"><b>' + esc(r.model_id || "no model") + " | " + esc(r.benchmark_id || "no benchmark") + " | " +
      esc(r.score === null || r.score === undefined ? "no score" : r.score) + "</b>" + verdict(r) + "</div>" +
      (msgs.length ? '<ul class="es-msgs">' + msgs.join("") + "</ul>" : "") +
      '<div class="es-rec-meta">Listed as <b>' + r.track + "</b>; values tagged <b>" + esc(r.default_tag) + "</b>" + (r.tag_inferred ? " (the file does not say, so this is read from its type)" : "") + "." +
      (missing.length ? " Required and not on record: " + missing.join(", ") + "." : "") + "</div>" +
      ES.fields(asRecord(r)) + "</div>";
  }
  function fileBox(file, n) {
    if (file.problem) { return '<div class="es-report-item"><div class="es-filebox"><b>' + esc(file.title) + "</b><br>" + file.problem + "</div></div>"; }
    return '<div class="es-report-item"><div class="es-report-head"><b>' + esc(file.title) + '</b><button class="es-btn is-small" type="button" data-save="' + n + '">Download the file</button></div>' +
      '<div class="es-filebox">' + (file.asIs ? "This is a datastore file already. It is kept as it is. " : "") + "Save it as<br><code>" + esc(file.path) + "</code>" +
      "<details><summary>Show the file</summary><pre>" + esc(file.text) + "</pre></details></div></div>";
  }
  var files = [];
  function check() {
    var text = $("#check-input").value.trim(), box = $("#check-report"), out = $("#file-out");
    files = [];
    if (!text) { box.innerHTML = '<p class="es-empty">Paste a record first, or load an example.</p>'; out.innerHTML = '<p class="es-empty">Nothing to save yet. Check a record in step 2 first.</p>'; return; }
    var obj;
    try { obj = parse(text); }
    catch (e) { box.innerHTML = '<div class="es-report-item"><div class="es-report-head"><span class="es-result is-bad">This is not valid JSON</span></div><div class="es-filebox">' + esc(e.message) + "</div></div>"; return; }
    var items = Array.isArray(obj) ? obj : [obj], reports = [];
    var docs = E.toEEEAll(items.filter(function (it) { return it && typeof it === "object" && !Array.isArray(it); }));
    items.forEach(function (item) {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        reports.push({ model_id: "", benchmark_id: "", score: null, well_formed: false, tier: "none", track: "predicted", default_tag: "unspecified", tag_inferred: false,
                       coverage: { required: { have: 0, of: 0, first_hand: 0, llm: 0, inferred: 0 } }, fields: [], warnings: [],
                       errors: [{ field: "(record)", message: "a record is a JSON object" }] });
        return;
      }
      var doc = docs.shift(), isFile = E.isEEE(item), structure = E.eeeStructureErrors(doc), mine = [];
      (isFile ? E.viewsFromEEE(item) : [E.viewFromFlat(item)]).forEach(function (view) {
        var r = E.check(view);
        if (isFile) { r.errors = structure.map(function (m) { return { field: "(EEE structure)", message: m }; }).concat(r.errors); r.well_formed = !r.errors.length; }
        mine.push(r); reports.push(r);
      });
      var title = (doc.model_info && doc.model_info.id || "no model") + " | " + mine.map(function (r) { return r.benchmark_id; }).join(", ");
      if (mine.some(function (r) { return !r.well_formed; })) { files.push({ title: title, problem: "Not well formed. Correct the errors listed in step 2 first." }); }
      else if (structure.length) { files.push({ title: title, problem: "The datastore file cannot be written yet: " + structure.map(esc).join("; ") + ". In a flat record, add <code>min_score</code> and <code>max_score</code>." }); }
      else { files.push({ title: title, asIs: isFile, path: E.datastorePath(doc), text: JSON.stringify(doc, null, 2) + "\n" }); }
    });
    var ok = reports.filter(function (r) { return r.well_formed; }), tiered = ok.filter(function (r) { return r.tier !== "none"; });
    box.innerHTML = "<p><b>" + ES.plural(reports.length, "record") + " checked.</b> " + tiered.length + " at the Required tier or above, " + (ok.length - tiered.length) +
      " well formed below it, " + (reports.length - ok.length) + " not well formed." +
      (reports.length > MAX_SHOWN ? " The first " + MAX_SHOWN + " are shown." : "") + "</p>" + reports.slice(0, MAX_SHOWN).map(reportItem).join("");
    var ready = files.filter(function (f) { return !f.problem; }).length;
    out.innerHTML = "<p><b>" + ES.plural(ready, "file") + " ready.</b> " + (files.length - ready ? (files.length - ready) + " cannot be written yet." : "") +
      (files.length > MAX_SHOWN ? " The first " + MAX_SHOWN + " are shown. For a set of this size, convert with the command-line tool described at the end of the page." : "") + "</p>" +
      files.slice(0, MAX_SHOWN).map(fileBox).join("");
  }
  function save(file) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([file.text], { type: "application/json" }));
    a.download = file.path.split("/").pop();
    document.body.appendChild(a); a.click(); a.remove();
    window.setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function showInCheck(obj) {
    $("#check-input").value = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
    check();
    $("#check").scrollIntoView();
  }
  function readFiles(list) {
    Promise.all(Array.prototype.map.call(list, function (f) { return f.text(); })).then(function (texts) {
      if (texts.length === 1) { showInCheck(texts[0]); return; }
      var all = [];
      try { texts.forEach(function (t) { var o = parse(t); all = all.concat(Array.isArray(o) ? o : [o]); }); showInCheck(all); }
      catch (e) { $("#check-report").innerHTML = '<p class="es-empty">One of the files is not valid JSON: ' + esc(e.message) + "</p>"; }
    });
  }

  /* ---------- wiring ---------- */
  buildForm();
  form.addEventListener("input", live);
  form.addEventListener("change", live);
  form.addEventListener("reset", function (e) { e.preventDefault(); clearForm(); $("#builder-loaded").hidden = true; live(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); showInCheck(readForm()); });
  form.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-hash]");
    if (!b) { return; }
    var text = $("#" + b.dataset.hash + "-text").value;
    if (text.trim()) { $("#" + b.dataset.hash).value = E.promptHash(text); live(); }
  });
  $("#check-run").addEventListener("click", check);
  $("#check-clear").addEventListener("click", function () { $("#check-input").value = ""; check(); $("#check-report").innerHTML = ""; $("#check-input").focus(); });
  $("#check-files").addEventListener("change", function (e) { if (e.target.files.length) { readFiles(e.target.files); e.target.value = ""; } });
  var drop = $("#check-drop");
  ["dragenter", "dragover"].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("is-over"); }); });
  ["dragleave", "drop"].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove("is-over"); }); });
  drop.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) { readFiles(e.dataTransfer.files); } });
  $$("button[data-example]").forEach(function (b) {
    b.addEventListener("click", function () { if (EXAMPLES[b.dataset.example]) { showInCheck(EXAMPLES[b.dataset.example]); } });
  });
  $("#file-out").addEventListener("click", function (e) { var b = e.target.closest("button[data-save]"); if (b) { save(files[+b.dataset.save]); } });

  var query = new URLSearchParams(window.location.search);
  if (query.get("record")) {
    try {
      var rec = JSON.parse(query.get("record"));
      fillForm(rec);
      if (rec.benchmark_id) {
        $("#builder-loaded").textContent = "The form holds the record for " + rec.model_id + " on " + rec.benchmark_id + (rec.source_name ? " from " + rec.source_name : "") +
          ". Correct what is wrong, add what only the evaluator knows, and say who is filling it in.";
        $("#builder-loaded").hidden = false;
      }
    } catch (e) { live(); }
  } else { live(); }
  if (query.get("example") && EXAMPLES[query.get("example")]) { showInCheck(EXAMPLES[query.get("example")]); }
})();
