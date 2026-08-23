# Estela

A gastronomic journey log built on a reusable 3D globe.
Finite canon guides (Michelin, Blue Ribbon, 50 Best, ...) become stars on a globe;
visited stars light up and connect into a personal trail — the *estela*.

- `index.html` — the globe foundation: country fills, crisp vector borders, tiered labels
  (16 major countries always visible → all 177 on zoom; 62 major cities in two tiers).
  Forked from `after-flight/index.html`, itself seeded from the Batavia `globe-base.html` v4
  (includes dateline-unwrap fill and polar-cap fixes).
- Three view modes, ported from `batavia-wtl/site/index.html`:
  **GLOBE ↔ MAP** is a morph, not two renderers — the base is a `PlaneGeometry` grid whose
  vertices lerp between a wrapped and an unfolded position, and borders, labels, city dots
  and the trail all carry the same `p0`/`p1` pair. **JOURNEY** draws great-circle arcs
  between visited stars in date order, with undated stars left lit but unthreaded (§5.3.3).
- `data/*.json` — canon layers as **static snapshots**, read at load and drawn as one
  toggleable group each. The first one is the world's Michelin 3-star count **by country**
  (140 across 19 countries), derived from Wikidata (CC0) — aggregate counts, not a place
  database. Per-restaurant coordinates land later, in the same file format (`grain:"place"`).
- The JOURNEY trail runs on a labelled **sample** of city coordinates. No restaurant names
  and no guide-sourced text exist anywhere in this repo.
- `check.html` — device diagnostic (iOS version, import-map support, WebGL, CDN reach).
  Written in ES5 with no modules so it still renders where the globe cannot.
- Live: https://ian-sanghyuk-han.github.io/estela/

## Hard rules (from ESTELA-HANDOFF-v1 §4)

- Canon data ships as **static JSON snapshots** in this repo. No live scraping, no runtime
  calls to any guide's servers. Manual refresh, once or twice a year.
- **Facts only** — name, address, coordinates, grade, cuisine, year.
  Never copy review text, inspector notes, or photos.
- Every star displays its **source layer** and a **last-verified date**.
- Guide trademarks are never used in the product name or logo.

## Stack

three.js r160 + topojson-client (CDN, import map) · world-atlas 110m country topology.
No build step: `index.html` is the whole app.

Conventions: code and docs in English; reports to the owner in Korean.
