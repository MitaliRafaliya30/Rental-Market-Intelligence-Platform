# Data Profiling — Phase 3 Data Discovery

All numbers are measured from the raw files. Percentages are of total data rows for that dataset.

---

## 1. `listings.csv` (36,403 rows × 79 cols)

- **Duplicate rows:** 0
- **Duplicate `id`:** 0 → `id` is a valid primary key
- **In-memory (deep):** ≈ 142.7 MB

### 1.1 Missing values — high-null columns

| Column | Nulls | % Null |
|---|---:|---:|
| calendar_updated | 36,403 | 100.00 |
| license | 30,937 | 84.98 |
| neighbourhood | 17,335 | 47.62 |
| neighborhood_overview | 17,336 | 47.62 |
| host_about | 15,439 | 42.41 |
| price | 15,124 | 41.55 |
| estimated_revenue_l365d | 15,124 | 41.55 |
| beds | 14,908 | 40.95 |
| bathrooms | 14,857 | 40.81 |
| host_acceptance_rate | 14,559 | 39.99 |
| host_response_rate | 14,531 | 39.92 |
| host_response_time | 14,531 | 39.92 |
| review_scores_* (7 cols) | ~11,310–11,348 | ~31.1 |
| first_review / last_review / reviews_per_month | 11,310 | 31.07 |
| host_location | 7,575 | 20.81 |
| host_neighbourhood | 7,392 | 20.31 |
| bedrooms | 5,920 | 16.26 |
| has_availability | 5,657 | 15.54 |

Columns with **0 nulls** include: `id`, `listing_url`, `scrape_id`, `last_scraped`, `source`, `host_id`, `neighbourhood_cleansed`, `neighbourhood_group_cleansed`, `latitude`, `longitude`, `property_type`, `room_type`, `accommodates`, `amenities`, `minimum_nights`, `maximum_nights`, all `availability_*`, all `number_of_reviews*`, `estimated_occupancy_l365d`, `instant_bookable`, and the `calculated_host_listings_count*` family.

> **Notable coupling:** `price` and `estimated_revenue_l365d` share the *same* 15,124 null rows — revenue is only computed where a price exists.
> The 7 `review_scores_*`, `first_review`, `last_review`, and `reviews_per_month` share ~11,310 nulls — these are exactly the listings with **no reviews** (36,403 − 25,093 reviewed = 11,310).

### 1.2 Cardinality (selected)

| Column | Distinct | Note |
|---|---:|---|
| id | 36,403 | unique key |
| host_id | 21,643 | many listings per host |
| scrape_id | 1 | constant |
| source | 2 | city scrape / previous scrape |
| neighbourhood_group_cleansed | 5 | boroughs |
| neighbourhood_cleansed | 223 | neighbourhoods |
| property_type | 74 | detailed taxonomy |
| room_type | 4 | core segment |
| neighbourhood (raw) | 1 | effectively useless (only "Neighborhood highlights") |
| has_availability | 1 | only `t` (rest null) |
| license | 1,978 | mostly null / `Exempt` |

### 1.3 Numeric statistics (selected)

| Column | mean | std | min | 25% | 50% | 75% | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| accommodates | 2.74 | 1.87 | 1 | 2 | 2 | 4 | 16 |
| bedrooms | 1.39 | 0.94 | 0 | 1 | 1 | 2 | 16 |
| beds | 1.63 | 1.20 | 0 | 1 | 1 | 2 | 40 |
| bathrooms | 1.19 | 0.56 | 0 | 1 | 1 | 1 | 15.5 |
| minimum_nights | 28.6 | 29.3 | 1 | 30 | 30 | 30 | 1,124 |
| maximum_nights | 60,108 | 1.13e7 | 1 | 130 | 365 | 1,125 | 2,147,483,647 |
| availability_365 | 161.7 | 147.3 | 0 | 0 | 153 | 318 | 365 |
| number_of_reviews | 26.9 | 68.4 | 0 | 0 | 3 | 22 | 3,518 |
| estimated_occupancy_l365d | 47.2 | 85.0 | 0 | 0 | 0 | 60 | 255 |
| estimated_revenue_l365d | 14,782 | 97,335 | 0 | 0 | 0 | 18,000 | 12,763,260 |
| review_scores_rating | 4.73 | 0.45 | 0 | 4.65 | 4.86 | 5.0 | 5.0 |
| reviews_per_month | 0.82 | 1.88 | 0.01 | 0.08 | 0.25 | 0.92 | 123.87 |

**`price` (parsed from `$` string, non-null only, n=21,279):**

| mean | std | min | 25% | 50% | 75% | max |
|---:|---:|---:|---:|---:|---:|---:|
| 447.87 | 3,174.21 | 3 | 90 | 150 | 257 | 50,052 |

`price == 0`: 0 rows. (See outliers in [data_quality_report.md](data_quality_report.md).)

### 1.4 Categorical distributions (selected)

**room_type**

| value | count |
|---|---:|
| Entire home/apt | 19,328 |
| Private room | 16,469 |
| Hotel room | 378 |
| Shared room | 228 |

**neighbourhood_group_cleansed (borough)**

| borough | count |
|---|---:|
| Manhattan | 16,225 |
| Brooklyn | 13,322 |
| Queens | 5,336 |
| Bronx | 1,155 |
| Staten Island | 365 |

**host_is_superhost**: f = 28,842 · t = 7,147 · NULL = 414
**instant_bookable**: f = 29,000 · t = 7,403
**host_identity_verified**: t = 31,642 · f = 4,748 · NULL = 13
**source**: city scrape = 21,552 · previous scrape = 14,851

### 1.5 Date ranges

| Column | Min | Max | Nulls |
|---|---|---|---:|
| last_scraped | 2025-08-02 | 2025-08-03 | 0 |
| host_since | 2008-08-11 | 2025-07-30 | 13 |
| first_review | 2009-05-25 | 2025-08-01 | 11,310 |
| last_review | 2011-05-12 | 2025-08-02 | 11,310 |
| calendar_last_scraped | 2025-08-02 | 2025-08-03 | 0 |

### 1.6 Sample record (row 0, abridged)

```
id=2539 · name="Superfast Wi-Fi. Clean & quiet home by the park"
host_id=2787 · host_since=2008-09-07 · host_is_superhost=f
neighbourhood_group_cleansed=Brooklyn · neighbourhood_cleansed=Kensington
lat=40.64529 · lon=-73.97238 · room_type=Private room · property_type=Private room in condo
accommodates=2 · bedrooms=1 · beds=1 · bathrooms_text="1 shared bath"
price=$260.00 · minimum_nights=30 · maximum_nights=730 · availability_365=365
number_of_reviews=9 · review_scores_rating=4.89 · estimated_occupancy_l365d=0
```

---

## 2. `calendar.csv` (13,287,103 rows × 7 cols)

- **In-memory (deep):** ≈ 1.84 GB
- **Distinct listing_id:** 36,403 (== full listings set)
- **Rows per listing:** ≈ 365 (forward 12-month calendar)

### 2.1 Missing values

| Column | Nulls | % Null |
|---|---:|---:|
| listing_id | 0 | 0.00 |
| date | 0 | 0.00 |
| available | 0 | 0.00 |
| **price** | 13,287,103 | **100.00** |
| **adjusted_price** | 13,287,103 | **100.00** |
| minimum_nights | 0 | 0.00 |
| maximum_nights | 0 | 0.00 |

### 2.2 Distributions & ranges

- **available:** `f` = 7,399,750 (55.7%) · `t` = 5,887,353 (44.3%)
- **date range:** 2025-08-02 → 2026-08-02
- **minimum_nights:** min 1 · max 1,124
- **price / adjusted_price:** no parseable values at all (0 of 13.29M rows parse to a number)

### 2.3 Sample records

| listing_id | date | available | price | adjusted_price | minimum_nights | maximum_nights |
|---|---|---|---|---|---|---|
| 2539 | 2025-08-03 | t | (null) | (null) | 30 | 730 |
| 2539 | 2025-08-04 | t | (null) | (null) | 30 | 730 |
| 2539 | 2025-08-05 | t | (null) | (null) | 30 | 730 |

---

## 3. `reviews.csv` (977,459 rows × 6 cols)

- **In-memory (deep):** ≈ 491.4 MB
- **Duplicate review `id`:** 0
- **Distinct listing_id:** 25,093
- **Distinct reviewer_id:** 861,113

### 3.1 Missing values

| Column | Nulls | % Null |
|---|---:|---:|
| listing_id | 0 | 0.00 |
| id | 0 | 0.00 |
| date | 0 | 0.00 |
| reviewer_id | 0 | 0.00 |
| reviewer_name | 4 | 0.0004 |
| comments | 260 | 0.027 |

(+ the 260 `comments` include blank/whitespace-only bodies counted as empty.)

### 3.2 Ranges

- **date range:** 2009-05-25 → 2025-08-02 (16+ years of history)
- **reviewers:** 861,113 distinct → most guests review once; small repeat-guest tail.

### 3.3 Sample records

| listing_id | id | date | reviewer_id | reviewer_name | comments (truncated) |
|---|---|---|---|---|---|
| 2539 | 55688172 | 2015-12-04 | 25160947 | Peter | "Great host " |
| 2539 | 97474898 | 2016-08-27 | 91513326 | Liz | "Nice room for the price. Great neighborhood…" |
| 2539 | 105340344 | 2016-10-01 | 90022459 | Евгений | "Very nice apt. New remodeled." |

> `comments` contains multilingual, emoji, and multi-line UTF-8 content — encoding must be handled as UTF-8 end-to-end.
