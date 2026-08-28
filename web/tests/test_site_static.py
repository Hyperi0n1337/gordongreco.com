from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted([*ROOT.glob('*.html'), *(ROOT / 'services').glob('*.html')])
PUBLIC_PAGES = [p for p in PAGES if p.name != 'client.html']
PROHIBITED = [
    r'legally obligated to act', r'puts your interests first, by law',
    r'assets (?:are )?custodied', r'quarterly performance reports',
    r'not a registered investment adviser[^.]*\bbut\b',
]

class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]; self.links=[]; self.images=[]; self.inputs=[]; self.labels=[]; self.text=[]
    def handle_starttag(self, tag, attrs):
        data=dict(attrs); self.tags.append((tag,data))
        if tag=='a': self.links.append(data)
        if tag=='img': self.images.append(data)
        if tag in {'input','select','textarea'}: self.inputs.append((tag,data))
        if tag=='label': self.labels.append(data)
    def handle_data(self,data): self.text.append(data)

def parse(path):
    p=AuditParser(); p.feed(path.read_text(encoding='utf-8')); return p

def test_expected_pages_and_landmarks():
    assert len(PAGES)==12
    for page in PAGES:
        p=parse(page); names=[t for t,_ in p.tags]
        assert names.count('h1')==1, page
        assert names.count('main')==1, page
        assert names.count('nav')>=1, page
        assert names.count('footer')==1, page
        assert any(a.get('href')=='#main' for a in p.links), page

def test_images_have_dimensions_and_alt():
    for page in PAGES:
        for img in parse(page).images:
            assert img.get('width') and img.get('height'), (page,img)
            assert 'alt' in img, (page,img)

def test_internal_links_resolve():
    for page in PAGES:
        for a in parse(page).links:
            href=a.get('href','')
            if not href or href.startswith(('#','mailto:','tel:','http://','https://')): continue
            target=(page.parent / urlsplit(href).path).resolve()
            assert target.exists(), (page,href,target)

def test_external_new_tabs_are_safe():
    for page in PAGES:
        for a in parse(page).links:
            if a.get('target')=='_blank':
                rel=set((a.get('rel') or '').split())
                assert {'noopener','noreferrer'} <= rel, (page,a)

def test_form_controls_have_labels():
    for page in PAGES:
        p=parse(page); labelled={x.get('for') for x in p.labels}
        for tag,field in p.inputs:
            if field.get('type')=='hidden': continue
            assert field.get('id') in labelled or field.get('aria-label') or field.get('aria-labelledby'), (page,tag,field)

def test_no_unverified_public_claims():
    for page in PAGES:
        text=' '.join(parse(page).text).lower()
        for pattern in PROHIBITED:
            assert not re.search(pattern,text,re.I), (page,pattern)

def test_client_shell_has_no_auth_upload_or_client_state():
    page=ROOT/'client.html'; raw=page.read_text(encoding='utf-8').lower(); p=parse(page)
    assert 'data-portal-state="not-enabled"' in raw
    assert 'noindex, nofollow' in raw
    assert '<form' not in raw
    for tag,field in p.inputs:
        assert field.get('type') not in {'password','file'}
    assert not re.search(r'localstorage|sessionstorage|client-specific data:',raw)

def test_no_google_font_payload_and_only_deferred_local_js():
    for page in PAGES:
        raw=page.read_text(encoding='utf-8')
        assert 'fonts.googleapis.com' not in raw
        assert 'tailwind.min.css' not in raw
        assert 'hero-bg.js' not in raw
