"""Re-render the static pages from the JSON already in out/ (no tests, no models, record hashes untouched).
Use after a UI-only change: uv run python scripts/render_pages.py"""
import json
from pathlib import Path
from earned_trust.cli import ui_template, ROOT

out = ROOT / "out"
for rec in sorted(out.glob("*/record.json")) + sorted(out.glob("*/ai/record.json")):
    data = json.loads(rec.read_text(encoding="utf-8"))
    html = ui_template("review.html").replace("/*RECORD_JSON*/", json.dumps(data).replace("</", "<\\/"))
    (rec.parent / "review.html").write_text(html, encoding="utf-8")
    print("review ", rec.parent.relative_to(ROOT))
for b in sorted(out.glob("*/budget.json")):
    data = json.loads(b.read_text(encoding="utf-8"))
    html = ui_template("budget.html").replace("/*BUDGET_JSON*/", json.dumps(data).replace("</", "<\\/"))
    (b.parent / "budget.html").write_text(html, encoding="utf-8")
    print("budget ", b.parent.relative_to(ROOT))
idx = out / "index.json"
if idx.exists():
    data = json.loads(idx.read_text(encoding="utf-8"))
    (out / "index.html").write_text(ui_template("index.html").replace("/*INDEX_JSON*/", json.dumps(data).replace("</", "<\\/")), encoding="utf-8")
    print("index")
(out / "card.html").write_text(ui_template("card.html"), encoding="utf-8")
print("card")
