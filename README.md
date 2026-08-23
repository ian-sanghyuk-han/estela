# Estela

A gastronomic journey log built on a map. Finite canon guides (Michelin, UNESCO, ...) become
stars; visited stars light up and connect into a personal trail — the *estela*.

- Live: https://ian-sanghyuk-han.github.io/estela/

## Stack

**MapLibre GL JS 5** (BSD-3-Clause) with `projection: 'globe'` — one map that unrolls from a
globe to a flat map to a street map as you zoom, with label collision and clustering built in.
`topojson-client` supplies the world outline. No build step: `index.html` is the whole app.

An earlier version hand-rolled the globe in three.js with its own morph, clustering and a
separate street map bolted on below city zoom. Every seam in that chain misbehaved, and all of
it turned out to be work the library already does. That version is in the history at
`d954376` if the three.js globe is ever wanted again (After Flight may still want it).

- `index.html` — the whole app.
- `data/*.json` — canon layers as **static snapshots**, one file per layer, each a toggleable
  map source. Two ship today, both Wikidata (CC0): the world's Michelin 3-star restaurants
  (140) and the UNESCO Cities of Gastronomy (36 of the official 56; the panel shows both).
- `내 장소` is a third layer built from the browser's own store: places are added one at a
  time by searching Nominatim and picking a result, which supplies the coordinates. There is
  deliberately **no bulk import** — see `docs/canon-sources.md` for why that line matters.
- `docs/canon-sources.md` — what each country offers as a finite list, and under what licence.
- `check.html` — device diagnostic, written in ES5 so it renders where the map cannot.

## Licences

MapLibre GL JS BSD-3-Clause · map tiles and place search © OpenStreetMap contributors (ODbL) ·
star data Wikidata (CC0). Attribution is shown in the app.

## Hard rules (handoff §4)

- Canon data ships as **static JSON snapshots**. No live scraping, no runtime calls to any
  guide's servers. Manual refresh, once or twice a year.
- **Facts only** — name, address, coordinates, grade, cuisine, year. Never review text,
  inspector notes, or photos.
- Every star shows its **source layer** and a **last-verified date**.
- Guide trademarks are never used in the product name or logo.

Conventions: code and docs in English; reports to the owner in Korean.
