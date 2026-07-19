{{
    config(
        materialized = 'incremental',
        incremental_strategy = 'delete+insert',
        unique_key = ['listing_id', 'calendar_date', '_snapshot_date'],
        tags = ['silver']
    )
}}

/*
    silver_calendar
    ---------------
    Cleans the raw Inside Airbnb calendar (daily availability) data.

    Grain: one row per listing per calendar night per snapshot
           (listing_id + calendar_date + _snapshot_date)
    Source: bronze.bronze_calendar (~13.3M rows per snapshot)
    Output: 5 business columns + 3 metadata

    Feeds: fact_daily_availability

    Two dates, two meanings:
      calendar_date  = the future night being described
      _snapshot_date = when that description was captured
    The same listing+night can differ across snapshots (a night gets
    booked between scrapes), which is why BOTH are in the grain - and
    why availability-over-time is a real demand signal.

    This is a FACT feed, not a dimension - no SCD2. Availability is a
    measure, observed fresh each snapshot, appended not versioned.

    Incremental is structural here, not optional: 13.3M rows/snapshot
    means a view would re-scan hundreds of millions of rows per query.

    Note: bronze_calendar was built with manual VARCHAR DDL (not
    INFER_SCHEMA), so 'available' is genuine text 't'/'f' and needs
    clean_boolean - unlike the listings booleans which were already typed.
*/

with source as (

    select * from {{ source('bronze', 'bronze_calendar') }}

),

cleaned as (

    select

        -- ============================================
        -- GRAIN KEYS
        -- ============================================
        try_to_number(listing_id)                        as listing_id,

        -- The future night being described. Renamed from 'date'
        -- (a reserved-ish word) to calendar_date for clarity and to
        -- distinguish it from _snapshot_date.
        try_to_date(date)                 as calendar_date,

        -- ============================================
        -- AVAILABILITY  (measure -> fact, never SCD2)
        -- ============================================
        -- 'available' is text 't'/'f' here (manual DDL bronze table),
        -- so clean_boolean does real work - the column it was built for.
        {{ clean_boolean('available') }}  as is_available,

        -- ============================================
        -- BOOKING RULES
        -- ============================================
        try_to_number(minimum_nights)               as minimum_nights,
        case
            when try_to_number(maximum_nights) = 2147483647 then null
            else try_to_number(maximum_nights)
        end                                 as maximum_nights,

        -- NOTE: price and adjusted_price are dropped. Both are 100%
        -- null in source (Phase 3). Keeping them would falsely imply
        -- the calendar carries pricing. Price history is built from
        -- listing snapshots via SCD2 instead.

        -- ============================================
        -- METADATA (passthrough)
        -- ============================================
        _source_filename                    as _source_filename,
        _loaded_at                          as _loaded_at,
        _snapshot_date                      as _snapshot_date

    from source

)

select * from cleaned

{% if is_incremental() %}

    -- Only process snapshots newer than what's already loaded.
    -- Same proven watermark pattern as silver_listings.
    where _snapshot_date > (select max(_snapshot_date) from {{ this }})

{% endif %}