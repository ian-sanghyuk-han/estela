# Estela

A gastronomic journey log built on a reusable 3D globe.
Finite canon guides (Michelin, Blue Ribbon, 50 Best, ...) become stars on a globe;
visited stars light up and connect into a personal trail — the *estela*.

- `index.html` — the globe foundation: country fills, crisp vector borders, tiered labels
  (16 major countries always visible → all 177 on zoom; 62 major cities in two tiers).
  Forked from `after-flight/index.html`, itself seeded from the Batavia `globe-base.html` v4
  (includes dateline-unwrap fill and polar-cap fixes).
- No star layers yet. P1 adds static canon-guide JSON snapshots on top of this base.
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
