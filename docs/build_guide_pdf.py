#!/usr/bin/env python3
"""
Builds docs/PROJECT_GUIDE.pdf from docs/PROJECT_GUIDE.md.

    .venv/bin/python docs/build_guide_pdf.py

Needs: markdown-it-py (already installed with the backend) and Google Chrome / Chromium for printing.
The architecture diagram is drawn by Mermaid, loaded from a CDN, so build it while online.
"""

import base64
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
SOURCE, TARGET = ROOT / "docs" / "PROJECT_GUIDE.md", ROOT / "docs" / "PROJECT_GUIDE.pdf"
LOGO = ROOT / "frontend" / "public" / "crosswalk-logo.png"

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: 'Inter','Helvetica Neue',Arial,sans-serif; font-size: 10.2pt; line-height: 1.5; color: #1b2430; margin: 0; }
.cover { text-align: center; padding: 60mm 0 0; page-break-after: always; }
.cover img { width: 62mm; } .cover h1 { font-size: 24pt; margin: 14mm 0 3mm; color: #193141; }
.cover p { color: #5e636b; font-size: 12pt; margin: 0; }
h1 { font-size: 20pt; color: #193141; margin: 0 0 4mm; }
h2 { font-size: 14.5pt; color: #193141; margin: 9mm 0 3mm; padding-bottom: 1.5mm; border-bottom: 1.2pt solid #139D8C; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #0f7f72; margin: 6mm 0 2mm; page-break-after: avoid; }
p { margin: 0 0 2.6mm; } ul, ol { margin: 0 0 3mm; padding-left: 5.5mm; } li { margin-bottom: 1mm; }
blockquote { margin: 0 0 4mm; padding: 2.5mm 4mm; background: #eef7f5; border-left: 2.5pt solid #139D8C; }
blockquote p { margin: 0; }
table { width: 100%; border-collapse: collapse; margin: 1mm 0 5mm; font-size: 8.9pt; }
tr { page-break-inside: avoid; } thead { display: table-header-group; }
th { background: #193141; color: #fff; text-align: left; padding: 1.8mm 2.2mm; font-weight: 600; }
td { padding: 1.7mm 2.2mm; border-bottom: 0.5pt solid #d9dee3; vertical-align: top; }
tr:nth-child(even) td { background: #f6f8f9; }
code { font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; font-size: 8.6pt; background: #eef1f3; padding: 0.2mm 1mm; border-radius: 1mm; }
pre { background: #f3f5f7; padding: 3mm 4mm; border-radius: 2mm; font-size: 8.3pt; line-height: 1.4; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
pre.mermaid { background: none; text-align: center; padding: 0; margin: 2mm 0 5mm; }
pre.mermaid svg { max-width: 100%; height: auto; }
hr { border: 0; border-top: 0.6pt solid #d9dee3; margin: 6mm 0; } a { color: #0f7f72; text-decoration: none; }
"""


def main() -> int:
    chrome = next((p for p in map(shutil.which, ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser")) if p), None)
    if not chrome:
        print("Chrome or Chromium is needed to print the PDF.", file=sys.stderr)
        return 1

    text = SOURCE.read_text(encoding="utf-8")
    diagrams: list[str] = []

    def stash(match: "re.Match[str]") -> str:  # keep Mermaid source out of the Markdown renderer
        diagrams.append(match.group(1))
        return f"\n\nMERMAIDBLOCK{len(diagrams) - 1}\n\n"

    body = MarkdownIt("commonmark").enable("table").render(re.sub(r"```mermaid\n(.*?)```", stash, text, flags=re.S))
    for index, source in enumerate(diagrams):
        body = body.replace(f"<p>MERMAIDBLOCK{index}</p>", f'<pre class="mermaid">{html.escape(source)}</pre>')

    logo = base64.b64encode(LOGO.read_bytes()).decode()
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Cross-Walk project guide</title><style>{CSS}</style></head><body>
<div class="cover"><img src="data:image/png;base64,{logo}"><h1>Project Guide</h1><p>How it works, and why it is built this way</p>
<p style="margin-top:6mm;font-size:10pt">Team Aether · DSOLVE 2026</p></div>
{body}
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: 'neutral', themeVariables: {{fontSize: '13px'}}}});</script>
</body></html>"""

    with tempfile.TemporaryDirectory() as tmp:
        source_html = Path(tmp) / "guide.html"
        source_html.write_text(page, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=20000", f"--print-to-pdf={TARGET}", source_html.as_uri()],
                       check=True, capture_output=True)
    print(f"wrote {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
