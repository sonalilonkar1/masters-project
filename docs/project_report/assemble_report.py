"""Assemble the final report from the chapter files.

Usage:
    python docs/project_report/assemble_report.py          # final_report.md and final_report.docx
    python docs/project_report/assemble_report.py --check  # cross-reference check only

The chapter files stay the source. The script converts author-year citation
keys to the IEEE numbers in references.md, replaces each Mermaid diagram with
its exported PNG, points image paths at the chapter folders, and checks that
every Section, Table and Figure reference has a target. The .docx needs pandoc.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent
OUT_MD = REPORT_DIR / "final_report.md"
OUT_DOCX = REPORT_DIR / "final_report.docx"

TITLE = "TraceAdvisor: Pre-Execution Resource Recommendations for Recurring Cluster Workloads"

CHAPTERS = [
    "abstract.md",
    "chapter_1_project_overview/ch1_project_overview.md",
    "chapter_2_project_architecture/ch2_project_architecture.md",
    "chapter_3_technology_descriptions/ch3_technology_descriptions.md",
    "chapter_4_project_design/ch4_project_design.md",
    "chapter_5_project_implementation/ch5_project_implementation.md",
    "chapter_6_testing_and_verification/ch6_testing_and_verification.md",
    "chapter_7_results_and_discussion/ch7_results_and_discussion.md",
    "chapter_8_operations_and_reproducibility/ch8_operations_and_reproducibility.md",
    "chapter_9_summary_and_conclusions/ch9_summary_and_conclusions.md",
]

# Author-year keys used in Chapters 2-9 and their numbers in references.md.
CITATIONS = {
    "Cortez 2017": 2,
    "Wilkes 2019": 7,
    "Alibaba 2020": 19,
}

MERMAID = re.compile(r"```mermaid\n.*?\n```\n+(\*\*Figure (\d+)\.(\d+)\*\*[^\n]*)", re.S)
CITATION_KEY = re.compile(r"\[([A-Z][A-Za-z]+(?: et al\.)? \d{4}[a-z]?)\]")
# A page break that pandoc keeps in the .docx.
PAGE_BREAK = "\n```{=openxml}\n<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>\n```\n\n"
IMAGE = re.compile(r"(!\[[^\]]*\]\()(figures/[^)]+)\)")


def convert_chapter(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip() + "\n"
    folder = path.parent.relative_to(REPORT_DIR)

    def mermaid_to_png(match: re.Match) -> str:
        caption, chapter, number = match.group(1), match.group(2), match.group(3)
        png = path.parent / "figures" / f"fig_{chapter}_{number}.png"
        if not png.exists():
            sys.exit(f"{path.name}: no PNG for Figure {chapter}.{number} ({png})")
        return f"![](figures/{png.name})\n\n{caption}"

    text = MERMAID.sub(mermaid_to_png, text)
    if "```mermaid" in text:
        sys.exit(f"{path.name}: a Mermaid block without a following figure caption")

    def cite(match: re.Match) -> str:
        key = match.group(1)
        if key not in CITATIONS:
            sys.exit(f"{path.name}: citation key [{key}] has no number in CITATIONS")
        return f"[{CITATIONS[key]}]"

    text = CITATION_KEY.sub(cite, text)
    if folder != Path("."):
        text = IMAGE.sub(lambda m: f"{m.group(1)}{(folder / m.group(2)).as_posix()})", text)
    return text


def references() -> str:
    lines = (REPORT_DIR / "references.md").read_text(encoding="utf-8").splitlines()
    entries = [line for line in lines if re.match(r"\[\d+\] ", line)]
    return "# References\n\n" + "\n\n".join(entries) + "\n"


def check(report: str) -> list[str]:
    """Return references to sections, tables and figures that have no target."""
    sections = set(re.findall(r"^#{2,4} (\d+(?:\.\d+)+) ", report, re.M))
    captions = set(re.findall(r"^\*\*((?:Table|Figure) \d+\.\d+)\*\*", report, re.M))
    problems = []
    for number in sorted(set(re.findall(r"\bSections? (\d+\.\d+(?:\.\d+)?)", report))):
        if number not in sections:
            problems.append(f"Section {number} is referenced but has no heading")
    for label in sorted(set(re.findall(r"\b((?:Table|Figure) \d+\.\d+)", report))):
        if label not in captions:
            problems.append(f"{label} is referenced but has no caption")
    mentions = re.findall(r"\b((?:Table|Figure) \d+\.\d+)", report)
    for kind, first, second in re.findall(r"\b(Table|Figure)s (\d+\.\d+) and (\d+\.\d+)", report):
        mentions += [f"{kind} {first}", f"{kind} {second}"]
    for label in sorted(captions):
        if mentions.count(label) < 2:
            problems.append(f"{label} has a caption but is never referenced in the text")
    for number in sorted(set(re.findall(r"\[(\d+)\]", report)), key=int):
        if not re.search(rf"^\[{number}\] ", report, re.M):
            problems.append(f"citation [{number}] has no entry in the reference list")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check cross-references")
    args = parser.parse_args(argv)

    parts = [f"---\ntitle: \"{TITLE}\"\n---\n"]
    parts += [convert_chapter(REPORT_DIR / name) for name in CHAPTERS]
    parts.append(references())
    report = PAGE_BREAK.join(parts)

    problems = check(report)
    for problem in problems:
        print(f"CHECK: {problem}")
    if args.check:
        return 1 if problems else 0

    OUT_MD.write_text(report, encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(REPORT_DIR.parent.parent)}")
    if shutil.which("pandoc") is None:
        print("pandoc not found: skipped the .docx")
        return 0
    subprocess.run(
        [
            "pandoc", str(OUT_MD.name), "-o", str(OUT_DOCX.name),
            "--from", "markdown-implicit_figures",
            "--toc", "--toc-depth=2", "--metadata", "toc-title=Table of Contents",
            "--resource-path", ".",
        ],
        cwd=REPORT_DIR,
        check=True,
    )
    print(f"wrote {OUT_DOCX.relative_to(REPORT_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
