# Where every restaurant is, legally

Surveyed 2026-08-24. Separate from `canon-sources.md`, which catalogues *curated* lists —
who is good. This catalogues *registries* — who exists.

**Why these exist everywhere.** Running a restaurant requires a licence in every developed
country, because food safety is regulated. The licence produces a public record. That
record is not a guide and carries no judgement, which is exactly why governments release
it and commercial guides do not. It answers "is this place real and open", never "is it
worth going".

**What this is for in Estela.** Search coverage, not a map layer. Drawing two million dots
would destroy the denominator that makes 완주 mean anything. Holding them in a search index
means nothing the owner looks for comes up empty — including the places no guide and no
volunteer mapper has ever recorded.

The test case: **거목한방순대국**, 강원 정선군 남면 도원2길 10 and a second branch at
서울 구로구 개봉로16가길 10-4. Absent from OpenStreetMap under either name, so our search
could never find it. Present in Korea's licence registry — 정선군's local map service cites
its management number `4291000-101-2010-00027`, whose shape matches the LOCALDATA format
confirmed from Seoul's own API sample (`3020000-101-2001-07985`): agency code, `101` for
일반음식점, licence year, serial. Both addresses geocode cleanly against OpenStreetMap.

---

## Tier A — one national file, ready to use

| | Source | Scale | Coordinates | Licence | Refresh |
|---|---|---|---|---|---|
| 🇰🇷 Korea | [전국일반음식점표준데이터](https://www.data.go.kr/data/15096283/standard.do) (행정안전부) | **2,129,830** incl. closed | EPSG:5174, needs WGS84 conversion | 이용허락범위 제한 없음 | every 2 days |
| 🇬🇧 UK | [FSA Food Hygiene Rating Scheme](https://ratings.food.gov.uk/open-data) — [API](https://api.ratings.food.gov.uk/help) | every licensed food business, all four nations | yes | free, **no authentication** | daily |
| 🇫🇷 France | [INSEE SIRENE](https://www.sirene.fr/sirene/public/static/open-data), NAF **5610A** | 40M establishments, 15M active | geocoded editions on regional portals | Licence Ouverte | daily |
| 🇲🇽 Mexico | [INEGI DENUE](https://en.www.inegi.org.mx/servicios/api_denue.html) | **5M+** establishments | yes | free API token by email | continuous |
| 🇭🇰 Hong Kong | [FEHD restaurant licences](https://data.gov.hk/en-data/dataset/hk-fehd-fehdlmis-restaurant-licences) | **17,387** licensed restaurants | via CSDI spatial portal | open | daily |
| 🇸🇬 Singapore | [SFA eating establishments](https://data.gov.sg/datasets?agencies=Singapore+Food+Agency+(SFA)) | all licensed food establishments | yes | Open Data Licence, commercial use allowed | periodic |

## Tier B — national system, download per municipality

| | Source | Note |
|---|---|---|
| 🇯🇵 Japan | 厚生労働省 **食品衛生申請等システム** — nationwide licences, downloadable per local authority. Many prefectures and wards also publish their own (Kyoto, Chiba, Kanagawa, Nagano, Setagaya, Kagoshima). | One assembly job per authority; monthly-ish refresh |

## Tier C — city by city

| | Source | Note |
|---|---|---|
| 🇺🇸 USA | No federal registry. Cities publish health-inspection data: [NYC DOHMH](https://data.cityofnewyork.us/Health/DOHMH-New-York-City-Restaurant-Inspection-Results/43nn-pn8j) carries every permitted restaurant with latitude and longitude, CSV/JSON/XML, daily. SF, Chicago, Seattle, Austin similar. | Cover the gastronomy cities individually |
| 🇮🇹 Italy | Regional portals (dati.gov.it, Dati Trentino, city ArcGIS instances) publish *esercizi di somministrazione* / *esercizi di ristorazione*, some geocoded | Fragmented, no national file |
| 🇪🇸 Spain | [datos.gob.es](https://datos.gob.es) carries city and regional *bares y restaurantes* datasets | Fragmented |
| 🇹🇼 Taiwan | [data.gov.tw](https://data.gov.tw) — catering industry datasets per city, with names, addresses and coordinates | Per city |

## Not yet checked

Thailand, Vietnam, Turkey, Portugal, Brazil, Peru, Australia, Germany, Netherlands,
Nordics. Brazil's CNPJ (Receita Federal, CNAE 5611-2) and Australia's ABR bulk extract are
the obvious next candidates — both are open national business registries.

---

## What these registries are not

They are **licence records, not guides**. Expect all of the following, and design around
them rather than pretending otherwise:

- **Closed businesses.** Korea's 2.1M includes 폐업; filter on 영업상태 and roughly 700–800k
  remain. Turnover in dense cities runs 20–30% a year, which is why the refresh cadence
  matters more than the size.
- **Registered names, not signboard names.** 사업장명 is often a corporate entity or the
  owner's registration, not what is painted above the door.
- **Everything.** Every convenience-store snack bar and every franchise branch is in here.
  There is no quality signal of any kind, and there must not appear to be one.
- **Projection differences.** Korea ships EPSG:5174 (Bessel central-origin TM), which needs
  a datum shift, not just a formula.

## The pattern worth remembering

Curated guides and public registries are distributed by **opposite** logics.

> A state publishes a **selective** food canon in inverse proportion to how commercially
> valuable its food is (see `canon-sources.md` §3b) — but it publishes a **complete**
> licence registry regardless, because food safety is regulated everywhere.

So the two sources compose cleanly and globally: the canon layer stays finite and
judged-by-others, the registry makes search exhaustive, and neither has to borrow anything
from a commercial guide.
