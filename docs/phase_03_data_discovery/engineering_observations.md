# Data Engineering Observations — Phase 3 Data Discovery

Observations derived from profiling to inform later design. **No warehouse, star schema, or Bronze/Silver/Gold is designed here** — these are candidate ideas only.

---

## 1. Bronze Layer responsibilities (raw ingestion)

- Ingest all three CSVs **as-is**, no casting — preserve `price` as string, booleans as `t`/`f`, calendar `price` nulls, etc.
- **Force UTF-8** read/write end-to-end (reviews contain multilingual + emoji text; a naive cp1252 read fails).
- Use a **proper multiline-aware CSV parser** for `listings` (embedded newlines → line-count ≠ record-count; true count is 36,403).
- Capture ingestion metadata: source filename, load timestamp, `scrape_id` (`20250801203054`), `last_scraped`, row counts for reconciliation.
- Enforce **schema-on-read** column list (79 / 7 / 6) so drift in future snapshots is detected.
- Keep `calendar` partition-friendly (it is 452 MB / 13.3 M rows) — read in chunks or as Parquet.

## 2. Silver Layer cleaning tasks (candidates)

| Task | Columns | Action (later) |
|---|---|---|
| Cast price → numeric | `listings.price` | strip `$` `,`, cast decimal; keep null where absent |
| Cast percentages → numeric | `host_response_rate`, `host_acceptance_rate` | strip `%`, /100 |
| Cast booleans | `host_is_superhost`, `host_has_profile_pic`, `host_identity_verified`, `instant_bookable`, `has_availability`, `calendar.available` | `t/f` → boolean |
| Cast dates | `last_scraped`, `host_since`, `first_review`, `last_review`, `calendar.date`, `reviews.date` | → DATE |
| Parse arrays | `amenities`, `host_verifications` | explode / normalise |
| Handle sentinels | `maximum_nights` & family = 2^31−1 | flag/clip |
| Reconcile bathrooms | `bathrooms` vs `bathrooms_text` | derive numeric from text (text is 0.35% null vs 40.8%) |
| Drop/observe dead columns | `calendar_updated` (100% null), `neighbourhood` (1 val), `scrape_id` (constant) | quarantine |
| Null strategy | price, review_scores, host rates | keep null (do not impute silently); document |
| Calendar price | `calendar.price`, `adjusted_price` | mark unavailable this snapshot; do not fabricate |
| Dedup check | `calendar` (`listing_id`,`date`) | verify the 8 extra rows aren't dup keys |
| Comment filtering | `reviews.comments` | flag automated/canned + empty (260) for NLP |

## 3. Gold Layer candidate metrics

- **Price metrics:** median/mean nightly price by borough / neighbourhood / room_type; price per guest (`price/accommodates`), price per bedroom.
- **Supply metrics:** listing counts and *available* listing counts by geography/type; active vs inactive supply.
- **Availability/occupancy:** `1 − availability_365/365`; adopt `estimated_occupancy_l365d`; availability trend from calendar by month.
- **Demand proxies:** reviews per month, `number_of_reviews_ltm`, new-review velocity by neighbourhood/time.
- **Quality:** avg `review_scores_rating` and sub-scores; superhost share.
- **Revenue (estimate):** `estimated_revenue_l365d` roll-ups (flag as modelled, 41.6% null).

## 4. Candidate dimension tables (derivable — not designed yet)

- **Dim Listing** (from `listings`: id, geo, room/property type, capacity, rules, attributes).
- **Dim Host** (derive from `listings.host_id` + host_* columns; 21,643 hosts).
- **Dim Neighbourhood / Borough** (223 neighbourhoods → 5 boroughs; a clean geo hierarchy).
- **Dim Date** (conforms `calendar.date` 2025-08→2026-08 and `reviews.date` 2009→2025).
- **Dim Guest/Reviewer** (optional, from `reviews.reviewer_id`; 861,113).
- **Dim Property/Room Type** (taxonomy: 74 property → 4 room types).

## 5. Candidate fact tables (candidates)

- **Fact Availability (daily)** — grain (`listing_id`, `date`) from `calendar` (13.3 M rows): `available`, `minimum_nights`, `maximum_nights`. (No price this snapshot.)
- **Fact Review (event)** — grain `reviews.id` (977 K rows): listing, date, reviewer → demand index.
- **Fact Listing Snapshot** — grain (`listing_id`, `scrape_id`) from `listings`: price, availability windows, review scores, estimated occupancy/revenue. Snapshot-typed for future accumulation.

## 6. Incremental loading opportunities

- **`reviews`** is naturally **append-only** by `date` → incremental high-watermark load on `date` / `id` (immutable events).
- **`calendar`** is a **full forward snapshot** per scrape (rolling 12 months) → load as a dated partition set per `scrape_id`; new snapshots replace/append by scrape date rather than row-level upsert.
- **`listings`** → **snapshot per scrape** (SCD-style). This delivery has a single `scrape_id`; future scrapes enable Type-2 history and would finally unlock price-over-time (currently blocked).
- Use `last_scraped` / `scrape_id` / `reviews.date` as watermarks.

## 7. Candidate partition columns

| Dataset | Partition candidate | Rationale |
|---|---|---|
| calendar | `date` (month) | 13.3 M rows, all time-based scans; monthly partitions prune well |
| reviews | `date` (year or year-month) | 16-year span, append-only, time-range queries |
| listings | `scrape_id` / `last_scraped` | snapshot isolation; future multi-snapshot growth |
| (any) | `neighbourhood_group_cleansed` | secondary partition for borough-scoped analytics |

## 8. Candidate clustering / sort columns

| Dataset | Cluster/sort candidate | Rationale |
|---|---|---|
| calendar | `listing_id` (then `date`) | join key + range scans per listing |
| reviews | `listing_id` (then `date`) | per-listing review lookups |
| listings | `neighbourhood_cleansed`, `room_type` | common group-by/filter predicates |
| listings | `id` | primary-key point lookups & joins |

---

### Cross-cutting engineering notes
- **Volume:** calendar ≈ 1.84 GB in memory — prefer Parquet + chunked/columnar processing over full pandas loads.
- **Referential integrity is already clean** (0 orphan FKs both ways) → FK enforcement in Silver is validation, not repair.
- **Pricing is the key data risk:** the only usable price is `listings.price` (41.6% null); calendar price is empty. Any pricing product feature must design around this.
