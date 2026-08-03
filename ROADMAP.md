# Roadmap

Where the BOV Engine is and where it's going. The composition model (every run
starts from the full template; the operator subtracts and customizes) is
specified in `TEMPLATE_OUTLINE.md`. Three stages:

1. **MVP / Prototype** — prove the template can be reproduced from data, and
   assemble a real book end to end. *(current stage)*
2. **Production** — a dependable tool the Anton Group team uses for real deals,
   across deal types, driven from the console.
3. **Full-scale integration** — a service inside the TAG property-intelligence
   AI system: a book is requested with a property id and returns automatically.

Dates are relative to the current working date (2026-08-03).

---

## Stage 1 — MVP / Prototype  *(in progress)*

Goal: given a job description, produce a correct multi-page BOV PDF whose
built pages are indistinguishable from the corporate template.

**Done**
- [x] Compile the corporate IDML into a portable template pack (geometry,
      tokens, colors, image slots).
- [x] Split the corporate master into a 53-page page library.
- [x] Assembler with the four page operations: passthrough, image stamp,
      data build, footer restamp.
- [x] Copy layer: character budgets + numeric/compliance validation.
- [x] Measure/build/correct tooling (`tools/`) that verifies a built page
      against the corporate original to sub-point accuracy.
- [x] Multifamily page builders, each diffed against corporate:
      Property Summary (25), Sale Comps Summary (35), Rent Comps Summary (41),
      Sale Comps Detail (37/38), Rent Comps Charts (44/45).
- [x] Operator console with page/preset selection, roster, photo library with
      focal points, and property intake.

**Remaining for MVP** — a full multifamily book assembled from the
full-template-first model:
- [ ] Full-53 config model: default = all pages ON, per-page `include` flag +
      payload; assembler honors `include:false`.
- [ ] Cover builder (plate 1) — property name + address over the hero photo.
- [ ] Table-of-contents builder (plate 4) — generated last from surviving pages.
- [ ] **Executive Summary** letter page (mandatory insert after TOC) — see spec
      in `TEMPLATE_OUTLINE.md`.
- [ ] Divider builder + navy duotone (8 section dividers, asset-class photo swap
      at run time).
- [ ] Team variant pages from structured headshot+contact data: presented-by
      (3), advisor bios (19–20, always included), back cover (53).
- [ ] Wire the console's **Assemble** button; full-53 checklist grouped by
      section with mandatory locks and per-page editors.
- [ ] Strip the superseded footer text from restamped pages (currently covered
      visually but still present in the PDF text layer).
- [ ] One full multifamily book assembled and reviewed end to end.

*Deferred to production, not MVP:* map generation (Google Maps API) and
financial charts/tables from Excel — MVP stamps manually-provided images.

---

## Stage 2 — Production

Goal: the team produces real client-ready books, for more than one deal type,
without touching code.

- [ ] **Deal-type plate sets.** Select a core plate set by asset class
      (multifamily / land / retail) rather than swapping single pages. Build the
      **land core** against the 2202 Albemarle Road development-site mapping
      (executive summary, zoning pathways, strategies, team experience).
- [ ] **House-voice copy generation.** Rewrite broker notes into house-voice
      prose at measured length, grounded strictly in the fact sheet; few-shot
      examples drawn from closed deals. (The model rewrites; it never authors the
      investment case or invents numbers.)
- [ ] **Pre-rendered combinatorics.** Bake section dividers per asset class,
      metro trios per market, and cover/bio/back per advisor, so nothing that
      varies per property is *designed* at generation time.
- [ ] **Map generation.** Regional/local/retailer/comp maps produced per run via
      the Google Maps API and stamped into their frames (replacing manual upload).
- [ ] **Financial data ingestion.** Read the Excel data dump that matches each
      financial slide and drop values in; migrate applicable financial pages from
      stamped images to rendered tables. *Later:* read directly from the team's
      full underwriting Excel models.
- [ ] **Central asset storage** the build worker can reach (full-res photos,
      focal points, logos, asset-class divider library) — a browser can't re-read
      local disk between sessions.
- [ ] **Preflight & QA.** Copy-fit checks, missing-asset warnings, and a
      page-count/footer-integrity check before export.
- [ ] **Clean output.** Remove buried original images and superseded text so
      files are small and searchable-correct.
- [ ] Licensing clearance for any new divider / asset-class imagery.

---

## Stage 3 — Full-scale integration into TAG property intelligence

Goal: a BOV is a first-class output of the TAG AI system, requested by id and
returned automatically.

- [ ] **Service API** behind `dashboard.aipropertyintelligence.com`. Proposed:

      POST /api/bov/requests  { property_id, preset, asset_class, advisors[],
                                comps:{sale:[],rent:[]}, overrides } -> {request_id}
      GET  /api/bov/requests/:id -> { status, pages, pdf_url, warnings[] }

- [ ] **Console as a dashboard route**, not a standalone file — sharing auth,
      property data, and the asset library with the rest of the platform.
- [ ] **Data auto-population** from the property-intelligence system: facts,
      comparables, metro stats, and demographics filled in automatically, with
      the broker reviewing rather than typing.
- [ ] **Template-reissue resilience.** Re-run the compiler when corporate
      reissues the template; the measure/verify tooling flags any page whose
      geometry moved.
- [ ] Throughput, versioning of generated books, and audit trail.

---

## Open questions

- **Landscape vs. portrait for land BOVs.** Corporate is landscape; dense zoning
  and transit tables read better tall. Decide before building the land core.
- **Console stack & hosting** for the dashboard route.
- **Where full-res originals live** so the build worker can reach them.
