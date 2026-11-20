"""Static markup for the figures that are easier to generate than to type.
   Each function returns an HTML/SVG string; build.py drops it in at <!--FIG:name-->.
   The figures are complete as markup: scripts only add hover and click behaviour."""
from html import escape as e

BLUE, VERM = '#0072b2', '#d55e00'


# ------------------------------------------------------------------ hero: the paper's Figure 1
def paths():
    """Same nodes, labels and layout as figures/figure_teaser.tex (TikZ coordinates in cm, converted to px).
       One difference: the paper's ribbons skip the middle "3-shot" chip; here the 68.20 path runs through it."""
    SX, SY, OX, OY = 56, 50, 0.22, 0.5
    X = lambda x: round((x - OX) * SX, 1)
    Y = lambda y: round((OY - y) * SY, 1)
    ya, yb, yc = -1.05, -2.35, -3.55
    W, H = 884, 306
    heads = [(1.5, 'Model × benchmark'), (4.5, 'Scoring mode'), (7.5, 'Harness'), (9.9, 'n-shot'), (12.3, 'Score shown'), (14.9, 'Published')]
    chips = [  # id, x, y, text width (cm), lines, paths
        ('m', 1.5, ya, 1.5, ['gemma-2-9b', '× BBH'], '1 2 3'),
        ('s1', 4.5, ya, 1.6, ['log-likelihood'], '1'), ('s2', 4.5, yb, 1.6, ['CoT generation'], '2 3'),
        ('h1', 7.5, ya, 1.7, ['lm-eval, OLv2 fork'], '1'), ('h2', 7.5, yb, 1.7, ["the model's own", 'pipeline'], '2 3'),
        ('n1', 9.9, ya, 0.75, ['3-shot'], '1'), ('n2', 9.9, yb, 0.75, ['3-shot'], '2'), ('n3', 9.9, yc, 0.75, ['0-shot'], '3'),
        ('v1', 12.3, ya, 1.6, ['leaderboard-', 'normalised'], '1'), ('v2', 12.3, yb, 1.6, ['raw'], '2 3')]
    ribs = [  # x1, y1, x2, y2, paths
        (2.5, ya, 3.5, ya, '1'), (2.5, ya, 3.5, yb, '2 3'),
        (5.5, ya, 6.4, ya, '1'), (5.5, yb, 6.4, yb, '2 3'),
        (8.6, ya, 9.35, ya, '1'), (8.6, yb, 9.35, yb, '2'), (8.6, yb, 9.35, yc, '3'),
        (10.45, ya, 11.3, ya, '1'), (10.45, yb, 11.3, yb, '2'), (10.45, yc, 11.3, yb, '3'),
        (13.3, ya, 14.3, ya, '1'), (13.3, yb, 14.3, yb, '2'), (13.3, yb, 14.3, yc, '3')]
    scores = [(1, ya, '34.10'), (2, yb, '68.20'), (3, yc, '69.00')]
    out = [f'<svg viewBox="0 0 {W} {H}" role="group" aria-labelledby="paths-title paths-desc">',
           '<title id="paths-title">One cell, two protocols: three published scores for Gemma-2-9B on BBH</title>',
           '<desc id="paths-desc">The Open LLM Leaderboard v2 publishes 34.10: log-likelihood scoring, a fork of lm-eval, 3-shot, leaderboard-normalised. The Gemma 2 report publishes 68.20 and the Gemma 3 report 69.00: chain-of-thought generation, the model\'s own pipeline, 3-shot and 0-shot, raw scale. No source records scoring mode, harness, shot count or score scale as a field; a reader sees only the published number.</desc>']
    for x, t in heads:
        out.append(f'<text class="hdr" x="{X(x)}" y="{Y(0.05) + 4}" text-anchor="middle">{e(t)}</text>')
    for x1, y1, x2, y2, ps in ribs:
        mx = (X(x1) + X(x2)) / 2
        out.append(f'<path class="rib" data-paths="{ps}" d="M{X(x1)},{Y(y1)} C{mx},{Y(y1)} {mx},{Y(y2)} {X(x2)},{Y(y2)}"/>')
    out.append(f'<text class="mlab" x="{X(4.5)}" y="{Y(ya + 0.42) + 3}" text-anchor="middle">OLv2</text>')
    out.append(f'<text class="mlab" x="{X(4.5)}" y="{Y(yb + 0.42) + 3}" text-anchor="middle">the model\'s reports</text>')
    for cid, x, y, tw, lines, ps in chips:
        w = (tw + 0.24) * SX; h = 36 if len(lines) == 2 else 23
        out.append(f'<g class="chip" data-paths="{ps}" tabindex="0" role="button" aria-label="{e(" ".join(lines))}: show the scores that pass through this step">')
        out.append(f'<rect x="{X(x) - w / 2:.1f}" y="{Y(y) - h / 2:.1f}" width="{w:.1f}" height="{h}" rx="3"/>')
        if len(lines) == 2:
            out.append(f'<text x="{X(x)}" y="{Y(y) - 3}" text-anchor="middle">{e(lines[0])}</text><text x="{X(x)}" y="{Y(y) + 11}" text-anchor="middle">{e(lines[1])}</text>')
        else:
            out.append(f'<text x="{X(x)}" y="{Y(y) + 4}" text-anchor="middle">{e(lines[0])}</text>')
        out.append('</g>')
    for p, y, val in scores:
        out.append(f'<g class="score" data-p="{p}" tabindex="0" role="button" aria-label="{val}: show the path behind this score">'
                   f'<rect class="hit" x="{X(14.3) + 4}" y="{Y(y) - 17}" width="{X(15.6) - X(14.3) - 4}" height="34" rx="3"/>'
                   f'<text x="{X(14.9)}" y="{Y(y) + 7}" text-anchor="middle">{val}</text></g>')

    def brace(x1, x2, y, cls):
        m = (x1 + x2) / 2
        return f'<path class="{cls}" d="M{x1},{y} q0,6 6,6 H{m - 6} q6,0 6,6 q0,-6 6,-6 H{x2 - 6} q6,0 6,-6"/>'
    by = Y(-4.15)
    out.append(brace(X(3.3), X(11.3), by, 'brace red'))
    out.append(f'<text class="blab red" x="{X(7.3)}" y="{by + 28}" text-anchor="middle">no source records this as a field</text>')
    out.append(brace(X(14.1), X(15.7), by, 'brace'))
    out.append(f'<text class="blab" x="{X(14.9)}" y="{by + 28}" text-anchor="middle">all you see</text>')
    ay = Y(-5.3)
    out.append(f'<path class="arrow red" d="M{X(14.3)},{ay} H{X(3.3) + 8}"/><path class="arrowhead red" d="M{X(3.3)},{ay} l10,-4.5 v9 z"/>')
    out.append(f'<text class="blab red" x="{X(8.8)}" y="{ay - 7}" text-anchor="middle">34.10 vs. 68.20 is a 34.1 pp gap, and no field recovers which path produced it</text>')
    out.append('</svg>')
    cards = ''.join(f'<li><b class="{c}">{val}</b> {e(who)}<span>{e(d)}</span></li>' for val, who, c, d in [
        ('34.10', 'OLv2', 'blue', 'log-likelihood; lm-eval, OLv2 fork; 3-shot; leaderboard-normalised'),
        ('68.20', "the model's reports", 'gold', "CoT generation; the model's own pipeline; 3-shot; raw"),
        ('69.00', "the model's reports", 'gold', "CoT generation; the model's own pipeline; 0-shot; raw")])
    return '<div class="paths-wide">' + '\n'.join(out) + '</div>\n<ul class="paths-narrow">' + cards + '</ul>'


# ------------------------------------------------------------------ one question, two runs
def pipeline():
    W, H = 880, 196
    xs = [58, 167, 276, 385, 494, 603, 712, 821]
    yt, ym, yb_ = 78, 108, 138
    stages = [  # key, header, split?, top label, bottom label
        ('item', 'Question', False, None, None), ('prompt', 'Prompt', True, '3 examples', '3 examples + reasoning'),
        ('model', 'Model', False, None, None), ('mode', 'Scoring mode', True, 'rank the options', 'generate, then extract'),
        ('mark', 'Right or wrong', False, None, None), ('avg', 'Average', False, None, None),
        ('rescale', 'Rescale', True, 'yes', 'no'), ('pub', 'Published score', True, '34.10', '68.20')]
    out = [f'<svg viewBox="0 0 {W} {H}" role="group" aria-labelledby="pipe-title pipe-desc">',
           '<title id="pipe-title">The steps from a benchmark question to a published score, for two sources</title>',
           '<desc id="pipe-desc">Eight steps: question, prompt, model, scoring mode, right or wrong, average, rescale, published score. The leaderboard and the developers\' report share the question, the model, the marking and the averaging. They differ in the prompt, the scoring mode and the rescaling, and publish 34.10 and 68.20.</desc>']
    for x, st in zip(xs, stages):
        out.append(f'<rect class="colbg{" on" if st[0] == "mode" else ""}" data-k="{st[0]}" x="{x - 53}" y="6" width="106" height="{H - 12}" rx="4"/>')
    pts_t = [(x, yt if st[2] else ym) for x, st in zip(xs, stages)]
    pts_b = [(x, yb_ if st[2] else ym) for x, st in zip(xs, stages)]
    out.append('<polyline class="edge lb" points="' + ' '.join(f'{x},{y}' for x, y in pts_t) + '"/>')
    out.append('<polyline class="edge rp" points="' + ' '.join(f'{x},{y}' for x, y in pts_b) + '"/>')
    for i, (x, (key, head, split, lt, lb)) in enumerate(zip(xs, stages)):
        on = ' on' if key == 'mode' else ''
        g = [f'<g class="stage{on}" data-k="{key}" tabindex="0" role="button" aria-label="{e(head)}">']
        g.append(f'<rect class="col" x="{x - 53}" y="6" width="106" height="{H - 12}" rx="4"/>')
        g.append(f'<text class="shead" x="{x}" y="28" text-anchor="middle">{e(head)}</text>')
        if split:
            big = ' big' if key == 'pub' else ''
            g.append(f'<circle class="node lb" cx="{x}" cy="{yt}" r="11"/><circle class="node rp" cx="{x}" cy="{yb_}" r="11"/>')
            g.append(f'<text class="nlab lb{big}" x="{x}" y="{yt - 19}" text-anchor="middle">{e(lt)}</text>')
            g.append(f'<text class="nlab rp{big}" x="{x}" y="{yb_ + 29}" text-anchor="middle">{e(lb)}</text>')
        else:
            g.append(f'<circle class="node both" cx="{x}" cy="{ym}" r="11"/>')
        g.append('</g>')
        out.append(''.join(g))
    out.append('</svg>')
    return '\n'.join(out)


# ------------------------------------------------------------------ rescaling as a stretch
def rescale():
    W, H = 704, 216
    x0, x1, yt, yb_ = 46, 658, 70, 160
    X = lambda v: x0 + (x1 - x0) * v / 100
    raw, k = 32.8859, 4
    base = 100 / k
    shown = max(0, (raw - base) / (100 - base) * 100)
    out = [f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="Two number lines: measured accuracy on top, the score shown underneath, with lines showing how the range above chance is stretched to 0 to 100">']
    out.append(f'<rect id="rs-below" class="below" x="{x0}" y="{yt - 9}" width="{X(base) - x0:.1f}" height="18"/>')
    out.append(f'<line class="ax" x1="{x0}" y1="{yt}" x2="{x1}" y2="{yt}"/><line class="ax" x1="{x0}" y1="{yb_}" x2="{x1}" y2="{yb_}"/>')
    for v in (0, 100):
        out.append(f'<text class="end" x="{X(v)}" y="{yt - 16}" text-anchor="middle">{v}</text><text class="end" x="{X(v)}" y="{yb_ + 26}" text-anchor="middle">{v}</text>')
        out.append(f'<line class="tick" x1="{X(v)}" y1="{yt - 5}" x2="{X(v)}" y2="{yt + 5}"/><line class="tick" x1="{X(v)}" y1="{yb_ - 5}" x2="{X(v)}" y2="{yb_ + 5}"/>')
    out.append(f'<text class="axt" x="{x0}" y="{yt - 36}">measured accuracy</text><text class="axt" x="{x0}" y="{yb_ + 46}">score shown</text>')
    out.append('<g id="rs-fan">' + ''.join(f'<line class="fan" x1="{X(base + (100 - base) * t / 5):.1f}" y1="{yt}" x2="{X(100 * t / 5):.1f}" y2="{yb_}"/>' for t in range(6)) + '</g>')
    out.append(f'<line id="rs-chance" class="chance" x1="{X(base):.1f}" y1="{yt - 12}" x2="{X(base):.1f}" y2="{yt + 12}"/><text id="rs-chancet" class="chancet" x="{X(base):.1f}" y="{yt + 27}" text-anchor="middle">chance {base:g}</text>')
    out.append(f'<line id="rs-map" class="map" x1="{X(raw):.1f}" y1="{yt}" x2="{X(shown):.1f}" y2="{yb_}"/>')
    out.append(f'<circle id="rs-dshown" class="node shown" cx="{X(shown):.1f}" cy="{yb_}" r="9"/><text id="rs-tshown" class="val" x="{X(shown):.1f}" y="{yb_ + 27}" text-anchor="middle">{shown:.2f}</text>')
    out.append(f'<text id="rs-traw" class="val" x="{X(raw):.1f}" y="{yt - 17}" text-anchor="middle">{raw:.2f}</text>')
    out.append(f'<rect id="rs-hit" class="hit" x="{x0 - 10}" y="{yt - 16}" width="{x1 - x0 + 20}" height="32"/>')
    out.append(f'<circle id="rs-draw" class="node raw" cx="{X(raw):.1f}" cy="{yt}" r="10" tabindex="0" role="slider" aria-label="Measured accuracy" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{raw:.2f}"/>')
    out.append('</svg>')
    return '\n'.join(out)


# ------------------------------------------------------------------ coverage bars
def coverage():
    L = ['All 12 sources, 46,559 records', '10 leaderboard sources, 28,755 records', '9 leaderboards without Open LLM Leaderboard v2, 1,965 records']
    rows = [('Shot count', [(80.5, 0), (98.0, 0), (71.0, 0)]), ('Harness', [(63.2, 57.5), (93.2, 93.2), (0, 0)]),
            ('Chain-of-thought status', [(50.0, 0), (77.6, 0), (0, 0)]), ('Prompt template', [(14.1, 0), (0, 0), (0, 0)]),
            ('Temperature', [(3.1, 0), (0, 0), (0, 0)])]

    def cell(label, v, att):
        if v == 0:
            return f'<td data-label="{label}"><span class="cell"><span class="track"></span><span class="v zero">0%</span></span></td>'
        segs = ''
        if att > 0: segs += f'<span class="fill att" style="--v:{att}"></span>'
        if v - att > 0.049: segs += f'<span class="fill" style="--v:{round(v - att, 1)}"></span>'
        return f'<td data-label="{label}"><span class="cell"><span class="track">{segs}</span><span class="v">{v}%</span></span></td>'
    body = ''.join(f'<tr><th scope="row">{n}</th>' + ''.join(cell(L[i], v, a) for i, (v, a) in enumerate(vals)) + '</tr>\n' for n, vals in rows)
    return ('<table class="cov"><thead><tr><th scope="col"><span class="sr">Field</span></th>'
            '<th scope="col"><b>All 12 sources</b> 46,559 records</th><th scope="col"><b>10 leaderboard sources</b> 28,755 records</th>'
            '<th scope="col"><b>9 leaderboards without Open LLM Leaderboard v2</b> 1,965 records</th></tr></thead>\n<tbody>\n' + body + '</tbody></table>')


def grid():
    cols = ['Shot count', 'Harness', 'Chain-of-thought status', 'Prompt template', 'Temperature']
    src = [('Open LLM Leaderboard v2', '26,790', [100, ('att', 100), 83.3, 0, 0]), ('AlpacaEval 2', '446', [100, 0, 0, 0, 0]),
           ('BFCL', '327', [100, 0, 0, 0, 0]), ('BigCodeBench', '280', [100, 0, 0, 0, 0]), ('Chatbot Arena', '218', [0, 0, 0, 0, 0]),
           ('EvalPlus', '214', [100, 0, 0, 0, 0]), ('Hugging Face model cards', '207', [5.8, 0, 0, 0, 0]), ('WildBench', '122', [0, 0, 0, 0, 0]),
           ('SWE-Bench', '117', [100, 0, 0, 0, 0]), ('MT-Bench', '34', [0, 0, 0, 0, 0])]

    def sq(v):
        if isinstance(v, tuple): return '<span class="sq att">100</span>'
        if v == 0: return '<span class="sq none">0</span>'
        if v == 100: return '<span class="sq full">100</span>'
        return f'<span class="sq part" style="--v:{v}">{v}</span>'
    head = '<tr><th scope="col">Leaderboard <small>(records)</small></th>' + ''.join(f'<th scope="col">{c}</th>' for c in cols) + '</tr>'
    body = ''.join(f'<tr><th scope="row">{n} <small>({r})</small></th>' + ''.join(f'<td>{sq(v)}</td>' for v in vals) + '</tr>\n' for n, r, vals in src)
    return f'<table class="grid"><thead>{head}</thead>\n<tbody>\n{body}</tbody></table>'


# ------------------------------------------------------------------ 291 squares
def waffle():
    cells = ['b1'] * 77 + ['b2'] * 45 + ['b3'] * 169
    assert len(cells) == 291
    return '<div class="waffle" role="img" aria-label="291 squares: 77 pairs within 1 percentage point, 45 between 1 and 5, 169 more than 5 apart">' + ''.join(f'<i class="{c}" data-b="{c}"></i>' for c in cells) + '</div>'


# ------------------------------------------------------------------ judges
def judges():
    js = ['GPT-4o-mini', 'Gemini-3.5-Flash', 'Llama-3.1-70B', 'Claude-Haiku-4.5']
    data = {'Ministral-8B': [8.44, 7.54, 8.62, 7.51], 'Qwen2.5-72B': [8.32, 8.59, 8.38, 7.74], 'Gemma-3-4B': [8.24, 7.96, 8.31, 7.26],
            'Llama-3.1-8B': [8.04, 7.61, 8.22, 6.87], 'Qwen2.5-7B': [7.86, 8.02, 7.96, 6.97]}
    spread = {'Ministral-8B': '1.11', 'Qwen2.5-72B': '0.84', 'Gemma-3-4B': '1.04', 'Llama-3.1-8B': '1.35', 'Qwen2.5-7B': '1.05'}   # as printed in the paper
    W, H = 704, 330
    xs = [170, 310, 450, 590]
    lo, hi, top, bot = 6.8, 8.8, 50, 300
    y = lambda v: bot - (v - lo) / (hi - lo) * (bot - top)
    out = [f'<svg viewBox="0 0 {W} {H}" role="group" aria-labelledby="judges-title judges-desc">',
           '<title id="judges-title">Mean MT-Bench rating of five models under four judge models</title>',
           '<desc id="judges-desc">' + ' '.join(f'{m}: {", ".join(f"{v:.2f}" for v in data[m])} under {", ".join(js)}.' for m in data) + '</desc>']
    for j, x in enumerate(xs):
        out.append(f'<text class="ax" x="{x}" y="22" text-anchor="middle">{e(js[j])}</text>')
        out.append(f'<line class="gridl" x1="{x}" y1="36" x2="{x}" y2="{bot + 8}"/>')
    for v in (7.0, 7.5, 8.0, 8.5):
        out.append(f'<line class="gridl" x1="{xs[0] - 10}" y1="{y(v):.1f}" x2="{W - 44}" y2="{y(v):.1f}"/>')
        out.append(f'<text class="ax" x="{W - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.1f}</text>')
    out.append(f'<text class="ax" x="{W - 8}" y="{top - 12}" text-anchor="end">mean rating</text>')
    # left labels, nudged apart so they do not overlap
    lab = sorted(((y(v[0]), m) for m, v in data.items()))
    placed = []
    for yy, m in lab:
        if placed and yy - placed[-1][0] < 15: yy = placed[-1][0] + 15
        placed.append((yy, m))
    ly = {m: yy for yy, m in placed}
    rank = {m: [] for m in data}
    for j in range(4):
        for r, m in enumerate(sorted(data, key=lambda k: -data[k][j]), 1): rank[m].append(r)
    assert rank['Ministral-8B'] == [1, 5, 1, 2], rank
    ordn = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th', 5: '5th'}
    overlay = ''
    for m, means in data.items():
        on = ' on' if m == 'Ministral-8B' else ''
        pts = ' '.join(f'{xs[j]},{y(means[j]):.1f}' for j in range(4))
        g = [f'<g class="model{on}" data-m="{e(m)}" data-spread="{spread[m]}" data-ranks="{",".join(ordn[r] for r in rank[m])}" data-v="{",".join(f"{v:.2f}" for v in means)}" tabindex="0" role="button" aria-label="{e(m)}: mean ratings {", ".join(f"{v:.2f}" for v in means)}">']
        marks = [f'<polyline class="jl" points="{pts}"/>']
        for j in range(4):
            marks.append(f'<circle class="jd" cx="{xs[j]}" cy="{y(means[j]):.1f}" r="4.5"/>')
        labels = ''.join(f'<text class="jv" x="{xs[j]}" y="{y(means[j]) - 10:.1f}" text-anchor="middle">{means[j]:.2f}</text>' for j in range(4))
        g.extend(marks)
        if on: overlay = ''.join(marks) + labels
        g.append(f'<text class="jt" x="{xs[0] - 22}" y="{ly[m] + 4:.1f}" text-anchor="end">{e(m)}</text>')
        g.append(f'<rect x="0" y="{ly[m] - 8:.1f}" width="{xs[0] - 14}" height="16" fill="transparent"/>')
        g.append('</g>')
        out.append(''.join(g))
    out.append(f'<g class="overlay" aria-hidden="true">{overlay}</g>')
    out.append('</svg>')
    return '\n'.join(out)


FIGS = {'paths': paths, 'pipeline': pipeline, 'rescale': rescale, 'coverage': coverage, 'grid': grid, 'waffle': waffle, 'judges': judges}
