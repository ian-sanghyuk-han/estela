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

## Shipped

| | Source | Places | Cells | Size |
|---|---|---|---|---|
| 🇬🇧 United Kingdom | FSA Food Hygiene Rating Scheme | **226,538** | 663 | 23.5 MB |
| 🇫🇷 France | DGAL Alim'confiance | **32,507** | 1,130 | 2.8 MB |
| 🇩🇰 Denmark | Fødevarestyrelsen Smiley | **10,914** | 167 | 1.0 MB |
| 🇺🇸 New York | NYC DOHMH | **30,032** | 7 | 2.5 MB |
| 🇨🇦 Toronto | City of Toronto DineSafe | **18,178** | 6 | 1.5 MB |
| 🇺🇸 Chicago | City of Chicago food inspections | **28,317** | 5 | 2.4 MB |
| 🇭🇰 Hong Kong | FEHD licences + ALS geocoding | **17,092** | 7 | 2.2 MB |
| 🇺🇸 Boston | City food establishment licences | **3,126** | 3 | 0.3 MB |
| 🇦🇺 Melbourne | City business census | **2,247** | 1 | 0.2 MB |
| | | **368,951** | | **34 MB** |

**United Kingdom.** Three of the FSA's fifteen categories — Restaurant/Cafe/Canteen
(122,873), Pub/bar/nightclub (**45,297**) and Takeaway/sandwich shop (58,368). Hospitals,
schools, manufacturers, supermarkets and mobile caterers are left out; they are not places
you would call somewhere to eat. Bars arrive free of charge with this, which is most of the
way to the F&B widening that was asked for long ago — wineries will not, since those are
brewing licences rather than food-service ones and live somewhere else entirely.

**France.** Only the `Restaurants` activity of 40 in the file; bakeries, butchers,
cheesemongers, canteens and abattoirs are all in there too. France keeps no separate bar
category, so cafés, bistros and brasseries that serve food are already inside — searching
Paris for *Le Bar* returns LE BARAV, LE BARJO, LE BARATIN.

*Honest limit:* Alim'confiance reaches **inspected** premises only — 32.5k against the
200k-odd restaurants SIRENE knows about. Full coverage wants SIRENE NAF 5610A geocoded
through BAN, both French government and both open, but a considerably bigger job.

**Denmark.** Two of the serving categories — Restauranter (9,536) and Uden behandling
(1,378, the bars and cafés that serve without cooking). Institutionskøkkener is canteens
and is left out, as school and hospital catering was left out of the UK. The XML ships
Geo_Lat and Geo_Lng, so nothing needed geocoding.

*Honest limit:* **12,420 of the 23,365 kept rows have no coordinates in the source** —
`<Geo_Lat />` is simply empty. They carry addresses, so Nominatim could fill them in, but
that is 12k lookups at one a second and was not worth it today.

**New York.** 31,319 permits, 30,032 of them with usable coordinates, collapsed from
roughly 300,000 inspection rows by CAMIS permit number. Alone among the registries so far
it publishes a **cuisine description** — American 4,604, Chinese 2,262, Coffee/Tea 2,168,
Pizza 1,578, Mexican 1,089 — which is a fact about the place rather than a judgement of it,
so it fills the category slot. Scores and letter grades are discarded.

**Toronto.** 106,570 infraction rows collapsed to 18,178 establishments. Honest difference
from New York: DineSafe carries **no establishment-type field**, so there is nothing to put
in the category slot and no way to filter groceries and bakeries out. Toronto's file is food
premises generally, not restaurants specifically.

**Chicago.** Two things New York does not give: a `facility_type`, so schools, children's
services and groceries are filtered out properly rather than swept in, and an `aka_name` —
the name in use rather than the corporation on the licence. Where they differ we take the
aka. 27,462 restaurants, 658 bakeries, 188 taverns.

**Hong Kong.** 17,203 licences, of which **17,188 geocoded — 100%** — through ALS in 67
minutes at three workers. 96 rows carry `(no record found)` in the shop-sign field, meaning
the licence exists but no sign was ever filed; a row with no searchable name is dropped
rather than shipped as a mystery. 12,518 restaurants, 4,569 light-refreshment, 5 marine.

**Boston.** The only one where closed premises never arrive: CKAN's SQL endpoint collapses
896,379 inspection rows to one per licence *and* filters `licstatus = Active` in a single
query. Retail Food is grocery and is dropped; Mobile Food Walk On is kept, since a food
truck is a real place to eat even if it moves.

**Melbourne.** Not a licence register at all — Australia registers per council, so there is
nothing national or even state-wide. This is the City of Melbourne's own **business census**,
covering the CBD and inner suburbs rather than greater Melbourne, and recounted each year;
only the latest (2024) is taken. Worth remembering as a fallback shape: where no licence
file exists, a city may still count its own businesses.

**The hygiene rating is deliberately discarded in all of them.** It is the state's judgement, and
Estela carries nobody's judgement about whether a place is good. We take only the fact that
it exists — and the category, so a row can say 펍·바 rather than leaving the reader to guess.

*Gotcha worth remembering:* Opendatasoft's `records` endpoint caps `offset + limit` at
10,000 and returns 400 forever past it. Use `exports` instead, which streams the whole
filtered set in one response.

### The shape every other country pours into

```
data/registry/manifest.json      grid size, and per source: label, country,
                                 folder, licence, total, and a cell → count index
data/registry/<folder>/<cell>.json   [[name, lat, lon, address], ...]
```

Cells are `0.25°` squares keyed `<floor(lat/step)>_<floor(lon/step)>`. The UK came to 667
cells, 21 MB, averaging 30 KB — central London is the outlier at 1.4 MB, which gzips to
roughly a third of that and is fetched once.

The browser loads a cell only when the owner starts typing **and** the view is narrow
enough that "every restaurant near here" is a sensible question — above 42 cells in view
it declines and says so instead. Nothing from the registry is ever drawn on the map.

**Verified reach:** `Bella Crust` (41 Rosebery Avenue, EC1R) and `Artizian Catering` are in
the registry and absent from OpenStreetMap entirely. That is the whole point of the tier —
it finds what no guide and no volunteer mapper recorded.

## 서비스 지역을 지구본에 칠한다 (2026-08-27)

칸은 이미 `0.25°`로 쪼개져 있고 목록도 manifest에 있으니, 칠하는 값은 공짜였다.
9개 출처의 칸을 합쳐 중복을 걷어내면 **1,989칸**. 겹친 칸이 두 번 칠해지지 않게
한 겹으로 만든 다음 별과 항적 **아래**에 깐다 — 바닥이지 주인공이 아니다.

색은 새로 하나 들였다(`--reach:#4F6D7A`). 포도주는 나, 올리브는 함께이고,
찾을 수 있는 땅은 둘 중 어느 쪽도 아니다 — 판단이 아니라 바닥이다.
세계 배율에서 진하고 파고들면 옅어진다.

그림이 말없이 사실을 말한다: **영국과 프랑스는 꽉 찼고, 덴마크는 얼룩이고,
미국은 점 세 개다.** 그게 지금 상태고, 그게 보여야 넓히는 일이 넓히는 것처럼 느껴진다.

## Tier A — one national file, ready to use

| | Source | Scale | Coordinates | Licence | Refresh |
|---|---|---|---|---|---|
| 🇰🇷 Korea | [전국일반음식점표준데이터](https://www.data.go.kr/data/15096283/standard.do) (행정안전부) | **2,129,830** incl. closed | EPSG:5174, needs WGS84 conversion | 이용허락범위 제한 없음 | every 2 days |
| 🇬🇧 UK | [FSA Food Hygiene Rating Scheme](https://ratings.food.gov.uk/open-data) — [API](https://api.ratings.food.gov.uk/help) | every licensed food business, all four nations | yes | free, **no authentication** | daily |
| 🇫🇷 France | [INSEE SIRENE](https://www.sirene.fr/sirene/public/static/open-data), NAF **5610A** | 40M establishments, 15M active | geocoded editions on regional portals | Licence Ouverte | daily |
| 🇲🇽 Mexico | [INEGI DENUE](https://en.www.inegi.org.mx/servicios/api_denue.html) | **5M+** establishments | yes | free API token by email | continuous |
| 🇭🇰 Hong Kong | [FEHD restaurant licences](https://www.fehd.gov.hk/english/licensing/license/text/LP_Restaurants_EN.XML) | **17,203** licensed restaurants | **none in the file** — geocode via [ALS](https://www.als.gov.hk/lookup) | open | daily |
| 🇸🇬 Singapore | ~~SFA eating establishments~~ | **corrected — see below** | | | |

### Hong Kong — a registry with the best names and no coordinates

FEHD's daily XML is 17,203 licences and, unusually, carries the **shop sign** (`SS`) — what
is actually painted above the door, not the company that holds the licence. That is better
raw material than most registries give. What it has no trace of is coordinates.

They come instead from **ALS**, the Hong Kong government's own Address Lookup Service:
free, no key, and it returns latitude and longitude for a postal address. Government data
geocoded by the same government. Measured 5 of 6 on a sample at 0.44 s a call; failures are
range addresses like *32-40 Wellington Street*, which a retry on the last three
comma-separated segments usually rescues.

**The lesson for the next country: a registry without coordinates is not a dead end if the
same government also runs an address lookup.** Check for that before giving up on one.

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

## Tier D — licensing exists, no open download found

| | Finding |
|---|---|
| 🇸🇬 Singapore | **Corrected 2026-08-24.** The Tier A entry above was wrong — inferred from a dataset title without opening it. `Licensed Food Establishments By Grade` turns out to be 55 rows of year, grade and count: a **statistic, not a list of places**. No establishment-level open dataset was found. |
| 🇹🇭 Thailand · 🇻🇳 Vietnam · 🇲🇾 Malaysia · 🇮🇩 Indonesia | Every one requires a food-business licence (Thailand's district office permit, Vietnam's Certificate of Eligibility for Food Safety, Indonesia's NIB). None publishes the resulting register as open data that could be found. |
| 🇮🇳 India | FSSAI licensing runs through FoSCoS and covers every operator, but no downloadable register surfaced. |
| 🇦🇺 Australia | Registration is per state **and per council** — NSW notifies to the local council, Victoria classifies by risk class. No central open register. |
| 🇩🇪 Germany · 🇳🇱 Netherlands · 🇸🇪 Sweden | Company registers exist (Gewerbeamt, KVK, Bolagsverket) but Europe restricts them commercially — by one count only **1 of 32 European countries** opens its entire company register for free. |
| 🇹🇷 Turkey · 🇵🇹 Portugal · 🇬🇷 Greece | Not confirmed either way. |

Worth retrying later rather than treating as settled — a negative search result is weaker
evidence than a positive one, and these were surveyed in one pass.

---

## The pattern that finds the next country

The reliable door is **not** the business register. Europe proves that: it is the most
open-data-friendly region on earth and its company registers are mostly paywalled, because
company data is a commercial product there.

The reliable door is the **consumer-facing food hygiene disclosure scheme**. Those exist to
be read by diners, so they are published, and they necessarily list every establishment:

| | Scheme |
|---|---|
| 🇬🇧 UK | Food Hygiene Rating Scheme (FHRS) |
| 🇩🇰 Denmark | **Smiley** — [Virk Data](http://datahub.virk.dk/dataset/smiley-kontrolrapporter), every food business, CVR and P-number, free XML, a public REST wrapper exists |
| 🇫🇷 France | **Alim'confiance** — hygiene inspection results, four levels, open |
| 🇺🇸 USA | City health inspections (NYC DOHMH and equivalents) |
| 🇨🇦 Canada | **Toronto DineSafe** — ~15,000 establishments, GIS coordinates, updated in real time |
| 🇭🇰 Hong Kong | FEHD licence lists |
| 🇰🇷 Korea | 인허가 대장 (same family, licensing rather than rating) |

**So when adding a country, search for its smiley — not its company register.**

## Also confirmed, heavy

| | Source | Note |
|---|---|---|
| 🇧🇷 Brazil | Receita Federal **CNPJ** open data, CNAE **5611-2** for restaurants | National and free, but ~85 GB, monthly, awkward layout, and **no coordinates** — addresses only. Mirrors exist. Treat as a last resort. |

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

---

## Dead ends checked, so nobody checks them twice

| | What happened |
|---|---|
| 🇸🇬 Singapore | `Licensed Food Establishments By Grade` is 55 rows of year/grade/count — a statistic. No establishment-level dataset found. |
| 🇮🇪 Ireland | data.gov.ie has no food-business register; a search for one returns food-waste statistics. |
| 🇳🇱 Netherlands | data.overheid.nl lists *Inspectieresultaten* as **planned** — "Databron nog niet beschikbaar". Nothing to download yet. |
| 🇹🇼 Taiwan | data.gov.tw's search API path has moved; the per-city catering datasets exist but were not reached this pass. |
| 🇪🇸 Barcelona | A restaurant list exists under CC BY 4.0, but the portal sits behind bot detection. Not circumvented. |
| 🇯🇵 Japan | The national 食品衛生申請等システム is mid domain-move and serves only a redirect notice. Tokyo's catalogue has 276 matching datasets, all per-municipality. |
| 🇳🇴 Norway · 🇫🇮 Finland | Both run smiley schemes (Smilefjes, Oiva) but the open-data endpoints found were dead or 403. Worth another pass. |
| 🇺🇸 San Francisco · Austin | Inspection files published without coordinates. |
| 🇺🇸 Seattle · 🇨🇦 Vancouver, Montreal | Login required, or no matching dataset found. |

## Two operational notes worth keeping

**Dense cities overflow a 0.25° cell.** New York fits in 7 cells with 14,125 in one;
Toronto in 6 with 11,748 in one; central London holds 16,760. Each is a megabyte-plus first
fetch. Splitting dense cells is in `backlog.md` alongside the prefix index.

**Inspection files are one row per event, never one per place.** New York, Toronto and the
UK all needed collapsing by a permit or establishment id first. Always check the row count
against the distinct-id count before believing a headline number.
