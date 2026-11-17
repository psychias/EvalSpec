/* Home page: the box that shows the published scores for one model on one benchmark, field by field. */
(function () {
  "use strict";
  // the article used to be at this address: a link to one of its sections is passed on to it
  if (window.location.hash.length > 1 && !document.getElementById(decodeURIComponent(window.location.hash.slice(1)))) {
    window.location.replace("article.html" + window.location.hash);
    return;
  }
  var ES = window.ES, box = document.getElementById("specimen");
  if (!ES || !box || !ES.site.featured) { return; }
  var want = ES.site.featured, MAX = 6;

  ES.loadShard(want.model).then(function (p) {
    var recs = [];
    for (var i = 0; i < p.n; i++) {
      if (p.models[p.cols.model[i]].key === want.model && p.benches[p.cols.bench[i]].key === want.bench) { recs.push(p.record(i)); }
    }
    if (!recs.length) { return; }
    // one score per source, predicted records first: the box opens on what the public record looked like
    var seen = {};
    recs = recs.filter(function (r) { return !r.superseded; })
      .sort(function (a, b) { return a.author - b.author || a.source.rank - b.source.rank || a.score - b.score; })
      .filter(function (r) { var k = r.source.key + "|" + r.score; if (seen[k]) { return false; } seen[k] = true; return true; })
      .slice(0, MAX);
    var model = recs[0].model, bench = recs[0].bench, current = 0;

    function draw() {
      var r = recs[current], procedure = ES.spec.fields.filter(function (f) { return f.tier === "required" && r.status[f.name] !== 5; });
      var onRecord = procedure.filter(function (f) { return r.status[f.name] >= 1 && r.status[f.name] <= 3; }).length;
      box.innerHTML =
        '<div class="es-rec">' +
          '<div class="es-rec-head"><b>' + ES.esc(model.id) + "</b><span>" + ES.esc(bench.label) + ", " + ES.plural(recs.length, "published score") + "</span></div>" +
          '<div class="es-rec-tabs" role="group" aria-label="Published scores">' + recs.map(function (x, i) {
            return '<button type="button" data-i="' + i + '" aria-pressed="' + (i === current) + '"><b>' + ES.score(x.score, x.hi) + "</b><span>" +
                   ES.esc(x.source.label) + "</span></button>";
          }).join("") + "</div>" +
          '<div class="es-rec-meta">' + ES.trackLabel(r) + " " + ES.sourceLine(r.source) + "</div>" +
          ES.fields(r, { tiers: ["required"], skipNA: true, stacked: true }) +
          '<div class="es-rec-foot"><span>' + onRecord + " of " + procedure.length + ' Required fields on record</span>' +
          '<a href="' + ES.esc(ES.modelUrl(model.id, bench.key)) + '">All reports for this model</a></div>' +
        "</div>" +
        '<figcaption>One model, one benchmark, ' + ES.plural(recs.length, "published score") + ". Select a score to see what its record says about how it was produced. " +
        "A solid mark was reported by whoever ran the evaluation, a grey one was read from the source by a language model, " +
        "a hatched one was inferred by a pipeline, and a dashed one is not on record.</figcaption>";
    }

    box.addEventListener("click", function (e) {
      var b = e.target.closest(".es-rec-tabs button");
      if (!b) { return; }
      current = +b.dataset.i; draw();
      var again = box.querySelector('.es-rec-tabs button[data-i="' + current + '"]');
      if (again) { again.focus(); }
    });
    draw();
  }, function () {});
})();
