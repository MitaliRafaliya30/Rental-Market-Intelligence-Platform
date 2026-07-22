{{
    config(
        materialized = 'incremental',
        incremental_strategy = 'append',
        tags = ['silver']
    )
}}

/*
    silver_reviews
    --------------
    Cleans and deduplicates Inside Airbnb review data.

    Grain: one row per review, ever (review_id)
    Source: bronze.bronze_reviews (all VARCHAR - manual DDL)
    Output: 7 business columns + 3 metadata

    Feeds: fact_review

    Why dedup:
      Reviews are events. Each snapshot re-sends all past reviews plus
      new ones (97.8% overlap between Aug and Sep). Without dedup, the
      same review would sit in Silver once per snapshot.

    Dedup rule: keep the EARLIEST snapshot each review appeared in.
      - It's when the review first entered our data (most honest date).
      - It's deterministic, so the model is idempotent.

    Known, monitored trade-off:
      503 reviews had reviewer_name changed between Aug and Sep (mostly
      encoding fixes like Chulgoo<->cheolgu). "Keep earliest" ignores
      these later edits. This is intentional: the changing field is
      cosmetic, and no business question uses it. The meaningful fields
      (comments, date, listing) are immutable. A warn test monitors the
      change volume - if the source ever starts editing comment text,
      we'll see it and revisit.

    This is a FACT feed, not a dimension - no SCD2.
*/

with source as (

    select * from {{ source('bronze', 'bronze_reviews') }}

    {% if is_incremental() %}
        -- Only look at reviews we haven't already stored.
        -- This is the dedup-aware filter: because each snapshot
        -- re-sends old reviews, we skip any review_id already in Silver
        -- rather than filtering by snapshot date.
        where id not in (select review_id from {{ this }})
    {% endif %}

),

cleaned as (

    select

        -- ============================================
        -- KEYS  (VARCHAR in bronze -> cast)
        -- ============================================
        try_to_number(id)                 as review_id,
        try_to_number(listing_id)         as listing_id,
        city_key                          as city_key,
        -- ============================================
        -- REVIEW CONTENT
        -- ============================================
        -- 'date' = when the stay was reviewed. This is the real
        -- time signal for demand-over-time (our only true time series).
        try_to_date(date)                 as review_date,

        -- reviewer_id sits directly on the fact as a degenerate
        -- dimension (861K distinct reviewers, most appear once - not
        -- worth a dimension table).
        try_to_number(reviewer_id)        as reviewer_id,
        reviewer_name                     as reviewer_name,
        comments                          as comments,

        -- ============================================
        -- NLP PREP
        -- ============================================
        -- Flag Airbnb's automated system messages so future sentiment
        -- analysis can skip them. These are not real guest reviews.
        case
            when comments ilike 'The host canceled%'          then true
            when comments ilike 'The reservation was canceled%' then true
            when comments ilike '%automated posting%'          then true
            else false
        end                                 as is_automated,

        -- ============================================
        -- METADATA (passthrough)
        -- ============================================
        _source_filename                    as _source_filename,
        _loaded_at                          as _loaded_at,
        _snapshot_date                      as _snapshot_date

    from source

),

deduplicated as (

    select
        *,
        -- Number the copies of each review, earliest snapshot first.
        row_number() over (
            partition by review_id
            order by _snapshot_date asc
        ) as rn
    from cleaned

)

select
    review_id,
    listing_id,
    review_date,
    reviewer_id,
    reviewer_name,
    comments,
    is_automated,
    city_key,
    _source_filename,
    _loaded_at,
    _snapshot_date
from deduplicated
where rn = 1    -- keep only the earliest copy of each review