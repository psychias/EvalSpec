/* EvalSpec in the browser: the same checks as tools/evalspec.py, driven by the same spec/fields.json.
   Browser: needs window.EVALSPEC_SPEC (data/spec.js) and defines window.EvalSpec.
   Node:    const EvalSpec = require("./evalspec.js")(spec);                                            */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory; }
  else { root.EvalSpec = factory(root.EVALSPEC_SPEC); }
})(typeof self !== "undefined" ? self : this, function (SPEC) {
  "use strict";
  var FIELDS = SPEC.fields, FIELD = {}, TIERS = SPEC.tiers.map(function (t) { return t.id; });
  var TAG_CLASS = {}, TAG_NAME = {}, MODE_ALIAS = {}, MISSING = SPEC.missing_values;
  FIELDS.forEach(function (f) { FIELD[f.name] = f; });
  SPEC.provenance_tags.forEach(function (t) { TAG_CLASS[t.id.toLowerCase()] = t["class"]; TAG_NAME[t.id.toLowerCase()] = t.id; });
  SPEC.scoring_modes.forEach(function (m) { [m.id].concat(m.aliases).forEach(function (a) { MODE_ALIAS[a] = m.id; }); });
  var IDENTITY = ["model_id", "benchmark_id"];
  var CONTEXT = SPEC.record_keys.map(function (k) { return k.name; }).filter(function (k) { return k !== "evidence_source"; });
  var SHA256 = /^sha256:[0-9a-f]{64}$/;
  var TIMESTAMP = /^([0-9]{4})-([0-9]{2})-([0-9]{2})([T ][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$/;
  var NUMBER = /^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$/;
  var URL = /^https?:\/\/\S+$/;

  function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function isMissing(v) { return v === null || v === undefined || (typeof v === "string" && MISSING.indexOf(v.trim().toLowerCase()) >= 0); }

  /* ---------- reading records ---------- */
  function isEEE(o) { return isObject(o) && Array.isArray(o.evaluation_results) && has(o, "model_info"); }

  function get(obj, parts) {            // a part ending in [] maps over a list and joins what it finds
    for (var i = 0; i < parts.length; i++) {
      if (!isObject(obj)) { return null; }
      var part = parts[i];
      if (part.slice(-2) === "[]") {
        var items = obj[part.slice(0, -2)], rest = parts.slice(i + 1);
        var found = (Array.isArray(items) ? items : []).map(function (it) { return get(it, rest); })
          .filter(function (v) { return !isMissing(v); }).map(String);
        return found.length ? found.join(", ") : null;
      }
      obj = obj[part];
    }
    return obj === undefined ? null : obj;
  }
  function read(doc, result, path) {
    var parts = path.split(".");
    return parts[0] === "evaluation_results[]" ? get(result, parts.slice(1)) : get(doc, parts);
  }
  function firstUrl(result) {           // the address a result was read from, when the file gives one
    var urls = (result.source_data || {}).url;
    return Array.isArray(urls) && urls.length && typeof urls[0] === "string" ? urls[0] : null;
  }
  function legacyTag(doc, details) {    // records written before provenance tags existed
    var sm = doc.source_metadata || {};
    if (sm.source_type === "evaluation_run") { return "source-reported"; }
    var names = ((sm.source_name || "") + " " + (details.source || "")).toLowerCase();
    if (has(details, "extraction_confidence") || names.indexOf("arxiv") >= 0 || names.indexOf("archiv") >= 0) { return "LLM-extracted"; }
    return "documentation-inferred";
  }
  function overrides(details) {
    var out = {};
    Object.keys(details).forEach(function (k) { if (k.indexOf("evidence_source.") === 0) { out[k.slice(16)] = details[k]; } });
    return out;
  }

  function viewsFromEEE(doc) {
    var sm = doc.source_metadata || {}, fileDetails = sm.additional_details || {}, mi = doc.model_info || {};
    return (doc.evaluation_results || []).map(function (result, index) {
      var gc = result.generation_config || {}, details = gc.additional_details || {}, args = gc.generation_args || {};
      var raw = {};
      FIELDS.forEach(function (f) {
        var paths = [f.eee_path].concat(f.eee_also);
        for (var i = 0; i < paths.length; i++) {
          var v = read(doc, result, paths[i]);
          if (!isMissing(v)) { raw[f.name] = v; break; }
        }
      });
      var collected = has(raw, "evaluation_timestamp") && String(raw.evaluation_timestamp) === String(doc.retrieved_timestamp === undefined ? null : doc.retrieved_timestamp);
      if (collected) { delete raw.evaluation_timestamp; }
      var prov = overrides(fileDetails), own = overrides(details);
      Object.keys(own).forEach(function (k) { prov[k] = own[k]; });
      var explicit = details.evidence_source || fileDetails.evidence_source;
      var mc = result.metric_config || {}, sd = result.score_details || {};
      var context = {
        score: sd.score === undefined ? null : sd.score,
        metric_name: mc.metric_name, min_score: mc.min_score, max_score: mc.max_score, lower_is_better: mc.lower_is_better,
        model_name: mi.name, developer: mi.developer,
        source_name: sm.source_name, source_organization_name: sm.source_organization_name,
        source_organization_url: sm.source_organization_url,
        source_type: sm.source_type, evaluator_relationship: sm.evaluator_relationship,
        source_kind: fileDetails.source_kind, source_url: firstUrl(result),
        extractor_model: fileDetails.extractor_model, extraction_date: fileDetails.extraction_date,
        evaluation_id: doc.evaluation_id, result_index: index,
        chain_of_thought: args.chain_of_thought, prompt_template: args.prompt_template,
        note: details.note, raw_score: (sd.details || {}).raw_score
      };
      Object.keys(context).forEach(function (k) { if (context[k] === undefined) { context[k] = null; } });
      var view = makeView(raw, explicit || legacyTag(doc, details), prov, context, !explicit, []);
      if (collected) { view.notes.push(["evaluation_timestamp", "equal to retrieved_timestamp: read as the date the record was collected, not the date of the run"]); }
      return view;
    });
  }

  function viewFromFlat(rec) {
    var raw = {}, notes = [];
    FIELDS.forEach(function (f) {
      if (has(rec, f.name)) { raw[f.name] = rec[f.name]; return; }
      var aliases = f.aliases || [];
      for (var i = 0; i < aliases.length; i++) {
        var v = get(rec, aliases[i].split("."));
        if (v !== null || has(rec, aliases[i])) {
          raw[f.name] = v;
          notes.push([f.name, "written as '" + aliases[i] + "'; the field is called '" + f.name + "'"]);
          break;
        }
      }
    });
    var es = rec.evidence_source, prov = {}, def = es;
    if (isObject(es)) { def = has(es, "default") ? es["default"] : null; Object.keys(es).forEach(function (k) { if (k !== "default") { prov[k] = es[k]; } }); }
    var context = {};
    CONTEXT.forEach(function (k) { context[k] = has(rec, k) ? rec[k] : null; });
    if (context.metric_name === null && typeof rec.metric === "string") { context.metric_name = rec.metric; }   // the released hook writes 'metric'
    var nulls = Object.keys(raw).filter(function (k) { return raw[k] === null; });
    var view = makeView(raw, def, prov, context, false, nulls);
    Object.keys(raw).forEach(function (k) {
      if (typeof raw[k] === "string" && has(view.values, k) && ["integer", "number", "integer_or_list"].indexOf(FIELD[k].type) >= 0) {
        notes.push([k, "written as text; use a number"]);
      }
    });
    view.notes = view.notes.concat(notes);
    return view;
  }

  function makeView(raw, defaultTag, prov, context, tagInferred, explicitNull) {
    var values = {}, invalid = {}, notes = [];
    Object.keys(raw).forEach(function (name) {
      var v = raw[name];
      if (isMissing(v) && !(name === "judge_model" && explicitNull.indexOf(name) >= 0)) { return; }
      var r = coerce(FIELD[name], v);
      if (r[0]) { values[name] = r[1]; if (r[2]) { notes.push([name, r[2]]); } }
      else { invalid[name] = r[2]; }
    });
    if (has(values, "judge_model") && typeof values.judge_model === "string" &&
        ["none", "null", "n/a", "not applicable"].indexOf(values.judge_model.trim().toLowerCase()) >= 0) { values.judge_model = null; }
    var mode = values.scoring_mode;
    if (!has(values, "judge_model") && !has(invalid, "judge_model") && ["log-likelihood", "generation", "execution"].indexOf(mode) >= 0) {
      values.judge_model = null;          // a scoring mode without a judge implies there is none
    }
    var def = TAG_NAME[String(defaultTag || "").toLowerCase()] || null;
    if (defaultTag && !def) { notes.push(["evidence_source", "'" + defaultTag + "' is not one of the five provenance tags"]); }
    var provenance = {};
    Object.keys(values).forEach(function (name) {
      var tag = TAG_NAME[String(has(prov, name) ? prov[name] : "").toLowerCase()] || null;
      if (!tag && def && TAG_CLASS[def.toLowerCase()] === "inferred" && IDENTITY.indexOf(name) >= 0) { tag = "API-exposed"; }
      if (name === "judge_model" && values[name] === null && !has(raw, name)) { tag = provenance.scoring_mode || tag; }
      provenance[name] = tag || def || "unspecified";
    });
    return { values: values, invalid: invalid, provenance: provenance, default_tag: def || "unspecified",
             tag_inferred: tagInferred, context: context, notes: notes,
             track: def === "source-reported" ? "author-reported" : "predicted" };
  }

  function number(v) {                  // a finite number, or null
    if (typeof v === "number") { return isFinite(v) ? v : null; }
    return typeof v === "string" && NUMBER.test(v.trim()) ? parseFloat(v.trim()) : null;
  }

  function coerce(f, v) {               // [ok, value, message]
    var t = f.type, s, n;
    if (t === "string" || t === "string_or_null") {
      if (v === null && t === "string_or_null") { return [true, null, null]; }
      if (typeof v === "object" || typeof v === "boolean") { return [false, null, "must be text"]; }
      s = String(v).trim();
      if ((f.not_values || []).indexOf(s.toLowerCase()) >= 0) { return [false, null, "'" + s + "' does not identify an immutable version"]; }
      return [true, s, null];
    }
    if (t === "enum") {
      s = String(v).trim().toLowerCase();
      if (has(MODE_ALIAS, s)) { return [true, MODE_ALIAS[s], s === MODE_ALIAS[s] ? null : "written as '" + v + "'; the value is '" + MODE_ALIAS[s] + "'"]; }
      return [false, null, "'" + v + "' is not one of: " + f["enum"].join(", ")];
    }
    if (t === "integer" || t === "number") {
      n = number(v);
      if (n === null || (t === "integer" && !Number.isInteger(n))) { return [false, null, t === "integer" ? "must be an integer" : "must be a number"]; }
      if (has(f, "min") && n < f.min) { return [false, null, "must be at least " + f.min]; }
      if (has(f, "exclusive_min") && n <= f.exclusive_min) { return [false, null, "must be greater than " + f.exclusive_min]; }
      if (has(f, "max") && n > f.max) { return [false, null, "must be at most " + f.max]; }
      return [true, n, null];
    }
    if (t === "integer_or_list") {
      var items = Array.isArray(v) ? v : String(v).trim().replace(/^[\[\]]+|[\[\]]+$/g, "").split(/[,\s]+/);
      var nums = items.filter(function (x) { return String(x) !== ""; }).map(number);
      if (!nums.length || nums.some(function (x) { return x === null || !Number.isInteger(x); })) { return [false, null, "must be an integer or a list of integers"]; }
      return [true, nums.length === 1 ? nums[0] : nums, null];
    }
    s = String(v).trim();
    if (t === "sha256") { return SHA256.test(s.toLowerCase()) ? [true, s.toLowerCase(), null] : [false, null, "must be 'sha256:' followed by 64 hexadecimal digits"]; }
    if (t === "timestamp") {
      var m = TIMESTAMP.exec(s);
      if (m) {
        var y = +m[1], mo = +m[2], d = +m[3], dt = new Date(Date.UTC(2000, mo - 1, d));
        dt.setUTCFullYear(y);
        if (y >= 1 && dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d) { return [true, s, null]; }
      }
      return [false, null, "must be an ISO 8601 date or date-time, for example 2026-07-03T10:00:00Z"];
    }
    if (t === "url") { return URL.test(s) ? [true, s, null] : [false, null, "must be an http or https address"]; }
    throw new Error("unknown field type " + t);
  }

  /* ---------- checking a view ---------- */
  function applies(f, values) {
    if (f.applies === "generation") { return values.scoring_mode === "generation"; }
    if (f.applies === "judge") { return values.scoring_mode === "preference" || typeof values.judge_model === "string"; }
    return true;
  }
  function scorePercent(context) {      // the score on 0 to 100 when the record states a 0-1 or 0-100 range
    var s = number(context.score), lo = number(context.min_score), hi = number(context.max_score);
    if (s === null || lo !== 0 || (hi !== 1 && hi !== 100)) { return null; }
    return Math.round(s * 100 / hi * 10000) / 10000;
  }

  function check(view) {
    var values = view.values, invalid = view.invalid, ctx = view.context;
    var errors = Object.keys(invalid).map(function (k) { return { field: k, message: invalid[k] }; });
    var warnings = view.notes.map(function (n) { return { field: n[0], message: n[1] }; });
    IDENTITY.forEach(function (key) {
      if (!has(values, key) && !has(invalid, key)) { errors.push({ field: key, message: "is required to identify the record" }); }
    });
    if (number(ctx.score) === null) { errors.push({ field: "score", message: "a numeric score is required" }); }
    else if (scorePercent(ctx) === null && (ctx.min_score === null || ctx.min_score === undefined || ctx.max_score === null || ctx.max_score === undefined)) {
      warnings.push({ field: "score", message: "the score's range is not stated; add min_score and max_score" });
    }
    if (view.default_tag === "unspecified") { warnings.push({ field: "evidence_source", message: "not stated; say who filled in the fields (see the five provenance tags)" }); }
    if (view.default_tag === "LLM-extracted" && isMissing(ctx.extractor_model)) { warnings.push({ field: "extractor_model", message: "an LLM-extracted record should name the model that extracted it" }); }
    if (isMissing(ctx.source_name)) { warnings.push({ field: "source_name", message: "not stated; say where the score is published, so that the registry can list the record under its source" }); }
    if (values.scoring_mode === "preference" && has(values, "judge_model") && values.judge_model === null) {
      warnings.push({ field: "judge_model", message: "preference scoring needs a scorer; name the judge model, or write 'human' for human raters" });
    }
    var fields = [], coverage = {};
    TIERS.forEach(function (t) { coverage[t] = { have: 0, of: 0, first_hand: 0, llm: 0, inferred: 0 }; });
    FIELDS.forEach(function (f) {
      var name = f.name, cov = coverage[f.tier], row = { name: name, tier: f.tier };
      if (!applies(f, values)) { row.status = "not_applicable"; }
      else if (has(values, name)) {
        var cls = TAG_CLASS[view.provenance[name].toLowerCase()] || "inferred";
        row.status = "reported"; row.value = values[name]; row.provenance = view.provenance[name];
        cov.have += 1; cov[cls === "first-hand" ? "first_hand" : cls] += 1; cov.of += 1;
      } else { row.status = has(invalid, name) ? "invalid" : "missing"; cov.of += 1; }
      fields.push(row);
    });
    var tier = "none";
    for (var i = 0; i < TIERS.length; i++) {
      if (coverage[TIERS[i]].have < coverage[TIERS[i]].of) { break; }
      tier = TIERS[i];
    }
    return { model_id: has(values, "model_id") ? values.model_id : null, benchmark_id: has(values, "benchmark_id") ? values.benchmark_id : null,
             score: ctx.score === undefined ? null : ctx.score,
             track: view.track, default_tag: view.default_tag, tag_inferred: view.tag_inferred,
             tier: tier, well_formed: !errors.length, coverage: coverage, fields: fields, errors: errors, warnings: warnings };
  }

  function eeeStructureErrors(doc) {    // the EEE keys a datastore file cannot do without
    var need = [["", ["schema_version", "evaluation_id", "retrieved_timestamp", "source_metadata", "model_info", "eval_library", "evaluation_results"]],
                ["source_metadata", ["source_type", "source_organization_name", "evaluator_relationship"]],
                ["model_info", ["name", "id"]], ["eval_library", ["name", "version"]]];
    var out = [];
    need.forEach(function (n) {
      var holder = n[0] ? (isObject(doc[n[0]]) ? doc[n[0]] : {}) : doc;
      n[1].forEach(function (k) { if (!has(holder, k)) { out.push((n[0] ? n[0] + "." : "") + k + " is missing"); } });
    });
    (doc.evaluation_results || []).forEach(function (r, i) {
      ["evaluation_name", "source_data", "metric_config", "score_details"].forEach(function (k) {
        if (!isObject(r) || !has(r, k)) { out.push("evaluation_results[" + i + "]." + k + " is missing"); }
      });
      var mc = isObject(r) ? r.metric_config : null;
      if (isObject(mc)) {
        var kind = has(mc, "score_type") ? mc.score_type : "levels";     // EEE reads a missing score_type as 'levels'
        var needKeys = { levels: ["level_names", "has_unknown_level"], continuous: ["min_score", "max_score"] }[kind] || [];
        ["lower_is_better"].concat(needKeys).forEach(function (k) {
          if (!has(mc, k)) { out.push("evaluation_results[" + i + "].metric_config." + k + " is missing (EEE requires it for a " + kind + " score)"); }
        });
      }
    });
    return out;
  }

  function views(obj) {                 // an EEE file, a flat record, or a list of either
    if (Array.isArray(obj)) { return obj.reduce(function (acc, item) { return acc.concat(views(item)); }, []); }
    if (isEEE(obj)) { return viewsFromEEE(obj); }
    if (isObject(obj)) { return [viewFromFlat(obj)]; }
    throw new Error("expected a JSON object or a list of objects");
  }

  /* ---------- flat record -> EEE file ---------- */
  function dumps(v) { return Array.isArray(v) ? "[" + v.join(", ") + "]" : JSON.stringify(v); }
  function slug(text) { return String(text).replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "unnamed"; }

  function toEEE(rec, now) {
    var view = viewFromFlat(rec), v = view.values, ctx = view.context;
    now = Math.floor(now === undefined ? Date.now() / 1000 : now);
    var modelId = String(has(v, "model_id") ? v.model_id : "unknown"), details = {};
    FIELDS.forEach(function (f) {
      var name = f.name;
      if (has(v, name) && v[name] !== null && f.eee_path.indexOf("additional_details") >= 0) {
        details[name] = typeof v[name] === "string" ? v[name] : dumps(v[name]);
      }
    });
    var judge = has(v, "judge_model") ? v.judge_model : undefined, llm = null;
    if (has(v, "judge_model") && judge === null && !has(v, "scoring_mode")) { details.judge_model = "none"; }
    if (typeof judge === "string" && judge.toLowerCase().indexOf("human") !== 0) {
      llm = { judges: judge.split(/,\s*/).map(function (j) { return { model_info: { name: j.split("/").pop(), id: j } }; }),
              input_prompt: "not recorded here; see judge_prompt_hash" };
    } else if (typeof judge === "string") { details.judge_model = judge; }
    Object.keys(view.provenance).forEach(function (k) {
      var t = view.provenance[k];
      if (t !== view.default_tag && t !== "unspecified" && !(k === "judge_model" && v[k] === null)) { details["evidence_source." + k] = t; }
    });
    var args = {};
    [["shots", "n_shot"], ["temperature", "temperature"], ["top_p", "top_p"]].forEach(function (p) { if (has(v, p[1])) { args[p[0]] = v[p[1]]; } });
    if (typeof ctx.chain_of_thought === "boolean") { args.chain_of_thought = ctx.chain_of_thought; }
    if (!isMissing(ctx.prompt_template)) { args.prompt_template = String(ctx.prompt_template); }
    var source = ctx.source_name || "unspecified source", author = view.track === "author-reported", fileDetails = {};
    ["extractor_model", "extraction_date", "source_kind"].forEach(function (k) { if (!isMissing(ctx[k])) { fileDetails[k] = String(ctx[k]); } });
    if (view.default_tag !== "unspecified") { fileDetails.evidence_source = view.default_tag; }
    var metric = { metric_name: ctx.metric_name || "unspecified", lower_is_better: !!ctx.lower_is_better, score_type: "continuous" };
    ["min_score", "max_score"].forEach(function (k) { if (number(ctx[k]) !== null) { metric[k] = ctx[k]; } });
    if (llm) { metric.llm_scoring = llm; }
    var bench = String(has(v, "benchmark_id") ? v.benchmark_id : "unknown");
    var result = {
      evaluation_name: bench,
      source_data: !isMissing(ctx.source_url) ? { dataset_name: bench, source_type: "url", url: [ctx.source_url] }
                                              : { dataset_name: bench, source_type: "other" },
      metric_config: metric,
      score_details: { score: ctx.score },
      generation_config: { generation_args: args, additional_details: details }
    };
    if (has(v, "evaluation_timestamp")) { result.evaluation_timestamp = v.evaluation_timestamp; }
    var model = { name: ctx.model_name || modelId.split("/").pop(), id: modelId };
    var developer = ctx.developer || (modelId.indexOf("/") >= 0 ? modelId.split("/")[0] : null);
    if (developer) { model.developer = String(developer); }
    if (has(v, "quantization") && v.quantization) { model.quantization = String(v.quantization); }
    var meta = { source_name: source, source_type: author ? "evaluation_run" : "documentation",
                 source_organization_name: ctx.source_organization_name || source,
                 evaluator_relationship: ctx.evaluator_relationship || "other" };
    if (!isMissing(ctx.source_organization_url)) { meta.source_organization_url = ctx.source_organization_url; }
    if (Object.keys(fileDetails).length) { meta.additional_details = fileDetails; }
    return {
      schema_version: SPEC["extends"].version,
      evaluation_id: ctx.evaluation_id || slug(source) + "/" + modelId.replace(/\//g, "_") + "/" + slug(bench) + "/" + now,
      retrieved_timestamp: String(now),
      source_metadata: meta,
      eval_library: { name: has(v, "harness_name") ? v.harness_name : "unknown", version: has(v, "harness_version") ? v.harness_version : "unknown" },
      model_info: model,
      evaluation_results: [result]
    };
  }

  function toEEEAll(records, now) {     // EEE files pass through; generated ids are made unique
    var seen = {};
    return records.map(function (rec) {
      if (isEEE(rec)) { return rec; }
      var doc = toEEE(rec, now), n = seen[doc.evaluation_id] = (seen[doc.evaluation_id] || 0) + 1;
      if (n > 1) { doc.evaluation_id += "/" + n; }
      return doc;
    });
  }
  function uuid() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) { return crypto.randomUUID(); }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }
  function datastorePath(doc, token) {  // data/<source>-<id>.jsonl, one record per line; the id keeps a submission from replacing a file
    return "data/" + slug(doc.source_metadata.source_name || "unnamed").toLowerCase() + "-" + (token || uuid().replace(/-/g, "").slice(0, 8)) + ".jsonl";
  }

  /* ---------- sha256 of a prompt template, trimmed as the released hook trims it ---------- */
  function sha256hex(bytes) {
    var K = [], H = [], i, j, isPrime = function (n) { for (var d = 2; d * d <= n; d++) { if (n % d === 0) { return false; } } return true; };
    var frac = function (x) { return ((x - Math.floor(x)) * 4294967296) | 0; };
    for (i = 2; K.length < 64; i++) { if (isPrime(i)) { if (H.length < 8) { H.push(frac(Math.sqrt(i))); } K.push(frac(Math.cbrt(i))); } }
    var l = bytes.length, total = ((l + 9 + 63) >> 6) << 6, m = new Uint8Array(total), w = new Int32Array(64);
    m.set(bytes); m[l] = 0x80;
    var view = new DataView(m.buffer);
    view.setUint32(total - 8, Math.floor(l / 536870912)); view.setUint32(total - 4, (l << 3) >>> 0);
    var rotr = function (x, n) { return (x >>> n) | (x << (32 - n)); };
    for (var off = 0; off < total; off += 64) {
      for (i = 0; i < 16; i++) { w[i] = view.getInt32(off + i * 4); }
      for (i = 16; i < 64; i++) {
        var s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3), s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (i = 0; i < 64; i++) {
        var t1 = (h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
        var t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      H = [(H[0] + a) | 0, (H[1] + b) | 0, (H[2] + c) | 0, (H[3] + d) | 0, (H[4] + e) | 0, (H[5] + f) | 0, (H[6] + g) | 0, (H[7] + h) | 0];
    }
    return H.map(function (x) { return ("00000000" + (x >>> 0).toString(16)).slice(-8); }).join("");
  }
  function promptHash(text) {
    var canonical = String(text).trim().split(/\r\n|\r|\n/).map(function (line) { return line.replace(/\s+$/, ""); }).join("\n");
    return "sha256:" + sha256hex(new TextEncoder().encode(canonical));
  }

  return { spec: SPEC, fields: FIELDS, field: FIELD, tiers: TIERS, tagClass: TAG_CLASS,
           isMissing: isMissing, isEEE: isEEE, views: views, viewFromFlat: viewFromFlat, viewsFromEEE: viewsFromEEE,
           check: check, applies: applies, scorePercent: scorePercent, eeeStructureErrors: eeeStructureErrors,
           toEEE: toEEE, toEEEAll: toEEEAll, datastorePath: datastorePath, uuid: uuid, slug: slug, promptHash: promptHash };
});
