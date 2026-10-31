"""Draw the report's block diagrams (Figures 2.1, 4.1, 4.3 and 4.4).

    ~/venvs/traceadvisor-lock/bin/python docs/project_report/diagrams/make_diagrams.py

Each figure is drawn at its printed size (7 in wide, the full width of a page)
with 7.5 pt text, and written as a vector PDF for the LaTeX report and a PNG
for the Word report into the chapter's figures/ folder.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

REPORT_DIR = Path(__file__).resolve().parents[1]
WIDTH = 7.0
FONT = 7.5
LINE = 0.135  # inches per text line at FONT
FILL, EDGE, ARROW = "#eeeeee", "#888888", "#555555"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FONT, "pdf.fonttype": 42})


class Diagram:
    def __init__(self, height: float):
        self.fig = plt.figure(figsize=(WIDTH, height))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set_xlim(0, WIDTH)
        self.ax.set_ylim(0, height)
        self.ax.axis("off")
        self.boxes = {}

    def box(self, key, x, y, w, title, lines=(), dashed=False):
        """A box centred at (x, y) with a bold title and plain lines below it."""
        h = (len(lines) + 1) * LINE + 0.16
        self.ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="square,pad=0",
                                         facecolor=FILL, edgecolor=EDGE, linewidth=0.7,
                                         linestyle="--" if dashed else "-"))
        top = y + h / 2 - 0.08 - LINE / 2
        self.ax.text(x, top, title, ha="center", va="center", fontweight="bold")
        for i, line in enumerate(lines, start=1):
            self.ax.text(x, top - i * LINE, line, ha="center", va="center")
        self.boxes[key] = (x, y, w, h)

    def frame(self, x0, y0, x1, y1, title):
        self.ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#fafafa",
                                    edgecolor=EDGE, linewidth=0.7, zorder=0))
        self.ax.text((x0 + x1) / 2, y1 - 0.11, title, ha="center", va="center", style="italic")

    def _anchor(self, key, side):
        x, y, w, h = self.boxes[key]
        return {"l": (x - w / 2, y), "r": (x + w / 2, y), "t": (x, y + h / 2), "b": (x, y - h / 2)}[side]

    def arrow(self, a, b, label=None, sides="rl", dashed=False, label_at=0.5, offset=None,
              start=None, end=None, rad=0.0):
        p = start or self._anchor(a, sides[0])
        q = end or self._anchor(b, sides[1])
        self.ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, color=ARROW,
                                          linewidth=0.7, linestyle="--" if dashed else "-",
                                          connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))
        if label:
            # Labels sit beside the arrow, never on it: above a horizontal arrow, right of a vertical one.
            horizontal = abs(q[0] - p[0]) >= abs(q[1] - p[1])
            n = label.count("\n") + 1
            if offset is None:
                offset = (0, 0.05 + n * LINE / 2) if horizontal else (0.07, 0)
            lx = p[0] + (q[0] - p[0]) * label_at + offset[0]
            ly = p[1] + (q[1] - p[1]) * label_at + offset[1]
            self.ax.text(lx, ly, label, ha="center" if horizontal else "left", va="center",
                         fontsize=FONT - 0.5, color="#333333", linespacing=1.1)

    def save(self, chapter_folder: str, name: str):
        out = REPORT_DIR / chapter_folder / "figures"
        for suffix, kwargs in ((".pdf", {"metadata": {"CreationDate": None}}), (".png", {"dpi": 300})):
            self.fig.savefig(out / f"{name}{suffix}", facecolor="white", **kwargs)
        plt.close(self.fig)
        print(f"wrote {chapter_folder}/figures/{name}.pdf and .png")


def figure_2_1():
    d = Diagram(4.05)
    y1, y2, y3 = 3.45, 2.05, 0.6
    d.box("SRC", 0.95, y1, 1.7, "Raw trace sources", ["Google ClusterData 2019", "Alibaba GPU 2020"])
    d.box("PREP", 3.5, y1, 2.0, "Dataset preparation", ["Loading, checksum verification",
                                                         "Window and run reconstruction", "Job and role construction"])
    d.box("ADP", 6.0, y1, 1.75, "Dataset adapters", ["Dataset-specific mapping", "Identity construction",
                                                      "Eligibility rules", "Resource aggregation"])
    d.box("CAN", 6.0, y2, 1.95, "Canonical layer", ["Canonical schema, units", "Capability profiles",
                                                     "Validation, rejected records"])
    d.box("HT", 3.5, y2, 1.85, "History and targets", ["Chronological split", "Point-in-time history",
                                                        "Features, next-run targets"])
    d.box("RE", 0.95, y2, 1.75, "Recommendation engine", ["Request, baselines", "ML, Hybrid",
                                                          "Validation-only selection", "Locked manifest"])
    d.box("EV", 0.95, y3, 1.6, "Replay evaluator", ["One-time test replay", "Violation, utilization",
                                                     "Waste, shortfall"])
    d.box("AR", 3.0, y3, 1.75, "Artifact repository", ["Views, targets, models", "Manifest, metrics",
                                                        "Checksums"])
    d.box("API", 4.85, y3, 1.3, "REST API", ["(planned)", "Read-only access"])
    d.box("FE", 6.35, y3, 1.2, "Web frontend", ["(planned)", "Recommendations", "Policy comparison"])
    d.arrow("SRC", "PREP", "raw files")
    d.arrow("PREP", "ADP", "prepared\nrecords")
    d.arrow("ADP", "CAN", "mapped records", sides="bt")
    d.arrow("CAN", "HT", "canonical\nviews", sides="lr")
    d.arrow("HT", "RE", "features,\nhistory,\ntargets", sides="lr")
    d.arrow("RE", "EV", "policy\nrecommendations", sides="bt")
    d.arrow("RE", "AR", "locked decisions\nand models", sides="bt", start=(1.65, d.boxes["RE"][1] - 0.25),
            offset=(0.55, 0.05))
    d.arrow("EV", "AR", "metrics")
    d.arrow("AR", "API")
    d.arrow("API", "FE")
    d.save("chapter_2_project_architecture", "fig_2_1")


def figure_4_1():
    d = Diagram(3.85)
    yg, ya = 3.3, 2.25
    d.frame(0.05, yg - 0.48, 6.95, yg + 0.5, "Google ClusterData 2019")
    d.frame(0.05, ya - 0.5, 6.95, ya + 0.5, "Alibaba GPU 2020")
    d.box("GR", 0.85, yg - 0.05, 1.4, "Kaggle sample", ["one CSV file"])
    d.box("GI", 2.65, yg - 0.05, 1.6, "Ingestion", ["windows, requests, events"])
    d.box("GX", 4.5, yg - 0.05, 1.6, "Run reconstruction", ["executions, occurrences"])
    d.box("GA", 6.2, yg - 0.05, 1.2, "Google adapter", ["(thin)"])
    d.box("AR", 0.85, ya - 0.05, 1.4, "Six official tables", [])
    d.box("AL", 2.65, ya - 0.05, 1.6, "Source loader", ["checksums, types,", "row numbers"])
    d.box("AA", 4.6, ya - 0.05, 1.95, "Alibaba adapter", ["joins, roles, instances,", "eligibility, aggregation"])
    d.box("SC", 3.0, 1.5, 1.45, "Canonical schema", [])
    d.box("PR", 3.0, 1.08, 1.45, "Capability profiles", [])
    d.box("FW", 5.9, 1.15, 1.6, "Adapter framework", ["validation"])
    d.box("CV", 1.5, 0.3, 2.6, "Canonical views", ["Google: occurrence", "Alibaba: role_occurrence, instance"])
    d.box("RJ", 3.95, 0.3, 1.4, "Rejected records", [])
    d.box("PM", 5.9, 0.3, 1.6, "Provenance", ["checksums, counts"])
    for a, b in (("GR", "GI"), ("GI", "GX"), ("GX", "GA"), ("AR", "AL"), ("AL", "AA")):
        d.arrow(a, b)
    d.arrow("GA", "FW", sides="bt", end=(6.2, d.boxes["FW"][1] + d.boxes["FW"][3] / 2))
    d.arrow("AA", "FW", sides="bt", end=(5.45, d.boxes["FW"][1] + d.boxes["FW"][3] / 2))
    d.arrow("SC", "FW", end=(5.1, 1.22))
    d.arrow("PR", "FW", end=(5.1, 1.08))
    d.arrow("FW", "PM", sides="bt")
    d.arrow("FW", "RJ", start=(5.35, 0.94), end=(4.3, 0.42))
    d.arrow("FW", "CV", start=(5.1, 1.0), end=(2.5, 0.5))
    d.save("chapter_4_project_design", "fig_4_1")


def figure_4_3():
    d = Diagram(2.75)
    y = 2.2
    d.box("CV", 0.6, y, 1.0, "Canonical", ["evaluation rows"])
    d.box("SP", 1.85, y, 1.15, "Chronological split", ["70 / 15 / 15"])
    d.box("HF", 3.55, y, 1.85, "Point-in-time history", ["next-run targets", "(within split for Alibaba)"])
    d.box("TR", 5.3, 2.45, 1.0, "Training set", [])
    d.box("VA", 5.3, 1.95, 1.0, "Validation set", [])
    d.box("ML", 6.45, 2.45, 0.9, "ML models", [])
    d.box("BL", 3.55, 1.05, 1.85, "Baseline candidates", ["Mean, P90, P95, P99", "× min_runs"])
    d.box("SEL", 6.3, 1.25, 1.2, "Validation-only", ["selection"])
    d.box("TE", 1.2, 1.2, 1.3, "Test set", ["held out"], dashed=True)
    d.box("LK", 6.3, 0.35, 1.2, "Locked decision", ["manifest"])
    d.box("FT", 2.55, 0.35, 1.3, "One-time", ["test replay"])
    d.box("MET", 0.7, 0.35, 1.2, "Shared metrics", [])
    d.arrow("CV", "SP")
    d.arrow("SP", "HF")
    d.arrow("HF", "TR", end=(4.8, 2.45))
    d.arrow("HF", "VA", end=(4.8, 1.95))
    d.arrow("HF", "TE", sides="bt", start=(2.85, 1.98), end=(1.2, 1.4), dashed=True)
    d.arrow("HF", "BL", "each row's own history", sides="bt")
    d.arrow("TR", "ML", "fit")
    d.arrow("ML", "SEL", sides="bt", end=(6.45, 1.45))
    d.arrow("VA", "SEL", "scoring", sides="rt", end=(6.05, 1.45), offset=(0.05, 0.12))
    d.arrow("BL", "SEL", sides="rl")
    d.arrow("SEL", "LK", sides="bt")
    d.arrow("LK", "FT", sides="lr")
    d.arrow("TE", "FT", "read only\nafter the lock", start=(1.5, 1.0), end=(2.3, 0.57), dashed=True,
            offset=(-0.5, -0.12))
    d.arrow("FT", "MET", sides="lr")
    d.save("chapter_4_project_design", "fig_4_3")


def figure_4_4():
    d = Diagram(1.75)
    d.frame(0.05, 0.95, 6.95, 1.7, "Published artifacts")
    items = [("A1", "Canonical views", []), ("A2", "Split tables", ["history, targets"]),
             ("A3", "Model outputs", ["baselines, ML"]), ("A4", "Decision manifest", []),
             ("A5", "Evaluation results", [])]
    for i, (key, title, lines) in enumerate(items):
        d.box(key, 0.8 + i * 1.35, 1.25, 1.2, title, lines)
    d.box("REPO", 1.6, 0.35, 2.0, "Artifact repository", ["checksums, metadata"])
    d.box("API", 3.9, 0.35, 1.5, "REST API (planned)", ["read-only"])
    d.box("FE", 5.95, 0.35, 1.9, "Web frontend (planned)", ["workloads, recommendations"])
    d.arrow("A1", "REPO", start=(1.6, 0.95), end=(1.6, 0.53))
    d.arrow("REPO", "API")
    d.arrow("API", "FE")
    d.save("chapter_4_project_design", "fig_4_4")


if __name__ == "__main__":
    figure_2_1()
    figure_4_1()
    figure_4_3()
    figure_4_4()
