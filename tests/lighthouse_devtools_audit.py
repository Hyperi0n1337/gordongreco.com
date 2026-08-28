#!/usr/bin/env python3
"""Run the Lighthouse bundled with Chromium DevTools against a local URL.

This avoids an npm dependency while producing a standard Lighthouse JSON result.
Chromium enterprise policies must permit the audited URL; use an unmanaged Chrome
or temporarily relax a local URL blocklist in controlled test environments.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def wait_for_debug_port(port: int, process: subprocess.Popen[str], seconds: float = 12.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=0.25) as response:
                json.load(response)
            return
        except Exception:
            if process.poll() is not None:
                break
            time.sleep(0.1)
    stderr = process.stderr.read() if process.stderr else ''
    raise RuntimeError(f'Chromium debugging port did not open. {stderr[-2000:]}')


def summarize(lhr: dict) -> dict:
    categories = {
        key: round((value.get('score') or 0) * 100)
        for key, value in lhr.get('categories', {}).items()
    }
    audits = lhr.get('audits', {})
    metrics = {}
    for key in [
        'first-contentful-paint', 'largest-contentful-paint', 'speed-index',
        'total-blocking-time', 'cumulative-layout-shift', 'interactive',
        'server-response-time', 'total-byte-weight', 'network-requests',
    ]:
        audit = audits.get(key)
        if not audit:
            continue
        metrics[key] = {
            'score': audit.get('score'),
            'numericValue': audit.get('numericValue'),
            'numericUnit': audit.get('numericUnit'),
            'displayValue': audit.get('displayValue'),
        }
    failures = []
    for key, audit in audits.items():
        score = audit.get('score')
        if isinstance(score, (int, float)) and score < 0.9 and audit.get('scoreDisplayMode') not in {'notApplicable', 'informative', 'manual'}:
            failures.append({'id': key, 'score': score, 'title': audit.get('title'), 'displayValue': audit.get('displayValue')})
    failures.sort(key=lambda item: (item['score'], item['id']))
    return {
        'lighthouseVersion': lhr.get('lighthouseVersion'),
        'fetchTime': lhr.get('fetchTime'),
        'requestedUrl': lhr.get('requestedUrl'),
        'finalDisplayedUrl': lhr.get('finalDisplayedUrl'),
        'categories': categories,
        'metrics': metrics,
        'audits_below_90': failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--output', required=True)
    parser.add_argument('--chrome', default='/usr/bin/chromium')
    parser.add_argument('--port', type=int, default=9465)
    parser.add_argument('--max-wait', type=int, default=80)
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix='gg-lighthouse-')
    host = urlsplit(args.url).hostname or '127.0.0.1'
    resolver_rules = (
        'MAP fonts.googleapis.com 127.0.0.1, '
        'MAP fonts.gstatic.com 127.0.0.1, '
        'MAP www.googletagmanager.com 127.0.0.1, '
        f'EXCLUDE {host}'
    )
    command = [
        args.chrome,
        '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
        '--disable-background-networking', '--remote-allow-origins=*',
        f'--remote-debugging-port={args.port}', f'--user-data-dir={profile}',
        f'--host-resolver-rules={resolver_rules}', 'about:blank',
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        wait_for_debug_port(args.port, process)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{args.port}')
            context = browser.contexts[0]
            target = context.pages[0]
            target.goto(args.url, wait_until='domcontentloaded', timeout=15_000)
            target.wait_for_timeout(600)
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/json/list', timeout=2) as response:
                targets = json.load(response)
            target_id = next(
                item['id'] for item in targets
                if item.get('type') == 'page' and item.get('url', '').startswith(args.url.split('#')[0])
            )
            devtools_url = (
                f'http://127.0.0.1:{args.port}/devtools/inspector.html?'
                f'ws=127.0.0.1:{args.port}/devtools/page/{target_id}&panel=lighthouse'
            )
            devtools = context.new_page()
            devtools.goto(devtools_url, wait_until='domcontentloaded', timeout=20_000)
            analyze = devtools.get_by_text('Analyze page load', exact=True)
            analyze.wait_for(state='visible', timeout=20_000)
            patch_result = devtools.evaluate(
                """async () => {
                  const module = await import('./panels/lighthouse/lighthouse.js');
                  const panel = module.LighthousePanel.LighthousePanel.instance();
                  const originalBuild = panel.buildReportUI.bind(panel);
                  const originalError = panel.handleError.bind(panel);
                  panel.buildReportUI = (lhr, artifacts) => {
                    window.__GG_LIGHTHOUSE_RESULT__ = lhr;
                    return originalBuild(lhr, artifacts);
                  };
                  panel.handleError = (error) => {
                    window.__GG_LIGHTHOUSE_ERROR__ = {
                      message: String(error?.message || error),
                      stack: String(error?.stack || ''),
                    };
                    return originalError(error);
                  };
                  return {panelKeys: Object.keys(panel), patched: typeof panel.buildReportUI === 'function'};
                }"""
            )
            (output / 'devtools_patch.json').write_text(json.dumps(patch_result, indent=2), encoding='utf-8')
            analyze.click()
            deadline = time.monotonic() + args.max_wait
            result = None
            error = None
            while time.monotonic() < deadline:
                state = devtools.evaluate(
                    """() => ({
                      result: window.__GG_LIGHTHOUSE_RESULT__ || null,
                      error: window.__GG_LIGHTHOUSE_ERROR__ || null,
                    })"""
                )
                if state['result']:
                    result = state['result']
                    break
                if state['error']:
                    error = state['error']
                    break
                time.sleep(0.75)
            devtools.screenshot(path=str(output / 'lighthouse-ui.png'), full_page=True)
            if error:
                raise RuntimeError(f"Lighthouse DevTools error: {error['message']}\n{error.get('stack', '')}")
            if result is None:
                status = devtools.locator('body').inner_text()[:3000]
                (output / 'timeout-status.txt').write_text(status, encoding='utf-8')
                raise TimeoutError(f'Lighthouse did not complete within {args.max_wait}s')
            (output / 'lighthouse.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            summary = summarize(result)
            (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            lines = [
                '# Lighthouse summary', '',
                f"- Lighthouse: {summary['lighthouseVersion']}",
                f"- URL: {summary['finalDisplayedUrl']}",
                f"- Fetch time: {summary['fetchTime']}", '',
                '## Category scores', '',
            ]
            lines.extend(f"- {name}: {score}" for name, score in summary['categories'].items())
            lines += ['', '## Metrics', '']
            lines.extend(
                f"- {name}: {value.get('displayValue') or value.get('numericValue')}"
                for name, value in summary['metrics'].items()
            )
            (output / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
            print(json.dumps(summary, indent=2))
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == '__main__':
    main()
