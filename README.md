# fastslides

Turn notebooks, md or Solveit dialogs into a slide deck with one command.

```bash
pip install fastslides
fastslides talk.md              # opens the slides in a browser
fastslides talk.ipynb --export  # writes talk.html and talk.pdf next to it
```

The HTML is one self-contained file: local images inlined, arrow keys, Space and PageUp/PageDown move between slides, and the slide number is in the URL, so a reload keeps your place. `--export` also prints the page to a 16:9 PDF with a headless Chrome, which must be installed.

## Writing slides

A slide deck is an ordinary document. A line containing only `---` starts a new slide; headings never do. In a notebook or dialog, a note cell containing only `---` breaks between cells. When any cell is exported (nbdev's `#| export`, or the Solveit export flag), only exported cells are rendered, so a working dialog can hold drafts and prompts beside the deck; `--no-exported` renders every cell. Code cells render as highlighted code with their stored outputs beneath.

Two columns: wrap the blocks in a fenced div.

```markdown
::: {.cols}
![](logo.png)

- first point
- second point
:::
```

`::: {.cols .narrow}` makes the left column a quarter of the width. An image on its own line shrinks to the space left on the slide. A slide that still does not fit scrolls, which is the cue to cut it.

`fastslides --help` lists the options, which are `viewmd`'s: `--refs`, `--hl`, `--head my.css` for your own styling, `--math`.

## How it works

`mdhtml` parses the Markdown (and `aidialog` turns notebooks into Markdown first). `mdhtml2slides` cuts the parsed tree at top-level `hr` elements and renders each group with `mdhtml2html`, so every Markdown feature mdhtml supports works on a slide. The page is `viewmd`'s, plus about forty lines of CSS and JS.
