{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    fact_listing_snapshot
    ---------------------
    Grain: one row per listing per snapshot.

    SCD2 fact join - the DATE-RANGE approach:
      We do NOT generate listing_sk from listing_id + snapshot_date,
      because SCD2 only creates a dimension version when something
      CHANGES. Unchanged listings have one version spanning multiple
      snapshots, so a generated per-snapshot SK would orphan.

      Instead we join each fact to the dimension VERSION whose
      effective date range contains the fact's snapshot date:
        snapshot_date >= effective_from AND < effective_to
      This resolves BOTH unchanged listings (one version spanning the
      range) and changed listings (the right version per snapshot).
      Then we pull the real listing_sk from the matched version.
*/

with listings as (

    select * from {{ ref('silver_listings') }}

),

joined as (

    select
        -- Real surrogate keys pulled from the matched dimension version
        dl.listing_sk,
        dh.host_sk,
        dloc.location_sk,

        cast(to_char(l._snapshot_date, 'YYYYMMDD') as integer) as snapshot_date_sk,

        l.listing_id,
        l._snapshot_date,

        -- Measures: availability
        l.availability_30,
        l.availability_60,
        l.availability_90,
        l.availability_365,

        -- Measures: demand proxies
        l.number_of_reviews,
        l.number_of_reviews_ltm,
        l.number_of_reviews_l30d,
        l.number_of_reviews_ly,
        l.reviews_per_month,

        -- Measures: vendor estimates
        l.estimated_occupancy_nights_l365d,
        l.estimated_revenue_usd_l365d,
        round(1 - (l.availability_365 / 365.0), 4) as estimated_occupancy_rate,

        -- Measures: review scores
        l.review_scores_rating,
        l.review_scores_accuracy,
        l.review_scores_cleanliness,
        l.review_scores_checkin,
        l.review_scores_communication,
        l.review_scores_location,
        l.review_scores_value,

        l.city_key

    from listings l

    -- SCD2 date-range join to the correct listing version
    inner join {{ ref('dim_listing') }} dl
        on  l.listing_id = dl.listing_id
        and l._snapshot_date >= dl.effective_from
        and l._snapshot_date <  dl.effective_to

    -- SCD2 date-range join to the correct host version
    inner join {{ ref('dim_host') }} dh
        on  l.host_id = dh.host_id
        and l._snapshot_date >= dh.effective_from
        and l._snapshot_date <  dh.effective_to

    -- Location is not SCD2 - simple join on the natural grain
    inner join {{ ref('dim_location') }} dloc
        on  l.city_key       = dloc.city_key
        and l.borough        = dloc.borough
        and l.neighbourhood  = dloc.neighbourhood

)

select * from joined