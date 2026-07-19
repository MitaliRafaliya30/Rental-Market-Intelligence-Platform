{{
    config(
        materialized = 'incremental',
        incremental_strategy= 'delete+insert',
        unique_key= ['listing_id', '_snapshot_date'],
        tags = ['silver']
    )
}}

/*
    silver_listings
    ---------------
    Cleans and types the raw Inside Airbnb listings data.

    Grain:  one row per listing per snapshot (listing_id + _snapshot_date)
    Source: bronze.bronze_listings (built via INFER_SCHEMA)
    Output: 55 columns (52 business + 3 metadata)

    Feeds: snap_listing, snap_host, dim_location,
           dim_property_type, fact_listing_snapshot

    Typing philosophy
    -----------------
    Bronze was built with INFER_SCHEMA, so numeric columns are already
    typed as NUMBER / FLOAT. We TRUST that. We only transform columns
    that actually need it:
      - text columns cast to their real type (dates, json)
      - text columns cleaned via macros (price, %, booleans, bathrooms)
    A bare column name below means "already correctly typed - use as is".
    A macro or cast means "this genuinely needed work". The code shows
    its own data-quality decisions.

    This model fixes what is WRONG. It does not decide what is USEFUL.
    No joins, no aggregations, no business logic, no imputation.
    Every transformation is row-independent - safe to run incrementally.
*/

with source as (

    select * from {{ source('bronze', 'bronze_listings') }}

),

cleaned as (

    select

        -- ============================================
        -- IDENTITY  (already NUMBER)
        -- ============================================
        "id"                                as listing_id,
        "host_id"                           as host_id,

        -- ============================================
        -- LINEAGE / ACTIVITY  (text)
        -- ============================================
        -- 'source' is an activity flag, not scrape bookkeeping.
        -- 'previous scrape' = not found in this scrape, carried
        -- forward from an older run. All 14,851 have no price (100%).
        -- Active listings have 98.7% price coverage. This column
        -- explains our biggest null problem.
        "source"                            as scrape_source,
        "source" = 'city scrape'            as is_active_listing,

        try_to_date("last_scraped")         as last_scraped_date,
        try_to_date("calendar_last_scraped") as calendar_last_scraped_date,

        -- ============================================
        -- LOCATION  (text + already FLOAT)
        -- ============================================
        -- The _cleansed columns are the reliable geo columns. Raw
        -- 'neighbourhood' has 1 distinct value and is dropped.
        "neighbourhood_cleansed"            as neighbourhood,
        "neighbourhood_group_cleansed"      as borough,
        "latitude"                          as latitude,
        "longitude"                         as longitude,

        -- ============================================
        -- PROPERTY  (text + already NUMBER/FLOAT)
        -- ============================================
        "name"                              as listing_name,
        "property_type"                     as property_type,
        "room_type"                         as room_type,
        "accommodates"                      as accommodates,

        -- bathrooms_text (text) is 0.35% null vs 40.81% on the numeric
        -- 'bathrooms' column. Parsing the text recovers 14,730 listings.
        -- We use the text column and DROP the numeric one.
        {{ parse_bathrooms('"bathrooms_text"') }}     as bathrooms,
        {{ parse_bathroom_type('"bathrooms_text"') }} as bathroom_type,

        "bedrooms"                          as bedrooms,
        "beds"                              as beds,

        -- amenities is text holding a JSON-ish array. Parse to VARIANT.
        -- Kept for a future "do amenities drive price?" analysis.
        try_parse_json("amenities")         as amenities,

        -- ============================================
        -- PRICE  (text - needs cleaning)
        -- ============================================
        -- The keystone column. calendar.price is 100% null, so price
        -- history is built by tracking this across snapshots via SCD2.
        {{ clean_price('"price"') }}        as price_usd,

        -- ============================================
        -- BOOKING RULES  (already NUMBER + text bool)
        -- ============================================
        "minimum_nights"                    as minimum_nights,

        -- 2147483647 = 2^31-1, an overflow placeholder meaning "no
        -- maximum". Not a real rule - left alone it poisons every
        -- average (source mean: 60,108). A CORRECTION, not outlier
        -- removal: the value is a lie, not just extreme.
        case
            when "maximum_nights" = 2147483647 then null
            else "maximum_nights"
        end                                 as maximum_nights,

        "instant_bookable" as is_instant_bookable,

        -- ============================================
        -- HOST  (text + already FLOAT)
        -- ============================================
        "host_name"                         as host_name,
        try_to_date("host_since")           as host_since_date,

         "host_is_superhost" as is_superhost,
        "host_identity_verified" as is_host_identity_verified,

        "host_response_time"                as host_response_time,
        {{ clean_percentage('"host_response_rate"') }}   as host_response_rate_pct,
        {{ clean_percentage('"host_acceptance_rate"') }} as host_acceptance_rate_pct,

        -- Airbnb-reported, includes listings in other cities, so it
        -- cannot be derived here. The calculated_* columns CAN be and
        -- are dropped.
        "host_listings_count"               as host_listings_count,
        "host_total_listings_count"         as host_total_listings_count,

        -- ============================================
        -- AVAILABILITY  (already NUMBER - measures, never SCD2)
        -- ============================================
        -- availability_eoy dropped: "nights until end of year" means
        -- 5 months in August, 1 month in December. Meaning shifts with
        -- measurement date, so not comparable across snapshots.
        "availability_30"                   as availability_30,
        "availability_60"                   as availability_60,
        "availability_90"                   as availability_90,
        "availability_365"                  as availability_365,

        -- ============================================
        -- DEMAND PROXIES  (already NUMBER/FLOAT + text dates)
        -- ============================================
        -- No booking data exists publicly. Reviews are a lower-bound
        -- proxy for completed stays.
        "number_of_reviews"                 as number_of_reviews,
        "number_of_reviews_ltm"             as number_of_reviews_ltm,
        "number_of_reviews_l30d"            as number_of_reviews_l30d,
        "number_of_reviews_ly"              as number_of_reviews_ly,
        "reviews_per_month"                 as reviews_per_month,

        try_to_date("first_review")         as first_review_date,
        try_to_date("last_review")          as last_review_date,

        -- ============================================
        -- VENDOR ESTIMATES  (already NUMBER/FLOAT)
        -- ============================================
        -- Inside Airbnb's modelled estimates, NOT observed bookings.
        -- Renamed to expose units. Never label as actuals downstream.
        "estimated_occupancy_l365d"         as estimated_occupancy_nights_l365d,
        "estimated_revenue_l365d"           as estimated_revenue_usd_l365d,

        -- ============================================
        -- REVIEW SCORES  (already FLOAT)
        -- ============================================
        -- ~31% null on all 7 is STRUCTURAL, not a defect - exactly the
        -- 11,310 listings with zero reviews. A null score for an
        -- unreviewed listing is correct. Never impute.
        "review_scores_rating"              as review_scores_rating,
        "review_scores_accuracy"            as review_scores_accuracy,
        "review_scores_cleanliness"         as review_scores_cleanliness,
        "review_scores_checkin"             as review_scores_checkin,
        "review_scores_communication"       as review_scores_communication,
        "review_scores_location"            as review_scores_location,
        "review_scores_value"               as review_scores_value,

        -- ============================================
        -- METADATA (passthrough - never transformed)
        -- ============================================
        -- _snapshot_date is the incremental watermark AND the SCD2
        -- effective date. Arrives from Bronze correct, leaves untouched.
        _source_filename                    as _source_filename,
        _loaded_at                          as _loaded_at,
        _snapshot_date                      as _snapshot_date

    from source

)

select * from cleaned

{% if is_incremental() %}

    -- Incremental run: only process snapshots newer than what's
    -- already loaded. On the very first run this block is skipped
    -- and the full table is built.
    -- delete+insert then replaces any matching snapshot, making
    -- re-loads idempotent (a retry can't create duplicates).
    where _snapshot_date > ( SELECT MAX(_snapshot_date) FROM {{ this }})

{% endif %}