#!/usr/bin/env python3
"""Generate the Gordon Greco static site from a compact shared copy/design system."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://gordongreco.com"
EMAIL = "markos@gordongreco.com"
SCHEDULER = "https://cal.com/markos-terzidis-hicsb3/intro-call"
GA_ID = "G-EM93GNSLSC"  # Preserved from supplied site; verification is outside this patch.

NAV = [
    ("home", "Home", "index.html"),
    ("services", "Services", "services.html"),
    ("about", "About", "about.html"),
    ("fees", "Fees", "index.html#fees"),
    ("client", "Client access", "client.html"),
    ("contact", "Contact", "contact.html"),
]

DISCLOSURE = (
    "Gordon Greco LLC is a pre-registration planning and research practice and is not a "
    "registered investment adviser. This site is informational only and does not provide "
    "investment, tax, or legal advice or solicit an advisory relationship."
)


def rel(depth: int, path: str) -> str:
    if path.startswith(("http://", "https://", "mailto:", "#")):
        return path
    return "../" * depth + path


def canonical(path: str) -> str:
    return f"{SITE_URL}/{path}" if path else f"{SITE_URL}/"


def analytics() -> str:
    # Kept byte-for-byte in behavior from the supplied site; authority excludes analytics changes.
    return f'''  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA_ID}');
  </script>'''


def schema_json(page: str) -> str:
    if page != "home":
        return ""
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": f"{SITE_URL}/#organization",
                "name": "Gordon Greco LLC",
                "url": f"{SITE_URL}/",
                "logo": f"{SITE_URL}/assets/logo.png",
                "email": EMAIL,
                "founder": {"@type": "Person", "name": "Markos Terzidis"},
                "description": "A pre-registration planning and research practice for complex financial decisions.",
            },
            {
                "@type": "WebSite",
                "@id": f"{SITE_URL}/#website",
                "url": f"{SITE_URL}/",
                "name": "Gordon Greco",
                "publisher": {"@id": f"{SITE_URL}/#organization"},
                "inLanguage": "en-US",
            },
        ],
    }
    return '  <script type="application/ld+json">' + json.dumps(data, separators=(",", ":")) + "</script>"


def head(*, title: str, description: str, path: str, depth: int, page: str, noindex: bool = False, extra_script: str = "") -> str:
    url = canonical(path)
    full_title = title if "Gordon Greco" in title else f"{title} | Gordon Greco"
    robots = '  <meta name="robots" content="noindex, nofollow">\n' if noindex else ""
    schema = schema_json(page)
    extra = f'  <script src="{rel(depth, extra_script)}" defer></script>\n' if extra_script else ""
    return f'''<!doctype html>
<html lang="en" class="no-js">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>document.documentElement.classList.replace('no-js','js');</script>
  <title>{html.escape(full_title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
{robots}  <link rel="canonical" href="{url}">
  <link rel="icon" href="{rel(depth, 'assets/favicon.ico')}" sizes="32x32">
  <link rel="apple-touch-icon" href="{rel(depth, 'assets/apple-touch-icon.png')}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Gordon Greco LLC">
  <meta property="og:title" content="{html.escape(full_title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE_URL}/assets/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(full_title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(description, quote=True)}">
  <meta name="twitter:image" content="{SITE_URL}/assets/og-image.png">
{analytics()}
{schema}
  <link rel="stylesheet" href="{rel(depth, 'css/site.css')}">
  <script src="{rel(depth, 'js/site.js')}" defer></script>
{extra}</head>'''


def nav(*, page: str, depth: int) -> str:
    links = []
    for key, label, href in NAV:
        current = ' aria-current="page"' if key == page else ""
        links.append(f'<a href="{rel(depth, href)}"{current}>{label}</a>')
    return f'''<a class="skip-link" href="#main">Skip to main content</a>
<header class="site-header">
  <nav class="nav-shell" aria-label="Primary navigation">
    <a class="brand" href="{rel(depth, 'index.html')}" aria-label="Gordon Greco home">
      <img src="{rel(depth, 'assets/logo-mark.webp')}" srcset="{rel(depth, 'assets/logo-mark.webp')} 1x, {rel(depth, 'assets/logo-mark-2x.webp')} 2x" width="44" height="44" alt="">
      <span><strong>Gordon Greco</strong><small>Planning &amp; research</small></span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="primary-links">
      <span class="sr-only">Toggle navigation</span>
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
    </button>
    <div class="nav-links" id="primary-links">
      {''.join(links)}
      <a class="button button-small" href="{rel(depth, 'contact.html#schedule')}">Intro call</a>
    </div>
  </nav>
</header>'''


def footer(depth: int) -> str:
    return f'''<footer class="site-footer">
  <div class="footer-grid shell">
    <div class="footer-brand">
      <a class="brand brand-footer" href="{rel(depth, 'index.html')}">
        <img src="{rel(depth, 'assets/logo-mark.webp')}" width="40" height="40" loading="lazy" alt="">
        <span><strong>Gordon Greco LLC</strong><small>Decision-ready financial analysis</small></span>
      </a>
      <p>{DISCLOSURE}</p>
    </div>
    <div>
      <h2>Explore</h2>
      <a href="{rel(depth, 'services.html')}">Services</a>
      <a href="{rel(depth, 'about.html')}">Approach</a>
      <a href="{rel(depth, 'index.html#fees')}">Fees</a>
      <a href="{rel(depth, 'client.html')}">Client access</a>
    </div>
    <div>
      <h2>Start</h2>
      <a href="{rel(depth, 'contact.html#schedule')}">Schedule an intro call</a>
      <a href="mailto:{EMAIL}">{EMAIL}</a>
      <a href="{rel(depth, 'privacy.html')}">Privacy</a>
      <a href="{rel(depth, 'terms.html')}">Terms &amp; disclosures</a>
    </div>
  </div>
  <div class="footer-bottom shell">
    <span>&copy; <span data-year>2026</span> Gordon Greco LLC</span>
    <span>No public portal sign-in or document upload is enabled.</span>
  </div>
</footer>'''


def layout(*, title: str, description: str, path: str, page: str, body: str, depth: int = 0, noindex: bool = False, extra_script: str = "", body_attrs: str = "") -> str:
    return f'''{head(title=title, description=description, path=path, depth=depth, page=page, noindex=noindex, extra_script=extra_script)}
<body data-page="{page}" {body_attrs}>
{nav(page=page, depth=depth)}
<main id="main" tabindex="-1">
{body}
</main>
{footer(depth)}
</body>
</html>
'''


def icon(name: str) -> str:
    paths = {
        "investment": '<path d="M5 19V9m7 10V5m7 14v-7M3 21h18M4 13l6-5 4 3 6-7"/>',
        "tax": '<path d="M7 3h10l3 3v15H4V3h3Zm2 5h6M8 12h8M8 16h5"/>',
        "retirement": '<path d="M12 3v18M5 8h14M7 8c0 3 2 5 5 5s5-2 5-5M8 21h8"/>',
        "estate": '<path d="M3 10 12 3l9 7M5 9v12h14V9M9 21v-7h6v7"/>',
        "business": '<path d="M4 7h16v14H4V7Zm4 0V4h8v3M4 12h16M10 12v3h4v-3"/>',
        "process": '<path d="M5 6h14M5 12h10M5 18h14M3 6h.01M3 12h.01M3 18h.01"/>',
    }
    return f'<svg class="line-icon" aria-hidden="true" viewBox="0 0 24 24">{paths[name]}</svg>'


HOME = f'''
<section class="home-hero">
  <div class="shell hero-grid">
    <div class="hero-copy" data-reveal>
      <p class="eyebrow">Pre-registration planning &amp; research</p>
      <h1>Financial decisions are connected. Your analysis should be too.</h1>
      <p class="lede">Gordon Greco helps business owners, families, and US/Greece households turn complex tax, investment, retirement, estate, and business questions into a decision-ready plan.</p>
      <div class="button-row">
        <a class="button" href="contact.html#schedule">Schedule an intro call</a>
        <a class="text-link" href="services.html">See the work <span aria-hidden="true">→</span></a>
      </div>
      <ul class="fit-list" aria-label="Best fit">
        <li>Business owners</li><li>Complex households</li><li>US/Greece coordination</li>
      </ul>
      <p class="boundary-note"><strong>Current boundary:</strong> planning and research only. Gordon Greco is not a registered investment adviser.</p>
    </div>
    <div class="decision-map" aria-label="Diagram showing connected financial decisions" data-reveal>
      <svg viewBox="0 0 620 520" role="img" aria-labelledby="decision-title decision-desc">
        <title id="decision-title">One connected decision view</title>
        <desc id="decision-desc">Business, tax, portfolio, retirement, and estate questions feed one coordinated analysis.</desc>
        <g class="map-lines"><path d="M310 250 138 105M310 250 485 105M310 250 515 325M310 250 310 435M310 250 105 325"/></g>
        <g class="map-node map-center"><rect x="205" y="190" width="210" height="120" rx="24"/><text x="310" y="235">ONE DECISION</text><text x="310" y="270">VIEW</text></g>
        <g class="map-node"><rect x="48" y="55" width="180" height="92" rx="18"/><text x="138" y="108">BUSINESS</text></g>
        <g class="map-node"><rect x="395" y="55" width="180" height="92" rx="18"/><text x="485" y="108">TAX</text></g>
        <g class="map-node"><rect x="425" y="278" width="180" height="92" rx="18"/><text x="515" y="331">PORTFOLIO</text></g>
        <g class="map-node"><rect x="220" y="388" width="180" height="92" rx="18"/><text x="310" y="441">RETIREMENT</text></g>
        <g class="map-node"><rect x="15" y="278" width="180" height="92" rx="18"/><text x="105" y="331">ESTATE</text></g>
      </svg>
      <p>Change one assumption. See what else moves.</p>
    </div>
  </div>
</section>
<section class="trust-strip" aria-label="What the first conversation covers">
  <div class="shell trust-grid"><span><strong>30 minutes</strong> for the fit call</span><span><strong>Written scope</strong> before paid work</span><span><strong>No sensitive uploads</strong> on this site</span></div>
</section>
<section class="section shell" id="work">
  <div class="section-heading" data-reveal><p class="eyebrow">Start with the decision</p><h2>Five areas, one coordinated view.</h2><p>Choose the question in front of you. The analysis connects it to the decisions it can affect.</p></div>
  <div class="service-grid">
    <article class="service-card" data-reveal>{icon('business')}<p class="card-kicker">For owners</p><h3>Business advisory</h3><p>Compare entity, compensation, cash-flow, and retirement-plan choices without separating the business from the household.</p><a href="services/business.html">Explore business decisions <span aria-hidden="true">→</span></a></article>
    <article class="service-card" data-reveal>{icon('tax')}<p class="card-kicker">Across the year</p><h3>Tax strategy</h3><p>Model timing, brackets, deductions, and cross-border coordination before a decision becomes a filing-season surprise.</p><a href="services/tax.html">Explore tax decisions <span aria-hidden="true">→</span></a></article>
    <article class="service-card" data-reveal>{icon('investment')}<p class="card-kicker">Research now; management planned</p><h3>Investment analysis</h3><p>Clarify risk, tax location, concentration, and implementation choices. Regulated management is not currently offered.</p><a href="services/investment.html">Explore investment analysis <span aria-hidden="true">→</span></a></article>
    <article class="service-card" data-reveal>{icon('retirement')}<p class="card-kicker">Before and through retirement</p><h3>Retirement planning</h3><p>Test contribution, claiming, spending, and withdrawal choices across taxes and time—not as isolated rules of thumb.</p><a href="services/retirement.html">Explore retirement decisions <span aria-hidden="true">→</span></a></article>
    <article class="service-card" data-reveal>{icon('estate')}<p class="card-kicker">In coordination with counsel</p><h3>Estate &amp; trust planning</h3><p>Map beneficiaries, ownership, liquidity, and planning gaps so legal and tax professionals can act from the same facts.</p><a href="services/estate.html">Explore estate decisions <span aria-hidden="true">→</span></a></article>
  </div>
</section>
<section class="section section-ink">
  <div class="shell split" data-reveal>
    <div><p class="eyebrow">Built for owner complexity</p><h2>Your company and household share a balance sheet.</h2><p>Entity structure changes compensation. Compensation changes taxes. Taxes change retirement contributions and available liquidity. Gordon Greco frames those choices together.</p><a class="button button-light" href="services/business.html">See the business-owner view</a></div>
    <div class="evidence-card"><p class="card-kicker">A useful engagement should leave you with</p><ul class="check-list"><li>A clear decision and the assumptions behind it</li><li>Side-by-side options with tradeoffs</li><li>Inputs, sources, and as-of dates</li><li>An action sequence and open questions</li></ul><p class="muted-on-dark">No invented outcome claims. No testimonial substitute. The proof is the work product.</p></div>
  </div>
</section>
<section class="section shell" id="process">
  <div class="section-heading" data-reveal><p class="eyebrow">What happens next</p><h2>Three steps. No account transfer on the first call.</h2></div>
  <ol class="process-grid">
    <li data-reveal><span>01</span><h3>Fit call</h3><p>Bring one decision or source of friction. We clarify the question, timing, and whether Gordon Greco is an appropriate research partner.</p></li>
    <li data-reveal><span>02</span><h3>Written scope</h3><p>You receive the proposed work, inputs, exclusions, fee, and next step before any paid engagement begins.</p></li>
    <li data-reveal><span>03</span><h3>Analysis review</h3><p>We review the options, assumptions, dependencies, and action sequence. Other professionals remain in their proper roles.</p></li>
  </ol>
</section>
<section class="section section-soft" id="fees">
  <div class="shell fee-layout" data-reveal>
    <div><p class="eyebrow">Fees</p><h2>Know the commercial terms before the work starts.</h2><p>Scoped planning and research work is quoted in writing based on complexity. No fee begins from a website visit or introductory call.</p></div>
    <div class="fee-card"><p class="fee-label">Planned investment-management fee</p><p class="fee-number">1% <span>annually</span></p><p>0.25% billed quarterly, <strong>only after</strong> registration status, custody, agreements, and the operating workflow are verified.</p><hr><p><strong>Planning &amp; research:</strong> scoped fee stated before engagement.</p></div>
  </div>
</section>
<section class="section shell">
  <div class="section-heading" data-reveal><p class="eyebrow">Common questions</p><h2>Resolve the objections before the call.</h2></div>
  <div class="faq-list">
    <details data-reveal><summary>Is Gordon Greco a registered investment adviser?</summary><p>No. The firm is currently a pre-registration planning and research practice. The site does not offer regulated investment advisory services.</p></details>
    <details data-reveal><summary>Do I need to move accounts or upload documents to speak?</summary><p>No. The introductory call requires neither. Do not send account numbers, tax documents, credentials, or other sensitive records through the public site.</p></details>
    <details data-reveal><summary>Can Gordon Greco replace my CPA or attorney?</summary><p>No. The work is designed to organize decisions and coordination points. Tax filing, legal drafting, and regulated advice stay with appropriately engaged professionals.</p></details>
    <details data-reveal><summary>What should I bring to the first call?</summary><p>One decision, its timing, and the people or systems already involved. A concise description is more useful than a document dump.</p></details>
  </div>
</section>
<section class="cta-band"><div class="shell" data-reveal><div><p class="eyebrow">Start with one decision</p><h2>See whether the work fits.</h2></div><a class="button button-light" href="contact.html#schedule">Schedule an intro call</a></div></section>
'''

SERVICES = '''
<section class="page-hero"><div class="shell narrow" data-reveal><p class="eyebrow">Services</p><h1>Choose the decision, not a package.</h1><p class="lede">The same financial choice can change taxes, cash flow, portfolio risk, retirement capacity, and estate coordination. Start with your situation and see the work that connects.</p><p class="boundary-note"><strong>Current boundary:</strong> planning and research only; no regulated investment management is currently offered.</p></div></section>
<section class="section shell">
  <div class="section-heading" data-reveal><p class="eyebrow">One-click decision view</p><h2>What matters most for your situation?</h2><p>Switch views to see the first questions and likely workstreams—not a recommendation or eligibility decision.</p></div>
  <div class="decision-switcher" data-decision-switcher data-reveal>
    <div class="tab-list" role="tablist" aria-label="Choose a planning situation">
      <button role="tab" id="tab-owner" aria-controls="panel-owner" aria-selected="true" tabindex="0" data-view="owner">Business owner</button>
      <button role="tab" id="tab-retirement" aria-controls="panel-retirement" aria-selected="false" tabindex="-1" data-view="retirement">Approaching retirement</button>
      <button role="tab" id="tab-crossborder" aria-controls="panel-crossborder" aria-selected="false" tabindex="-1" data-view="crossborder">US/Greece household</button>
    </div>
    <div class="decision-panel" role="tabpanel" id="panel-owner" aria-labelledby="tab-owner" data-panel="owner">
      <div><p class="card-kicker">First questions</p><h3>Connect company cash flow to household choices.</h3><ul class="check-list"><li>How should entity and owner compensation be compared?</li><li>What cash must remain in the business?</li><li>Which retirement-plan choices change the tax picture?</li></ul></div>
      <div><p class="card-kicker">Likely workstreams</p><div class="tag-links"><a href="services/business.html">Business advisory</a><a href="services/tax.html">Tax strategy</a><a href="services/retirement.html">Retirement planning</a></div></div>
    </div>
    <div class="decision-panel" role="tabpanel" id="panel-retirement" aria-labelledby="tab-retirement" data-panel="retirement" hidden>
      <div><p class="card-kicker">First questions</p><h3>Coordinate spending, taxes, and portfolio withdrawals.</h3><ul class="check-list"><li>Which income sources should fund each stage?</li><li>How do claiming and conversion choices interact?</li><li>Which risks matter before and after retirement?</li></ul></div>
      <div><p class="card-kicker">Likely workstreams</p><div class="tag-links"><a href="services/retirement.html">Retirement planning</a><a href="services/tax.html">Tax strategy</a><a href="services/investment.html">Investment analysis</a></div></div>
    </div>
    <div class="decision-panel" role="tabpanel" id="panel-crossborder" aria-labelledby="tab-crossborder" data-panel="crossborder" hidden>
      <div><p class="card-kicker">First questions</p><h3>Build one fact pattern across two countries.</h3><ul class="check-list"><li>Where are income, assets, and obligations located?</li><li>Which questions require US or Greek specialists?</li><li>What timing or ownership facts need reconciliation?</li></ul></div>
      <div><p class="card-kicker">Likely workstreams</p><div class="tag-links"><a href="services/tax.html">Tax coordination</a><a href="services/estate.html">Estate coordination</a><a href="services/investment.html">Investment analysis</a></div></div>
    </div>
  </div>
</section>
<section class="section section-soft"><div class="shell">
  <div class="section-heading" data-reveal><p class="eyebrow">Workstreams</p><h2>Specific outputs, stated boundaries.</h2></div>
  <div class="comparison-grid">
    <article data-reveal><div class="comparison-head">''' + icon("business") + '''<h3>Business advisory</h3></div><p>Entity, compensation, benefits, cash-flow, and owner-household tradeoff analysis.</p><dl><div><dt>Useful output</dt><dd>Side-by-side option memo and action sequence</dd></div><div><dt>Fee</dt><dd>Scoped in writing</dd></div></dl><a href="services/business.html">View business scope →</a></article>
    <article data-reveal><div class="comparison-head">''' + icon("tax") + '''<h3>Tax strategy</h3></div><p>Timing, bracket, deduction, conversion, and cross-border issue mapping.</p><dl><div><dt>Useful output</dt><dd>Scenario comparison and coordination questions</dd></div><div><dt>Fee</dt><dd>Scoped in writing</dd></div></dl><a href="services/tax.html">View tax scope →</a></article>
    <article data-reveal><div class="comparison-head">''' + icon("investment") + '''<h3>Investment analysis</h3></div><p>Risk, concentration, tax location, implementation, and monitoring research.</p><dl><div><dt>Useful output</dt><dd>Decision memo and assumptions</dd></div><div><dt>Fee</dt><dd>Research scoped; management not active</dd></div></dl><a href="services/investment.html">View investment scope →</a></article>
    <article data-reveal><div class="comparison-head">''' + icon("retirement") + '''<h3>Retirement planning</h3></div><p>Contribution, claiming, spending, withdrawal, and tax-sequence analysis.</p><dl><div><dt>Useful output</dt><dd>Scenario range and decision calendar</dd></div><div><dt>Fee</dt><dd>Scoped in writing</dd></div></dl><a href="services/retirement.html">View retirement scope →</a></article>
    <article data-reveal><div class="comparison-head">''' + icon("estate") + '''<h3>Estate coordination</h3></div><p>Ownership, beneficiary, liquidity, document-gap, and professional coordination review.</p><dl><div><dt>Useful output</dt><dd>Gap map for discussion with counsel</dd></div><div><dt>Fee</dt><dd>Scoped in writing</dd></div></dl><a href="services/estate.html">View estate scope →</a></article>
  </div>
</div></section>
<section class="section shell"><div class="scope-callout" data-reveal><div><p class="eyebrow">Not sure where to start?</p><h2>Bring the decision that feels stuck.</h2><p>The fit call identifies the smallest useful scope. It is not an account-opening call and does not require sensitive documents.</p></div><a class="button" href="contact.html#schedule">Schedule an intro call</a></div></section>
'''

ABOUT = '''
<section class="page-hero"><div class="shell narrow" data-reveal><p class="eyebrow">About</p><h1>Built for decisions that cross tax, investments, and business.</h1><p class="lede">Gordon Greco is a pre-registration planning and research practice founded by Markos Terzidis. The method is quantitative, source-aware, and designed to make complex choices discussable.</p></div></section>
<section class="section shell"><div class="founder-grid" data-reveal>
  <div class="founder-mark" aria-hidden="true"><span>MT</span><svg viewBox="0 0 240 240"><circle cx="120" cy="120" r="88"/><path d="M54 144c42-8 56-64 92-64 22 0 32 24 42 50"/></svg></div>
  <div><p class="eyebrow">Founder</p><h2>Markos Terzidis</h2><p>Markos brings an engineering mindset and a US/Greece perspective to financial questions. The supplied firm context supports a focus on cross-border coordination, business-owner complexity, and decision modeling; it does not supply regulated credentials or performance history, so none are implied here.</p><p>The goal is practical: establish the facts, make assumptions visible, compare options, and leave the client and their other professionals with a usable next step.</p><a class="text-link" href="contact.html#schedule">Discuss a decision <span aria-hidden="true">→</span></a></div>
</div></section>
<section class="section section-ink"><div class="shell"><div class="section-heading" data-reveal><p class="eyebrow">The method</p><h2>Evidence over adjectives.</h2><p>Credibility should come from transparent work, not unverified credentials, testimonials, or outcome claims.</p></div><div class="principle-grid">
  <article data-reveal><span>01</span><h3>Define the decision</h3><p>Name the choice, deadline, constraints, and people involved before adding models.</p></article>
  <article data-reveal><span>02</span><h3>Trace the dependencies</h3><p>Show how tax, liquidity, portfolio, retirement, estate, and business variables connect.</p></article>
  <article data-reveal><span>03</span><h3>Make assumptions inspectable</h3><p>Identify sources, as-of dates, unavailable inputs, and the assumptions that drive the result.</p></article>
  <article data-reveal><span>04</span><h3>End with an action sequence</h3><p>Separate decisions that can be made now from items requiring a CPA, attorney, custodian, or future registration.</p></article>
</div></div></section>
<section class="section shell"><div class="section-heading" data-reveal><p class="eyebrow">Who the work fits</p><h2>Complexity is the common thread.</h2></div><div class="audience-grid">
  <article data-reveal><h3>Business owners</h3><p>When company cash flow, compensation, entity choice, benefits, and household planning are inseparable.</p></article>
  <article data-reveal><h3>Cross-border households</h3><p>When US and Greek assets, income, family, or obligations require one coordinated fact pattern.</p></article>
  <article data-reveal><h3>Pre-retirees and retirees</h3><p>When claiming, withdrawals, taxes, spending, and portfolio risk must be sequenced together.</p></article>
  <article data-reveal><h3>Families with multiple professionals</h3><p>When the CPA, attorney, broker, and household need clearer questions and consistent inputs.</p></article>
</div></section>
<section class="section section-soft"><div class="shell boundary-grid" data-reveal><div><p class="eyebrow">What is verified now</p><h2>A clear boundary is part of trust.</h2></div><div><ul class="check-list"><li>Gordon Greco LLC and founder Markos Terzidis</li><li>Pre-registration planning and research status</li><li>Published planning topics and fee intent</li><li>No public portal authentication or uploads</li></ul></div><div><p class="card-kicker">Do not infer</p><ul class="x-list"><li>RIA registration or active advisory agreements</li><li>Professional designations not supplied</li><li>Client outcomes, AUM, or performance</li><li>Verified custody or portal backend</li></ul></div></div></section>
<section class="cta-band"><div class="shell" data-reveal><div><p class="eyebrow">The first step</p><h2>Bring one complex decision.</h2></div><a class="button button-light" href="contact.html#schedule">Schedule an intro call</a></div></section>
'''

CONTACT = f'''
<section class="page-hero"><div class="shell narrow" data-reveal><p class="eyebrow">Contact</p><h1>Start with one decision.</h1><p class="lede">Use a 30-minute introductory call to clarify the question, timing, and fit. No account transfer, login, or sensitive document upload is part of this step.</p></div></section>
<section class="section shell" id="schedule"><div class="contact-grid">
  <div data-reveal><p class="eyebrow">Primary next step</p><h2>Schedule the fit call.</h2><p>Choose a time through the existing external scheduler. You will leave Gordon Greco’s site; do not include account numbers, tax documents, credentials, or other sensitive records in scheduling notes.</p><a class="button" href="{SCHEDULER}" target="_blank" rel="noopener noreferrer">Open the scheduler <span aria-hidden="true">↗</span></a><p class="microcopy">The scheduler route is preserved from the supplied site but was not account-verified in this implementation.</p>
  <div class="expect-card"><p class="card-kicker">The call covers</p><ul class="check-list"><li>The decision and why it matters now</li><li>The systems and professionals already involved</li><li>The smallest useful scope</li><li>Fee and inputs, if a next step makes sense</li></ul></div></div>
  <div class="form-card" data-reveal><p class="eyebrow">Prefer email?</p><h2>Send a concise note.</h2><form action="https://formspree.io/f/xdawkbna" method="post" aria-describedby="form-safety"><input type="hidden" name="_subject" value="Gordon Greco website inquiry"><div class="field"><label for="name">Name</label><input id="name" name="name" type="text" autocomplete="name" required></div><div class="field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" inputmode="email" required></div><div class="field"><label for="situation">What best describes the decision?</label><select id="situation" name="situation"><option value="">Choose one (optional)</option><option>Business owner decision</option><option>Tax coordination</option><option>Retirement decision</option><option>Investment analysis</option><option>Estate coordination</option><option>US/Greece coordination</option><option>Something else</option></select></div><div class="field"><label for="message">What is the decision, and when does it need attention?</label><textarea id="message" name="message" rows="6" required maxlength="2000"></textarea></div><p class="form-safety" id="form-safety"><strong>Public form:</strong> do not include Social Security numbers, account numbers, credentials, tax documents, or other sensitive information.</p><button class="button" type="submit">Send the note</button></form><p class="microcopy">The supplied Formspree endpoint is preserved. Endpoint ownership and delivery were not verified because credentials are outside scope.</p></div>
</div></section>
<section class="section section-soft"><div class="shell"><div class="section-heading" data-reveal><p class="eyebrow">After you reach out</p><h2>A simple, explicit handoff.</h2></div><ol class="process-grid compact"><li data-reveal><span>01</span><h3>Context</h3><p>Markos reviews the decision, timing, and stated constraints.</p></li><li data-reveal><span>02</span><h3>Fit</h3><p>The next conversation confirms whether planning and research is appropriate.</p></li><li data-reveal><span>03</span><h3>Scope</h3><p>Any paid work starts only after written scope, fee, inputs, and exclusions are clear.</p></li></ol></div></section>
'''

CLIENT = f'''
<section class="page-hero client-hero"><div class="shell narrow" data-reveal><p class="eyebrow">Client access</p><h1>Invited client? Use the secure link in your invitation.</h1><p class="lede">There is no public sign-in on this website. The client space remains disabled until an authenticated route, server-side authorization, and a bounded workflow are verified.</p><div class="status-pill" role="status"><span aria-hidden="true"></span> Public portal: not enabled</div></div></section>
<section class="section shell"><div class="client-route" data-reveal><div><p class="eyebrow">For invited clients</p><h2>Use the route you received directly.</h2><p>A valid invitation should identify the secure destination and the sender. Do not enter credentials into a link reached through this public page.</p></div><ol><li><span>1</span><div><h3>Open the verified invitation</h3><p>Use the secure link delivered through the confirmed client communication channel.</p></div></li><li><span>2</span><div><h3>Confirm the destination</h3><p>Check the domain and instructions before entering any information.</p></div></li><li><span>3</span><div><h3>Ask when anything looks wrong</h3><p>Missing, expired, or unexpected link? Contact Markos directly instead of trying alternate sign-in pages.</p></div></li></ol><a class="button" href="mailto:{EMAIL}?subject=Client%20access%20help">Contact Markos about access</a></div></section>
<section class="section section-soft"><div class="shell"><div class="section-heading" data-reveal><p class="eyebrow">Future pilot boundary</p><h2>The portal must earn its way into use.</h2><p>These are design intentions, not active public features.</p></div><div class="portal-grid"><article data-reveal><span>01</span><h3>Invite and verify</h3><p>Server-enforced identity and household authorization before any client data is shown.</p></article><article data-reveal><span>02</span><h3>Publish reviewed information</h3><p>Client-safe records with source, scope, as-of time, freshness, and explicit unavailable states.</p></article><article data-reveal><span>03</span><h3>Add requests deliberately</h3><p>Reviewable requests only after authorization, recovery, and advisor workflow are verified.</p></article></div><div class="boundary-box" data-reveal><h3>Not available on this public site</h3><ul class="x-list"><li>Username or password entry</li><li>Account balances or client-specific data</li><li>Document upload or messaging</li><li>Scenario calculations or instructions</li></ul></div></div></section>
<section class="cta-band"><div class="shell" data-reveal><div><p class="eyebrow">Prospective client?</p><h2>Use the public contact path instead.</h2></div><a class="button button-light" href="contact.html#schedule">Go to contact</a></div></section>
'''

PRIVACY = f'''
<section class="page-hero legal-hero"><div class="shell narrow" data-reveal><p class="eyebrow">Legal</p><h1>Privacy policy</h1><p class="lede">Effective August 27, 2026</p></div></section>
<section class="section shell"><article class="legal-copy">
<p>Gordon Greco LLC respects your privacy. This policy describes information collected through this public website. The site is not a client portal and must not be used to send sensitive financial records.</p>
<h2>1. Information collected</h2><p>The contact form collects the name, email address, planning category, and message you choose to submit. The external scheduler collects the information you provide there. Google Analytics 4 may collect site-use information such as pages viewed, referring source, device type, and approximate geography.</p><p>Do not submit Social Security numbers, account numbers, credentials, tax documents, or other sensitive financial information through this site.</p>
<h2>2. How information is used</h2><p>Inquiry information is used to respond, evaluate fit, schedule a conversation, and improve the public site. Gordon Greco does not sell or rent inquiry information for marketing.</p>
<h2>3. Service providers</h2><p>Formspree relays the public contact form, Cal.com supports scheduling, Google Analytics supports aggregate site measurement, and the hosting provider may retain ordinary server logs. Each provider applies its own terms and privacy practices.</p>
<h2>4. Retention</h2><p>The supplied policy states that inquiry emails are retained for up to 90 days unless a relationship is established or retention is requested. Analytics and scheduling data follow the applicable provider settings. These settings should be operationally verified before deployment.</p>
<h2>5. Choices and requests</h2><p>To ask what inquiry information is held, request a correction, or request deletion, email <a href="mailto:{EMAIL}">{EMAIL}</a>. Browser settings and Google’s opt-out tooling can limit analytics collection.</p>
<h2>6. Security</h2><p>The public site uses HTTPS in deployment. No public web form can make sensitive information risk-free, so use only the confirmed secure channel provided for an approved workflow.</p>
<h2>7. Children</h2><p>This site is intended for adults and is not knowingly directed to children under 13.</p>
<h2>8. Changes and contact</h2><p>Material updates will change the effective date above. Questions may be sent to <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
</article></section>
'''

TERMS = f'''
<section class="page-hero legal-hero"><div class="shell narrow" data-reveal><p class="eyebrow">Legal</p><h1>Terms &amp; disclosures</h1><p class="lede">Effective August 27, 2026</p></div></section>
<section class="section shell"><article class="legal-copy">
<h2>1. Informational site</h2><p>This website describes a pre-registration planning and research practice. Content is general information and is not personalized investment, tax, accounting, or legal advice.</p>
<h2>2. Regulatory status</h2><p>Gordon Greco LLC is not a registered investment adviser and does not represent that regulated investment advisory services are currently available. Registration, credentials, agreements, custody, and operating workflows must be independently verified before any future regulated offering is described as active.</p>
<h2>3. Fees</h2><p>The site describes a planned investment-management fee of 1% annually, billed 0.25% quarterly, contingent on verified registration and an executed agreement. Planning and research fees are scoped separately in writing. Website content alone does not create a fee obligation or engagement.</p>
<h2>4. No guarantee</h2><p>Financial decisions involve uncertainty and risk, including possible loss of principal. No outcome, return, tax result, or planning result is promised. Past performance, where discussed by third-party sources, does not guarantee future results.</p>
<h2>5. Professional coordination</h2><p>Gordon Greco does not replace a CPA, attorney, broker, custodian, or other regulated professional. Users remain responsible for engaging appropriately qualified professionals and verifying decisions before implementation.</p>
<h2>6. Third-party services and links</h2><p>Links to Formspree, Cal.com, Google, hosting providers, or other external services are provided for convenience. Gordon Greco does not control their availability, security, or content.</p>
<h2>7. Intellectual property</h2><p>Unless otherwise stated, site copy, graphics, and design are owned by Gordon Greco LLC. Limited personal use is permitted; republication or commercial reuse requires permission.</p>
<h2>8. Availability and liability</h2><p>The site is provided as available and may contain errors or interruptions. To the maximum extent permitted by applicable law, Gordon Greco LLC is not liable for decisions made solely from public website content.</p>
<h2>9. Jurisdiction</h2><p>Services, if any, are available only where lawful. The supplied baseline identifies New Jersey law; deployment should confirm the governing-law language against the firm’s actual operating and registration status.</p>
<h2>10. Privacy and contact</h2><p>See the <a href="privacy.html">privacy policy</a>. Questions may be sent to <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
</article></section>
'''


def service_body(*, eyebrow: str, title: str, lead: str, best_for: Iterable[str], questions: Iterable[str], outputs: Iterable[str], boundaries: Iterable[str], fee: str, related: Iterable[tuple[str, str]]) -> str:
    best = ''.join(f'<li>{html.escape(x)}</li>' for x in best_for)
    qs = ''.join(f'<li>{html.escape(x)}</li>' for x in questions)
    outs = ''.join(f'<li>{html.escape(x)}</li>' for x in outputs)
    bounds = ''.join(f'<li>{html.escape(x)}</li>' for x in boundaries)
    related_links = ''.join(f'<a href="{href}">{html.escape(label)} <span aria-hidden="true">→</span></a>' for label, href in related)
    return f'''
<section class="page-hero service-hero"><div class="shell narrow" data-reveal><p class="eyebrow">{eyebrow}</p><h1>{title}</h1><p class="lede">{lead}</p><div class="button-row"><a class="button" href="../contact.html#schedule">Discuss this decision</a><a class="text-link" href="../services.html">Compare all services →</a></div></div></section>
<section class="section shell"><div class="service-overview"><div data-reveal><p class="eyebrow">Best fit when</p><ul class="signal-list">{best}</ul></div><div data-reveal><p class="eyebrow">Questions the work can clarify</p><ol class="question-list">{qs}</ol></div></div></section>
<section class="section section-soft"><div class="shell deliverable-grid"><div data-reveal><p class="eyebrow">Useful output</p><h2>A decision record you can use.</h2><ul class="check-list">{outs}</ul></div><div class="sample-output" data-reveal><div class="sample-head"><span>Decision memo</span><span>Illustrative structure</span></div><div class="sample-row"><strong>Decision</strong><span>What must be decided, by when</span></div><div class="sample-row"><strong>Options</strong><span>Side-by-side tradeoffs</span></div><div class="sample-row"><strong>Assumptions</strong><span>Sources, as-of dates, unknowns</span></div><div class="sample-row"><strong>Next actions</strong><span>Owner, sequence, dependencies</span></div></div></div></section>
<section class="section section-ink"><div class="shell boundary-grid"><div data-reveal><p class="eyebrow">Scope boundary</p><h2>Analysis is not implementation authority.</h2><p>Other professionals stay in their proper roles. The scope states what Gordon Greco will and will not do before work begins.</p></div><div data-reveal><ul class="x-list">{bounds}</ul></div><div class="fee-mini" data-reveal><p class="card-kicker">Fee</p><p>{fee}</p><a class="button button-light" href="../contact.html#schedule">Start with a fit call</a></div></div></section>
<section class="section shell"><div class="related" data-reveal><div><p class="eyebrow">Connected work</p><h2>This decision rarely stands alone.</h2></div><div class="related-links">{related_links}</div></div></section>
'''

SERVICES_DETAIL = {
    "business": dict(
        title="Business Advisory | Gordon Greco", description="Decision-ready analysis for business owners: entity, compensation, cash flow, retirement plan, and household tradeoffs.", eyebrow="Business advisory", h1="Run the business and household from the same facts.", lead="Compare entity, owner compensation, benefits, liquidity, and retirement-plan choices without treating the company as separate from personal planning.",
        best_for=["Owner compensation or entity choice is changing", "Business cash and household liquidity compete", "Benefits or retirement-plan design needs comparison", "A sale, transition, or major investment is approaching"],
        questions=["How do entity and compensation options compare after payroll, tax, and administrative costs?", "How much cash should remain in the business versus move to household goals?", "Which retirement-plan structures fit the business facts and owner priorities?", "What decision sequence reduces avoidable rework across professionals?"],
        outputs=["Entity and compensation option table", "90-day cash and decision calendar", "Owner/household dependency map", "Questions for payroll, CPA, attorney, or benefits provider"],
        boundaries=["No entity formation or legal drafting", "No payroll, bookkeeping, or tax return filing represented", "No guarantee of tax savings", "No account movement or transaction authority"],
        fee="Scoped in writing based on the decision set and complexity.", related=[("Tax strategy", "tax.html"), ("Retirement planning", "retirement.html"), ("Estate coordination", "estate.html")]),
    "tax": dict(
        title="Tax Strategy | Gordon Greco", description="Year-round tax scenario analysis and professional coordination for business owners, families, and US/Greece households.", eyebrow="Tax strategy", h1="Model tax choices before the deadline makes them for you.", lead="Organize timing, brackets, deductions, conversions, and cross-border questions into scenarios that can be reviewed with the appropriate tax professional.",
        best_for=["A business or compensation decision changes taxable income", "A conversion, sale, or large gain is being considered", "US and Greek facts need one coordinated issue list", "Retirement withdrawals or benefits create tax timing choices"],
        questions=["Which assumptions change the estimated federal, state, or cross-border result?", "What timing options should be compared before year-end?", "Where do specialist interpretations or filings remain unresolved?", "How do tax choices affect liquidity, portfolio, and retirement decisions?"],
        outputs=["Scenario table with visible assumptions", "Year-round decision calendar", "Cross-border fact and question map", "CPA-ready coordination memo"],
        boundaries=["No tax return preparation or filing represented", "No legal opinion on treaty or entity matters", "No guarantee of a tax result", "Estimates require professional verification before action"],
        fee="Scoped in writing based on jurisdictions, scenarios, and coordination needs.", related=[("Business advisory", "business.html"), ("Retirement planning", "retirement.html"), ("Estate coordination", "estate.html")]),
    "investment": dict(
        title="Investment Analysis | Gordon Greco", description="Tax-aware investment research covering risk, concentration, asset location, implementation, and monitoring decisions.", eyebrow="Investment analysis", h1="Make portfolio choices in the context of taxes and cash needs.", lead="Research risk, concentration, account location, implementation, and monitoring choices without implying that regulated portfolio management is currently active.",
        best_for=["A portfolio is concentrated or difficult to explain", "Tax location and withdrawal needs affect allocation", "A proposed change needs side-by-side analysis", "The household needs a clearer monitoring framework"],
        questions=["Which risks and concentrations actually drive the portfolio?", "How do taxes and account types change implementation choices?", "What assumptions support each option?", "What should be monitored, and what would trigger review?"],
        outputs=["Portfolio decision memo", "Risk and concentration summary", "Tax-location and implementation questions", "Monitoring measures and review triggers"],
        boundaries=["Gordon Greco is not currently a registered investment adviser", "No trading, custody, discretion, or account access", "No performance or return promise", "Any future management service requires verified registration and agreement"],
        fee="Research is scoped in writing. A planned 1% annual management fee is not active before verified registration and engagement.", related=[("Tax strategy", "tax.html"), ("Retirement planning", "retirement.html"), ("Business advisory", "business.html")]),
    "retirement": dict(
        title="Retirement Planning | Gordon Greco", description="Retirement scenario analysis connecting contributions, Social Security, spending, withdrawals, taxes, and portfolio risk.", eyebrow="Retirement planning", h1="Sequence income, taxes, and risk across retirement.", lead="Compare contribution, claiming, spending, and withdrawal choices across time while making uncertainty and assumptions visible.",
        best_for=["Retirement is within sight or already underway", "Social Security and withdrawal timing interact", "Roth conversion or contribution choices need context", "Spending, inheritance, or care assumptions are changing"],
        questions=["Which income sources fund each stage, and with what tax effect?", "How do claiming and conversion options compare under stated assumptions?", "Which scenarios create the most pressure on liquidity or portfolio risk?", "What decisions have deadlines, and which can wait?"],
        outputs=["Retirement scenario range", "Income and withdrawal sequence", "Decision calendar", "Assumption and sensitivity register"],
        boundaries=["No guarantee that assets will last", "Social Security and tax estimates require source verification", "No insurance or securities sales", "No account implementation authority"],
        fee="Scoped in writing based on scenarios, accounts, and coordination needs.", related=[("Tax strategy", "tax.html"), ("Investment analysis", "investment.html"), ("Estate coordination", "estate.html")]),
    "estate": dict(
        title="Estate & Trust Planning | Gordon Greco", description="Estate and trust coordination research covering ownership, beneficiaries, liquidity, planning gaps, and cross-border questions.", eyebrow="Estate & trust coordination", h1="Give your attorney a clearer financial fact pattern.", lead="Map ownership, beneficiaries, liquidity, documents, and cross-border coordination points so legal and tax professionals can address the right questions.",
        best_for=["Beneficiaries and account ownership may not align", "A trust or estate plan needs financial coordination", "Business or cross-border assets complicate the fact pattern", "Liquidity, care, or special-needs questions affect planning"],
        questions=["Where are ownership, beneficiary, or document gaps visible?", "What liquidity or tax questions should be raised with counsel?", "Which people and professionals need the same facts?", "What changes require legal drafting rather than financial research?"],
        outputs=["Estate coordination map", "Beneficiary and ownership review", "Document and decision gap list", "Attorney/CPA discussion memo"],
        boundaries=["No legal advice or document drafting", "No trust creation or amendment", "No guarantee of tax or benefit treatment", "Legal conclusions stay with engaged counsel"],
        fee="Scoped in writing based on entities, documents, jurisdictions, and coordination needs.", related=[("Tax strategy", "tax.html"), ("Business advisory", "business.html"), ("Retirement planning", "retirement.html")]),
}

PAGES = {
    "index.html": dict(title="Gordon Greco — Decision-Ready Financial Planning Research", description="Planning and research for business owners, families, and US/Greece households facing connected tax, investment, retirement, estate, and business decisions.", path="", page="home", body=HOME),
    "services.html": dict(title="Services | Gordon Greco", description="Compare Gordon Greco planning and research workstreams for business, tax, investment, retirement, and estate decisions.", path="services.html", page="services", body=SERVICES, extra_script="js/decision-view.js"),
    "about.html": dict(title="About | Gordon Greco", description="Meet Markos Terzidis and the evidence-first planning and research method behind Gordon Greco.", path="about.html", page="about", body=ABOUT),
    "contact.html": dict(title="Contact | Gordon Greco", description="Schedule a 30-minute introductory call or send a concise, non-sensitive note about the financial decision in front of you.", path="contact.html", page="contact", body=CONTACT),
    "client.html": dict(title="Client Access | Gordon Greco", description="Orientation for invited Gordon Greco clients. No public portal sign-in or upload is enabled.", path="client.html", page="client", body=CLIENT, noindex=True, body_attrs='data-portal-state="not-enabled"'),
    "privacy.html": dict(title="Privacy Policy | Gordon Greco", description="How Gordon Greco handles information submitted through its public website and external contact services.", path="privacy.html", page="legal", body=PRIVACY),
    "terms.html": dict(title="Terms & Disclosures | Gordon Greco", description="Terms, pre-registration status, fee context, and public-site disclosures for Gordon Greco LLC.", path="terms.html", page="legal", body=TERMS),
}


def generate() -> None:
    for path, kwargs in PAGES.items():
        (ROOT / path).write_text(layout(**kwargs), encoding="utf-8")
    service_dir = ROOT / "services"
    service_dir.mkdir(exist_ok=True)
    for slug, data in SERVICES_DETAIL.items():
        data = dict(data)
        title = data.pop("title")
        description = data.pop("description")
        h1 = data.pop("h1")
        body = service_body(title=h1, **data)
        (service_dir / f"{slug}.html").write_text(layout(title=title, description=description, path=f"services/{slug}.html", page="services", body=body, depth=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if generated output differs from files on disk")
    args = parser.parse_args()
    if not args.check:
        generate()
        return
    original = {p: (ROOT / p).read_text(encoding="utf-8") for p in PAGES}
    original.update({f"services/{slug}.html": (ROOT / "services" / f"{slug}.html").read_text(encoding="utf-8") for slug in SERVICES_DETAIL})
    generate()
    changed = [p for p, value in original.items() if (ROOT / p).read_text(encoding="utf-8") != value]
    if changed:
        raise SystemExit("Generated files were stale: " + ", ".join(changed))


if __name__ == "__main__":
    main()
