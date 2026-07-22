# Business Understanding & Question Validation — Phase 3 Data Discovery

Part A explains *why* the important columns exist and whether they are likely Gold-layer material. Part B tests each target business question against what the data can actually support.

---

## Part A — Business meaning of key columns

| Column | Why it exists | Business questions it supports | Likely in Gold? |
|---|---|---|---|
| `listings.id` | Unique listing identity | All per-listing analysis; join key | ✅ Yes (dim key) |
| `neighbourhood_group_cleansed` | Standardised borough | Supply/price by borough | ✅ Yes (dim) |
| `neighbourhood_cleansed` | Standardised neighbourhood (223) | Fine-grained supply/price geography | ✅ Yes (dim) |
| `latitude` / `longitude` | Precise geolocation | Map viz, spatial clustering | ⚪ Maybe (geo) |
| `room_type` / `property_type` | Product taxonomy | Price/supply by product type | ✅ Yes (dim) |
| `accommodates`, `bedrooms`, `beds`, `bathrooms` | Capacity | Price normalisation (price per guest/bed) | ✅ Yes (dim/measure) |
| `price` | Current nightly rate | **Price questions** (core money metric) | ✅ Yes (fact) — after cast |
| `minimum_nights` / `maximum_nights` | Booking rules | Segment short- vs long-stay supply | ⚪ Maybe |
| `availability_30/60/90/365`, `availability_eoy` | Pre-computed availability windows | Supply/occupancy proxy | ✅ Yes (fact) |
| `estimated_occupancy_l365d` | Vendor occupancy estimate (nights) | **Occupancy** (ready-made) | ✅ Yes (fact) |
| `estimated_revenue_l365d` | Vendor revenue estimate | Revenue analysis | ✅ Yes (fact) — but 41.6% null |
| `number_of_reviews`, `_ltm`, `_l30d`, `_ly`, `reviews_per_month` | Review counts | **Demand proxy** over time windows | ✅ Yes (fact) |
| `review_scores_*` | Quality ratings | Quality vs price/demand | ✅ Yes (fact) |
| `host_is_superhost`, `host_since`, response/acceptance | Host quality/behaviour | Host-quality segmentation | ⚪ Maybe (dim) |
| `license` | STR regulatory status | Compliance analysis | ⚪ Maybe (sparse) |
| `calendar.date` + `available` | Daily availability state | **Time-based supply/occupancy** | ✅ Yes (fact) |
| `calendar.price` | Intended per-night price | Per-night/seasonal pricing | ❌ No — 100% null here |
| `reviews.date` | Review timeline | **Demand over time** (proxy) | ✅ Yes (fact) |
| `reviews.comments` | Review text | Sentiment/NLP (optional) | ⚪ Maybe (NLP) |

---

## Part B — Can we answer the target questions?

Verdict scale: ✅ Yes · 🟡 Partially / with assumptions · ❌ No (not from these datasets).

### Q1. Which neighbourhoods have the highest prices? — ✅ Yes (with caveats)
- **Data:** `listings.price` + `neighbourhood_cleansed` / `neighbourhood_group_cleansed`.
- **How:** cast price from `$` string to numeric, group by neighbourhood, compute median/mean.
- **Caveats / assumptions:**
  - `price` is **41.6% null** (15,124 listings) — the answer covers only the 21,279 priced listings; assume they are representative (unverified).
  - Extreme outliers (max $50,052, std $3,174) → **median** is safer than mean.
  - Price is a *listed* rate, not a *transacted* rate.

### Q2. Which neighbourhoods have the highest supply? — ✅ Yes
- **Data:** count of `listings.id` grouped by neighbourhood/borough (0 nulls on both geo columns).
- **How:** simple count; optionally weight by `availability_365` for *available* supply.
- **Caveats:** "supply" = listed supply in this snapshot; measured perfectly. Borough distribution already visible: Manhattan 16,225 · Brooklyn 13,322 · Queens 5,336 · Bronx 1,155 · Staten Island 365.

### Q3. How do prices change over time? — 🟡 Partially → effectively ❌ for true time series
- **What we *cannot* do:** build a real nightly/seasonal price time series. `calendar.price` and `adjusted_price` are **100% null**, and only **one** listings snapshot exists (no scrape history).
- **What we *can* do (assumption-heavy):** nothing reliable. There is no second time point and no dated price.
- **Verdict:** With only this snapshot, price-over-time **cannot be answered directly.** It becomes answerable only if (a) multiple snapshots are collected over time, or (b) `calendar.price` is re-sourced.

### Q4. Can occupancy be estimated? — 🟡 Yes, estimated (not measured)
- **Path A (ready-made):** `listings.estimated_occupancy_l365d` — a vendor-provided estimate in nights (0 nulls). Directly usable.
- **Path B (availability-based):** `1 − availability_365/365` gives a booked-share proxy from `calendar`/listings availability.
- **Path C (review-based / "San Francisco model"):** infer bookings from review frequency (`number_of_reviews_ltm`, `reviews_per_month`) × assumed review rate × avg stay length.
- **Assumptions/limits:** availability≠occupancy (a blocked night may be host-blocked, not booked); review-based models assume a fixed review probability. All three are **estimates**, explicitly not actual bookings.

### Q5. Can demand be estimated? — 🟡 Yes, proxied
- **Data:** `reviews` volume over time (`date`), and listings' `number_of_reviews_*` / `reviews_per_month`.
- **How:** reviews are a lower-bound proxy for completed stays (only a fraction of guests review). Aggregate reviews by month/neighbourhood as a demand index.
- **Assumptions/limits:** review-to-booking ratio is unknown and assumed constant; ignores browsing/enquiry demand and cancelled stays; 31% of listings have no reviews.

### Q6. Which questions cannot be answered directly?
| Question | Status | Blocker |
|---|---|---|
| True **price-over-time / seasonality** | ❌ | `calendar.price` 100% null + single snapshot |
| Actual **bookings / transacted revenue** | ❌ | No reservation/transaction data; only estimates & proxies |
| Actual **occupancy** (vs estimate) | ❌ | No booking records; availability & reviews are proxies |
| **Guest demographics / search demand** | ❌ | No guest profile or search-funnel data |
| **Host revenue actuals** | ❌ | Only `estimated_revenue_l365d` (modelled, 41.6% null) |
| Price **per night by date** | ❌ | Calendar price empty |

---

## Part C — Global assumptions & limitations

1. **Single snapshot (01-Aug-2025).** No historical dimension for listings → no change-over-time on listing attributes/prices.
2. **Listed ≠ transacted.** Prices are asking prices; occupancy/demand are estimates/proxies, never observed bookings.
3. **Calendar contributes availability only** — its price columns are unusable in this delivery.
4. **Coverage gaps:** price (41.6% null), reviews (31% of listings none), host-behaviour rates (~40% null) — subset analyses assume the covered subset is representative (not independently verified).
5. **Outliers present** in price and nights fields; use robust statistics (median/percentiles) until Silver-layer treatment.
