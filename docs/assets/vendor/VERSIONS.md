# Vendored assets

Every third-party asset the public site depends on is committed here so the
site makes zero external requests at runtime (the one allowed exception is the
Learn page's user-initiated BYO-key call to `api.anthropic.com`, whose SDK is
itself vendored below). Downloaded from the official jsDelivr npm CDN and
Google Fonts at build time.

| Asset | Version | Files | Source |
| --- | --- | --- | --- |
| KaTeX | 0.16.9 | `katex/dist/katex.min.js`, `katex/dist/katex.min.css`, `katex/dist/contrib/auto-render.min.js`, `katex/dist/fonts/*.woff2` (20) | `cdn.jsdelivr.net/npm/katex@0.16.9/dist/` |
| dagre | 0.8.5 | `dagre.min.js` | `cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js` |
| reveal.js | 5.1.0 | `reveal/reveal.js`, `reveal/reveal.css`, `reveal/theme-white.css`, `reveal/math.js` | `cdn.jsdelivr.net/npm/reveal.js@5.1.0/` |
| pdf.js (pdfjs-dist) | 4.10.38 | `pdfjs/pdf.min.mjs`, `pdfjs/pdf.worker.min.mjs` | `cdn.jsdelivr.net/npm/pdfjs-dist@4/build/` |
| @anthropic-ai/sdk | 0.110.0 | `anthropic/sdk.mjs` | `cdn.jsdelivr.net/npm/@anthropic-ai/sdk/+esm` |
| standardwebhooks (SDK dep) | 1.0.0 | `anthropic/standardwebhooks.mjs` | `cdn.jsdelivr.net/npm/standardwebhooks@1.0.0/+esm` |
| @stablelib/base64 (SDK dep) | 1.0.1 | `anthropic/stablelib-base64.mjs` | `cdn.jsdelivr.net/npm/@stablelib/base64@1.0.1/+esm` |
| fast-sha256 (SDK dep) | 1.3.0 | `anthropic/fast-sha256.mjs` | `cdn.jsdelivr.net/npm/fast-sha256@1.3.0/+esm` |
| Inter | v20 (Google Fonts) | `inter/inter.css`, `inter/inter-{400,500,600,700,800}-{latin,latin-ext}.woff2` (10) | Google Fonts `css2?family=Inter:wght@400;500;600;700;800` |

## Modifications made for self-containment

- **KaTeX CSS**: the `@font-face` `src` lists were trimmed to the `.woff2`
  format only (the `.woff` and `.ttf` fallbacks were dropped, and those files
  are not vendored). Every current browser supports woff2. 20 woff2 faces are
  vendored under `katex/dist/fonts/`. The files keep the canonical npm `dist/`
  layout (`dist/katex.min.js`, `dist/katex.min.css`, `dist/contrib/auto-render.min.js`,
  `dist/fonts/`) so the reveal.js math plugin resolves them from a single
  `katex: { local: '.../vendor/katex' }` config.
- **Anthropic SDK**: the jsDelivr `+esm` bundles re-import their dependencies
  from `/npm/...` at runtime, which would defeat standalone. The import
  specifiers were rewritten to local relative paths:
  `sdk.mjs` -> `./standardwebhooks.mjs`; `standardwebhooks.mjs` ->
  `./fast-sha256.mjs` and `./stablelib-base64.mjs`. The two leaf modules have
  no further imports. The message-creation path the Learn page uses
  (`new Anthropic(...).messages.create`) does not touch the webhook code, but
  the dependency is vendored intact rather than stubbed so the SDK stays whole.
- **Inter**: only the `latin` and `latin-ext` subsets are vendored (all five
  weights). The `@font-face` rules keep their original `unicode-range`
  descriptors, so non-latin ranges simply fall back to the system stack; all
  site copy and physics symbols are covered by latin/latin-ext.

Total committed vendored size: ~3.5 MB.
