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


# ------------------------------------------------------------------ rulers
def _ticks(x_of, edge_y, direction, lo=0, hi=100, every=1, label_dy=None, cls='rt'):
    """Ruler marks from lo to hi on a scale mapped by x_of. direction -1 draws up from edge_y, +1 down."""
    out = []
    v = lo
    while v <= hi:
        L = 14 if v % 10 == 0 else 9 if v % 5 == 0 else 5
        out.append(f'<line class="{cls}" x1="{x_of(v):.1f}" y1="{edge_y}" x2="{x_of(v):.1f}" y2="{edge_y + direction * L}"/>')
        if v % 10 == 0 and label_dy is not None:
            out.append(f'<text class="rn" x="{x_of(v):.1f}" y="{edge_y + label_dy}" text-anchor="middle">{v}</text>')
        v += every
    return ''.join(out)


def rescale():
    """A slide rule: the upper ruler is measured accuracy, the lower one starts at the chance level."""
    W, H, x0, x1 = 704, 190, 44, 660
    X = lambda v: x0 + (x1 - x0) * v / 100
    raw, k = 32.8859, 4
    base = 100 / k
    shown = max(0, (raw - base) / (100 - base) * 100)
    XL = lambda v: X(base + (100 - base) * v / 100)
    out = [f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="Two rulers lying against each other. The upper one measures accuracy from 0 to 100. The lower one has its 0 at the chance level and its 100 at the same place as the upper one. A cursor reads one position off both.">']
    out.append(f'<text class="rname" x="32" y="14">accuracy, as the harness measured it</text>')
    out.append(f'<text class="rname" x="32" y="182">score, as the leaderboard shows it</text>')
    out.append(f'<rect class="ruler up" x="32" y="52" width="640" height="42"/>')
    out.append('<g class="marks">' + _ticks(X, 94, -1, label_dy=-19) + '</g>')
    out.append(f'<g id="rs-lower"><rect class="ruler low" x="{X(base) - 12:.1f}" y="94" width="{672 - X(base) + 12:.1f}" height="42"/>'
               + _ticks(XL, 94, 1, every=1, label_dy=29)
               + f'<text class="rchance" x="{X(base) - 18:.1f}" y="119" text-anchor="end">chance {base:g}</text></g>')
    out.append(f'<rect id="rs-hit" class="hit" x="32" y="46" width="640" height="96"/>')
    out.append(f'<g id="rs-cursor" class="cursor" transform="translate({X(raw):.1f},0)" tabindex="0" role="slider" aria-label="Measured accuracy" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{raw:.2f}">'
               '<rect class="win" x="-13" y="46" width="26" height="96" rx="2"/><line class="hair" x1="0" y1="46" x2="0" y2="142"/>'
               f'<text id="rs-traw" class="read" x="0" y="38" text-anchor="middle">{raw:.2f}</text>'
               f'<text id="rs-tshown" class="read" x="0" y="160" text-anchor="middle">{shown:.2f}</text></g>')
    out.append('</svg>')
    return '\n'.join(out)


def gapruler():
    """The two published scores and the leaderboard's unrescaled value on one ruler, with what separates them."""
    W, H, x0, x1 = 888, 150, 50, 838
    X = lambda v: x0 + (x1 - x0) * v / 100
    a, m, b = 34.10, 53.77, 68.20

    def brace(xa, xb, y):
        c = (xa + xb) / 2
        return f'M{xa:.1f},{y} q0,6 6,6 H{c - 6:.1f} q6,0 6,6 q0,-6 6,-6 H{xb - 6:.1f} q6,0 6,-6'
    out = [f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="A ruler from 0 to 100 with three marks: 34.10, the score the leaderboard shows; 53.77, the same score before rescaling; 68.20, the score in the report. Rescaling accounts for 19.7 points of the distance and everything else for 14.4.">']
    out.append(f'<rect class="ruler up" x="{x0 - 14}" y="46" width="{x1 - x0 + 28}" height="38"/>')
    out.append(f'<rect class="band lb" data-part="rescale" x="{X(a):.1f}" y="46" width="{X(m) - X(a):.1f}" height="38"/>')
    out.append(f'<rect class="band rp" data-part="mode" x="{X(m):.1f}" y="46" width="{X(b) - X(m):.1f}" height="38"/>')
    out.append('<g class="marks">' + _ticks(X, 84, -1, label_dy=-18) + '</g>')
    for v, cls, lab in [(a, 'lb', '34.10'), (m, 'lbraw', '53.77'), (b, 'rp', '68.20')]:
        out.append(f'<line class="pin" x1="{X(v):.1f}" y1="34" x2="{X(v):.1f}" y2="84"/><circle class="nd {cls}" cx="{X(v):.1f}" cy="34" r="7"/>'
                   f'<text class="val {cls}" x="{X(v):.1f}" y="18" text-anchor="middle">{lab}</text>')
    for part, xa, xb, l1, l2 in [('rescale', X(a), X(m), 'rescaling', '19.7 pp'), ('mode', X(m), X(b), 'everything else', '14.4 pp')]:
        c = (xa + xb) / 2
        out.append(f'<g class="part" data-part="{part}" tabindex="0"><rect class="hitp" x="{xa:.1f}" y="46" width="{xb - xa:.1f}" height="96"/>'
                   f'<path class="brace" d="{brace(xa + 2, xb - 2, 92)}"/>'
                   f'<text class="bl" x="{c:.1f}" y="120" text-anchor="middle">{l1}</text><text class="bl" x="{c:.1f}" y="136" text-anchor="middle">{l2}</text></g>')
    out.append('</svg>')
    return '\n'.join(out)


# ------------------------------------------------------------------ two protocol variants under one benchmark label
# The paper's Figures 5 and 7, set as HTML from figures/fig_style.tex. Text is the paper's.
# {d:key|text} marks a part that differs between the two variants; [..] in italics is a placeholder; lines starting "!" are red notes.
_COLS = {
 'gsm8k': dict(head='GSM8K', sub='Qwen2.5-14B-Instruct · lm-evaluation-harness 0.4.11 · 5-shot',
   a=dict(tab='Plain few-shot (direct answer)', instr='{d:instr|[system] You are Qwen, created by Alibaba Cloud.}',
          prompt=['Q: [few-shot question 1] A: #### 12', '… [4 more exemplars, each ending #### n] …', 'Q: [target question]', 'A: 16-3-4 = 9; 9 × 2 = 18. {d:out|#### 18}'], bar='58.5%'),
   delta='↓ Δ = −56.0 pp',
   b=dict(tab='Chain-of-thought few-shot', instr='{d:instr|[system] You are an expert problem solver. Think step by step, then state the answer.}',
          prompt=['Q: [same 5 exemplars]', 'Q: [target question]', 'A: Janet uses 3 + 4 = 7 eggs each day. 16 − 7 = 9 remain. 9 × 2 = 18.', '!{d:out|The answer is $18 per day.}', '!{d:out|#### delimiter absent}'], bar='2.5%'),
   foot='Same model · same harness · same 5-shot context. CoT prompt elicits prose; the #### regex finds nothing; parser records 0 for correctly-answered items.'),
 'belebele': dict(head='Belebele', sub='Mistral-7B · two papers · two evaluation regimes',
   a=dict(tab='Reka report · 0-shot · multilingual', instr='[canonical reconstruction; template not published]',
          prompt=['Passage: [reading-comprehension context]', 'Question: [question]', 'A) [option] B) [option] C) [option] D) [option]', 'Answer:', '!{d:shot|0-shot, no exemplars in context}', '!{d:lang|averaged over 150 language variants}'], bar='32.80'),
   delta='↓ Δ = +46.6 pp',
   b=dict(tab='Falcon2 report · 5-shot · English', instr='[canonical reconstruction; template not published]',
          prompt=['{d:shot|Example 1: [English passage + question] Answer: B}', '{d:shot|… [4 more exemplars] …}', 'Passage: {d:lang|[English passage]}', 'Question: [question]', 'A) [option] B) [option]', 'Answer:', '!{d:shot|5-shot} · {d:lang|English only}'], bar='79.42'),
   foot="One benchmark label · two dimensions differ (n-shot, language scope). Falcon2's own 0-shot English score = 32.48 ≈ Reka's 32.80 ⇒ n-shot, not language scope, drives the gap."),
 'bbh': dict(head='BBH · Gemma-2-9B', sub='Five sources · two score clusters · two protocols',
   a=dict(tab='OLv2 & SEA-LION · 3-shot · log-lik.', instr='[lighteval BBH protocol, per OLv2 documentation]',
          prompt=['Q: Which statement is logically false?', 'Given: all mammals breathe air; whales are mammals.', '(A) Whales breathe air. (B) Whales swim.', '(C) Whales are reptiles. (D) Whales have lungs.', '{d:mode|rank: argmax log P(choice | context)}', '!3-shot · {d:mode|log-likelihood ranking}', '!OLv2 = 34.10 = SEA-LION = 34.10 (exact match)'], bar='34.10'),
   delta='↓ Δ = +34.8 pp',
   b=dict(tab='Gemma 2 / Gemma 3 reports · CoT', instr='[CoT generation protocol, Suzgun et al. 2023]',
          prompt=["Q: Which statement is logically false? {d:mode|Let's think step by step.}", '{d:mode|A: All mammals breathe air; whales are mammals, therefore whales breathe air, true. Whales are not reptiles, false. The answer is (C).}', '!Gemma 2 = 68.20 · Gemma 3 = 69.00 · Gemma 3 = 69.40'], bar='68.87 (mean)'),
   foot='Two score clusters · two protocols. OLv2 & SEA-LION: exact 2-decimal match ⇒ shared pipeline, not independent evidence.'),
 'hellaswag': dict(head='HellaSwag', sub='Gemma-7B · two papers · two protocols',
   a=dict(tab='Phi-3 report · 5-shot · generation', instr='[canonical reconstruction; prompt not published]',
          prompt=['Context: She bopped along, but the music was really loud, so she turned it down. Now, how does the next sentence go?', 'A) She turned it up more. B) She left the store.', 'C) She decreased the volume. D) She plugged her ears.', '{d:mode|Answer: C}', '!{d:mode|free-text generation} · {d:shot|5-shot}'], bar='49.80'),
   delta='↓ Δ = +31.4 pp',
   b=dict(tab='Gemma report · 0-shot · log-lik.', instr='[canonical reconstruction; prompt not published]',
          prompt=['Context: She bopped along, but the music was really loud, so she turned it down.', 'Completion A: She turned it up more.', 'Completion B: She left the store.', 'Completion C: She decreased the volume.', 'Completion D: She plugged her ears.', '{d:mode|rank by log P(completion | context)}', '!{d:mode|log-likelihood ranking} · {d:shot|0-shot}'], bar='81.20'),
   foot='One benchmark label · two dimensions differ. Scoring mode: generation vs. log-likelihood. N-shot: 5 vs. 0. Primary driver: scoring mode, not n-shot.'),
}


def _ptext(t):
    import re
    t = e(t)
    t = re.sub(r'\[(?!system\])([^\]]+)\]', r'<i>[\1]</i>', t)
    t = re.sub(r'\{d:(\w+)\|', r'<span class="df" data-d="\1" tabindex="0">', t).replace('}', '</span>')
    return t


def _pcol(key):
    c = _COLS[key]

    def panel(v):
        lines = ''.join(f'<span class="{"rd" if l.startswith("!") else "ln"}">{_ptext(l.lstrip("!"))}</span>' for l in v['prompt'])
        return (f'<div class="ppanel"><span class="ptab">{e(v["tab"])}</span>'
                f'<p class="plab">Instruction</p><p class="pmono">{_ptext(v["instr"])}</p>'
                f'<p class="plab">Prompt</p><p class="pmono">{lines}</p></div>')
    return (f'<section class="pcol" aria-label="{e(c["head"])}"><h4 class="phead">{e(c["head"])}</h4><p class="psub">{e(c["sub"])}</p>'
            f'{panel(c["a"])}<p class="pbar">{e(c["a"]["bar"])}</p><p class="pdelta">{e(c["delta"])}</p>'
            f'{panel(c["b"])}<p class="pbar">{e(c["b"]["bar"])}</p><p class="pfoot">{e(c["foot"])}</p></section>')


def gemmaflow():
    """The two Gemma-2-9B scores on BBH in the style of the paper's parser-flow figure (Figure 10):
       tabbed panels in two rows, protocol -> score scale -> published score, with the difference at the right."""
    def panel(tab, instr, lines, cls=''):
        body = ''
        if instr is not None:
            body += f'<p class="plab">Instruction</p><p class="pmono">{_ptext(instr)}</p><p class="plab">Prompt</p>'
        body += '<p class="pmono">' + ''.join(f'<span class="{"rd" if l.startswith("!") else "ln"}">{_ptext(l.lstrip("!"))}</span>' for l in lines) + '</p>'
        return f'<div class="ppanel {cls}"><span class="ptab">{e(tab)}</span>{body}</div>'
    arrow = '<span class="parrow" aria-hidden="true"><svg viewBox="0 0 34 12"><path d="M0,6 H26"/><path class="hd" d="M34,6 l-9,-4 v8 z"/></svg></span>'
    rows = [
        ('lb',
         panel('OLv2 · 3-shot · log-lik.', '[BBH protocol, per OLv2 documentation]',
               ['Q: Which statement is logically false?', 'Given: all mammals breathe air; whales are mammals.', '(A) Whales breathe air. (B) Whales swim.', '(C) Whales are reptiles. (D) Whales have lungs.',
                '{d:mode|rank: argmax log P(choice | context)}', '!3-shot · {d:mode|log-likelihood ranking}', '!{d:harness|lm-eval, OLv2 fork}']),
         panel('Leaderboard-normalised', None,
               ['{d:scale|(raw − chance) / (100 − chance) × 100}', 'per subtask, then averaged', '!{d:scale|raw = 53.77}', '!{d:scale|shown = 34.10}']),
         '↓ Δ = −19.7 pp (normalisation)',
         panel('OLv2', None, ['gemma-2-9b', 'BBH'], 'tiny'), '34.10'),
        ('rp',
         panel('Gemma 2 report · 3-shot · CoT', '[CoT generation protocol, Suzgun et al. 2023]',
               ["Q: Which statement is logically false? {d:mode|Let's think step by step.}",
                '{d:mode|A: All mammals breathe air; whales are mammals, therefore whales breathe air, true. Whales are not reptiles, false. The answer is (C).}',
                '!3-shot · {d:mode|CoT generation}', "!{d:harness|the model's own pipeline}"]),
         panel('Raw scale', None, ['{d:scale|accuracy as measured}', '!{d:scale|no rescaling}']),
         None,
         panel('Gemma 2 report', None, ['gemma-2-9b', 'BBH'], 'tiny'), '68.20'),
    ]
    out = ['<div class="pflow">',
           '<p class="pfh c1">Protocol (input)</p><p class="pfh c3">Score scale</p><p class="pfh c5">Published score</p>']
    for n, (key, p1, p2, d2, p3, score) in enumerate(rows, start=1):
        out.append(f'<div class="pf c1 r{n}">{p1}</div><div class="pf c2 r{n}">{arrow}</div>'
                   f'<div class="pf c3 r{n}">{p2}' + (f'<p class="pdelta">{e(d2)}</p>' if d2 else '') + '</div>'
                   f'<div class="pf c4 r{n}">{arrow}</div><div class="pf c5 r{n}">{p3}<p class="pbar">{score}</p></div>')
    out.append('<div class="pbracket" aria-hidden="true"><span>Δ = +34.1 pp (report − OLv2)</span></div>')
    out.append('<p class="pdelta between">↓ Δ = +34.1 pp (report − OLv2)</p>')
    out.append("<p class=\"pfoot\">Same model · same benchmark · same 3-shot context. Of the 34.1 pp, 19.7 is the leaderboard's normalisation (53.77 raw, 34.10 shown) and 14.4 is everything else: log-likelihood ranking vs. CoT generation, in two different pipelines. Neither source records scoring mode or harness as a field.</p>")
    out.append('</div>')
    return '\n'.join(out)


def protocols():
    return '<div class="protos">' + '\n'.join(_pcol(k) for k in ('gsm8k', 'belebele', 'bbh')) + '</div>'


def hellaswag():
    return '<div class="protos one">' + _pcol('hellaswag') + '</div>'


# ------------------------------------------------------------------ coverage bars
def coverage():
    L = ['All 12 sources, 46,559 records', '10 leaderboard sources, 28,755 records', '9 leaderboards without Open LLM Leaderboard v2, 1,965 records']
    rows = [('Shot count', [(80.5, 0), (98.0, 0), (71.0, 0)]), ('Harness', [(63.2, 57.5), (93.2, 93.2), (0, 0)]),
            ('Chain-of-thought status', [(50.0, 0), (77.7, 0), (0, 0)]), ('Prompt template', [(14.1, 0), (0, 0), (0, 0)]),
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
    src = [('Open LLM Leaderboard v2', '26,790', [100, ('att', 100), 83.4, 0, 0]), ('AlpacaEval 2', '446', [100, 0, 0, 0, 0]),
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


FIGS = {'paths': paths, 'pipeline': pipeline, 'rescale': rescale, 'gemmaflow': gemmaflow, 'protocols': protocols, 'hellaswag': hellaswag, 'coverage': coverage, 'grid': grid, 'waffle': waffle, 'judges': judges}
