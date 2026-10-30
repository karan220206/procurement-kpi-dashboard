"""Chart style shared by every notebook, so all figures in the project look the same.

Colors follow a colorblind-validated categorical order (blue, orange, aqua); comparisons use at
most these three. One series = one color; emphasis = the highlight color against muted gray.
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from utils import REPORTS_DIR

FIG_DIR = REPORTS_DIR / "figures"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]   # categorical slots 1-3
MUTED = "#c3c2b7"                             # de-emphasised marks
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de"

# Sequential single-hue ramp (light -> dark blue) for magnitudes such as heatmaps
BLUES = LinearSegmentedColormap.from_list(
    "blues", ["#eef4fc", "#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])


def apply_style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "text.color": INK,
        "xtick.color": INK_2, "ytick.color": INK_2, "xtick.major.size": 0, "ytick.major.size": 0,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "grid.linestyle": "-",
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.axisbelow": True, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlepad": 24, "font.size": 10, "lines.linewidth": 2, "legend.frameon": False,
        "figure.figsize": (9, 4.2), "figure.dpi": 100, "savefig.dpi": 150, "savefig.bbox": "tight",
        "patch.edgecolor": SURFACE, "patch.linewidth": 1.5,   # surface gap between adjacent bars
    })


def subtitle(ax, text):
    """Grey one-line explanation under the chart title."""
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_2, fontsize=9, va="bottom")


def save(fig, name):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png")
