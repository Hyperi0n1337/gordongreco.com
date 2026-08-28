# Gordon Greco

This public repository is the deployable source mirror for the current Gordon
Greco website and secure-client-portal project.

- GitHub Pages: <https://hyperi0n1337.github.io/gordongreco.com/>
- Public website source and generated pages live at the repository root.
- The complete portal implementation lives under [`portal/`](portal/).
- Portal authentication, private storage, and database services are deployed
  separately; GitHub Pages never receives client records or secrets.

Build and verify the public site:

```bash
python scripts/generate_site.py
python tests/run_static_contract.py
python scripts/build_public.py
```

Verify the portal source:

```bash
cd portal
python scripts/verify.py --no-write
```

Never commit client documents, database exports, credentials, cookies, browser
profiles, tokens, private identifiers, or deployment secrets.
