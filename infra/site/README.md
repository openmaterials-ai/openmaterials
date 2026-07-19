# The site Worker

The edge deployment of openmaterials.ai. Wrangler serves the repository's
`docs/` directory as static assets, byte-identical to the GitHub Pages
deployment, and the Worker script runs only for the routes a fragment-only
static site cannot express:

- `GET /healthz`: liveness plus the published map/lineage version, read from
  the same `data/version.json` every browser reads.
- `GET /l/<64-hex>`: the canonical permalink for a committed value. The id is
  a lineage id (the sha256 of the value's canonical lineage). The Worker
  resolves it against `data/instances.json`, serves a shell whose Open Graph
  metadata names the property, material, value, and id (so the link unfurls
  as the value it is), and redirects to the playground datasheet
  (`/play/#id=<id>`), the one renderer. A well-formed id that matches no
  committed value gets an honest 404 naming the hash; a malformed id gets a
  400 before any data is read.

- `POST /s` and `GET /s/<code>[/raw]`: the short-link store, the Worker's one
  write surface. Minting stores a lineage envelope (or a bare record,
  normalized to a one-element envelope) in the `SHORTLINKS` KV namespace and
  returns `<origin>/s/<code>`; the code is 9 unambiguous base58 characters.
  Minting is origin-gated (the site plus localhost) and rate-limited per IP
  per day; payloads are capped at 64 KB and 64 lineages, and a stored payload
  is PUBLIC by construction (anyone with the code can read it). `GET
  /s/<code>` serves a crawlable shell built only from the stored envelope and
  redirects into `/play/#s=<code>`, where the playground fetches
  `/s/<code>/raw` (open CORS, immutable) and renders through the same
  dual-read path as a `#x=` link. Unknown codes 404 naming the code;
  malformed codes 400 before any read.

Everything else falls through to the assets, so removing the Worker returns
the site to plain static hosting. The Worker holds no secrets and, outside
the explicitly public short-link store, no data of its own: the permalink
resolver reads the same committed projection the site serves, so it can never
disagree with the map.

## Develop

```
cd infra/site
npx wrangler dev --port 8971
```

## Deploy

```
cd infra/site
npx wrangler deploy
```

Deploys to the `openmaterials-site` Worker on workers.dev. Attaching the
production domain (openmaterials.ai) is a DNS decision made by the project
owner, not by this deploy; until then GitHub Pages remains the origin the
domain points at, and the two deployments serve identical bytes.

The Python suite pins the contract in `tests/test_site_worker.py` (the assets
directory, the exact `run_worker_first` list, the static fallthrough, the
no-credentials rule) and runs the resolver's node tests against the real
committed projection.
