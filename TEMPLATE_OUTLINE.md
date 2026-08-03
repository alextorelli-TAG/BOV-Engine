# BOV Template Outline & Build Model

Authoritative spec for how a BOV book is composed. Pairs with `ROADMAP.md`
(what's built) and `CLAUDE.md` (how the code works).

## The composition model

- **Every run starts from the complete template**, all pages ON. The operator
  *subtracts and customizes* — never builds from a blank book.
- **Point-and-click include/exclude** per page and per section. Some pages are
  **mandatory** (locked ON). The rest are optional.
- **Asset class is a top-level switch.** It (a) swaps the *core* plate set —
  multifamily / land / retail have different offering metrics and comps — and
  (b) sets the default **divider** backgrounds so section photos match the deal
  (office/industrial/residential/land).
- **Footers renumber automatically.** Page numbers are baked into corporate
  artwork, so the assembler white-boxes the footer band and restamps the correct
  running number + section on every included page. Dropping or inserting a page
  never breaks downstream numbering.
- **The template is 53 corporate plates plus engine inserts.** The Executive
  Summary is inserted after the TOC; the land core adds its own pages. Inserts
  are renumbered like everything else.

## Page-type taxonomy

| Tag | Meaning | Engine operation | Operator action |
|---|---|---|---|
| **B** | Boilerplate, locked corporate | passthrough | include / exclude |
| **A** | Annual corporate stat (⚑ = asset-class-specific) | passthrough (refreshed yearly) | include / exclude |
| **T** | Team / advisor, from structured headshot + contact data | build / variant | pick who's on the deal |
| **V** | Metro variant, pre-built per market | variant | pick market |
| **D** | Divider — asset-class stock background | build (duotone) | pick / confirm stock photo |
| **P** | Property photo (+ focal point) | stamp | upload / select + focal |
| **M** | Map or chart image | stamp | see *Data sources* below |
| **X** | Data build — rendered from property facts | build | enter / confirm data |

## Full ordered outline

`✅` = builder complete · `▢` = builder to do · mandatory pages can't be excluded.

| # | Page | Type | Mandatory | Status | Notes |
|---|---|---|:--:|:--:|---|
| **Front matter** ||||||
| 1 | Cover | X + P | ✔ | ✅ | property name/address over hero |
| 2 | Disclaimer | B | ✔ | ✅ | activity-ID stamp only |
| ~~3~~ | ~~Presented By~~ | — | — | — | **dropped — redundant (off by default)** |
| ~~4~~ | **Executive Summary** | X | ✔ | ✅ | letter format; sits after Disclaimer → page 3 |
| ~~5~~ | Table of Contents | X | ✔ | ✅ | generated **last** from surviving pages |
| **§1 The M&M Advantage** — *optional* ||||||
| 5 | Divider | D | | ▢ | |
| 6–9 | Welcome / Mission / Advantage / Specialists | B | | ✅ | locked |
| 10–11 | Track Record / Year Stats | A | | ✅ | yearly |
| 12 | Property-type Rank | A ⚑ | | ✅ | multifamily→office/retail |
| 13–18 | Website / Research / Insights / Capital / MMCC | B | | ✅ | locked |
| **§2 Team Overview & Resumes** — *always included; varies by team* ||||||
| 19 | Divider | D + T | ✔ | ▢ | |
| 20 | Advisor Bios | T | ✔ | ▢ | repeatable per advisor |
| **§3 Marketing Plan** — *optional* ||||||
| 21 | Divider | D | | ▢ | |
| 22–23 | Max Exposure / Comprehensive | B | | ✅ | locked |
| **§4 Investment Overview** — *core, mandatory* ||||||
| 24 | Divider | D | ✔ | ▢ | |
| 25 | Property Summary | X + P | ✔ | ✅ | |
| 26–28 | Regional / Local / Retailer Maps | M | | ▢ | Google Maps |
| 29 | Photo Grid | P ×4–5 | | ✅ (stamp) | |
| **§5 Financial Analysis** — *mandatory* ||||||
| 30 | Divider | D | ✔ | ▢ | |
| 31 | Operating Statement | X | ✔ | ✅ | house-style table from proforma OpEx |
| 32 | Cash Flow Projection | X | ✔ | ✅ | house-style table from proforma |
| **§6 Sale Comparables** — *core, mandatory* ||||||
| 33 | Divider | D | ✔ | ▢ | |
| 34 | Comps Map | M | | ✅ | Google Maps (geocoded pins) + orange-pin legend |
| 35 | Sale Comps Summary | X | ✔ | ✅ | |
| 36 | Chart | M | | ▢ | from Excel data |
| 37–38 | Sale Comps Detail | X + P | | ✅ | |
| **§7 Rent Comparables** — *multifamily; N/A for land* ||||||
| 39 | Divider | D | | ▢ | |
| 40 | Rent Comps Map | M | | ✅ | Google Maps (geocoded pins) + orange-pin legend |
| 41 | Rent Comps Summary | X | | ✅ | |
| 42–43 | Charts | M | | ▢ | from Excel data |
| 44–45 | Rent Comps Charts | X + P | | ✅ | |
| **§8 Market Overview** — *optional, per metro* ||||||
| 46 | Divider | D | | ▢ | |
| 47–49 | Metro Overview / Economy / Demographics | V + P | | ▢ | pre-built per market |
| 50–52 | Demographic Charts | M | | ▢ | from Excel/data |
| **Back** ||||||
| 53 | Back Cover | T + P | ✔ | ▢ | per advisor |

## Data sources

- **Property photos (P)** — operator uploads/selects; each frame carries a focal
  point so varied aspect ratios crop without decapitating buildings.
- **Team & contacts (T)** — standard headshots + contact info arrive as
  **structured data**; the model composes presented-by, bios, and back cover from
  it. Operator picks who's on the deal.
- **Maps (M, geographic)** — **Google Maps API** to generate regional/local/
  retailer/comp maps per run (roadmap). *Interim:* manual upload + stamp.
- **Financial charts & tables (M/X)** — *interim:* an **Excel data dump that
  matches the target slide format**; the model reads it and drops values in.
  *Roadmap:* read directly from the team's full underwriting Excel models. As
  structured data lands, financial pages can migrate from stamped images (M) to
  rendered tables (X).
- **Facts (X)** — property fact sheet + broker's thesis notes. The model
  **rewrites into house voice at measured length; it never authors the
  investment case and never states a number absent from the facts** (`copyfit`).

## Asset-class behavior

- Switching asset class swaps the **core** — §4 offering metrics, §6/§7 comps
  columns (a land deal replaces per-unit/rent metrics with lot/zoning/FAR/BSF and
  drops the whole rent-comparables section).
- It also sets **default divider backgrounds** so section photos read as the
  right property type. Dividers are rebuilt at run time: the chosen stock photo
  is composited full-bleed under the corporate **navy duotone**, then the section
  eyebrow/title/subtitles and logo are drawn on top. Any asset-class-tagged photo
  can be used — no fixed pre-baked set.

## Executive Summary spec (page 4a)

A one-page letter, always included, directly after the TOC. Reuses the house
design system (same two-tone head, colors, fonts, footer as the built plates).

- **Head:** `EXECUTIVE SUMMARY // {PROPERTY}` — navy prefix + orange suffix,
  letter-spaced, with the standard rule.
- **Eyebrow:** `{BUILDING NAME} · {CITY, STATE}` in orange, letter-spaced.
- **Attention block** (right-aligned): `Attn: {name}, {title}` / `{company}` /
  `{street} · {city, state zip}` / `{Month Year}`.
- **Salutation:** `Dear {first},` in the display face.
- **Body:** 4–5 house-voice paragraphs from the fact sheet + broker notes —
  positioning, physical/leasing description, the valuation range + guidance + NOI
  + cap-rate (all traceable to facts), and the buyer-network close.
- **Signature:** `Sincerely,` / `{Advisor Name}` (display bold) /
  `{titles}` in orange.
- **Footer:** `{n} | EXECUTIVE SUMMARY`.

## Renumbering & inserts

The assembler processes an ordered list; each entry has an `include` flag and a
payload. It renumbers footers from the running count of *included* pages, so
inserts (Executive Summary, land pages) and exclusions both resolve correctly.
Superseded footer text under the restamp will be stripped so exported PDFs are
text-correct, not just visually correct.
