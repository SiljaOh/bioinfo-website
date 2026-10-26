"""Figure: DP matrix with traceback and coloured alignment for one sequence pair.

Uses the output of our Java alignment tool:

    java -cp out alignment.Main --pairs hb.pairs --seqlib hb.seqlib -m MATRICES/blosum62.mat \
         --mode global --format ali --dpmatrices dp > hb.ali
    python3 src/plot_alignment_example.py hb.ali dp/HBA_HUMAN_HBB_HUMAN MATRICES/blosum62.mat plots/alignment_example.png
"""
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import gridspec  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ali_file, dp_prefix, matrix_file, out = sys.argv[1:5]

# alignment output: ">idA idB score" followed by "idA: SEQ" and "idB: SEQ"
lines = [l.strip() for l in open(ali_file) if l.strip()]
header = lines[0][1:].split()
score = float(header[2])
a = lines[1].split(":", 1)[1].strip()
b = lines[2].split(":", 1)[1].strip()

# substitution matrix in the course format (ROWINDEX / COLINDEX / MATRIX lines)
mlines = open(matrix_file).read().splitlines()
rowi = next(l for l in mlines if l.startswith("ROWINDEX")).split()[1]
coli = next(l for l in mlines if l.startswith("COLINDEX")).split()[1]
mat = {}
for i, row in enumerate(l.split()[1:] for l in mlines if l.startswith("MATRIX")):
    for j, v in enumerate(row):
        mat[(rowi[i], coli[j])] = float(v)


def similar(x, y):
    return x != "-" and y != "-" and mat.get((x, y), mat.get((y, x), 0)) > 0


M = np.loadtxt(dp_prefix + "_M.txt")
M[~np.isfinite(M)] = np.nan
path = np.loadtxt(dp_prefix + "_path.txt")
ident = sum(x == y and x != "-" for x, y in zip(a, b))
n = len(a)

fig = plt.figure(figsize=(14, 5.6))
gs = gridspec.GridSpec(1, 2, width_ratios=[1, 1.7], wspace=0.22)

ax = fig.add_subplot(gs[0])
im = ax.imshow(M, cmap="viridis", aspect="auto")
ax.plot(path[:, 1], path[:, 0], color="#ff4d4d", lw=1.8, label="optimal traceback")
ax.set(title="Gotoh DP matrix (M) with traceback", xlabel=f"{header[1]} position", ylabel=f"{header[0]} position")
ax.legend(loc="lower left", fontsize=9)
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
cb.set_label("score")

ax2 = fig.add_subplot(gs[1])
ax2.axis("off")
ax2.set_title(f"Global alignment {header[0]} vs. {header[1]}  ·  score {score:.0f}  ·  identity {ident}/{n} = {100 * ident / n:.0f} %",
              fontsize=11)
W = 50
cw = 1 / (W + 6)
y = 0.9
for start in range(0, n, W):
    for k, (label, seq, other) in enumerate(((header[0][:3], a, b), ("", None, None), (header[1][:3], b, a))):
        yy = y - k * 0.06
        ax2.text(0, yy, label, family="monospace", fontsize=9, fontweight="bold", va="center", transform=ax2.transAxes)
        for i in range(start, min(start + W, n)):
            x = (i - start + 5) * cw
            if seq is None:
                ch = "|" if a[i] == b[i] and a[i] != "-" else (":" if similar(a[i], b[i]) else " ")
                ax2.text(x, yy, ch, family="monospace", fontsize=9, ha="center", va="center",
                         transform=ax2.transAxes, color="#555")
                continue
            c, o = seq[i], other[i]
            bg = "#2e7d32" if c == o and c != "-" else ("#9ccc65" if similar(c, o) else ("white" if c == "-" else "#e8e8e8"))
            ax2.text(x, yy, c, family="monospace", fontsize=9, ha="center", va="center", transform=ax2.transAxes,
                     color="white" if bg == "#2e7d32" else "black",
                     bbox=dict(boxstyle="square,pad=0.15", fc=bg, ec="none"))
    y -= 0.27
ax2.legend(handles=[Patch(fc="#2e7d32", label="identical"), Patch(fc="#9ccc65", label="similar (score > 0)"),
                    Patch(fc="#e8e8e8", label="mismatch")],
           loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.02))
fig.savefig(out, dpi=150, bbox_inches="tight")
print("saved", out)
