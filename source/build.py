#!/usr/bin/env python3
"""Turns article.src.html into ../index.html.
   <cite k="a,b"></cite>  -> numbered citation markers, in order of first use
   <fn>text</fn>          -> numbered footnote markers; text collected into the appendix
   <!--FOOTNOTES--> and <!--REFERENCES--> are replaced by the generated lists.
   Everything ends up as plain static HTML; the page needs no build step to be served."""
import json, re, html, sys, pathlib
here = pathlib.Path(__file__).parent
src = (here / 'article.src.html').read_text(encoding='utf-8')
import figs
src = re.sub(r'<!--FIG:(\w+)-->', lambda m: figs.FIGS[m.group(1)](), src)
refs = {r['key']: r for r in json.loads((here / 'refs.json').read_text(encoding='utf-8'))}

order = []
def cite(m):
    keys = [k.strip() for k in m.group(1).split(',')]
    nums = []
    for k in keys:
        if k not in refs: sys.exit('unknown citation key: ' + k)
        if k not in order: order.append(k)
        nums.append(order.index(k) + 1)
    label = ', '.join(str(n) for n in nums)
    return f'<a class="cite-ref" href="#ref-{nums[0]}" data-refs="{",".join(str(n) for n in nums)}" aria-label="Reference {label}">[{label}]</a>'
notes = []
def fn(m):
    notes.append(m.group(1).strip())
    n = len(notes)
    return f'<a class="fn-ref" id="fnref-{n}" href="#fn-{n}" data-fn="{n}" aria-label="Footnote {n}">{n}</a>'

# footnotes may contain citations, so number in document order with one combined pass
def both(m):
    return fn(m) if m.group(0).startswith('<fn>') else cite(m)
out = re.sub(r'<fn>(.*?)</fn>|<cite k="([^"]+)"></cite>', lambda m: fn(re.match(r'<fn>(.*?)</fn>', m.group(0), re.S)) if m.group(0).startswith('<fn>') else cite(re.match(r'<cite k="([^"]+)"></cite>', m.group(0))), src, flags=re.S)
# citations inside collected footnote text
notes = [re.sub(r'<cite k="([^"]+)"></cite>', cite, t) for t in notes]

fl = '\n'.join(f'  <li id="fn-{i}">{t} <a class="backlink" href="#fnref-{i}" aria-label="Back to text">[&#8617;]</a></li>' for i, t in enumerate(notes, 1))
def ref_li(i, r):
    e = html.escape
    link = f' <a href="{e(r["url"])}">[link]</a>' if r['url'] else ''
    tail = ', '.join(x for x in [e(r['authors']), e(r['venue']), e(r['year'])] if x)
    return f'  <li id="ref-{i}"><span class="title">{e(r["title"])}</span>{link}<br>{tail}.</li>'
rl = '\n'.join(ref_li(i, refs[k]) for i, k in enumerate(order, 1))
out = out.replace('<!--FOOTNOTES-->', f'<ol class="footnotes">\n{fl}\n</ol>').replace('<!--REFERENCES-->', f'<ol class="references">\n{rl}\n</ol>')
dest = here.parent / 'index.html'
dest.write_text(out, encoding='utf-8')
print(f'wrote {dest}: {len(notes)} footnotes, {len(order)} references, {len(out)//1024} KB')
unused = [k for k in refs if k not in order]
if unused: print('unused refs:', ', '.join(unused))
