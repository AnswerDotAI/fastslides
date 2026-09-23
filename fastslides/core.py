"Render Markdown, notebooks and Solveit dialogs as HTML slides: one slide per `---`, arrow keys to move, print to PDF"
import asyncio, base64, webbrowser
from pathlib import Path
from typing import Annotated

import fastcore.xtras  # for patches  # chkstyle: ignore
from fastcore.meta import delegates
from fastcore.script import call_parse

from aidialog.dialog import dlg2md
from aidialog.ipynb import read_ipynb

from mdhtml import DASHES, replacements, md2mdhtml, mdhtml2dom, mdhtml2html
from mdhtml.export import Html
from mdhtml.mustache import MUSTACHE, mustache_pill
from mdhtml._cli import parse_args, read_src
from mdhtml.md2html import CACHE, HlMode, RefsMode, _inline_imgs, page
from mdhtml.viewmd import TYPROSE, _head_section

__all__ = ['mdhtml2slides', 'render', 'html2pdf', 'main']

CSS = r"""
html { font-size: 1.25vw; }
body { max-width: none; margin: 0; padding: 0; }
section.slide { display: none; flex-direction: column; box-sizing: border-box; overflow: hidden; }
section.slide.cur { display: flex; height: 100vh; padding: 4vh 6vw; }
section.slide figure { flex: 1; min-height: 0; display: flex; margin: 1em 0; }
section.slide figure img { max-height: 100%; max-width: 100%; object-fit: contain; object-position: left top; }
figcaption { display: none; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5em; align-items: start; }
.cols.narrow { grid-template-columns: 1fr 3fr; }
section.slide .cols figure { flex: none; display: block; margin: 0; }
section.slide .cols figure img { max-height: 55vh; width: auto; }
@media print {
  @page { size: 13.333in 7.5in; margin: 0; }
  html { font-size: 0.1667in; }
  section.slide, section.slide.cur { display: flex; height: 7.5in; padding: 0.4in 0.8in; break-after: page; }
  section.slide figure { margin: 0.3in 0; }
  section.slide .cols figure img { max-height: 4in; }
  pre { white-space: pre-wrap; overflow: hidden; }
}
"""

JS = r"""
document.body.classList.add('prose', 'prose-2xl');
document.body.classList.toggle('prose-invert', matchMedia('(prefers-color-scheme: dark)').matches);
const s = [...document.querySelectorAll('section.slide')];
let i = (parseInt(location.hash.slice(1)) || 1) - 1;
function show(n) {
  i = Math.max(0, Math.min(s.length - 1, n));
  s.forEach((e, j) => e.classList.toggle('cur', j === i));
  location.hash = i + 1;
  scrollTo(0, 0);
}
document.addEventListener('keydown', e => {
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); show(i + 1); }
  else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) { e.preventDefault(); show(i - 1); }
  else if (e.key === 'Home') show(0);
  else if (e.key === 'End') show(s.length - 1);
});
show(i);
"""


def _split(frag):
    "Top-level node groups of `frag`, cut at `hr` elements (consumed); groups with no content are dropped"
    groups, cur = [], []
    for n in frag.children:
        if n.name == 'hr':
            groups.append(cur)
            cur = []
        else: cur.append(n)
    groups.append(cur)
    return [g for g in groups if any(n.to_html().strip() for n in g)]


def mdhtml2slides(src, dest=None, **kwargs):
    "Lower MDHTML to one `<section class=\"slide\">` per top-level `hr`, each rendered by `mdhtml2html(**kwargs)`; returns `Html` with the slides' warnings, written to `dest` if given"
    rendered = [mdhtml2html(''.join(n.to_html() for n in g), auto_ids=False, **kwargs) for g in _split(mdhtml2dom(src))]
    res = Html(''.join(f'<section class="slide">{h}</section>' for h in rendered), [w for h in rendered for w in h.warnings])
    if dest: Path(dest).write_text(res)
    return res


@delegates(parse_args)
def render(
    file: str = None,  # Markdown file (or .ipynb notebook) to present (default: stdin)
    refs: RefsMode = RefsMode.lenient,  # References: target ids ('ids'), numbered ('resolve'), or numbered with ids as fallback ('lenient')
    hl: HlMode = HlMode.spans,  # Code highlighting: classed spans, the Highlight API, or off
    implicit_figures: bool = True,  # Promote image-only paragraphs to figures
    exported: bool = True,  # For notebooks: only exported messages, when any are exported
    head: Annotated[str, "File inlined into the page head: .css as <style>, .js as <script>, else raw HTML; repeatable", dict(action="append")] = None,
    **kwargs):
    "The slides page for `file` as one self-contained HTML string, local images inlined; warnings print"
    text = dlg2md(read_ipynb(file), exportfilter=exported) if file and file.endswith(".ipynb") else read_src(file)
    src = md2mdhtml(text, implicit_figures=implicit_figures, frontmatter=False,
        templates=MUSTACHE, callbacks={'template_token': mustache_pill, 'text': replacements(*DASHES)}, **kwargs)
    html = mdhtml2slides(src, refs=refs, hl=None if hl == HlMode.off else hl)
    for w in [*src.warnings, *html.warnings]: print(w)
    base = Path(file).resolve().parent if file else Path.cwd()
    return page(_inline_imgs(html, base) + f"<style>{CSS}</style><script>{JS}</script>", title=Path(file).stem if file else "slides",
        preview=refs != RefsMode.resolve, head=[f'<link rel="stylesheet" href="{TYPROSE}">', *(_head_section(f) for f in head or ())])


async def html2pdf(html, pdf):
    "Print the page at `html` to `pdf` with a headless Chrome, honouring its `@page` size"
    from fastcdp.skill import CDP
    cdp = await CDP.launch(headless=True)
    pg = await cdp.new_page()
    await pg.goto(Path(html).resolve().as_uri(), wait='idle')
    data = await pg.page.printToPDF(preferCSSPageSize=True, printBackground=True)
    Path(pdf).write_bytes(base64.b64decode(data))
    await cdp.quit()


@call_parse(pos=['file'])
@delegates(render)
def main(
    file: str = None,  # Markdown file (or .ipynb notebook) to present (default: stdin)
    export: bool = False,  # Write `<out>.html` and `<out>.pdf` instead of opening a browser
    out: str = None,  # Output path without extension, for `--export` (default: the input's)
    **kwargs):
    "Render `file` as slides: open them in a browser, or `--export` them as HTML and PDF"
    html = render(file, **kwargs)
    if not export:
        dest = CACHE / f"{Path(file).stem if file else 'slides'}.html"
        dest.mk_write(html)
        return webbrowser.open(dest.as_uri())
    out = Path(out) if out else Path(file).with_suffix('')
    out.with_suffix('.html').write_text(html)
    asyncio.run(html2pdf(out.with_suffix('.html'), out.with_suffix('.pdf')))
    for ext in ('.html', '.pdf'): print(out.with_suffix(ext), out.with_suffix(ext).stat().st_size // 1024, 'KB')
