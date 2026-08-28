# Context read proof

Complete archive read: **PASS**. ZIP integrity: **PASS**. Members read: **50**. Source byte count: **666911**. Source SHA-256: `06bebd6f96afe3b97639c6406f7beef8c1d96ed24e3ef248e6f2f0aecaa3c356`.

The public `mas/web/` snapshot was copied byte-for-byte to `apps/public-site/`. The old Streamlit client portal and onboarding/conversion files were read for boundaries and ownership but not copied into the secure implementation. No source archive bytes, credentials, authenticators, real client documents, SSNs, tax returns, or browser profiles are packaged.

| Source member | Bytes | SHA-256 |
|---|---:|---|
| `mas/advisory/client/portal.py` | 7474 | `a03b292583d67b6ecfadea1c497a0070d639f22fe6ef16644f0f8711ec86c231` |
| `mas/advisory/onboarding/conversion.py` | 24029 | `493a90037ced05558e9c148313308eab77da0bfeb3987378eacbaacfc5f7f514` |
| `mas/scripts/ops/build_ibkr_client_onboarding_guides.py` | 32866 | `5ef828e9b3382d3c030adfd6120e0b6f18f793f8044195a3107ef8d503677417` |
| `mas/tests/test_advisory_client_conversion.py` | 4980 | `597232d7d92024665cc7e6f32053b2b7f3b4e8c8bdc368d69b2df59e066d7846` |
| `mas/tests/test_ibkr_client_onboarding_guides.py` | 2326 | `09b363e1c24f95a5bea47dbd8490cd0c0cc39704e70a83bc2ea2f4880925fedd` |
| `mas/web/.gitignore` | 47 | `25a23e81f16489eb0f30a47624b7a0a01291bc5145c65ebc9577e9a351dba6db` |
| `mas/web/.nojekyll` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `mas/web/AGENT_POLISH_PROMPT.md` | 14347 | `cdcec5ec37ddb2976dd244ab38817c7a087322cce92383051cd1d428b9b157b1` |
| `mas/web/CHANGELOG.md` | 2636 | `8714872bec8140e9907ed0de430eaaa689ec1d6f213d0cb22bab0db290aad705` |
| `mas/web/CLIENT_PORTAL_BOUNDARY.md` | 1351 | `2a415a32d1d84ae9107720c6e5a174f7111c5e6036490c7748e317af5315526f` |
| `mas/web/NETLIFY_SWITCHOVER.md` | 2180 | `535a3ad22e8aad96d340755cedb63c51742d8d0cc1bac94b5bd93b3916ac1478` |
| `mas/web/about.html` | 16360 | `058df1d921d9a38abe5b3d6c7c84b3cd3614e36da0be4348536ce5c3d9cbd3fb` |
| `mas/web/assets/apple-touch-icon.png` | 41452 | `b66bc403fae565c7506d0792caf48e0a454aa28e9ae238d4f94bb94f2ff7a961` |
| `mas/web/assets/favicon.ico` | 2095 | `4b7c141524a9629a834f8fdc205d3ec314ec0d496f62752f4c7c492d068e39f0` |
| `mas/web/assets/ibkr-logo-white.png` | 5148 | `19e8e92a063a4f76292cdf355d102f3b22c4b62f1239accf8ace32e8e6bda700` |
| `mas/web/assets/ibkr-logo.png` | 5639 | `40539cb20abefb4f23b458bbf7fbb9ceab27b815797c360f9781effd7783aa26` |
| `mas/web/assets/logo.png` | 386326 | `d9973e7fd9f80bd9172e459c7df85936406d233eea5e36685805f19a340f02f8` |
| `mas/web/assets/og-image.png` | 111175 | `7355095afe4953e8934796f93dffc30454e6ee052f237942510c41dcb59cfb0a` |
| `mas/web/build.sh` | 1243 | `56d01f83e5c19b794f49c60d28e472e14c83cf76432cb482483770b98af62e3e` |
| `mas/web/client.html` | 9701 | `217e4849c684940e90380958a170491a2c2018def5a3a668bfc1381b50e4aec4` |
| `mas/web/contact.html` | 14387 | `628c03676c4fe7e1306edc42a84de9dedcf3752e4064bf20be2d7ad241092ccd` |
| `mas/web/css/input.css` | 59 | `cc1a7ad0d019ddb1d32d0ecb588ba0ac26ce41d8625dd6c366348b25f83a28ec` |
| `mas/web/css/style.css` | 35921 | `eb144c3d732db315cc093df8318c80670e670ddaa4ecd77a1fc0d49b142841a6` |
| `mas/web/css/tailwind.min.css` | 9587 | `f99e45d12395f06c68c08d3ebaf2ee58e5f181a3485b9abf83ce976c0850363d` |
| `mas/web/css/tokens.css` | 3411 | `c2a9ad2b7dd6023befad3e75284a6c06fe495e5a784237b574cb54a12b5f8e9c` |
| `mas/web/deploy.sh` | 1766 | `6bda91cb08813ce7f19c2f54377b5276a42c2599455ea996e08a85c90a912411` |
| `mas/web/index.html` | 23601 | `e7fdd4c74011735fc7c444b469287d81920f5ec7b14a386148a584dbf4119465` |
| `mas/web/js/calculator.js` | 66 | `81e2680ca700d08e63f0055684f8963367e9ef0b911aacd8cb906406a9dcefb1` |
| `mas/web/js/hero-bg.js` | 5858 | `754ef82879e5e3758ea19d5065246a4da2d868e11d4e1e8784dc8475e70e6f74` |
| `mas/web/js/nav.js` | 7179 | `dd7f0165f168ac9012379984e91d679133f83a711bd841feae8af93ab441d8c4` |
| `mas/web/llms-full.txt` | 6714 | `d8364ebae88eafb35f53401b816d213df9f4dc8b1dbba56bf2e75a882d40b3f4` |
| `mas/web/llms.txt` | 2165 | `5bf1007de07db359252f7407adbac968d1be13d86b528dae6b21a8420bec60d6` |
| `mas/web/netlify.toml` | 1039 | `a9ff71d9c5b67486b91c6a8df0823a0f62368b71bb387a4f07806cbee0a017e2` |
| `mas/web/privacy.html` | 14713 | `ab92f8a3f67929000c1a4a0a50395e13304cc979cdfa33a0c04b2ca62e3738eb` |
| `mas/web/robots.txt` | 531 | `4fe7114d742c088b17d4971d8c1b473993eeb0fd21185004ec0260e95dbd2f05` |
| `mas/web/scripts/add_canonicals.py` | 1731 | `976eb320a284ad196a6db42bd5347e7c1c762def8ef2a72749275da87f987457` |
| `mas/web/scripts/add_legal_footer_links.py` | 2109 | `05eacefb54bf7bbc9e58cbe76404cf36c9e55defa7732ad3e3b7898b6df5c8d0` |
| `mas/web/scripts/fix_domain.py` | 723 | `99142ffd2c977c837089716c017e8114fe8e7dc16b6ea93224bb3f02cf35d609` |
| `mas/web/scripts/screenshot_policy_pages.py` | 6145 | `f0885a2113decefaa72eb686b16a9d060fff9df5b89b8bce074312cfa739023a` |
| `mas/web/scripts/sync_tailwind_gold.py` | 792 | `f5f7e53354dc06d2df8cfca712a26d3e01f45bc96a08056afac9cb3f4edf362b` |
| `mas/web/services/business.html` | 16040 | `ac186b89fc3a8c00a38ef9a366d0347cc756472cca81585a8eae24ec5a0c6bfa` |
| `mas/web/services/estate.html` | 15283 | `804e64eabe7b696693b949e4ab2326f6540bb5edb0b36cf93d652ea63ae5a2b3` |
| `mas/web/services/investment.html` | 15239 | `d2766cb5a093c0521e7df39cb2d2011d9b872cacaf94a8d2024f25f1366bbcbd` |
| `mas/web/services/retirement.html` | 16338 | `df05fd13c11238d10699d8fcca9ee9dad04502789e1fa18aa50256a953593b47` |
| `mas/web/services/tax.html` | 14970 | `633c15f36cfa447d7f67050fa1baf798842ae96f4c7b46cb2409f35a3e7c49ab` |
| `mas/web/services.html` | 18044 | `31964b35a6c61568b38070c4fdc044c8924abb3471e4f5750c6527b64fa4d6f0` |
| `mas/web/sitemap.xml` | 1665 | `59b5a06e8f5b4820ea979b65895d0a95b6dba760cdc680b5f27e254fe112d9f9` |
| `mas/web/tailwind.config.js` | 1032 | `4de38ada8c749d84e31d1a2f90897639317d52278c8fb6e451abaf4860bc794e` |
| `mas/web/tailwind.preset.js` | 2028 | `08f0700bf66d747154e3c5a6cf3f4ae05756e8bafc2b748f0163230e59957ac1` |
| `mas/web/terms.html` | 14352 | `03c336c1e0fdd39ebb889bb9f166f63f9187ec7b6cd950dd7aac09c877551f14` |
