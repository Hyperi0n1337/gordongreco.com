# Gordon Greco LLC — Final Polish Agent Prompt

**Context:** Gordon Greco LLC is a fee-only fiduciary wealth management firm operated by Markos
Terzidis. The business has two codebases:

1. **Website** — `C:/github/Markos_Analytics_Suite/mas/web/` — Static HTML/CSS/JS marketing site
2. **Advisory Suite** — `C:/github/Markos_Analytics_Suite/mas/advisory/` — Python PDF generators
   producing every client-facing deliverable (advisory reports, quarterly statements, IPS, invoices,
   education decks, presentation slides, tax analysis reports)

This is a wealth management firm. Every document and every page is a selling tool. Clients judge the
firm's competence by the quality of its materials. Nothing can be sloppy, inconsistent, or
unprofessional. Treat this with the standard of a Goldman Sachs or PWL Capital deliverable.

---

## SECTION 1 — PDF Document Suite (Advisory Suite)

### 1.1 Shared Theme (`pdf_theme.py`)

The single source of truth for all visual styling is:
`mas/advisory/brand/tokens.json`, with generated PDF theme outputs under
`mas/advisory/brand/_generated/` and `mas/advisory/style/`.

**Brand palette (MUST be consistent across ALL PDFs):**
- Primary/Dark: `#141414` (near-black — covers, table headers)
- Gold accent: `#c8a97e` (section rules, highlights, callouts)
- Gold light: `#dfc5a4` (accent rows, lighter touches)
- Body text: `#1a1a1a`
- Muted text: `#555555`
- Light text: `#888888` (captions, footers)
- Off-white bg: `#fafaf8` (alternating table rows)
- Border: `#e8e6e1`
- Green: `#4a9e6f` (positive indicators)
- Red: `#9b2335` (negative indicators)
- Amber: `#b7791f` (warning indicators)

**Font:** Inter (Regular, Medium, SemiBold, Bold) — TTF files in `inputs/assets/fonts/`.
Helvetica fallback if Inter not registered.

**Page size:** US Letter (8.5" × 11")

**The three PWL-inspired shared helpers** (already in `pdf_theme.py` — use them everywhere):
- `theme.fig_caption(n, title, source="")` → Paragraph — place after every chart/pie/drawing
- `theme.exec_summary(text)` → list of flowables — use as page 2 of every advisory-class report
- `theme.pwl_tbl(data, widths, caption="", fig_n=None)` → list — use for multi-column
  comparison tables (no dark header, gold bottom rule only, barely-there alternating rows)

### 1.2 Document Hierarchy and Purpose

| Generator | When to use | Key quality bar |
|---|---|---|
| `advisory_report_generator.py` | Before first meeting, annual review | Full analysis, exec summary page 2, PWL tables for comparisons, fig captions on all charts |
| `presentation_deck.py` | During live meetings / screen share | One idea per slide, big numbers, no paragraphs |
| `client_education_deck.py` | Client onboarding / education sessions | Concept-first, data-backed, 20 slides max |
| `client_report.py` | Quarterly — sent automatically | Performance-first, clean charts, colored P&L |
| `ips_generator.py` | Investment Policy Statement | Legal-quality, precise, no frills |
| `invoice_generator.py` | Monthly/quarterly billing | Professional, unambiguous, easy to pay |
| `tax_analysis_report.py` | Tax strategy analysis | Dense, precise, no approximations |

### 1.3 Consistency Audit — What to Check in EVERY Generator

Go through each generator file and verify ALL of the following. Fix anything that deviates.

**Cover page checklist (applies to ALL generators):**
- [ ] Dark full-bleed background (#141414) via `theme.make_dark_cover_callback()` or equivalent
- [ ] Logo centered, no text on same line as logo
- [ ] "Gordon Greco LLC" firm name in white, Inter-Bold or Inter-SemiBold
- [ ] "Global Tax & Wealth Advisors" subtitle in muted/gray
- [ ] Gold divider line (HRFlowable, ACCENT color, 2pt) between logo block and client info
- [ ] Client name in gold (#c8a97e), prominent
- [ ] Report title/type label below client name in white or light gray
- [ ] "Prepared by Markos Terzidis" or equivalent attribution
- [ ] Date of preparation
- [ ] Disclaimer in small font (GG_CoverDisclaimer style) at bottom of cover
- [ ] PageBreak after cover — NOT used as a background pattern on subsequent pages

**Body pages checklist:**
- [ ] Footer on every page: "Gordon Greco LLC — [Report Type] | Confidential" (left) + page number (right)
- [ ] Section headers: `_section()` / `theme.section_header()` — gold eyebrow label + large title + gold rule
- [ ] All tables: either `_tbl()` (dark header for snapshot data) or `theme.pwl_tbl()` (minimal for comparisons)
- [ ] All charts and pie diagrams followed by `theme.fig_caption(n, title, source)` immediately below
- [ ] Disclaimer block on last page (client-specific, not generic)
- [ ] No orphaned section headers at bottom of page (use `KeepWithNext` or manual `PageBreak`)
- [ ] Consistent 0.85" left/right margins for reports, 0.75" for decks (match across generators)

**Specific generators — known gaps to fix:**

`client_report.py` (quarterly statements):
- Verify pie chart figures have `theme.fig_caption()` after each
- Verify performance line charts have Figure N captions
- Margins: currently 1.0" — acceptable but verify it's intentional (wider = more upscale for QR)
- Verify colored P&L cells use `theme.colored_pct()` and `theme.colored_dollar()`, not inline HTML

`ips_generator.py`:
- Uses `theme.render_letterhead()` — verify this produces a cover consistent with other docs
- If not using dark cover, it should at least have the letterhead + gold rule header
- Verify signature block at end is clean and professional (blank lines for dates, names, titles)

`invoice_generator.py`:
- Total due box: must be prominent — large font, gold border, right-aligned dollar amount
- Payment instructions must be in a shaded box (BG_OFF background), not inline paragraph
- "Thank you for your business" footer must be present
- Verify bank/wire transfer details are either present or have a clear placeholder

`tax_analysis_report.py`:
- Canvas-drawn cover: verify it achieves the same visual result as the dark cover in other docs
- Compact body text (8.5–9pt) is intentional for density — do not change
- All data tables: use `theme.pwl_tbl()` for multi-column comparisons, `_tbl()` for summaries
- Every chart (bar, line, pie) must have Figure N caption

`client_education_deck.py`:
- Verify `_callout()` boxes use gold accent border, not a different color
- Two-column layouts (`_two_col()`) must have consistent gutter spacing
- Concept slides: one concept per slide with a supporting data point — not more

### 1.4 New Document — Weekly Intelligence Digest (Planned)

When building the weekly digest PDF:
- Use the same dark cover, same Inter font, same theme module
- Format: research-paper style (closer to PWL Capital academic style — dense prose, numbered sections)
- Body text: 10.5pt, 16pt leading (slightly larger than current reports)
- Tables: exclusively `theme.pwl_tbl()` — no dark headers (digest = analytical, not snapshot)
- All charts: Figure N captions with data source cited
- Footer: "Gordon Greco LLC — Weekly Intelligence Digest | Week of [DATE]"
- Last page: disclosure + sources cited block

---

## SECTION 2 — Website (`C:/github/Markos_Analytics_Suite/mas/web/`)

### 2.1 Current State

The site is generated as static HTML/CSS/JS from `scripts/generate_site.py`, using
`css/site.css`, `js/site.js`, and the page-specific `js/decision-view.js`. `build.sh`
validates the source and publishes only the public `dist/` tree. It has 12 public routes.

**Deployment:** Configured for Netlify from `Markos_Analytics_Suite` with base
directory `mas/web`, build command `bash build.sh`, and publish directory `dist`.
Domain: `gordongreco.com`. CNAME file is set. Canonical tags are on all pages.

### 2.2 Fixes Still Required

**CRITICAL — Legal pages (verify current files):**

1. **`privacy.html`** — Privacy Policy. Verify it covers:
   - What data is collected (name, email via contact form)
   - How it's used (only for responding to inquiries)
   - Third-party processors: Formspree (form handling), Cal.com (scheduling), Google Analytics (GA4)
   - Data retention: 90 days for inquiries, none stored beyond that
   - User rights: contact arhra1337@gmail.com to request deletion
   - No selling of data
   - Match the site's visual style exactly (dark nav, footer, same CSS classes)

2. **`terms.html`** — Terms of Service / Disclosures page. Verify it covers:
   - Investment advisory disclosures (no guarantee of returns, fiduciary standard)
   - Website is for informational purposes only — not personalized advice
   - Regulatory status: registered or exempt RIA (placeholder — Markos fills)
   - Limitation of liability
   - Governing law: State of New Jersey (or wherever registered)
   - Match the site's visual style exactly

3. **Footer links to both pages** — verify every HTML page includes them.
   In every HTML file's footer, after the existing disclaimer block, use:
   ```html
   <a href="/privacy.html" class="text-gray-400 hover:text-gold-400 text-sm">Privacy Policy</a>
   <span class="text-gray-600">·</span>
   <a href="/terms.html" class="text-gray-400 hover:text-gold-400 text-sm">Terms & Disclosures</a>
   ```

**HIGH — Form and integration verification:**

4. **Verify Formspree endpoint `f/xdawkbna` is active.** The contact form at `contact.html` posts to
   this. Log into formspree.io and confirm the endpoint exists, is active, and email delivery works.
   If the endpoint is dead, create a new one and update `contact.html` line ~175.

5. **Verify Cal.com scheduling link.** The embed at `contact.html` uses
   `markos-terzidis-hicsb3/intro-call`. Log into cal.com and confirm this event type is active,
   visible, and properly configured (duration, buffer time, availability).

6. **Verify GA4 property.** Tracking ID `G-EM93GNSLSC` appears on all pages. Confirm this is the
   correct GA4 measurement ID in the Google Analytics dashboard. If not, update all 9 HTML files.

**MEDIUM — Content polish:**

7. **`about.html`** — Verify Markos's credentials, background, and story are complete and accurate.
   No placeholder or approximate content. The "about" page is the most-read page for prospects.

8. **`services/` sub-pages** — Each service page should end with a clear CTA section:
   "Schedule a free consultation" button linking to `contact.html`. Verify all 5 sub-pages have this.

9. **`index.html`** — Verify the hero section headline is the strongest possible hook.
   The current text should speak to the specific client type (HNW individual, business owner, retiree).

10. **`og-image.png`** — Referenced in all pages as `assets/og-image.png`. Verify this file exists
    and is a proper 1200×630px image. If missing, it will break all social sharing previews.

11. **`favicon.ico` and `apple-touch-icon.png`** — Verify both exist in `assets/`. If missing,
    every browser tab will show a broken favicon — deeply unprofessional for a financial firm.

### 2.3 Hosting — Recommended Approach

**Netlify (recommended):**
1. Connect the `Hyperi0n1337/Markos_Analytics_Suite` GitHub repo to Netlify
2. Base directory: `mas/web`
3. Build command: `bash build.sh`
4. Publish directory: `dist`
5. Set custom domain: `gordongreco.com` in Netlify dashboard
6. Netlify auto-provisions SSL via Let's Encrypt
7. The `netlify.toml` in the repo handles: HTTP→HTTPS redirect, www→apex redirect,
   cache headers for CSS/JS/assets

**Alternative — GitHub Pages:**
1. CNAME file is already set to `gordongreco.com`
2. Enable Pages in GitHub repo Settings → Pages → Source: Deploy from branch `main`, root `/`
3. Add custom domain in GitHub Pages settings → it will verify CNAME automatically
4. SSL auto-provisioned

**DNS setup (either option):**
- Add an `A` record pointing `gordongreco.com` to Netlify or GitHub Pages IPs
- Add a `CNAME` record for `www` pointing to `gordongreco.com`
- Propagation: 24-48 hours

### 2.4 Visual Consistency with PDF Brand

The website and PDF documents should feel like they come from the same firm:
- Dark `#141414` used in nav bar and hero sections ✓
- Gold `#c8a97e` used for CTA buttons and accent elements ✓
- Inter font loaded from Google Fonts ✓
- Verify: the exact gold hex matches between CSS (`css/style.css`) and PDF theme (`pdf_theme.py`)
  - In `style.css`: search for the gold color definition and confirm it's `#c8a97e`
  - In `pdf_theme.py`: `ACCENT = colors.HexColor("#c8a97e")`

---

## SECTION 3 — Agent Instructions

You are acting as a senior engineer and design consultant for Gordon Greco LLC, a wealth management
firm. Your job is to bring every document and every web page to Goldman Sachs-level quality.

**Do NOT:**
- Add lorem ipsum or placeholder content — use accurate real content or ask for it explicitly
- Change the brand colors, fonts, or cover structure — they are intentional
- Create new design systems — extend the existing `pdf_theme.py` module
- Modify any database, financial data, or computation logic — only visual/layout work
- Skip the verification step — every PDF must be rendered and page-counted after changes

**DO:**
- Fix every inconsistency listed above
- Verify each PDF compiles and renders with the relevant `mas/advisory/` entry point.
- Run `venv/Scripts/python.exe -m py_compile <file>` before running edited Python files.
- After every PDF fix, confirm page count and that no ReportLab warnings appear
- For website changes, verify all internal links still resolve and no HTML is broken
- Commit all changes with descriptive messages per file group, not one giant commit

**Execution order (do in this sequence):**
1. PDF suite consistency fixes (start with `client_report.py` — highest client visibility)
2. Verify `privacy.html` and `terms.html` for the website
3. Verify footer links to privacy/terms on all HTML pages
4. Verify all assets exist (`og-image.png`, `favicon.ico`, `apple-touch-icon.png`)
5. Verify form/cal integrations are live (manual check — report status, don't try to automate)
6. Final commit and push both repos

**Quality bar:** When you're done, a prospect who receives a PDF from Gordon Greco LLC should
feel they are dealing with a top-tier professional advisory firm — not a startup.
Every number should be right-aligned. Every header should have its gold rule. Every chart should
have its Figure caption. Every page should have its footer. No exceptions.
