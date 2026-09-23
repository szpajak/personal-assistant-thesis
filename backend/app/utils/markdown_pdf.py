"""Render the deterministic CV Markdown template (see
``CVService.format_cv_markdown``) into a PDF using fpdf2.

fpdf2's built-in ``markdown=True`` support on ``cell()``/``multi_cell()``
handles inline ``**bold**`` automatically for the standard Arial/Helvetica
core font, so only two things need manual handling here: whole-line
constructs that aren't valid CommonMark-lite for fpdf2 (``# ``/``## ``/
``### `` headers, ``---`` rules, a lone ``*italic*`` line) and Markdown link
syntax (``[label](url)``, used only in the contact-info header line).
"""

from __future__ import annotations

import re

from fpdf import FPDF

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_FULL_RE = re.compile(r"^\*\*(.+)\*\*$")
_ITALIC_FULL_RE = re.compile(r"^\*([^*]+)\*$")

# fpdf2 core fonts default to Latin-1, which cannot encode • / smart quotes /
# em dashes. Switch the PDF to cp1252 (WinAnsi) so those glyphs render, and
# still strip anything outside that encoding (emoji, most non-Western text).
_CORE_FONT_ENCODING = "cp1252"
_ICON_LABELS = {
    "\U0001f4e7": "Email: ",
    "\U0001f4f1": "Phone: ",
    "\U0001f517": "LinkedIn: ",
    "\U0001f4bb": "GitHub: ",
    "\U0001f310": "Site: ",
}


def _sanitize(text: str) -> str:
    """Swap emoji icons for ASCII labels and drop any other glyph the core
    Helvetica/Arial font can't encode, so PDF export never crashes on
    LLM-produced Unicode punctuation (curly quotes, em dashes, ...)."""
    for icon, label in _ICON_LABELS.items():
        text = text.replace(icon, label)
    return text.encode(_CORE_FONT_ENCODING, errors="replace").decode(_CORE_FONT_ENCODING)


def _multi_cell(
    pdf: FPDF,
    height: float,
    text: str,
    *,
    markdown: bool = False,
    indent: float = 0.0,
) -> None:
    """Write a block that always starts at the left margin (plus optional
    indent) and returns the cursor there.

    fpdf2's ``multi_cell`` defaults to ``new_x=RIGHT``, which parks ``x`` on
    the right margin after the call. The next ``multi_cell(w=0)`` then has
    *zero* remaining width and raises ``Not enough horizontal space to
    render a single character`` - exactly what happens for real CVs, where
    ``format_cv_markdown`` emits consecutive lines with no blank line
    between them (``### Role | Company`` immediately followed by
    ``*2021 - Present*``, education heading + institution, Languages +
    Interests, ...). Explicit ``new_x=LMARGIN`` plus a pre-call ``set_x``
    makes block layout independent of whatever the previous line did.
    """
    pdf.set_x(pdf.l_margin + indent)
    usable = pdf.w - pdf.r_margin - pdf.x
    if usable <= 0:
        pdf.set_x(pdf.l_margin)
        usable = pdf.w - pdf.r_margin - pdf.l_margin
    pdf.multi_cell(
        usable,
        height,
        text=text,
        align="L",
        markdown=markdown,
        wrapmode="CHAR",
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _write_line_with_links(
    pdf: FPDF, text: str, *, size: float = 11, height: float = 6.0, safe_mode: bool = False
) -> None:
    """Write a single paragraph line containing ``[label](url)`` links (used
    only for the header contact line, which has no bold/italic runs)."""
    pdf.set_font("Arial", size=size)
    pdf.set_x(pdf.l_margin)
    if safe_mode:
        # Drop link markup entirely and fall through to the plain multi_cell
        # path below, which is the most defensive rendering we have.
        plain = _LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", text)
        _multi_cell(pdf, height, _sanitize(plain))
        return
    pos = 0
    for match in _LINK_RE.finditer(text):
        if match.start() > pos:
            pdf.write(height, _sanitize(text[pos : match.start()]), wrapmode="CHAR")
        pdf.set_text_color(37, 99, 235)
        pdf.write(height, _sanitize(match.group(1)), link=match.group(2), wrapmode="CHAR")
        pdf.set_text_color(0, 0, 0)
        pos = match.end()
    if pos < len(text):
        pdf.write(height, _sanitize(text[pos:]), wrapmode="CHAR")
    pdf.ln(height)


def render_markdown_to_pdf(pdf: FPDF, markdown_text: str, *, safe_mode: bool = False) -> None:
    """Render ``markdown_text`` into ``pdf`` (a page must already be added).

    Recognizes exactly the constructs produced by
    :func:`app.services.cv_service.format_cv_markdown`:

    - ``# `` -> candidate name (large bold)
    - a lone ``**bold**`` line -> headline
    - the contact line / location -> plain paragraphs (links handled specially)
    - ``## `` -> section header (bold, underlined with a rule)
    - ``### `` -> sub-header (role / institution / project title)
    - a lone ``*italic*`` line -> period / company line
    - ``---`` -> horizontal rule
    - ``- `` bullets and any other paragraph -> rendered with fpdf2's
      built-in ``markdown=True`` inline ``**bold**`` support

    Every wrapped call goes through :func:`_multi_cell`, which resets
    ``x`` to the left margin, passes ``wrapmode="CHAR"``, and uses
    ``new_x=LMARGIN`` so the next block starts with a full line of width.
    fpdf2's default ``multi_cell(..., new_x=RIGHT)`` parks the cursor on
    the right margin; the next ``w=0`` call then raises ``"Not enough
    horizontal space to render a single character"`` - and real CVs emit
    consecutive lines with no blank line between them (role heading then
    period, education then institution). ``wrapmode="CHAR"`` also covers
    the separate upstream wrapping bugs (#1250, #1582) on long unbroken
    tokens and inline ``**bold**`` fragments.

    If ``safe_mode`` is set, inline ``**bold**`` parsing (``markdown=True``)
    is disabled for bullets/paragraphs - the one thing here that splits a
    line into multiple text fragments, which is what upstream issue #1250
    identifies as the actual trigger for the spurious exception. Everything
    else (headers, links, whole-line bold/italic) already renders as a
    single plain fragment and is left as-is. Used by
    :meth:`app.services.cv_service.CVService.export_cv_to_pdf` as a
    last-resort retry so a PDF always exports even if some future edge case
    still trips up fpdf2's line breaker.
    """
    pdf.core_fonts_encoding = _CORE_FONT_ENCODING
    for raw_line in markdown_text.split("\n"):
        line = raw_line.strip()

        if not line:
            pdf.ln(2)
            continue

        if line == "---":
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            continue

        if line.startswith("# "):
            pdf.set_font("Arial", style="B", size=20)
            _multi_cell(pdf, 10, _sanitize(line[2:].strip()))
            continue

        if line.startswith("### "):
            pdf.ln(1)
            pdf.set_font("Arial", style="B", size=12)
            _multi_cell(pdf, 7, _sanitize(line[4:].strip()))
            continue

        if line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Arial", style="B", size=14)
            _multi_cell(pdf, 8, _sanitize(line[3:].strip()))
            pdf.set_draw_color(180, 180, 180)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)
            continue

        bold_full = _BOLD_FULL_RE.match(line)
        if bold_full:
            pdf.set_font("Arial", style="B", size=13)
            _multi_cell(pdf, 7, _sanitize(bold_full.group(1)))
            continue

        italic_full = _ITALIC_FULL_RE.match(line)
        if italic_full:
            pdf.set_font("Arial", style="I", size=10)
            _multi_cell(pdf, 6, _sanitize(italic_full.group(1)))
            continue

        if _LINK_RE.search(line):
            _write_line_with_links(pdf, line, safe_mode=safe_mode)
            continue

        if line.startswith("- "):
            pdf.set_font("Arial", size=11)
            bullet_text = line[2:].strip()
            _multi_cell(
                pdf,
                6,
                _sanitize(f"\u2022 {bullet_text}"),
                markdown=not safe_mode,
                indent=5,
            )
            continue

        pdf.set_font("Arial", size=11)
        _multi_cell(pdf, 6, _sanitize(line), markdown=not safe_mode)
