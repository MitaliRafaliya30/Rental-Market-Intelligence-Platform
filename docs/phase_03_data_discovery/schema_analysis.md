# Schema Analysis — Phase 3 Data Discovery

Data types below are the **types as observed when read raw** (pandas inference), not proposed target types. Where the observed type is wrong for the business meaning (e.g. price read as string), that is flagged and carried into [data_quality_report.md](data_quality_report.md).

**Category legend**
- **Key** — primary identifier of the row
- **FK** — foreign key referencing another dataset
- **Dim** — dimension attribute (descriptive, used to slice/filter/group)
- **Fact** — numeric measure / metric
- **Meta** — operational/technical metadata (scrape bookkeeping, URLs, pre-computed derived fields)

---

## 1. `listings.csv` (79 columns)

| # | Column | Observed type | Description | Business meaning | Category |
|---:|---|---|---|---|---|
| 1 | id | int64 | Airbnb listing id | Primary key of a listing | **Key** |
| 2 | listing_url | str | Web URL of listing | Deep-link; derivable from id | Meta |
| 3 | scrape_id | int64 | Batch id of scrape (single value `20250801203054`) | Load/batch identifier | Meta |
| 4 | last_scraped | str (date) | Date row was scraped (2025-08-02/03) | Snapshot freshness | Meta |
| 5 | source | str | `city scrape` / `previous scrape` | How the record entered this snapshot | Meta |
| 6 | name | str | Listing title | Marketing headline | Dim |
| 7 | description | str | Long free-text description | Listing detail | Dim |
| 8 | neighborhood_overview | str | Host's blurb about the area | Area description | Dim |
| 9 | picture_url | str | Cover photo URL | Media asset | Meta |
| 10 | host_id | int64 | Airbnb host id | FK to host (host is not a separate file, but this groups listings) | **FK** (host) |
| 11 | host_url | str | Host profile URL | Media/link | Meta |
| 12 | host_name | str | Host display name | Host attribute | Dim |
| 13 | host_since | str (date) | Date host joined | Host tenure | Dim |
| 14 | host_location | str | Host's stated location | Host attribute | Dim |
| 15 | host_about | str | Host bio | Host attribute | Dim |
| 16 | host_response_time | str | Bucketed response speed | Host service quality | Dim |
| 17 | host_response_rate | str (`NN%`) | % of enquiries answered | Host service metric (stored as text) | Fact* |
| 18 | host_acceptance_rate | str (`NN%`) | % of requests accepted | Host service metric (stored as text) | Fact* |
| 19 | host_is_superhost | str (`t`/`f`) | Superhost flag | Quality badge (boolean-as-text) | Dim |
| 20 | host_thumbnail_url | str | Host thumbnail | Media | Meta |
| 21 | host_picture_url | str | Host photo | Media | Meta |
| 22 | host_neighbourhood | str | Host's neighbourhood | Host attribute | Dim |
| 23 | host_listings_count | float64 | Host's listing count (Airbnb-reported) | Host portfolio size | Fact |
| 24 | host_total_listings_count | float64 | Host's total listings incl. other types | Host portfolio size | Fact |
| 25 | host_verifications | str (list-like) | Verification methods | Host trust attribute | Dim |
| 26 | host_has_profile_pic | str (`t`/`f`) | Has profile pic | Boolean-as-text | Dim |
| 27 | host_identity_verified | str (`t`/`f`) | Identity verified | Boolean-as-text | Dim |
| 28 | neighbourhood | str | Raw neighbourhood text | Low quality (see below) | Dim |
| 29 | neighbourhood_cleansed | str | Standardised neighbourhood (223 distinct) | Reliable area dimension | Dim |
| 30 | neighbourhood_group_cleansed | str | Borough (5 distinct) | Reliable borough dimension | Dim |
| 31 | latitude | float64 | Latitude | Geo point | Dim |
| 32 | longitude | float64 | Longitude | Geo point | Dim |
| 33 | property_type | str | Detailed property type (74 distinct) | Product taxonomy | Dim |
| 34 | room_type | str | Room type (4 distinct) | Core product segment | Dim |
| 35 | accommodates | int64 | Max guests | Capacity | Fact |
| 36 | bathrooms | float64 | Bathroom count (numeric) | Capacity | Fact |
| 37 | bathrooms_text | str | Bathroom description | Capacity (text form) | Dim |
| 38 | bedrooms | float64 | Bedroom count | Capacity | Fact |
| 39 | beds | float64 | Bed count | Capacity | Fact |
| 40 | amenities | str (list-like) | JSON-ish array of amenities | Feature set | Dim |
| 41 | price | **str** (`$NNN.NN`) | Current nightly listed price | **Core money metric, stored as string** | Fact* |
| 42 | minimum_nights | int64 | Min stay | Booking rule | Fact |
| 43 | maximum_nights | int64 | Max stay | Booking rule | Fact |
| 44 | minimum_minimum_nights | float64 | Min of min-nights over calendar | Derived rule stat | Meta |
| 45 | maximum_minimum_nights | float64 | Max of min-nights over calendar | Derived rule stat | Meta |
| 46 | minimum_maximum_nights | float64 | Min of max-nights over calendar | Derived rule stat | Meta |
| 47 | maximum_maximum_nights | float64 | Max of max-nights over calendar | Derived rule stat | Meta |
| 48 | minimum_nights_avg_ntm | float64 | Avg min-nights next-twelve-months | Derived rule stat | Meta |
| 49 | maximum_nights_avg_ntm | float64 | Avg max-nights next-twelve-months | Derived rule stat | Meta |
| 50 | calendar_updated | float64 | Always NULL | Deprecated field | Meta |
| 51 | has_availability | str (`t`) | Availability flag | Only `t`/NULL present | Dim |
| 52 | availability_30 | int64 | Nights available next 30d | Availability metric | Fact |
| 53 | availability_60 | int64 | Nights available next 60d | Availability metric | Fact |
| 54 | availability_90 | int64 | Nights available next 90d | Availability metric | Fact |
| 55 | availability_365 | int64 | Nights available next 365d | Availability metric | Fact |
| 56 | calendar_last_scraped | str (date) | Calendar scrape date | Freshness | Meta |
| 57 | number_of_reviews | int64 | Total reviews all-time | Demand proxy | Fact |
| 58 | number_of_reviews_ltm | int64 | Reviews last 12 months | Recent demand proxy | Fact |
| 59 | number_of_reviews_l30d | int64 | Reviews last 30 days | Very recent demand | Fact |
| 60 | availability_eoy | int64 | Nights available to end of year | Availability metric | Fact |
| 61 | number_of_reviews_ly | int64 | Reviews last year | Demand proxy | Fact |
| 62 | estimated_occupancy_l365d | int64 | Airbnb/InsideAirbnb occupancy est. (nights) | **Pre-computed occupancy** | Fact |
| 63 | estimated_revenue_l365d | float64 | Estimated revenue last 365d | **Pre-computed revenue** | Fact |
| 64 | first_review | str (date) | Date of first review | Listing maturity | Dim |
| 65 | last_review | str (date) | Date of last review | Recency of activity | Dim |
| 66 | review_scores_rating | float64 | Overall rating (0–5) | Quality metric | Fact |
| 67 | review_scores_accuracy | float64 | Accuracy sub-score | Quality metric | Fact |
| 68 | review_scores_cleanliness | float64 | Cleanliness sub-score | Quality metric | Fact |
| 69 | review_scores_checkin | float64 | Check-in sub-score | Quality metric | Fact |
| 70 | review_scores_communication | float64 | Communication sub-score | Quality metric | Fact |
| 71 | review_scores_location | float64 | Location sub-score | Quality metric | Fact |
| 72 | review_scores_value | float64 | Value sub-score | Quality metric | Fact |
| 73 | license | str | STR registration / `Exempt` | Regulatory compliance | Dim |
| 74 | instant_bookable | str (`t`/`f`) | Instant-book flag | Boolean-as-text | Dim |
| 75 | calculated_host_listings_count | int64 | Host listings in this dataset | Host portfolio (computed) | Fact |
| 76 | calculated_host_listings_count_entire_homes | int64 | ‑ entire homes | Host portfolio | Fact |
| 77 | calculated_host_listings_count_private_rooms | int64 | ‑ private rooms | Host portfolio | Fact |
| 78 | calculated_host_listings_count_shared_rooms | int64 | ‑ shared rooms | Host portfolio | Fact |
| 79 | reviews_per_month | float64 | Avg reviews/month | Demand-rate proxy | Fact |

\* **Fact\*** = business measure that is currently stored in a non-numeric form (string with `$` or `%`) and must be cast before use.

---

## 2. `calendar.csv` (7 columns)

| # | Column | Observed type | Description | Business meaning | Category |
|---:|---|---|---|---|---|
| 1 | listing_id | int64 | Listing id | References `listings.id` | **FK / part of Key** |
| 2 | date | str (date) | Calendar night (2025-08-02 → 2026-08-02) | The night being described | **Key (composite with listing_id)** |
| 3 | available | str (`t`/`f`) | Available that night? | Availability state (boolean-as-text) | Fact/Dim |
| 4 | price | float64 | **100% NULL** | Intended per-night price — unusable here | Fact (empty) |
| 5 | adjusted_price | float64 | **100% NULL** | Intended adjusted price — unusable here | Fact (empty) |
| 6 | minimum_nights | int64 | Min stay for this date | Booking rule for the night | Fact |
| 7 | maximum_nights | int64 | Max stay for this date | Booking rule for the night | Fact |

**Composite primary key:** (`listing_id`, `date`).

---

## 3. `reviews.csv` (6 columns)

| # | Column | Observed type | Description | Business meaning | Category |
|---:|---|---|---|---|---|
| 1 | listing_id | int64 | Listing reviewed | References `listings.id` | **FK** |
| 2 | id | int64 | Review id | Primary key of a review | **Key** |
| 3 | date | str (date) | Date review posted | Timeline of demand | Dim/Fact |
| 4 | reviewer_id | int64 | Guest id | Reviewer identity | FK (guest) |
| 5 | reviewer_name | str | Guest first name | Reviewer attribute (4 nulls) | Dim |
| 6 | comments | str | Free-text review body | Sentiment/NLP source (260 nulls/empty) | Dim |

**Primary key:** `id`.
