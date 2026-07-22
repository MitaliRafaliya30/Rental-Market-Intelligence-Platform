# Dataset Overview — Phase 3 Data Discovery

**Project:** Rental Market Intelligence Platform
**Source:** NYC Airbnb (Inside Airbnb–style export)
**Snapshot date:** 01 August 2025 (scrape timestamps `2025-08-02` → `2025-08-03`)
**Prepared:** 2026-07-14
**Scope:** Discovery & profiling only. No cleaning, transformation, or modelling performed.

All figures below are measured directly from the raw files with pandas 3.0.3 / Python 3.13.7. Where a value could not be verified from the data, that is stated explicitly.

---

## 1. Files at a glance

| Dataset | Rows (data) | Columns | File size on disk | In-memory (deep) | Grain |
|---|---:|---:|---:|---:|---|
| `listings.csv` | 36,403 | 79 | 76,996,955 B (≈ 73.4 MB) | ≈ 142.7 MB | One row per listing |
| `calendar.csv` | 13,287,103 | 7 | 474,237,645 B (≈ 452.3 MB) | ≈ 1.84 GB | One row per listing per calendar date |
| `reviews.csv` | 977,459 | 6 | 306,884,115 B (≈ 292.7 MB) | ≈ 491.4 MB | One row per review event |

> **Note on row counts:** `listings.csv` contains embedded newlines inside free-text fields (`description`, `host_about`, `amenities`, etc.). A naive line count (`wc -l`) reports 77,866 lines, but the true parsed record count is **36,403**. Always parse with a proper CSV reader, not line counting.

---

## 2. `listings.csv`

- **Rows:** 36,403
- **Columns:** 79
- **File size:** 76,996,955 bytes (≈ 73.4 MB)
- **In-memory footprint (deep):** ≈ 142.7 MB
- **Grain:** One row = one Airbnb listing as observed in the 01-Aug-2025 scrape. `id` is unique across all rows (0 duplicates).
- **Purpose:** The **master / dimension-like table** describing each property and its host. Holds descriptive attributes (location, room/property type, capacity, amenities), host attributes (tenure, response behaviour, superhost status), pre-aggregated review scores, availability windows, and a single current listed `price`. This is the anchor table both other datasets reference.

---

## 3. `calendar.csv`

- **Rows:** 13,287,103
- **Columns:** 7
- **File size:** 474,237,645 bytes (≈ 452.3 MB)
- **In-memory footprint (deep):** ≈ 1.84 GB
- **Grain:** One row = the availability state of one listing on one calendar date. Coverage is exactly **365 dates per listing** (36,403 listings × 365 = 13,287,095; the file has 13,287,103, i.e. a handful of listings carry a small number of extra dated rows).
- **Date range:** `2025-08-02` → `2026-08-02` (a forward-looking 12-month booking calendar).
- **Purpose:** The **daily availability fact table**. It records, for the year ahead, whether each listing is available (`t`) or not (`f`) on each night, plus the minimum/maximum-nights rule in force for that date.
- **Critical limitation:** `price` and `adjusted_price` are **100% NULL** in this snapshot (see [data_quality_report.md](data_quality_report.md)). Calendar therefore provides *availability* but **not** per-night pricing.

---

## 4. `reviews.csv`

- **Rows:** 977,459
- **Columns:** 6
- **File size:** 306,884,115 bytes (≈ 292.7 MB)
- **In-memory footprint (deep):** ≈ 491.4 MB
- **Grain:** One row = one guest review left on a listing. `id` (review id) is unique (0 duplicates).
- **Date range:** `2009-05-25` → `2025-08-02`.
- **Distinct listings reviewed:** 25,093 (68.9% of all listings have ≥1 review).
- **Distinct reviewers:** 861,113.
- **Purpose:** The **review event fact table**. Because Airbnb only allows a review after a completed stay, each review is a proxy signal for a *booked & completed reservation*, which is the basis for demand / occupancy estimation.

---

## 5. Relationship summary (high level)

```
listings (1) ──< calendar (many)     via listing_id = listings.id   [exact 1:1 coverage of listing set]
listings (1) ──< reviews  (many)     via listing_id = listings.id   [subset: only reviewed listings]
```

- Every `calendar.listing_id` and every `reviews.listing_id` resolves to an existing `listings.id` — **0 orphan foreign keys** in either file.
- `calendar` covers **all** 36,403 listings; `reviews` covers the **25,093** listings that have received at least one review.

Full detail in [relationship_analysis.md](relationship_analysis.md).
