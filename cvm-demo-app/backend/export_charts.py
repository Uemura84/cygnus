"""Export high-resolution PNG charts for Braskem and Vale."""

import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Style constants (matching Cygnus v4) ─────────────────────────────────────

FINANCIAL_BLUE = "#2E86C1"
COST_RED       = "#C0392B"
COST_RED_65    = (192/255, 57/255, 43/255, 0.65)
NAVY           = "#0b1f3a"
TEAL           = "#0e8f9a"
AMBER          = "#EF9F27"
RED            = "#E24B4A"
DARK_RED       = "#991b1b"

BAND_COLOR = {
    "Healthy":         TEAL,
    "Stable":          TEAL,
    "Watchlist":       AMBER,
    "High Risk":       RED,
    "Distress":        RED,
    "Severe Distress": DARK_RED,
}

DPI = 300
OUT_DIR = os.path.join(os.path.dirname(__file__), "exports")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Helvetica Neue", "Arial"],
    "font.size": 10,
})


def _base_ax(ax):
    ax.set_facecolor("#F8FAFC")
    ax.tick_params(labelsize=8, colors="#475569")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#e2e8f0")
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.5)


def _year(period_str):
    return (period_str or "")[:4]


def _annual_only(series):
    seen = {}
    for r in series:
        yr = _year(r.get("period"))
        if yr:
            seen[yr] = r
    return list(seen.values())


# ── Revenue / COGS ──────────────────────────────────────────────────────────

def chart_revenue_cogs(step4, company):
    ts = _annual_only(step4.get("time_series", []))
    valid = [r for r in ts if r.get("revenue_abs") is not None]
    if len(valid) < 2:
        return

    periods  = [_year(r.get("period")) for r in valid]
    rev_brl  = [r.get("revenue_abs", 0) / 1_000_000 for r in valid]
    cogs_brl = [abs(r.get("cogs_abs", 0)) / 1_000_000 for r in valid]
    x = list(range(len(periods)))

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor("white")
    _base_ax(ax)

    ax.plot(x, rev_brl,  marker="o", lw=2.5, ms=6, color=FINANCIAL_BLUE,
            label="Revenue", zorder=5)
    ax.plot(x, cogs_brl, marker="s", lw=2.5, ms=6, color=COST_RED, alpha=0.65,
            label="COGS", linestyle="--", zorder=5)
    ax.fill_between(x, cogs_brl, rev_brl, alpha=0.08, color=FINANCIAL_BLUE)

    bbox_rev  = dict(boxstyle="round,pad=0.25", facecolor="white",
                     edgecolor="#e2e8f0", alpha=0.9)
    bbox_cogs = dict(boxstyle="round,pad=0.25", facecolor="white",
                     edgecolor="#e2e8f0", alpha=0.9)
    for i, (rv, cg) in enumerate(zip(rev_brl, cogs_brl)):
        ax.annotate(f"{rv:.1f}B", (i, rv), textcoords="offset points",
                    xytext=(0, 12), ha="center", va="bottom",
                    fontsize=10, fontweight="bold",
                    color=FINANCIAL_BLUE, fontfamily="monospace",
                    bbox=bbox_rev, zorder=10)
        ax.annotate(f"{cg:.1f}B", (i, cg), textcoords="offset points",
                    xytext=(0, -12), ha="center", va="top",
                    fontsize=10, fontweight="bold",
                    color=COST_RED_65, fontfamily="monospace",
                    bbox=bbox_cogs, zorder=10)

    ax.set_xticks(x)
    ax.set_xticklabels(periods, fontsize=9)
    ax.set_title(f"{company} — Revenue vs COGS (BRL B)",
                 fontsize=12, color=NAVY, pad=10, fontweight="bold")
    ax.set_ylabel("BRL B", fontsize=9, color="#475569")
    ax.legend(fontsize=9, framealpha=0)

    plt.tight_layout(pad=0.5)
    path = os.path.join(OUT_DIR, f"{company.lower()}_revenue_cogs.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ {path}")


# ── Margin Bridge (Waterfall) ────────────────────────────────────────────────

def chart_margin_bridge(step4, company):
    bridge = step4.get("margin_bridge")
    if not bridge or bridge.get("start_value") is None:
        return

    start_label = bridge["start_label"].replace("_", " ").title()
    end_label   = bridge["end_label"].replace("_", " ").title()
    items = [
        {"name": start_label, "value": bridge["start_value"], "type": "total"},
        *[{"name": f["name"].replace("_", " ").title(), "value": f["value"], "type": "change"}
          for f in bridge["factors"]],
        {"name": end_label, "value": bridge["end_value"], "type": "total"},
    ]

    names  = [it["name"] for it in items]
    values = [it["value"] for it in items]
    types  = [it["type"] for it in items]

    # Compute bar positions (base + height)
    running = 0
    bases   = []
    heights = []
    colors  = []

    for it in items:
        if it["type"] == "total":
            base = min(it["value"], 0)
            h    = abs(it["value"])
            running = it["value"]
        else:
            if it["value"] >= 0:
                base = running
                h    = it["value"]
            else:
                base = running + it["value"]
                h    = abs(it["value"])
            running += it["value"]
        bases.append(base)
        heights.append(h)

        if it["type"] == "total":
            colors.append(FINANCIAL_BLUE)
        elif it["value"] < 0:
            colors.append(COST_RED_65)
        else:
            colors.append((46/255, 134/255, 193/255, 0.70))

    x = np.arange(len(items))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    _base_ax(ax)

    bar_w = 0.55
    bars = ax.bar(x, heights, bottom=bases, width=bar_w, color=colors, zorder=3)

    # Connector lines
    for i in range(len(items) - 1):
        y_conn = bases[i] + heights[i] if items[i]["type"] == "total" or items[i]["value"] >= 0 else bases[i]
        if items[i]["type"] == "total":
            y_conn = items[i]["value"]
        else:
            y_conn = bases[i] + heights[i] if items[i]["value"] >= 0 else bases[i]
            if items[i]["value"] >= 0:
                y_conn = bases[i] + heights[i]
            else:
                y_conn = bases[i]
        # running after this item
        if items[i]["type"] == "total":
            running_after = items[i]["value"]
        else:
            running_after = sum(it["value"] for it in items[:i+1] if it["type"] == "change") + items[0]["value"]

        ax.plot([x[i] + bar_w/2, x[i+1] - bar_w/2], [running_after, running_after],
                color=(11/255, 31/255, 58/255, 0.22), lw=0.8, ls="--", zorder=2)

    # Value labels
    bbox_props = dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="#e2e8f0", alpha=0.9)
    for i, it in enumerate(items):
        val = it["value"]
        if it["type"] == "total":
            label = f"{val:.1f}%"
            y_pos = bases[i] + heights[i]
            va = "bottom"
            offset = (0, 8)
            color = FINANCIAL_BLUE
        else:
            sign = "+" if val >= 0 else "−"
            label = f"{sign}{abs(val):.1f}%"
            if val >= 0:
                y_pos = bases[i] + heights[i]
                va = "bottom"
                offset = (0, 8)
            else:
                y_pos = bases[i]
                va = "top"
                offset = (0, -8)
            color = FINANCIAL_BLUE if val >= 0 else COST_RED

        ax.annotate(label, (x[i], y_pos), textcoords="offset points",
                    xytext=offset, ha="center", va=va,
                    fontsize=11, fontweight="bold", color=color,
                    fontfamily="monospace", bbox=bbox_props, zorder=10)

    ax.axhline(0, color="#94a3b8", lw=0.8, zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8, rotation=15, ha="right")
    ax.set_title(f"{company} — Margin Bridge: Peak to Current",
                 fontsize=12, color=NAVY, pad=10, fontweight="bold")
    ax.set_ylabel("%", fontsize=9, color="#475569")

    plt.tight_layout(pad=0.5)
    path = os.path.join(OUT_DIR, f"{company.lower()}_margin_bridge.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ {path}")


# ── Distress Gauge ───────────────────────────────────────────────────────────

def chart_distress_gauge(step6, company):
    distress = step6.get("distress", {})
    score = distress.get("distress_score", step6.get("risk_score"))
    band  = distress.get("band", step6.get("risk_level", ""))
    if score is None:
        return

    pct = min(max(score, 0), 100) / 100
    band_color = BAND_COLOR.get(band, "#475569")

    fig, ax = plt.subplots(figsize=(5, 3.2))
    fig.patch.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")

    cx, cy = 0.5, 0.35
    R_outer = 0.38
    R_inner = 0.28

    # Draw gradient arc segments
    n_segments = 200
    for i in range(n_segments):
        t0 = math.pi * (1 - i / n_segments)
        t1 = math.pi * (1 - (i + 1) / n_segments)
        frac = i / n_segments

        # Gradient: teal → amber → red
        if frac < 0.5:
            f = frac / 0.5
            r = int(14 + f * (239 - 14))
            g = int(143 + f * (159 - 143))
            b = int(154 + f * (39 - 154))
        else:
            f = (frac - 0.5) / 0.5
            r = int(239 + f * (226 - 239))
            g = int(159 + f * (75 - 159))
            b = int(39 + f * (74 - 39))

        color = (r/255, g/255, b/255, 0.85)

        wedge = mpatches.Wedge(
            (cx, cy), R_outer, math.degrees(t1), math.degrees(t0),
            width=R_outer - R_inner, facecolor=color, edgecolor="none",
            transform=ax.transAxes
        )
        ax.add_patch(wedge)

    # Needle
    theta = math.pi * (1 - pct)
    needle_len = R_outer - 0.02
    nx = cx + needle_len * math.cos(theta)
    ny = cy + needle_len * math.sin(theta)
    ax.annotate("", xy=(nx, ny), xytext=(cx, cy),
                arrowprops=dict(arrowstyle="-", color=(11/255, 31/255, 58/255, 0.3),
                                lw=2),
                xycoords="axes fraction", textcoords="axes fraction")

    # Hub
    hub = plt.Circle((cx, cy), 0.018, transform=ax.transAxes,
                      color=(11/255, 31/255, 58/255, 0.3), zorder=10)
    ax.add_patch(hub)
    hub_inner = plt.Circle((cx, cy), 0.008, transform=ax.transAxes,
                            color="#f5f7fa", zorder=11)
    ax.add_patch(hub_inner)

    # Score text
    ax.text(cx, cy + 0.10, str(int(round(score))),
            transform=ax.transAxes, ha="center", va="center",
            fontsize=28, fontweight="bold", color=band_color)

    # Band label
    ax.text(cx, cy + 0.01, band,
            transform=ax.transAxes, ha="center", va="center",
            fontsize=12, fontweight="600", color="#4a5568")

    # Scale labels
    ax.text(cx - R_outer - 0.02, cy - 0.06, "0",
            transform=ax.transAxes, ha="center", fontsize=8, color="#94a3b8")
    ax.text(cx + R_outer + 0.02, cy - 0.06, "100",
            transform=ax.transAxes, ha="center", fontsize=8, color="#94a3b8")
    ax.text(cx, cy + R_outer + 0.06, "50",
            transform=ax.transAxes, ha="center", fontsize=8, color="#94a3b8")

    # Title
    ax.text(cx, 0.95, f"{company} — Distress Score",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=13, fontweight="bold", color=NAVY)

    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.1)

    plt.tight_layout(pad=0.3)
    path = os.path.join(OUT_DIR, f"{company.lower()}_distress_gauge.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ {path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for company, folder in [("Braskem", "BRASKEM_S_A"), ("Vale", "VALE_S_A")]:
        print(f"\n{company}:")
        s4_path = os.path.join(CACHE_DIR, folder, "step4.json")
        s6_path = os.path.join(CACHE_DIR, folder, "step6.json")

        s4 = json.load(open(s4_path))["data"]
        s6 = json.load(open(s6_path))["data"]

        chart_revenue_cogs(s4, company)
        chart_margin_bridge(s4, company)
        chart_distress_gauge(s6, company)

    print(f"\nAll charts exported to {OUT_DIR}/")


if __name__ == "__main__":
    main()
