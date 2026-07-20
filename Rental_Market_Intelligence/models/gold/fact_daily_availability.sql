{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    fact_daily_availability
    -----------------------
    Grain: one row per listing per calendar night per snapshot.
    Source: silver_calendar (~13.3M rows per snapshot).

    The measure is is_available. This fact answers occupancy and
    seasonal-demand questions: which nights/months are booked, when
    does a neighbourhood fill up.

    TWO date keys, two meanings:
      date_sk          -> the calendar NIGHT being described
      snapshot_date_sk -> WHEN that availability was captured

    SCD2 join: same date-range pattern as fact_listing_snapshot.
    We join to the listing VERSION live at the _snapshot_date (when
    the availability was captured), using effective_from/to.
*/

with calendar as (

    select * from {{ ref('silver_calendar') }}

),

joined as (

    select
        -- Listing FK: the version live when this was captured.
        dl.listing_sk,

        -- Two date FKs (both YYYYMMDD integers, matching dim_date)
        cast(to_char(c.calendar_date, 'YYYYMMDD') as integer)  as date_sk,
        cast(to_char(c._snapshot_date, 'YYYYMMDD') as integer) as snapshot_date_sk,

        -- Natural keys / degenerate
        c.listing_id,
        c.calendar_date,
        c._snapshot_date,

        -- Measure
        c.is_available,

        -- Booking rules (per-night, kept from silver)
        c.minimum_nights,
        c.maximum_nights,

        c.city_key

    from calendar c

    -- SCD2 date-range join: match to the listing version that was
    -- current when this availability was scraped (_snapshot_date).
    inner join {{ ref('dim_listing') }} dl
        on  c.listing_id = dl.listing_id
        and c._snapshot_date >= dl.effective_from
        and c._snapshot_date <  dl.effective_to

)

select * from joined