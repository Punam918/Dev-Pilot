#!/usr/bin/env python3
"""Render the engineering handbook as HTML/PDF (optional docs dependencies only).

Usage: .venv/bin/python scripts/build_handbook.py --dependency-dir /tmp/devpilot-doc-tools
Requires Markdown, Playwright and a Chrome/Chromium executable. Does not load
application settings, credentials, model services, or repository environment files.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = r"""
@page { size: A4; margin: 19mm 17mm 19mm; }
* { box-sizing: border-box; }
html { color: #233044; background: white; }
body { margin: 0; font-family: Arial, Helvetica, sans-serif; font-size: 10pt; line-height: 1.52; }
h1,h2,h3 { color: #142640; line-height: 1.24; break-after: avoid-page; }
h1 { font-size: 23pt; margin: 0 0 8mm; padding-top: 3mm; border-top: 3px solid #f37940; break-before: page; }
h2 { font-size: 14pt; margin-top: 7mm; margin-bottom: 3mm; }
h3 { font-size: 11.5pt; margin-top: 5mm; }
p { margin: 0 0 3.2mm; orphans: 3; widows: 3; }
a { color: #235b8c; text-decoration: none; overflow-wrap: anywhere; }
strong { color: #162b45; }
li { margin: 1.5mm 0; }
ul,ol { padding-left: 6mm; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.1pt; overflow-wrap: anywhere; }
p code,li code,td code { background: #edf2f6; padding: 0.25mm 0.6mm; border-radius: 2px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: 4mm; background: #edf2f6; border-left: 3px solid #9eb4cc; line-height: 1.45; }
blockquote { margin: 4mm 0; padding: 3mm 5mm; background: #f0f5f9; border-left: 3px solid #f37940; }
blockquote p:last-child { margin-bottom: 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 4mm 0 6mm; table-layout: fixed; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th,td { border: 1px solid #d8e1eb; padding: 2.3mm 2.5mm; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { color: #fff; background: #223b59; }
td:first-child { font-weight: 500; }
tbody tr:nth-child(even) { background: #f5f8fb; }
table code { font-size: 7.5pt; }
img { max-width: 100%; height: auto; max-height: 225mm; object-fit: contain; display: block; margin: 5mm auto; }
.cover { break-after: page; padding-top: 16mm; }
.cover .brand { letter-spacing: 4px; font-weight: 700; font-size: 13pt; color: #f37940; }
.cover .title { margin: 12mm 0 5mm; font-size: 43pt; font-weight: 750; line-height: 1.06; color: #142640; }
.cover .subtitle { font-size: 20pt; line-height: 1.3; margin-bottom: 12mm; color: #4c6079; }
.cover .rule { height: 4px; width: 23mm; background: #f37940; margin: 9mm 0; }
.cover .intro { font-size: 12pt; max-width: 150mm; }
.cover .topics { background: #edf2f6; padding: 7mm; margin-top: 10mm; font-size: 11pt; line-height: 1.8; }
.cover .edition { margin-top: 12mm; font-size: 9pt; color: #52677e; }
.front-title { font-size: 25pt; color: #142640; margin-bottom: 5mm; }
.toc { font-size: 10pt; }
.toc ul { list-style: none; margin: 0; padding: 0; }
.toc li { margin: 0; border-bottom: 1px solid #e1e8ef; padding: 1.8mm 0; break-inside: avoid; }
.diagram { background: #f1f5fa; border: 1px solid #d4dfea; padding: 4mm; margin: 5mm 0; break-inside: avoid; }
.diagram-title { font-size: 9pt; font-weight: 700; letter-spacing: 1px; margin-bottom: 3mm; }
.flow-row { display: flex; align-items: center; gap: 2mm; margin: 2mm 0; }
.flow-row > div { flex: 1; min-width: 0; text-align: center; background: #fff; border: 1px solid #c8d5e4; padding: 3mm 1.5mm; font-size: 9pt; font-weight: 700; }
.flow-row small { font-size: 8pt; font-weight: 400; }
.diagram-note { margin-top: 3mm; font-size: 8.5pt; color: #475f7c; }
@media screen { body { max-width: 900px; margin: 40px auto; padding: 40px; box-shadow: 0 2px 20px #14264018; } h1 { margin-top: 60px; } }
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependency-dir', type=Path)
    parser.add_argument('--browser', default=shutil.which('google-chrome') or shutil.which('chromium'))
    args = parser.parse_args()
    if args.dependency_dir:
        sys.path.insert(0, str(args.dependency_dir.resolve()))
    import markdown
    from playwright.sync_api import sync_playwright

    source = ROOT / 'docs/DEVPILOT_ENGINEERING_HANDBOOK.md'
    destination = source.with_name('DevPilot_Engineering_Handbook')
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc', 'sane_lists'],
                           extension_configs={'toc': {'toc_depth': '1'}})
    content = md.convert(source.read_text())
    cover = '''<section class="cover"><div class="brand">DEVPILOT / ENGINEERING HANDBOOK</div>
<div class="title">Understand<br>the entire project.</div>
<div class="subtitle">From your first request<br>to interview-ready explanations</div>
<div class="rule"></div><p class="intro">A beginner-friendly guide to what DevPilot does,
why its components exist, how its code executes, and what the available evidence actually proves.</p>
<div class="topics">35 chapters · 45 interview questions<br>
Architecture &amp; source code · Models &amp; MCP tools<br>
Approvals &amp; testing · Docker &amp; Kubernetes<br>
CI/CD &amp; observability · Troubleshooting &amp; practice</div>
<p class="edition">Repository-based learning edition · September 2026<br>
Includes local validation results and known limitations.<br>
No project credentials are included.</p></section>'''
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DevPilot — Engineering Handbook</title><style>{CSS}</style></head><body>
{cover}<section aria-label="Contents"><div class="front-title">Your reading map</div>
<p>Read Chapters 1–6 first. Follow one real demo with Chapter 27. Use Chapters 29–31 to rehearse interview answers, and Chapter 26 to locate the implementation.</p>
<p>The contents below are clickable. The PDF also includes chapter bookmarks.</p>{md.toc}</section>
<main>{content}</main></body></html>'''
    html_path = destination.with_suffix('.html')
    pdf_path = destination.with_suffix('.pdf')
    html_path.write_text(document)
    if not args.browser:
        raise SystemExit('Chrome/Chromium not found; specify --browser /path/to/browser')
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.browser, headless=True,
                                    args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(html_path.as_uri(), wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        broken = page.locator('img').evaluate_all('(images) => images.filter(i => !i.complete || !i.naturalWidth).map(i => i.src)')
        if broken or errors:
            raise RuntimeError(f'HTML render failed: images={broken}, errors={errors}')
        page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True,
                 tagged=True, outline=True, display_header_footer=True,
                 header_template='<div style="width:100%;font-size:8px;color:#61758b;margin:0 17mm;letter-spacing:1px">DEVPILOT · ENGINEERING HANDBOOK</div>',
                 footer_template='<div style="width:100%;font-size:8px;color:#61758b;margin:0 17mm;display:flex;justify-content:space-between"><span>Architecture · implementation · evidence</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
        browser.close()
    print(f'HTML: {html_path}\nPDF: {pdf_path}\nSource words: {len(source.read_text().split()):,}')


if __name__ == '__main__':
    main()
