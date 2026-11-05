"""Draw the two original SVGs; the chart reads actual simulator output."""
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
from line import read_json, simulate


def text(x, y, label, size=26, color="#163036", weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{label}</text>'


def svg(name, height, contents):
    (here / (name + ".svg")).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" font-family="DejaVu Sans,sans-serif">'
        f'<rect width="1000" height="{height}" rx="18" fill="#edf4f3"/>{contents}</svg>\n', encoding="utf-8"
    )


flow = text(45, 55, "One line, three stations", 40, weight=700)
flow += text(45, 100, "Baseline: one waiting slot between adjacent stations", 25)
for label, sec, x in [("Feed", 5, 45), ("Assemble", 8, 390), ("Inspect", 6, 735)]:
    fill = "#883c15" if label == "Assemble" else "#125965"
    flow += f'<rect x="{x}" y="145" width="220" height="112" rx="12" fill="{fill}"/>'
    flow += text(x + 18, 192, label, 30, "#ffffff", 700)
    flow += text(x + 18, 232, f"{sec} s / part", 25, "#ffffff")
for x in (267, 612):
    flow += f'<path d="M{x} 204h115m-12-8 12 8-12 8" fill="none" stroke="#254149" stroke-width="4"/>'
    flow += f'<rect x="{x+41}" y="191" width="26" height="26" rx="4" fill="#edf4f3" stroke="#254149" stroke-width="3"/>'
flow += text(45, 316, "Assemble sets the baseline nominal ceiling: 3,600 ÷ 8 = 450 parts/h.", 24)
svg("bottleneck-flow", 355, flow)

panels = [
    (88, "Change a station cycle", [
        ("faster-assemble", "Faster Assemble", "#007060", ""),
        ("faster-feed", "Faster Feed", "#783ba7", "6 5"),
        ("baseline", "Baseline", "#18394a", "2 6")]),
    (577, "Buffer space during a pause", [
        ("inspection-pause-two", "2 waiting slots", "#007060", ""),
        ("inspection-pause-zero", "0 waiting slots", "#a24712", "7 5")]),
]
chart = text(43, 56, "Completed parts during the same 120 seconds", 34, weight=700)
chart += text(43, 96, "Synthetic model output • both panels use the same scale", 23)
for x, title, lines in panels:
    bottom, top, width = 451, 180, 340
    X = lambda t: x + t * width / 120
    Y = lambda count: bottom - count * (bottom - top) / 20
    chart += text(x - 4, 144, title, 20, weight=700)
    for y in range(0, 21, 5):
        chart += f'<path d="M{x} {Y(y)}h{width}" stroke="#c9d9d7"/>'
        chart += text(x - (39 if y >= 10 else 25), Y(y) + 6, str(y), 19)
    for t in (0, 40, 80, 120):
        chart += text(X(t) - 7, bottom + 32, str(t), 19)
    chart += text(x + 94, bottom + 66, "Elapsed seconds", 20)
    if x > 500:
        chart += f'<rect x="{X(40)}" y="{top}" width="{X(61)-X(40)}" height="{bottom-top}" fill="#f4ca82" opacity=".35"/>'
        chart += text(X(40) + 4, top + 25, "Pause", 17)
    for i, (case, label, color, dash) in enumerate(lines):
        report = simulate(read_json(here.parent / "examples" / (case + ".json")))
        segments = [f"M{x} {bottom}"]
        for count, moment in enumerate(report["completion_times_s"], 1):
            segments.append(f"H{X(moment):.2f}V{Y(count):.2f}")
        segments.append(f"H{X(120):.2f}")
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        chart += f'<path d="{" ".join(segments)}" stroke="{color}" stroke-width="3" fill="none"{dash_attr}/>'
        y = 558 + i * 29
        chart += f'<path d="M{x} {y-5}h34" stroke="{color}" stroke-width="3"{dash_attr}/>'
        chart += text(x + 43, y, f'{label}: {report["completed"]}', 20, color, 700)
svg("bottleneck-completions", 640, chart)
