{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    fact_review
    -----------
    Grain: one row per review (deduplicated).
    Source: silver_reviews (~1M distinct reviews).

    Reviews are our demand proxy and only true long-term time series
    (dating back to 2009). This fact answers demand-over-time questions.

    Two dates, two roles:
      review_date    = when the stay was reviewed (drives time-series
                       analysis; joins to dim_date as the review night)
      _snapshot_date = when we captured the review (drives the SCD2
                       join - matches the listing version live at
                       capture time)

    reviewer_id / reviewer_name = DEGENERATE DIMENSION. Kept on the
    fact, no dim_reviewer - 861K mostly-single-occurrence reviewers
    would be a large table serving no business question.

    is_automated flags Airbnb system messages (for future NLP filtering).
*/

with reviews as (

    select * from {{ ref('silver_reviews') }}

),

joined as (

    select
        -- Listing FK: the version live when we captured this review.
        dl.listing_sk,

        -- Date FK: the review date (when the stay was reviewed).
        cast(to_char(r.review_date, 'YYYYMMDD') as integer) as review_date_sk,

        -- Natural key
        r.review_id,
        r.listing_id,
        r.review_date,
        r._snapshot_date,

        -- Degenerate dimension: reviewer, stored directly on the fact
        r.reviewer_id,
        r.reviewer_name,

        -- Review content
        r.comments,
        r.is_automated,

        r.city_key

    from reviews r

    -- SCD2 date-range join on the CAPTURE date (_snapshot_date),
    -- matching the listing version live when we ingested the review.
    inner join {{ ref('dim_listing') }} dl
        on  r.listing_id = dl.listing_id
        and r._snapshot_date >= dl.effective_from
        and r._snapshot_date <  dl.effective_to

)

select * from joined