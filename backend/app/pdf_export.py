"""Optional, offline PDF export of a stored validated report; no model rewrite.

Install playwright and its Chromium browser before running this local operator
command. Rendering blocks external network requests and executes no JavaScript.
"""
import argparse
import asyncio
import html
import json
from pathlib import Path


def _escape(value):
    return html.escape(str(value), quote=True)


def report_html(report):
    if not isinstance(report, dict) or not report.get('id') or not report.get('release_id'):
        raise ValueError('A stored report with identity and source release is required')
    if not isinstance(report.get('source_index'), list) or not isinstance(report.get('assessments'), list):
        raise ValueError('A validated source index and assessment list are required')
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<title>Technical Viva report</title><style>',
             '@page{size:A4;margin:18mm}body{font:11pt/1.5 Arial,sans-serif;color:#17202a}',
             'h1{font-size:24pt}h2{font-size:16pt;margin-top:24pt;break-after:avoid}',
             'table{border-collapse:collapse;width:100%;margin:12pt 0;table-layout:fixed}',
             'th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ccd4dc;padding:7pt;overflow-wrap:anywhere}',
             'thead{display:table-header-group}.card{break-inside:avoid}blockquote{border-left:3px solid #ccd4dc;padding-left:10pt}',
             '.meta{font-size:9pt;color:#52606d;overflow-wrap:anywhere}.critical{border:2px solid #8b2525;padding:10pt}',
             '</style></head><body><h1>Technical Viva evaluation</h1>']
    for field in ('id', 'session_id', 'release_id', 'bundle_hash', 'rubric_version', 'prompt_version', 'model_config_version', 'completion', 'finish_reason', 'created_at'):
        if field in report:
            parts.append(f'<p class="meta"><strong>{_escape(field.replace("_", " "))}:</strong> {_escape(report[field])}</p>')
    if report.get('critical_error'):
        parts.append('<p class="critical"><strong>Critical Playground error</strong> remains unresolved by interview performance.</p>')
    parts.append('<h2>Interview dimensions</h2><table><thead><tr><th>Dimension</th><th>Assessment</th><th>Rationale</th></tr></thead><tbody>')
    for item in report['assessments']:
        score = 'Not assessed' if item.get('score') is None else f'{item["score"]}/4'
        parts.append(f'<tr><td>{_escape(item.get("dimension", ""))}</td><td>{_escape(score)}<br>{_escape(item.get("status", ""))}</td><td>{_escape(item.get("rationale", ""))}</td></tr>')
    parts.append('</tbody></table>')
    for field in ('strengths', 'misconceptions', 'missed_topics', 'recommendations'):
        parts.append(f'<h2>{_escape(field.replace("_", " ").title())}</h2><ul>')
        for value in report.get(field, []):
            parts.append(f'<li>{_escape(value)}</li>')
        parts.append('</ul>')
    parts.append('<h2>Question review</h2>')
    for item in report.get('questions', []):
        parts.append(f'<section class="card"><h3>{_escape(item.get("question_id", ""))}</h3><p>{_escape(item.get("feedback", ""))}</p>')
        for source in item.get('sources', []):
            parts.append(f'<blockquote>{_escape(source.get("excerpt", ""))}</blockquote><p class="meta">{_escape(source.get("document_id", ""))} · {_escape(source.get("locator", ""))}</p>')
        parts.append('</section>')
    parts.append('<h2>Playground outcome</h2><ul>')
    for item in report.get('playground_scores', []):
        parts.append(f'<li>{_escape(item.get("name", ""))}: {_escape(item.get("earned", ""))}/{_escape(item.get("available", ""))}</li>')
    parts.append('</ul><h2>Transcript</h2>')
    for item in report.get('transcript', []):
        parts.append(f'<p><strong>{_escape(item.get("speaker", ""))}</strong> <span class="meta">({_escape(item.get("delivery", ""))})</span>: {_escape(item.get("text", ""))}</p>')
    parts.append('<h2>Complete source index</h2><table><thead><tr><th>Document</th><th>Version and checksum</th><th>Usage / availability</th></tr></thead><tbody>')
    for item in report['source_index']:
        document = item.get('document', {})
        parts.append(f'<tr><td>{_escape(document.get("title", ""))}<br><span class="meta">{_escape(document.get("id", ""))}</span></td><td>{_escape(document.get("version", ""))}<br><span class="meta">{_escape(document.get("checksum", ""))}</span></td><td>{_escape(item.get("usage", ""))}<br>{_escape(document.get("availability", ""))}</td></tr>')
    parts.append(f'</tbody></table><p>{_escape(report.get("assessment_notice", "AI-assisted assessment; supervised practical assessment remains necessary."))}</p></body></html>')
    return ''.join(parts)


async def export_pdf(report, output, *, overwrite=False):
    destination = Path(output)
    if destination.suffix.lower() != '.pdf':
        raise ValueError('PDF output must have a .pdf extension')
    if destination.exists() and not overwrite:
        raise FileExistsError('Output exists; pass --overwrite explicitly')
    content = report_html(report)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError('PDF export requires playwright and playwright install chromium') from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            context = await browser.new_context(java_script_enabled=False)
            await context.route('**/*', lambda route: route.abort())
            page = await context.new_page()
            await page.set_content(content, wait_until='load')
            await page.pdf(path=str(destination), format='A4', print_background=True,
                           prefer_css_page_size=True, display_header_footer=False)
        finally:
            await browser.close()
    return destination


def main():
    parser = argparse.ArgumentParser(description='Export stored validated Viva report JSON to PDF')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        report = json.loads(args.input.read_text(encoding='utf-8'))
        result = asyncio.run(export_pdf(report, args.output, overwrite=args.overwrite))
        print(str(result))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
