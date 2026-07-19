# Silver Listings — Schema Design

**Project:** Rental Market Intelligence Platform
**Layer:** Silver
**Model:** `silver_listings`
**Source:** `{{ source('bronze', 'bronze_listings') }}`
**Status:** Design approved — implementation pending (Step 4)

---

## 1. Contract

| Property | Value |
|---|---|
| **Grain** | One row per **listing per snapshot** (`listing_id` + `_snapshot_date`) |
| **Source columns** | 79 |
| **Silver columns** | 55 (52 business + 3 metadata) |
| **Dropped** | 27 |
| **Materialization** | `view` (V1) → `incremental` once snapshots accumulate |
| **Joins** | None — source-aligned, single source table |
| **Downstream** | `snap_listing`, `snap_host`, `dim_location`, `dim_property_type`, `fact_listing_snapshot` |

### Why the grain includes `_snapshot_date`

The same listing appears in every monthly snapshot. Listing `2539` in the August file and listing `2539` in the September file are **two different states of the same listing over time**, not duplicate records.

Consequences:

- A `unique` test on `listing_id` alone **will fail**, and should — that is not the grain.
- The correct uniqueness test is `dbt_utils.unique_combination_of_columns(['listing_id', '_snapshot_date'])`.
- `_snapshot_date` is the **incremental watermark** and the **SCD2 effective date**. Everything depends on it.

---

## 2. The Silver / Gold boundary

> **Silver fixes what is _wrong_. Gold decides what is _useful_.**

| Operation | Layer | Why |
|---|---|---|
| Cast `"$260.00"` → `260.00` | Silver | The source misrepresented a number as text — objectively wrong |
| Null the `2147483647` sentinel | Silver | `2^31−1` is a placeholder, not a booking rule — a falsehood |
| Derive `bathrooms` from `bathrooms_text` | Silver | Reconciling two representations of the same fact |
| Compute `price / accommodates` | **Gold** | A business metric someone invented |
| Exclude the `$50,052` outlier | **Gold** | A judgment about relevance, not a correction |
| Classify a neighbourhood as "premium" | **Gold** | Pure business opinion |

**Why the boundary matters:** if business logic leaks into Silver, Silver becomes opinionated. The moment a second consumer wants a different opinion, they bypass Silver and go to Bronze — and now four dashboards report four different median prices. Silver must stay **neutral** to stay **shared**.

---

## 3. Column taxonomy — the SCD2 decision

Not every column that changes belongs in an SCD2 dimension.

> **Test: if this value changes, is it a new _version of the listing_, or a new _measurement of the listing_?**

| Kind | Changes? | Gold destination | Example |
|---|---|---|---|
| **Attribute — tracked** | Slowly, meaningfully | `dim_listing` / `dim_host`, SCD2 versioned | `price_usd`, `is_superhost` |
| **Attribute — untracked** | Rarely or meaninglessly | `dim_listing`, overwritten in place | `listing_name`, `latitude` |
| **Measure** | Every snapshot, by design | `fact_listing_snapshot` | `number_of_reviews`, `availability_365` |

**Why this matters:** `number_of_reviews` changes in almost every snapshot. If it were tracked in `snap_listing`, every listing receiving a single review would fork a new SCD2 version. After ten snapshots the dimension would hold ten versions of nearly every listing, and the *price* changes that matter would be buried under review-count noise. The SCD2 history would degrade into a slow, bloated copy of the fact table.

Silver keeps all three kinds in **one** table (it is source-aligned — one row per listing per snapshot, everything the source said). **Gold splits them.**

---

## 4. KEEP — Identity & lineage (5)

| Bronze | Silver | Type | Kind | Rationale |
|---|---|---|---|---|
| `id` | `listing_id` | `NUMBER` | key | Natural key. 0 nulls, 0 duplicates per snapshot (Phase 3 verified). |
| `last_scraped` | `last_scraped_date` | `DATE` | meta | Record freshness. |
| `source` | `scrape_source` | `VARCHAR` | **tracked** | **Activity flag** — see §9. |
| *(derived)* | `is_active_listing` | `BOOLEAN` | **tracked** | `scrape_source = 'city scrape'`. Enables delisting detection. |
| `calendar_last_scraped` | `calendar_last_scraped_date` | `DATE` | meta | Calendar freshness. |

**On `is_active_listing` being derived in Silver:** this decodes a two-value enum into the boolean it already is — the same category of operation as `t`/`f` → `BOOLEAN`. It is not a business rule. Judgment call; documented as such.

**Why tracked:** when a listing flips from `city scrape` to `previous scrape` between snapshots, SCD2 records the exact snapshot it went inactive — giving **delisting detection and listing churn over time** for free.

---

## 5. KEEP — Listing attributes (14)

| Bronze | Silver | Type | Kind | Notes |
|---|---|---|---|---|
| `name` | `listing_name` | `VARCHAR` | untracked | Renames are cosmetic — tracking would fragment history. |
| `neighbourhood_cleansed` | `neighbourhood` | `VARCHAR` | untracked | 223 distinct, 0 nulls. Feeds `dim_location`. |
| `neighbourhood_group_cleansed` | `borough` | `VARCHAR` | untracked | 5 distinct, 0 nulls. Renamed for readability. |
| `latitude` | `latitude` | `FLOAT` | untracked | A property does not move. |
| `longitude` | `longitude` | `FLOAT` | untracked | As above. |
| `property_type` | `property_type` | `VARCHAR` | **tracked** | 74 distinct. Feeds `dim_property_type`. |
| `room_type` | `room_type` | `VARCHAR` | **tracked** | 4 distinct. See note below. |
| `accommodates` | `accommodates` | `NUMBER` | **tracked** | Capacity change = new listing offer. |
| `bathrooms_text` | `bathrooms` | `DECIMAL(4,1)` | **tracked** | Parsed — see §11. |
| `bathrooms_text` | `bathroom_type` | `VARCHAR` | **tracked** | Parsed — see §11. |
| `bedrooms` | `bedrooms` | `NUMBER` | **tracked** | 16.26% null. Keep nulls explicit. |
| `beds` | `beds` | `NUMBER` | **tracked** | 40.95% null. Keep nulls explicit. |
| `amenities` | `amenities` | `VARIANT` | untracked | `TRY_PARSE_JSON`. Kept as a V2 option (see §12). |
| `price` | `price_usd` | `DECIMAL(10,2)` | **tracked ★** | The reason this project exists. |

### ★ `price_usd` — the keystone column

Phase 3 established that `calendar.price` is **100% NULL**, which killed per-night price-over-time analysis. The recovery plan is to build price history from **listing snapshots tracked via SCD2**. This single column, tracked across monthly snapshots, is that recovery.

`DECIMAL(10,2)` — **not** `FLOAT`. Float comparison in SCD2 change detection produces phantom versions (`260.00` vs `260.0` registering as a change when nothing changed). Fixed precision makes change detection deterministic.

### `room_type` / `property_type` as tracked — rationale

A host converting `Entire home/apt` → `Private room` is a genuine market signal, and in NYC specifically it is how hosts respond to short-term-rental regulation. Tracking it captures that behaviour.

**Accepted risk:** a re-categorisation by Airbnb (rather than by the host) would also fork a version. Judged acceptable — the signal outweighs the noise.

---

## 6. KEEP — Booking rules (3)

| Bronze | Silver | Type | Kind | Notes |
|---|---|---|---|---|
| `minimum_nights` | `minimum_nights` | `NUMBER` | **tracked** | Median = 30 — a fingerprint of NYC's 30-day STR rules. |
| `maximum_nights` | `maximum_nights` | `NUMBER` | **tracked** | Sentinel `2147483647` → `NULL` (issue L16). |
| `instant_bookable` | `is_instant_bookable` | `BOOLEAN` | **tracked** | `t`/`f` → boolean. 0 nulls. |

---

## 7. KEEP — Host attributes (10)

These ten columns feed `snap_host` → `dim_host`.

| Bronze | Silver | Type | Kind | Notes |
|---|---|---|---|---|
| `host_id` | `host_id` | `NUMBER` | key (FK) | 21,643 distinct across 36,403 listings. |
| `host_name` | `host_name` | `VARCHAR` | untracked | Cosmetic. |
| `host_since` | `host_since_date` | `DATE` | untracked | Immutable by definition. |
| `host_is_superhost` | `is_superhost` | `BOOLEAN` | **tracked** | Status change is a real quality signal. |
| `host_response_time` | `host_response_time` | `VARCHAR` | **tracked** | 39.92% null. |
| `host_response_rate` | `host_response_rate_pct` | `DECIMAL(5,2)` | **tracked** | Strip `%`. Scale 0–100. |
| `host_acceptance_rate` | `host_acceptance_rate_pct` | `DECIMAL(5,2)` | **tracked** | Strip `%`. Scale 0–100. |
| `host_identity_verified` | `is_host_identity_verified` | `BOOLEAN` | **tracked** | 13 nulls. |
| `host_listings_count` | `host_listings_count` | `NUMBER` | **tracked** | Airbnb-reported — **includes listings outside this dataset**. Not derivable. |
| `host_total_listings_count` | `host_total_listings_count` | `NUMBER` | **tracked** | As above. |

### Why `host_listings_count` is kept but `calculated_host_listings_count*` is dropped

> **Drop what you can derive. Keep what you cannot.**

`calculated_host_listings_count*` is computed by Inside Airbnb **from this same dataset** — reproducible with `COUNT(*) GROUP BY host_id` in Gold. Storing it is storing a redundant, potentially stale copy.

`host_listings_count` is Airbnb-reported and includes listings in **other cities**. That information does not exist anywhere in this dataset and cannot be derived. Keep it.

---

## 8. KEEP — Measures (17)

All are `fact_listing_snapshot` material. **None are SCD2-tracked** — they change every snapshot by design.

| Bronze | Silver | Type | Notes |
|---|---|---|---|
| `availability_30` | `availability_30` | `NUMBER` | 0 nulls |
| `availability_60` | `availability_60` | `NUMBER` | 0 nulls |
| `availability_90` | `availability_90` | `NUMBER` | 0 nulls |
| `availability_365` | `availability_365` | `NUMBER` | 0 nulls. Occupancy proxy: `1 − availability_365/365` |
| `number_of_reviews` | `number_of_reviews` | `NUMBER` | All-time count |
| `number_of_reviews_ltm` | `number_of_reviews_ltm` | `NUMBER` | Last 12 months — demand proxy |
| `number_of_reviews_l30d` | `number_of_reviews_l30d` | `NUMBER` | Last 30 days |
| `number_of_reviews_ly` | `number_of_reviews_ly` | `NUMBER` | Last year |
| `reviews_per_month` | `reviews_per_month` | `DECIMAL(6,2)` | 31.07% null (structural) |
| `estimated_occupancy_l365d` | `estimated_occupancy_nights_l365d` | `NUMBER` | Vendor estimate, in nights. 0 nulls. Renamed to expose the unit. |
| `estimated_revenue_l365d` | `estimated_revenue_usd_l365d` | `DECIMAL(12,2)` | Vendor estimate. 41.55% null — same rows as `price`. |
| `first_review` | `first_review_date` | `DATE` | Listing maturity |
| `last_review` | `last_review_date` | `DATE` | Activity recency |
| `review_scores_rating` | `review_scores_rating` | `DECIMAL(3,2)` | ~31% null (structural) |
| `review_scores_accuracy` | `review_scores_accuracy` | `DECIMAL(3,2)` | ~31% null |
| `review_scores_cleanliness` | `review_scores_cleanliness` | `DECIMAL(3,2)` | ~31% null |
| `review_scores_checkin` | `review_scores_checkin` | `DECIMAL(3,2)` | ~31% null |
| `review_scores_communication` | `review_scores_communication` | `DECIMAL(3,2)` | ~31% null |
| `review_scores_location` | `review_scores_location` | `DECIMAL(3,2)` | ~31% null |
| `review_scores_value` | `review_scores_value` | `DECIMAL(3,2)` | ~31% null |

> **Structural nulls are not defects.** The ~31% null on all `review_scores_*` / `first_review` / `last_review` / `reviews_per_month` corresponds exactly to the **11,310 listings with zero reviews** (36,403 − 25,093 = 11,310). A null score for an unreviewed listing is *correct*. Never impute.

---

## 9. `scrape_source` — the key finding

### The measurement

```sql
SELECT
    "source",
    COUNT(*) AS total,
    COUNT_IF("price" IS NULL) AS price_null,
    ROUND(100.0 * COUNT_IF("price" IS NULL) / COUNT(*), 2) AS pct_null
FROM BRONZE.BRONZE_LISTINGS
GROUP BY "source";
```

| source | total | price_null | pct_null |
|---|---:|---:|---:|
| `previous scrape` | 14,851 | 14,851 | **100.00** |
| `city scrape` | 21,552 | 273 | **1.27** |

**Reconciliation:** 14,851 + 273 = **15,124** — exactly the total null count measured in Phase 3. Nothing unexplained.

### What it means

`previous scrape` does not mean "scraped earlier." It means **the listing was not found in the current scrape and its record was carried forward from a previous run** — and carried-forward records have no price, 100% of the time, without exception.

### Why this reframes the project

| | Statement |
|---|---|
| **Before** | "Price is 41.6% null. I'll analyse the 21,279 priced listings and assume they're representative — unverified." |
| **After** | "Price is **98.7% populated for actively-scraped listings**. The 14,851 nulls are entirely stale carried-forward records for listings not found in the current scrape — they are not missing data, they are inactive listings. Identified by cross-tabulating price nullity against `source`; counts reconcile exactly." |

The first is a hedge. The second is an **explanation**.

### Downstream consequences

1. **`source` is promoted from Meta to a first-class Silver column.** Phase 3's `schema_analysis.md` classified it as scrape bookkeeping. It is not — it is a listing activity/freshness flag, and it explains the single largest data-quality issue in the dataset.
2. **`business_validation.md` must be corrected.** The claim *"assume they are representative (unverified)"* is now verified and **false** — priced and unpriced listings are not two random halves of one population; they are active vs. stale listings.
3. **Gold gains an informed filtering decision.** Counting stale listings as "supply" would overstate every market by up to 40%. Silver **records** the distinction; Gold **decides** what to do about it — the boundary rule doing real work.
4. **Issue L7 severity drops** from 🔴 to 🟡. The risk was largely an artefact of mixing two record types.

### Open, immaterial

The 273 `city scrape` rows with null price (1.27%) are unexplained. **Materiality judgment: monitor, do not investigate.** A `warn`-severity test, not an engineering effort.

---

## 10. DROP — 27 columns

| Reason | Columns | Justification |
|---|---|---|
| **Structurally empty** | `calendar_updated` | 100% null (L5) |
| **Degenerate** | `scrape_id`, `neighbourhood`, `has_availability` | 1 distinct value each (L13 / L14 / L15). `_snapshot_date` carries `scrape_id`'s meaning better. |
| **Derivable from `id`** | `listing_url`, `host_url` | Zero information |
| **Media / CDN** | `picture_url`, `host_thumbnail_url`, `host_picture_url` | Change meaninglessly → would fork SCD2 versions on every photo swap |
| **Free text, no V1 question** | `description`, `neighborhood_overview`, `host_about` | 42–48% null |
| **Superseded** | `bathrooms` (numeric) | 40.81% null; `bathrooms_text` is 0.35% null — parse that instead (L22) |
| **Derivable in Gold** | `calculated_host_listings_count`, `_entire_homes`, `_private_rooms`, `_shared_rooms` | `COUNT(*) GROUP BY host_id` |
| **Scraper bookkeeping** | `minimum_minimum_nights`, `maximum_minimum_nights`, `minimum_maximum_nights`, `maximum_maximum_nights`, `minimum_nights_avg_ntm`, `maximum_nights_avg_ntm` | Derived stats over the calendar; carry the `2^31−1` sentinel (L16) |
| **Low value** | `host_location` (20.81% null), `host_neighbourhood` (20.31% null), `host_has_profile_pic` (near-constant), `host_verifications` (invalid JSON — single quotes) | |
| **Semantics unstable over time** | `availability_eoy` | ★ see below |
| **No V1 question** | `license` | 84.98% null. Flagged for V2 (NYC STR regulation analysis). |

### ★ `availability_eoy` — dropped for an unusual reason

It means "nights available until end of year." In the **August** snapshot that is a ~5-month window; in the **December** snapshot it is a ~1-month window.

**The column's meaning changes depending on when it was measured**, so comparing it across snapshots is meaningless. `availability_365` is a fixed forward window and *is* comparable.

Dropped because its **semantics are not stable across time** — not because it is null, constant, or redundant.

---

## 11. `bathrooms_text` parser

### Verified vocabulary — 34 distinct values, 6 patterns

| Pattern | Examples | ~Rows | → `bathrooms` | → `bathroom_type` |
|---|---|---:|---|---|
| `N bath` / `N baths` | `1 bath`, `2.5 baths`, `0 baths` | 22,500 | `N` | `unspecified` |
| `N shared bath(s)` | `1 shared bath`, `0 shared baths` | 9,600 | `N` | `shared` |
| `N private bath(s)` | `1 private bath` | 3,900 | `N` | `private` |
| `Half-bath` | | 48 | `0.5` | `unspecified` |
| `Shared half-bath` | | 23 | `0.5` | `shared` |
| `Private half-bath` | | 31 | `0.5` | `private` |
| *(empty)* | | 127 | `NULL` | `NULL` |

Values sum to exactly 36,403. The 127 empties match the Phase 3 measurement of 0.35% null.

### The recovery

| | Nulls | Coverage |
|---|---:|---:|
| `bathrooms` (numeric source column) | 14,857 | 59.2% |
| `bathrooms_text` (parsed) | 127 | **99.65%** |

**Deriving from text recovers 14,730 listings' bathroom counts — 40.5% of the dataset — that a naive pipeline silently loses.**

### Why `bathroom_type` is a three-state enum, not a boolean

The source distinguishes **three** states: `shared`, `private`, and unmarked (`1 bath`). A boolean `is_shared_bathroom` would force the ~22,500 unmarked rows into `true` or `false` — **both are inventions**. The source did not say.

`bathroom_type` records exactly what the source said and nothing more. Gold decides how to treat `unspecified` — that is a judgment, and judgments are Gold's.

### Resolved: `bathrooms = 0` is real (issue L20)

`0 baths` (106 rows) and `0 shared baths` (387 rows) appear as **explicit text values**. The source deliberately states "zero bathrooms" in words for 493 listings. `bathrooms = 0` is **real data, not an artefact** — DEFER confirmed, with evidence rather than assumption.

---

## 12. Design decisions log

| Decision | Chosen | Alternative | Rationale |
|---|---|---|---|
| `bathroom_type` representation | Three-state enum | Boolean `is_shared_bathroom` | ~22,500 rows say only `N bath` — a boolean invents information for 62% of the dataset |
| `amenities` | Keep as `VARIANT` | Drop for V1 | Serves no V1 question, but "do amenities drive price?" is an obvious V2 analysis. `TRY_PARSE_JSON` costs nothing; backfilling later would. |
| `room_type` / `property_type` | SCD2-tracked | Untracked | Host-driven re-categorisation is a real NYC regulatory-response signal. Accepted risk: an Airbnb-side re-categorisation also forks a version. |
| `is_active_listing` derived in Silver | Yes | Defer to Gold | Decodes a two-value enum into the boolean it already is — same category as `t`/`f` → `BOOLEAN`, not a business rule. |
| Percentage scale | `100.00` (0–100) | `1.00` (0–1) | Preserves source semantics; `_pct` suffix makes the scale unambiguous |
| Price precision | `DECIMAL(10,2)` | `FLOAT` | Float comparison in SCD2 produces phantom versions |
| Null handling | Keep explicit | Impute | A null means *unknown*. An imputed median means *we know it's $150* — a fabrication that propagates with no audit trail. |
| Outliers (`$50,052`, `beds = 40`) | Keep, warn-test | Remove in Silver | Removing real data is editorialising. A sentinel is a **lie**; an outlier is **data**. |
| `review_scores_* = 0` | Keep, warn-test | Correct to `NULL` | 4 rows (0.011%), all with reviews. Ambiguous and immaterial → monitor, don't fix. |

---

## 13. Case normalisation

`BRONZE_LISTINGS` was created via `INFER_SCHEMA`, which produced **quoted lowercase identifiers** — every reference requires double quotes (`"price"`, `"source"`). `BRONZE_CALENDAR` and `BRONZE_REVIEWS` were created with hand-written DDL and have normal uppercase identifiers.

This is an inconsistency **inside Bronze**: `INFER_SCHEMA` convenience bought a case-sensitivity tax.

**Resolution:** Silver's explicit `SELECT ... AS` list normalises it away permanently. Nothing downstream of Silver ever types a double quote.

> **Silver is the last place the source's weirdness is allowed to exist.**

---

## 14. Column count

| | Count |
|---|---:|
| Bronze source columns | 79 |
| Dropped | 27 |
| **Silver business columns** | **52** |
| Metadata columns | 3 |
| **Total Silver columns** | **55** |

*Note: the Step 1 design estimated "~45". The actual figure is 55 — the initial estimate under-counted the 17 measure columns. All 17 earn their place as `fact_listing_snapshot` material; the estimate was corrected rather than columns cut to fit it.*

---

## 15. Downstream lineage

```
bronze_listings
      │
      └──► silver_listings ──┬──► snap_listing ──► dim_listing
                             ├──► snap_host    ──► dim_host
                             ├──► dim_location
                             ├──► dim_property_type
                             └──► fact_listing_snapshot
```

`silver_listings` fans out to **five** Gold models. This is the concrete argument for Silver's existence: **clean the price once, and five downstream models inherit it correctly.**

---

## 16. Phase 3 issue disposition — traceability

| Issue | Severity | Disposition | Resolution |
|---|---|---|---|
| L1 — price as `$` string | 🔴 | CAST | `clean_price()` → `DECIMAL(10,2)` |
| L2 — percentages as `%` string | 🟠 | CAST | `clean_percentage()` → `DECIMAL(5,2)`, scale 0–100 |
| L3 — booleans as `t`/`f` | 🟠 | CAST | `clean_boolean()` → `BOOLEAN` |
| L4 — arrays as string | 🟠 | CAST / DROP | `amenities` → `VARIANT`; `host_verifications` dropped (invalid JSON) |
| L5 — `calendar_updated` 100% null | 🟠 | DROP | Structurally empty |
| L6 — `license` 85% null | 🟠 | DROP | No V1 question; flagged for V2 |
| L7 — `price` 41.55% null | 🔴 → 🟡 | **EXPLAINED** | Stale `previous scrape` carry-forwards — see §9 |
| L8 — `estimated_revenue` 41.55% null | 🟠 | KEEP | Same rows as `price`; nulls explicit |
| L9 — `bathrooms` / `beds` ~41% null | 🟠 | RECONCILE / KEEP | `bathrooms` parsed from text (recovers 14,730); `beds` nulls kept explicit |
| L10 — host rate columns ~40% null | 🟠 | KEEP | Nulls explicit |
| L11 — review scores ~31% null | 🟡 | KEEP | **Structural, not a defect** — the 11,310 unreviewed listings |
| L12 — free text 42–48% null | 🟡 | DROP | No V1 question |
| L13 — `scrape_id` constant | 🟡 | DROP | Degenerate; `_snapshot_date` is better |
| L14 — `neighbourhood` degenerate | 🟠 | DROP | Use `neighbourhood_cleansed` |
| L15 — `has_availability` only `t`/null | 🟡 | DROP | Redundant with `availability_365` |
| L16 — `2147483647` sentinel | 🟠 | CORRECT | → `NULL` on `maximum_nights`; sentinel-carrying siblings dropped |
| L17 — price outliers (max $50,052) | 🟠 | DEFER | Real data. Gold decides. Median over mean. |
| L18 — `beds` max 40 | 🟠 | DEFER + warn test | Suspicious, not provably false |
| L19 — `review_scores = 0` | 🟠 → 🟡 | DEFER + warn test | 4 rows, all with reviews. Ambiguous, immaterial. |
| L20 — `bathrooms = 0` | 🟡 | **DEFER — confirmed real** | `0 baths` / `0 shared baths` are explicit source text |
| L21 — `minimum_nights` max 1,124 | 🟡 | DEFER | Extreme but legal under NYC STR rules |
| L22 — `bathrooms` vs `bathrooms_text` | 🟠 | RECONCILE | Parse the text column |
| L23 — `room_type` / `property_type` redundancy | 🟡 | KEEP BOTH | Hierarchy: 74 property types → 4 room types |
| L24 — duplicates | ✅ | NONE | 0 duplicate rows, 0 duplicate `id` |

---

## 17. What `silver_listings` deliberately does **not** do

- **No joins** to `calendar` or `reviews` — coupling models makes debugging a nightmare. Joins are Gold's job.
- **No aggregations** — grain-preserving only.
- **No business metrics** — no `price_per_guest`, no `occupancy_rate`, no `market_tier`.
- **No surrogate keys** — generated in Gold when dimensions are built.
- **No SCD2** — that is `dbt snapshot`, which *reads* this model.
- **No null imputation** — nulls stay explicit.
- **No outlier removal** — only sentinel correction. **A sentinel is a lie; an outlier is data.**

---

## 18. Implementation notes for Step 4

**Row-independence is mandatory.** Every transformation operates on a single row in isolation. Nothing looks at other rows. This is what makes the model safe to run **incrementally** — an incremental run processes only the new snapshot's rows, and a transformation that depended on the full dataset (e.g. "null prices >3σ from the mean") would produce different results depending on batch contents.

**Cast defensively.** `TRY_CAST` / `TRY_TO_NUMBER` / `TRY_TO_DATE` throughout. A hard cast on one malformed row fails the entire model and kills 36,402 good rows. `TRY_` nulls the bad row, loads the rest, and lets a dbt test surface the anomaly — graceful degradation with observability.

**`_snapshot_date` is passthrough.** Never derived, never transformed. It arrives from Bronze correct and leaves Silver untouched. It is the incremental watermark and the SCD2 effective date.

**Macros required (Step 3.5):** `clean_price()`, `clean_boolean()`, `clean_percentage()`, `parse_bathrooms()`, `parse_bathroom_type()`.

---

## 19. Sign-off

| | |
|---|---|
| **Approved by** | Mitali Rafaliya |
| **Grain** | `listing_id` + `_snapshot_date` — confirmed |
| **`amenities`** | Keep as `VARIANT` — confirmed |
| **`room_type` / `property_type`** | SCD2-tracked — confirmed |
| **`bathroom_type`** | Three-state enum — proceeding as designed |
| **Next** | Step 3.5 — macros; Step 4 — `silver_listings.sql` |
