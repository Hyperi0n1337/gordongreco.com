# Gordon Greco website design and copy system

## Positioning

**Audience:** business owners, complex families, pre-retirees/retirees, and US/Greece households.

**Job:** turn connected financial questions into a decision-ready plan with visible assumptions, tradeoffs, boundaries, and next actions.

**Current legal boundary:** Gordon Greco LLC is a pre-registration planning and research practice. Do not describe it as a registered investment adviser, active fiduciary advisory firm, tax preparer, custodian, portfolio manager, or portal operator until those claims are independently verified.

## Message order

1. Who the page is for and what decision it clarifies.
2. The useful output—not a vague capability claim.
3. What happens next, including fee where relevant.
4. Scope boundaries and the role of other professionals.
5. One primary action: `Schedule an intro call`.

Use specific verbs: compare, map, model, coordinate, sequence, review. Avoid superlatives, unverified scale, outcome promises, “institutional-grade,” and generic “comprehensive” claims.

## Tokens

- Ink `#111b2d`; navy `#17365f`; dark navy `#0e2748`.
- Gold `#b08a54`; pale gold `#d7bd93`.
- Paper `#fbfaf7`; soft blue-gray `#f2f5f8`; rule `#dce2e9`.
- Body: system sans stack. Display: resilient system serif stack. No blocking web fonts.
- Radius: 18px cards, full-pill CTAs. Focus: 3px `#f2b84b` with 3px offset.
- Maximum content width: 1180px; reading width: 800–920px.

## Components

- Sticky header with one emphasized CTA and accessible mobile toggle.
- Page hero: eyebrow, one concrete H1, short lead, optional boundary note.
- Service card: audience cue, decision, concise explanation, specific deep link.
- Decision memo sample: decision, options, assumptions, next actions.
- Boundary block: explicit exclusions; never hide them in legal fine print.
- CTA band: one action only.

## Motion

- Reveal once on entry; no perpetual decorative animation.
- Hero relationship lines draw once on the home page.
- Hover/focus feedback moves no more than 4px.
- `prefers-reduced-motion: reduce` disables smooth scrolling, transforms, reveals, and animation.
- Content remains visible when JavaScript is absent.

## Performance rules

- One local CSS file and one shared deferred JS file; a second tiny JS file only on the services comparison.
- System fonts; no remote font requests.
- Inline SVG for explanatory diagrams; supplied brand mark is cropped and compressed to exact display sizes.
- Width and height on every image.
- No autoplay media, canvas background, scheduling embed, or decorative 3D.
- Analytics implementation is unchanged in this patch because analytics changes are outside authority.
