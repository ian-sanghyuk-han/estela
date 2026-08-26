# Known work, not yet done

Raised 2026-08-24. Recorded here so it survives the session rather than living in a chat log.

---

## 1. Search without travelling there first — **the big one**

Typing already autocompletes: `Be` → `Bel` → `Bella` narrows to Bella Crust as you type.
What it will not do is find it while you are looking at Seoul, because the registry loads
by map cell and only for the part of the world on screen.

That was the right first cut — it kept a quarter of a million rows out of the browser —
but the owner is right that it is backwards for how people search now. You should type
`Bella` and be told *"Bella Crust, London"*, not have to already be in London.

**Plan: a prefix index alongside the cells.**

```
data/registry/index/<src>/<aa>.json      [[name, cellkey], ...]
```

Bucketed on the first two characters of the name. Typing the second character fetches one
bucket and substring-matches inside it. The entry deliberately carries **no coordinates and
no address** — just the cell it lives in — which keeps a bucket to tens of kilobytes.
Location for the result row comes free: a cell key is a lat/lon, and `placeAt()` already
turns a lat/lon into the nearest town name, so the row can say "London" without storing it.
Clicking fetches that one cell for the exact coordinates.

Rough size for the UK: 226,877 entries at roughly 30 bytes is ~7 MB across ~400 buckets,
averaging under 20 KB each. Biggest buckets (`th`, `ca`, `sa`) may need a third character.

**Known limit:** bucketing on the *name's* first two letters means `Crust` will not find
`Bella Crust`. Indexing every word would fix it and roughly doubles the size. Start with
first-word matching and see whether it actually bites.

**Why after the next country and not before:** the index is a build step plus client work,
and building it once for three countries costs barely more than once for one. Doing Korea
and France first means the index gets designed against real multi-country data — different
alphabets, different name lengths — instead of being retrofitted.

---

## 1b. Dense cells — measured, and less urgent than it looked

Chicago's downtown cell holds 23,578 places, central London 16,760, New York 14,125. Raw
those are 2.1 MB, 1.7 MB and 1.2 MB, which sounds alarming. **Gzipped, as GitHub Pages
serves them, they are 374 KB, 492 KB and 309 KB** — a one-time fetch the first time you
search in that city, then cached.

So splitting dense cells is worth doing eventually for politeness on a phone connection,
but it is not the emergency the raw figures suggested. Measure before optimising.

## 2. A saved place that closes down

The registries know. Korea's carries 영업상태 and refreshes every two days; the FSA drops
closed premises. So on each refresh we can tell that a place someone stamped has gone.

**Never delete it silently.** A journey is a record of where someone has been, and a
restaurant closing does not un-happen the visit. The behaviour should be:

- mark it — the card and the journey row say 문 닫은 것으로 보입니다, with the date we noticed
- keep counting it in 도장 and 여정; it was a real visit
- drop it out of 가고 싶은 곳, where it is now useless
- only the owner deletes it, and only from a confirm that says plainly it cannot be undone

The pattern already exists: the orphan handling in the journey keeps records it cannot
match, names them, counts them separately, and deletes only on an explicit confirm reading
*자리를 잃은 기록을 영구히 지웁니다. 되돌릴 수 없습니다.* Closed places should reuse exactly that
shape.

**Prerequisite:** a stable id per saved place tying it back to its registry row. Today a
place added from the registry keeps only name and coordinates, so a refresh cannot find it
again. Store the source id and the registry's own key at the moment of saving.

---

## 3. When this becomes a database problem

Everything is in `localStorage` today, which is one browser on one machine. It works and it
costs nothing, and it should stay that way until an account is genuinely needed. The things
that will force the change, roughly in order:

1. **The same journey on phone and laptop.** The first real pain, and the first thing an
   account buys.
2. **Groups** — 우리 모임 9명 중 4명. Cannot exist without accounts; already marked 계정 필요
   in the layer panel.
3. **Registry refresh** — knowing a saved place closed means re-checking saved places
   against a newer registry, which is a job that wants to run somewhere other than the
   owner's browser.

Until then: an export/import of the whole journey as one file would cover most of case 1
for almost no work, and is worth doing before any server exists.

---

## 4. 영업시간 — half the data exists, and August is a trap

Naver shows whether a place is open *right now* by comparing the clock against hours the
**owner typed in** at 스마트플레이스. It is not inferred. Google works the same way. That is
the same moat as the category field: they have a relationship with the proprietor and we
do not.

The one open source is OSM's `opening_hours`, which is a proper machine-readable format —
measured at **46% of named restaurants in Paris**. Government registries have nothing: a
hygiene licence does not ask what time you open.

So "지금 영업 중" is possible for about half of places and impossible for the rest, and the
empty half must stay visibly empty rather than be guessed at.

**And the owner's catch, which matters more than the coverage number:** in August half of
France closes for les vacances and the posted hours mean nothing. Anywhere we show hours,
the vacation months need a plain warning — **영업 중 문의 필수** — rather than a confident
green "영업 중". The same applies to Italy in August and to the long holidays elsewhere.

---

## 5. Shape of the personal layer, settled

Worth writing down because the owner raised the right worry: if every user edits restaurant
data, does the data explode?

It does not, because the two layers stay separate.

```
공용 — one copy for everyone          개인 — only where you touched
  name · coords · address              your stamps and dates
  source · category · open/closed      your lists and their order
  369,000 places = 34 MB               your photos, notes, price
                                       200 visits = 200 rows, not 369,000
```

A thousand people with two hundred places each is roughly 40 MB — about the size of the
shared data, not a multiple of it. **Personal rows appear only where someone actually went.**

The real hazard is different: if users edit the *shared* record, you inherit moderation,
versioning and conflict. So edits always land on the personal overlay, never on the shared
row. If many people report the same correction that becomes a signal to act on later, but
that is P5 at the earliest.
