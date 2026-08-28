#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Route, sync_playwright

PAGES = [
    'index.html', 'services.html', 'about.html', 'contact.html', 'client.html',
    'privacy.html', 'terms.html', 'services/business.html', 'services/tax.html',
    'services/investment.html', 'services/retirement.html', 'services/estate.html',
]
VIEWPORTS = {'mobile': (390, 844), 'tablet': (820, 1180), 'desktop': (1440, 1100)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/')
    parser.add_argument('--output', default='reports/browser')
    parser.add_argument('--screenshots', action='store_true')
    parser.add_argument('--viewport', choices=['all', *VIEWPORTS], default='all')
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    selected = VIEWPORTS if args.viewport == 'all' else {args.viewport: VIEWPORTS[args.viewport]}
    base_origin = f"{urlsplit(args.base_url).scheme}://{urlsplit(args.base_url).netloc}"
    results: dict[str, object] = {
        'base_url': args.base_url,
        'viewport_filter': args.viewport,
        'pages': [],
        'keyboard': {},
        'interaction': {},
        'no_javascript': {},
    }
    executable = os.environ.get('GG_CHROME_PATH', '/usr/bin/chromium')

    def local_only(route: Route) -> None:
        if route.request.url.startswith(base_origin):
            route.continue_()
        else:
            route.abort('blockedbyclient')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=executable,
            args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
        )
        for name, (width, height) in selected.items():
            context = browser.new_context(
                viewport={'width': width, 'height': height},
                reduced_motion='reduce' if name == 'mobile' else 'no-preference',
            )
            context.route('**/*', local_only)
            for path in PAGES:
                page = context.new_page()
                errors: list[str] = []
                page.on('pageerror', lambda error, errors=errors: errors.append(str(error)))
                page.goto(args.base_url + path, wait_until='domcontentloaded', timeout=15_000)
                page.wait_for_timeout(180)
                metrics = page.evaluate(
                    '''() => {
                      const durations = [...document.querySelectorAll('*')]
                        .flatMap((el) => getComputedStyle(el).animationDuration.split(','))
                        .map((value) => Number.parseFloat(value) || 0);
                      return {
                        title: document.title,
                        h1: document.querySelectorAll('h1').length,
                        main: Boolean(document.querySelector('main')),
                        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                        active: document.querySelector('[aria-current="page"]')?.textContent.trim() || null,
                        reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
                        maxAnimationSeconds: Math.max(0, ...durations),
                        images: [...document.images].map((image) => ({
                          src: image.getAttribute('src'),
                          naturalWidth: image.naturalWidth,
                          naturalHeight: image.naturalHeight,
                          complete: image.complete,
                        })),
                      };
                    }'''
                )
                entry = {'viewport': name, 'path': path, **metrics, 'page_errors': errors}
                results['pages'].append(entry)  # type: ignore[index]
                assert metrics['h1'] == 1 and metrics['main'] and metrics['overflow'] <= 1 and not errors, entry
                assert all(image['complete'] and image['naturalWidth'] > 0 for image in metrics['images']), entry
                if name == 'mobile':
                    assert metrics['reducedMotion'] and metrics['maxAnimationSeconds'] <= 0.001, entry
                if args.screenshots:
                    # Full-page capture does not itself trigger IntersectionObserver. Walk the page
                    # once so the evidence shows the same revealed sections a reader encounters.
                    page.evaluate('''async () => {
                      document.documentElement.style.scrollBehavior = 'auto';
                      const step = Math.max(320, Math.floor(innerHeight * 0.72));
                      for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
                        scrollTo(0, y);
                        await new Promise((resolve) => setTimeout(resolve, 45));
                      }
                      document.querySelectorAll('[data-reveal]').forEach((node) => node.classList.add('is-visible'));
                      document.documentElement.classList.remove('reveal-ready');
                      scrollTo(0, 0);
                      await new Promise((resolve) => setTimeout(resolve, 80));
                    }''')
                    slug = path.replace('/', '__').replace('.html', '') or 'home'
                    page.screenshot(path=str(out / f'{slug}--{name}.png'), full_page=True, animations='disabled')
                page.close()
            context.close()

        # Interaction tests are run once so split viewport runs remain fast and mergeable.
        if args.viewport in {'all', 'mobile'}:
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            context.route('**/*', local_only)
            page = context.new_page()
            page.goto(args.base_url + 'index.html', wait_until='domcontentloaded', timeout=15_000)
            page.locator('.nav-toggle').focus()
            focus_style = page.locator('.nav-toggle').evaluate(
                '(element) => ({outlineStyle:getComputedStyle(element).outlineStyle, outlineWidth:getComputedStyle(element).outlineWidth})'
            )
            page.keyboard.press('Enter')
            expanded = page.locator('.nav-toggle').get_attribute('aria-expanded')
            page.keyboard.press('Escape')
            closed = page.locator('.nav-toggle').get_attribute('aria-expanded')
            focus_returned = page.evaluate('document.activeElement === document.querySelector(".nav-toggle")')
            results['keyboard'] = {
                'focus_style': focus_style,
                'expanded': expanded,
                'closed': closed,
                'focus_returned': focus_returned,
            }
            assert expanded == 'true' and closed == 'false' and focus_returned
            assert focus_style['outlineStyle'] != 'none' and focus_style['outlineWidth'] != '0px'

            page.goto(args.base_url + 'services.html', wait_until='domcontentloaded', timeout=15_000)
            page.locator('#tab-owner').focus()
            page.keyboard.press('ArrowRight')
            selected_tab = page.locator('[role="tab"][aria-selected="true"]').get_attribute('id')
            owner_hidden = page.locator('#panel-owner').is_hidden()
            retirement_visible = page.locator('#panel-retirement').is_visible()
            results['interaction'] = {
                'selected_after_arrow': selected_tab,
                'owner_hidden': owner_hidden,
                'retirement_visible': retirement_visible,
            }
            assert selected_tab == 'tab-retirement' and owner_hidden and retirement_visible
            context.close()

            no_js_context = browser.new_context(viewport={'width': 390, 'height': 844}, java_script_enabled=False)
            no_js_context.route('**/*', local_only)
            no_js_page = no_js_context.new_page()
            no_js_page.goto(args.base_url + 'index.html', wait_until='domcontentloaded', timeout=15_000)
            no_js_state = no_js_page.evaluate('''() => ({
              navVisible: Boolean(document.querySelector('.nav-links')?.offsetParent),
              hiddenRevealCount: [...document.querySelectorAll('[data-reveal]')]
                .filter((node) => getComputedStyle(node).opacity === '0').length,
              mainTextLength: document.querySelector('main')?.innerText.length || 0,
            })''')
            results['no_javascript'] = no_js_state
            assert no_js_state['navVisible'] and no_js_state['hiddenRevealCount'] == 0 and no_js_state['mainTextLength'] > 500
            no_js_context.close()
        browser.close()

    result_path = out / f'browser_audit--{args.viewport}.json'
    result_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({
        'pages_checked': len(results['pages']),
        'screenshots': len(list(out.glob('*.png'))),
        'keyboard': results['keyboard'],
        'interaction': results['interaction'],
        'no_javascript': results['no_javascript'],
        'result': str(result_path),
    }, indent=2))


if __name__ == '__main__':
    main()
