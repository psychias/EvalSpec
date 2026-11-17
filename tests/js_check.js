/* Runs assets/js/evalspec.js on a JSON list of inputs and prints what it finds.
   Used by tests/test_evalspec.py to compare the browser validator with the Python one. */
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..");
const spec = JSON.parse(fs.readFileSync(path.join(root, "spec", "fields.json"), "utf8"));
const E = require(path.join(root, "assets", "js", "evalspec.js"))(spec);
const inputs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = inputs.map(function (x) {
  const res = { reports: E.views(x).map(E.check), structure: E.isEEE(x) ? E.eeeStructureErrors(x) : [] };
  if (!E.isEEE(x) && !Array.isArray(x)) { res.eee = E.toEEE(x, 1790000000); res.eee_reports = E.views(res.eee).map(E.check); }
  return res;
});
out.push({ hashes: ["Q: {{question}}\nA:", "", "  trailing spaces  \r\nsecond line\t\n\n", "ünïcödé ✓ 測試", "x".repeat(200)].map(E.promptHash) });
process.stdout.write(JSON.stringify(out));
