# Data Quality Report — Phase 3 Data Discovery

This document **identifies** issues only. Nothing is fixed. Each issue lists evidence measured from the raw files and a severity to help prioritise Silver-layer work later.

**Severity:** 🔴 High (blocks a business question or corrupts a metric) · 🟠 Medium (needs cleaning, workaround exists) · 🟡 Low (cosmetic / minor).

---

## 1. `listings.csv`

### 1.1 Wrong data types / values-stored-as-text

| # | Issue | Column(s) | Evidence | Severity |
|---|---|---|---|---|
| L1 | **Price stored as string** with `$` and `.00` | `price` | Sample `"$260.00"`; dtype = str | 🔴 |
| L2 | **Percentages stored as string** with `%` | `host_response_rate`, `host_acceptance_rate` | e.g. `"100%"`, `"0%"` | 🟠 |
| L3 | **Booleans stored as text** `t`/`f` | `host_is_superhost`, `host_has_profile_pic`, `host_identity_verified`, `instant_bookable`, `has_availability` | value_counts show `t`/`f` | 🟠 |
| L4 | **List/JSON stored as string** | `amenities`, `host_verifications` | `["Blender", …]`, `['email','phone']` | 🟠 |

### 1.2 Missing values (high null %)

| # | Column | % Null | Note | Severity |
|---|---|---:|---|---|
| L5 | `calendar_updated` | 100.00 | Entirely empty / deprecated — drop candidate | 🟠 |
| L6 | `license` | 84.98 | Mostly missing; `Exempt` = 3,186; regulatory signal weak | 🟠 |
| L7 | `price` | 41.55 | 15,124 listings have **no price** at all | 🔴 |
| L8 | `estimated_revenue_l365d` | 41.55 | Same rows as missing price | 🟠 |
| L9 | `bathrooms` / `beds` | 40.8 / 41.0 | Capacity gaps; `bathrooms_text` has only 0.35% null → better source | 🟠 |
| L10 | `host_response_rate` / `_acceptance_rate` / `_response_time` | ~40 | Host-behaviour metrics sparse | 🟠 |
| L11 | 7× `review_scores_*`, `first_review`, `last_review`, `reviews_per_month` | ~31 | = the 11,310 listings with 0 reviews (structural, not an error) | 🟡 |
| L12 | `neighbourhood`, `neighborhood_overview`, `host_about` | ~42–48 | Free text; low analytical value | 🟡 |

### 1.3 Useless / degenerate columns

| # | Issue | Column | Evidence | Severity |
|---|---|---|---|---|
| L13 | Single-value column | `scrape_id` | 1 distinct value | 🟡 |
| L14 | Raw neighbourhood unusable | `neighbourhood` | 1 distinct value (`"Neighborhood highlights"`) after nulls; use `neighbourhood_cleansed` instead | 🟠 |
| L15 | `has_availability` only `t`/null | `has_availability` | 1 distinct non-null value | 🟡 |

### 1.4 Invalid values & outliers

| # | Issue | Column | Evidence | Severity |
|---|---|---|---|---|
| L16 | **Sentinel / absurd max_nights** | `maximum_nights`, `minimum_maximum_nights`, `maximum_maximum_nights`, `maximum_nights_avg_ntm` | max = 2,147,483,647 (= 2^31−1, integer sentinel) | 🟠 |
| L17 | **Extreme price outliers** | `price` (parsed) | max = 50,052 vs median 150; std 3,174 ≫ mean 448 | 🟠 |
| L18 | **Extreme bed count** | `beds` | max = 40 for accommodates≤16 → suspect | 🟠 |
| L19 | **Zero-value review scores** | `review_scores_*` | min = 0 on a 1–5 scale → likely placeholder, not a real 0 | 🟠 |
| L20 | **`bathrooms` = 0** | `bathrooms` | min = 0 (may be legitimate "0 shared baths" studios — verify) | 🟡 |
| L21 | **Very large `minimum_nights`** | `minimum_nights` | max = 1,124 nights (~3 years) — plausible but extreme | 🟡 |

### 1.5 Consistency

| # | Issue | Detail | Severity |
|---|---|---|---|
| L22 | `bathrooms` (numeric) vs `bathrooms_text` disagree on completeness | numeric 40.8% null, text 0.35% null — two representations of the same fact | 🟠 |
| L23 | `room_type` vs `property_type` redundancy | 74 property types roll up into 4 room types; keep both but define hierarchy | 🟡 |
| L24 | Duplicate rows | **0** duplicate rows and **0** duplicate `id` — no dedup needed here | ✅ |

---

## 2. `calendar.csv`

| # | Issue | Column(s) | Evidence | Severity |
|---|---|---|---|---|
| C1 | **`price` is 100% NULL** | `price` | 13,287,103 / 13,287,103 null | 🔴 |
| C2 | **`adjusted_price` is 100% NULL** | `adjusted_price` | 13,287,103 / 13,287,103 null | 🔴 |
| C3 | **Boolean stored as text** | `available` | values `t`/`f` | 🟠 |
| C4 | `date` stored as string | `date` | needs cast to DATE | 🟠 |
| C5 | Extreme `minimum_nights` | `minimum_nights` | max = 1,124 | 🟡 |
| C6 | Slight grain irregularity | whole file | 13,287,103 rows vs 36,403 × 365 = 13,287,095 → 8 extra dated rows; confirm no per-listing duplicate (`listing_id`,`date`) before use | 🟠 |

> **Consequence of C1/C2:** Calendar cannot contribute *any* pricing information in this snapshot. Any per-night or seasonal pricing analysis must fall back to the single `listings.price`, or the calendar price column must be re-sourced.

---

## 3. `reviews.csv`

| # | Issue | Column(s) | Evidence | Severity |
|---|---|---|---|---|
| R1 | Null / empty `comments` | `comments` | 260 rows null or whitespace-only | 🟡 |
| R2 | Null `reviewer_name` | `reviewer_name` | 4 rows | 🟡 |
| R3 | `date` stored as string | `date` | cast to DATE | 🟠 |
| R4 | Automated / non-guest comments | `comments` | Airbnb inserts canned text (e.g. cancellation notices) — needs filtering for sentiment work (present in Inside Airbnb data generally; flag for Silver) | 🟠 |
| R5 | Duplicate review `id` | `id` | **0** duplicates — clean | ✅ |
| R6 | Orphan foreign keys | `listing_id` | **0** — every review resolves to a listing | ✅ |

---

## 4. Cross-dataset issues

| # | Issue | Detail | Severity |
|---|---|---|---|
| X1 | **Pricing exists in only one place** | `listings.price` (41.6% null) is the *only* price signal; `calendar.price` is empty | 🔴 |
| X2 | Reviewed-listing gap | 11,310 listings (31%) have no reviews → any review-derived demand metric is undefined for them | 🟠 |
| X3 | Snapshot-only | Single 01-Aug-2025 snapshot; no history of `listings` over time → cannot see price/attribute change across scrapes | 🟠 |

---

## 5. Summary counts

| Dataset | Duplicate rows | Duplicate PK | 100%-null columns | Type-mismatch columns |
|---|---:|---:|---:|---:|
| listings | 0 | 0 | 1 (`calendar_updated`) | ≥ 8 (price, 2 rates, 5 booleans, 2 list cols) |
| calendar | (verify C6) | (verify C6) | 2 (`price`, `adjusted_price`) | 2 (`available`, `date`) |
| reviews | 0 | 0 | 0 | 1 (`date`) |
