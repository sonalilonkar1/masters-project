"""Build the IEEE-template LaTeX version of the final report.

Usage:
    python docs/project_report/build_latex.py              # writes docs/project_report/latex/
    python docs/project_report/build_latex.py --compile    # also compiles report.pdf (needs tectonic)

The chapter Markdown files stay the source. Each chapter becomes an IEEEtran
section (Chapter 4 -> IV, 4.3 -> IV-C); "Section 4.3", "Table 7.1" and
"Figure 4.2" become \\ref labels so LaTeX numbers them; citations become \\cite
with a thebibliography built from references.md; tables and figures become
floats. The SJSU front pages (title, copyright, approval, abstract,
acknowledgments) come first, single-column. Upload the whole latex/ folder to
Overleaf and compile report.tex with pdfLaTeX or XeLaTeX, or paste
report_single_file.tex into the Overleaf main file and upload figures/.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent
OUT_DIR = REPORT_DIR / "latex"
TEMPLATE_CLS = REPORT_DIR / "template" / "LaTeX" / "IEEEtran.cls"

sys.path.insert(0, str(REPORT_DIR))
from assemble_report import CHAPTERS, CITATIONS, MERMAID  # noqa: E402

FRONT = {
    "title": "TraceAdvisor: Pre-Execution Resource Recommendations for Recurring Cluster Workloads",
    "authors": ["Shivani Jariwala", "Meghana Koti", "Sonali Lonkar", "Sofia Silva"],
    "degree": "Master of Science in Software Engineering",
    "date": "December 2026",
    "year": "2026",
    "advisor": "Dan Harkey",
    "acknowledgments": (
        "The authors are deeply indebted to Professor Dan Harkey for guidance and valuable "
        "feedback throughout this project, and to Professor Gheorghi Guzun, the project's "
        "previous advisor, for guidance during its earlier stages."
    ),
}


# Single-panel figures, set narrower than the page width.
NARROW_FIGURES = {"4.2": 0.6, "7.1": 0.6}

UNICODE = {"²": "$^{2}$", "−": "$-$", "±": "$\\pm$", "·": "$\\cdot$", "⁻¹": "$^{-1}$", "¹": "$^{1}$"}

NUM = r"\d+(?:\.\d+)*"


def raw(tex: str) -> str:
    """Inline raw LaTeX that pandoc passes through unchanged."""
    return f"`{tex}`{{=latex}}"


def pandoc(markdown: str, wrap: str = "preserve") -> str:
    result = subprocess.run(
        ["pandoc", "-f", "markdown-implicit_figures-auto_identifiers-subscript-superscript",
         "-t", "latex", f"--wrap={wrap}", "--syntax-highlighting=none"],
        input=markdown, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def label(kind: str, number: str) -> str:
    return f"{kind}:{number}"


def inline_refs(text: str) -> str:
    """Section, chapter, table, figure and citation references -> raw \\ref and \\cite."""
    text = re.sub(rf"\bChapters ({NUM}) and ({NUM})",
                  lambda m: raw(f"Sections~\\ref{{sec:{m[1]}}} and~\\ref{{sec:{m[2]}}}"), text)
    text = re.sub(rf"\bSections ({NUM}) and ({NUM})",
                  lambda m: raw(f"Sections~\\ref{{sec:{m[1]}}} and~\\ref{{sec:{m[2]}}}"), text)
    text = re.sub(rf"\b(?:Chapter|Section) ({NUM})(?<!\.)",
                  lambda m: raw(f"Section~\\ref{{sec:{m[1].rstrip('.')}}}"), text)
    text = re.sub(rf"\bTables ({NUM}) and ({NUM})",
                  lambda m: raw(f"Tables~\\ref{{tab:{m[1]}}} and~\\ref{{tab:{m[2]}}}"), text)
    text = re.sub(rf"\bTable ({NUM})", lambda m: raw(f"Table~\\ref{{tab:{m[1]}}}"), text)
    text = re.sub(rf"\bFigure ({NUM})", lambda m: raw(f"Fig.~\\ref{{fig:{m[1]}}}"), text)
    for key, number in CITATIONS.items():
        text = text.replace(f"[{key}]", f"[{number}]")
    text = re.sub(r"\[(\d+)\](?:, \[(\d+)\])*",
                  lambda m: raw("\\cite{" + ",".join(f"ref{n}" for n in re.findall(r"\d+", m[0])) + "}"),
                  text)
    for char, tex in UNICODE.items():
        text = text.replace(char, raw(tex))
    return text


def convert_table(caption: str, number: str, rows: list[str]) -> str:
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    header, body = cells[0], cells[2:]
    ncols = len(header)
    sep = "\n\nCELLSEPARATOR\n\n"
    flat = [caption] + [c or "EMPTYCELL" for row in [header] + body for c in row]
    converted = pandoc(sep.join(inline_refs(c) for c in flat), wrap="none").split("\nCELLSEPARATOR\n")
    converted = [c.strip().replace("EMPTYCELL", "") for c in converted]
    if len(converted) != len(flat):
        sys.exit(f"Table {number}: {len(converted)} cells converted, {len(flat)} expected")
    caption_tex, cell_tex = converted[0], converted[1:]
    lengths = [max(len(row[i]) for row in [header] + body) for i in range(ncols)]
    wide = ncols >= 4 or sum(lengths) > 90
    # Width follows the body text and the longest header word, so short columns stay readable.
    weights = [max(min(max(len(row[i]) for row in body), 60), *(len(w) + 2 for w in header[i].split()), 8)
               for i in range(ncols)]
    total = sum(weights)
    spec = "".join(f">{{\\raggedright\\arraybackslash}}p{{{0.97 * w / total - 0.02:.3f}\\linewidth}}" for w in weights)
    lines = []
    for r in range(len(body) + 1):
        row = cell_tex[r * ncols:(r + 1) * ncols]
        if r == 0:
            row = [f"\\textbf{{{c}}}" for c in row]
        lines.append(" & ".join(row) + r" \\" + (r" \hline" if r == 0 else ""))
    env = "table*" if wide else "table"
    return "\n".join([
        f"\\begin{{{env}}}[!t]", "\\centering", "\\footnotesize",
        f"\\caption{{{caption_tex}}}\\label{{{label('tab', number)}}}",
        f"\\begin{{tabular}}{{{spec}}}", "\\hline", *lines, "\\hline", "\\end{tabular}", f"\\end{{{env}}}",
    ])


def convert_figure(image: str | None, placeholder: str | None, number: str, caption: str) -> str:
    # Every figure spans the full page width, so its text prints at a readable size;
    # single plots are drawn narrower so they do not fill half a page.
    env = "figure*"
    if image:
        width = NARROW_FIGURES.get(number, 0.92)
        body = f"\\includegraphics[width={width}\\linewidth]{{figures/{Path(image).name}}}"
    else:
        body = f"\\fbox{{\\parbox[c][1.6in][c]{{0.9\\linewidth}}{{\\centering {pandoc(placeholder)}}}}}"
    return "\n".join([f"\\begin{{{env}}}[!t]", "\\centering", body,
                      f"\\caption{{{pandoc(inline_refs(caption), wrap='none')}}}\\label{{{label('fig', number)}}}",
                      f"\\end{{{env}}}"])


def wrap_commands(block: str, width: int = 52) -> str:
    """Break long shell command lines with a backslash continuation so they fit one column."""
    out = []
    for line in block.split("\n"):
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            if cut <= 0:
                break
            out.append(line[:cut] + " \\")
            line = "    " + line[cut + 1:]
        out.append(line)
    return "\n".join(out)


def convert_chapter(path: Path) -> tuple[str, list[Path]]:
    text = path.read_text(encoding="utf-8")
    images = []

    text = MERMAID.sub(lambda m: f"![](figures/fig_{m[2]}_{m[3]}.png)\n\n{m[1]}", text)
    blocks = {}

    def stash(tex: str) -> str:
        key = f"RAWBLOCK{len(blocks)}END"
        blocks[key] = tex
        return f"\n\n{key}\n\n"

    def figure(m: re.Match) -> str:
        image = m["image"]
        if image:
            # Use the vector PDF when there is one; it stays sharp at any size.
            if (path.parent / image).with_suffix(".pdf").exists():
                image = str(Path(image).with_suffix(".pdf"))
            images.append(path.parent / image)
        return stash(convert_figure(image, m["placeholder"], m["number"], m["caption"]))

    text = re.sub(
        r"(?:!\[[^\]]*\]\((?P<image>figures/[^)]+)\)|\*\*\[(?P<placeholder>Placeholder:[^\]]*)\]\*\*)\n\n"
        rf"\*\*Figure (?P<number>{NUM})\*\* (?P<caption>[^\n]+)",
        figure, text)

    def table(m: re.Match) -> str:
        return stash(convert_table(m["caption"], m["number"], m["rows"].strip().split("\n")))

    text = re.sub(rf"\*\*Table (?P<number>{NUM})\*\* (?P<caption>[^\n]+)\n\n(?P<rows>(?:\|[^\n]*\n?)+)",
                  table, text)

    def heading(m: re.Match) -> str:
        level, number, title = len(m[1]), m[2].rstrip("."), m[3]
        command = {1: "section", 2: "subsection", 3: "subsubsection"}[level]
        title_tex = pandoc(inline_refs(title), wrap="none")
        return stash(f"\\{command}{{{title_tex}}}\\label{{sec:{number}}}")

    text = re.sub(r"^(#{1,3}) (?:Chapter )?(\d+(?:\.\d+)*\.?) (.+)$", heading, text, flags=re.M)

    # In the IEEE layout each chapter is a section.
    text = re.sub(r"\b([Tt])his chapter\b", lambda m: f"{m[1]}his section", text)
    parts = re.split(r"(```.*?```)", text, flags=re.S)
    text = "".join(p if p.startswith("```") else inline_refs(p) for p in parts)
    tex = pandoc(text)
    for key, value in blocks.items():
        tex = tex.replace(key, value)
    tex = re.sub(r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}",
                 lambda m: "\\begin{verbatim}" + wrap_commands(m[1]) + "\\end{verbatim}", tex, flags=re.S)
    tex = re.sub(r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}",
                 lambda m: "{\\footnotesize\n\\begin{verbatim}" + m[1] + "\\end{verbatim}\n}", tex, flags=re.S)
    return tex + "\n", images


def bibliography() -> str:
    lines = (REPORT_DIR / "references.md").read_text(encoding="utf-8").splitlines()
    items = []
    for line in lines:
        m = re.match(r"\[(\d+)\] (.+)", line)
        if not m:
            continue
        entry = re.sub(r"(https?://\S+?)([.,;]?)(?=\s|$)", lambda u: raw(f"\\url{{{u[1]}}}") + u[2], m[2])
        items.append(f"\\bibitem{{ref{m[1]}}}\n{pandoc(entry, wrap='none')}")
    return "\\begin{thebibliography}{" + str(len(items)) + "}\n\n" + "\n\n".join(items) + "\n\n\\end{thebibliography}\n"


def abstract() -> tuple[str, str]:
    text = (REPORT_DIR / "abstract.md").read_text(encoding="utf-8")
    body = re.sub(r"^# Abstract\s*", "", text).split("**Keywords:**")
    return pandoc(inline_refs(body[0].strip()), wrap="none"), body[1].strip()


def front_matter(abstract_tex: str) -> str:
    f = FRONT
    authors_lines = r"\\".join(f["authors"])
    title = f["title"]
    return rf"""\onecolumn
\pagenumbering{{roman}}
\thispagestyle{{empty}}
\begin{{center}}
\vspace*{{1in}}
{{\LARGE\bfseries {title}\par}}
\vspace{{1in}}
A Project Report\\[0.5em]
Presented to\\
The Faculty of the College of Engineering\\[1em]
San Jos\'{{e}} State University\\[1em]
In Partial Fulfillment\\
Of the Requirements for the Degree\\
{f['degree']}\\[1in]
By\\[0.5em]
{authors_lines}\\[1in]
{f['date']}
\end{{center}}
\newpage
\thispagestyle{{empty}}
\vspace*{{\fill}}
\begin{{center}}
Copyright \copyright\ {f['year']}\\[1em]
{authors_lines}\\[1em]
ALL RIGHTS RESERVED
\end{{center}}
\vspace*{{\fill}}
\newpage
\begin{{center}}
\vspace*{{2in}}
{{\large APPROVED}}\\[1.5in]
\rule{{3in}}{{0.4pt}}\\
{f['advisor']}, Project Advisor
\end{{center}}
\newpage
\begin{{center}}
{{\large\bfseries ABSTRACT}}\\[1em]
{title}\\[0.5em]
By {", ".join(f['authors'][:-1])} and {f['authors'][-1]}
\end{{center}}
\vspace{{1em}}
\noindent {abstract_tex}
\newpage
\begin{{center}}
{{\large\bfseries Acknowledgments}}
\end{{center}}
\vspace{{1em}}
\noindent {f['acknowledgments']}
\newpage
\tableofcontents
\newpage
\listoffigures
\newpage
\listoftables
\newpage
\twocolumn
\pagenumbering{{arabic}}
"""


PREAMBLE = r"""\documentclass{IEEEtran}
% Generated by docs/project_report/build_latex.py from the chapter Markdown files.
% Edit the chapters and rebuild instead of editing this file.
\usepackage{iftex}
\ifPDFTeX
  \usepackage[utf8]{inputenc}
  \usepackage[T1]{fontenc}
\fi
\usepackage{amssymb}
\usepackage[cmex10]{amsmath}
\usepackage{array}
\usepackage{graphicx}
\usepackage{url}
\usepackage{cite}
\usepackage[hidelinks]{hyperref}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\hyphenation{op-tical net-works semi-conduc-tor}

\begin{document}
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--compile", action="store_true", help="compile report.pdf with tectonic")
    args = parser.parse_args(argv)
    if shutil.which("pandoc") is None:
        sys.exit("pandoc not found")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "sections").mkdir(parents=True)
    (OUT_DIR / "figures").mkdir()
    shutil.copy(TEMPLATE_CLS, OUT_DIR / "IEEEtran.cls")

    abstract_tex, keywords = abstract()
    inputs = []
    for name in CHAPTERS[1:]:
        path = REPORT_DIR / name
        tex, images = convert_chapter(path)
        for image in images:
            shutil.copy(image, OUT_DIR / "figures" / image.name)
        stem = path.stem
        (OUT_DIR / "sections" / f"{stem}.tex").write_text(tex, encoding="utf-8")
        inputs.append(f"\\input{{sections/{stem}}}")

    report = (
        PREAMBLE + front_matter(abstract_tex)
        + f"\\title{{{FRONT['title']}}}\n"
        + "\\author{\\IEEEauthorblockN{" + ", ".join(FRONT["authors"]) + "}\\\\\n"
        + "\\IEEEauthorblockA{Department of Computer Engineering\\\\San Jos\\'{e} State University (SJSU)\\\\"
          "San Jos\\'{e}, CA, USA}}\n"
        + "\\maketitle\n\n"
        + f"\\begin{{abstract}}\n{abstract_tex}\n\\end{{abstract}}\n\n"
        + f"\\begin{{IEEEkeywords}}\n{keywords}\n\\end{{IEEEkeywords}}\n\n"
        + "\n".join(inputs) + "\n\n"
        + bibliography() + "\n\\end{document}\n"
    )
    (OUT_DIR / "report.tex").write_text(report, encoding="utf-8")
    # The same document in one file, with every chapter inlined, for pasting into Overleaf.
    single = re.sub(r"\\input\{sections/([^}]+)\}",
                    lambda m: (OUT_DIR / "sections" / f"{m[1]}.tex").read_text(encoding="utf-8"), report)
    (OUT_DIR / "report_single_file.tex").write_text(single, encoding="utf-8")
    print(f"wrote {OUT_DIR.relative_to(REPORT_DIR.parent.parent)}/")

    if args.compile:
        subprocess.run(["tectonic", "--keep-logs", "report.tex"], cwd=OUT_DIR, check=True)
        print(f"wrote {(OUT_DIR / 'report.pdf').relative_to(REPORT_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
