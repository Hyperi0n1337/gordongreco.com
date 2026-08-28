# Accessibility and keyboard audit

## Implemented

- A visible-on-focus skip link targets a keyboard-focusable `<main>` landmark.
- One H1 per page; semantic header, nav, main, section/article, form, and footer structure.
- Mobile navigation exposes `aria-expanded`/`aria-controls`, closes with Escape or outside click, and returns focus after Escape.
- Service situation selector uses the ARIA tabs pattern with Left/Right/Up/Down, Home, and End keyboard support.
- Every form control has an explicit label, sensible autocomplete/input mode, native required validation, and a safety description.
- Every image has explicit dimensions and alt text; decorative brand marks use empty alt text.
- Minimum 48px primary controls; no hover-only content; underlined or strongly differentiated text links.
- High-visibility focus ring and a reduced-motion mode that disables smooth scrolling, reveal transforms, and animation.
- Client-access page exposes no form, password, file upload, local storage, account data, or client-specific state.

## Automated evidence

- `tests/test_site_static.py` checks page count, landmarks, H1s, internal links, image dimensions/alts, form labels, safe external links, prohibited unverified claims, portal boundary, and payload regressions.
- `tests/browser_audit.py` checks all 12 pages at 390px, 820px, and 1440px; horizontal overflow; image loading; JS errors; focus outline; mobile navigation keyboard behavior; reduced motion; and ARIA tab keyboard behavior.
- Lighthouse accessibility results are stored under `reports/lighthouse/` when run by the supplied verification command.

## Manual review notes

- Reading order follows visual order at all breakpoints.
- Legal and scope limitations are presented in body text rather than color-only or fine-print treatment.
- The interactive services view is supplemental; all five service detail links remain available without JavaScript.
- Formspree and Cal.com accessibility after navigation are outside this static-site patch and should be verified in their configured accounts.
