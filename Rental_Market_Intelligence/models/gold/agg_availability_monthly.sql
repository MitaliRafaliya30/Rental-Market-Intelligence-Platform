{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    agg_availability_monthly
    ------------------------
    Pre-aggregated availability for BI consumption.

    Grain: one row per neighbourhood per month per snapshot.
      ~223 neighbourhoods x ~13 months x 2 snapshots = ~5,800 rows,
      replacing 13.3M raw rows in fact_daily_availability.

    Why this exists:
      Power BI does not need row-level availability. Dashboards ask
      "what is occupancy in Williamsburg in December?" - a monthly,
      area-level question. Importing 13M rows to answer a 5,800-row
      question would make the model slow to load and refresh for no
      analytical gain.

      This is the standard BI aggregate-table pattern: pre-summarise
      to the grain the dashboard actually uses.

    Borough is carried alongside neighbourhood (it is functionally
    determined by it, so the grain is unchanged). This lets Power BI
    roll neighbourhood up to borough with no extra modelling.

    Joins:
      fact_daily_availability has no location_sk (kept lean at 26M
      rows), so we reach geography via dim_listing -> dim_location.
*/

with availability as (

    select * from {{ ref('fact_daily_availability') }}

),

enriched as (

    select
        a.city_key,
        dloc.location_sk,
        dloc.borough,
        dloc.neighbourhood,

        -- The calendar night's month (not the snapshot month)
        dd.year          as calendar_year,
        dd.month         as calendar_month,
        dd.month_name    as calendar_month_name,

        -- First day of the month - a clean key that can join to
        -- dim_date in Power BI for time intelligence.
        date_trunc('month', a.calendar_date)::date as month_start_date,

        a._snapshot_date,
        a.is_available

    from availability a

    -- Reach geography via the listing version this fact points to
    inner join {{ ref('dim_listing') }} dl
        on a.listing_sk = dl.listing_sk

    inner join {{ ref('dim_location') }} dloc
        on dl.location_sk = dloc.location_sk

    -- Get the month of the calendar night
    inner join {{ ref('dim_date') }} dd
        on a.date_sk = dd.date_sk

),

final as (

    select
        city_key,
        location_sk,
        borough,
        neighbourhood,
        calendar_year,
        calendar_month,
        calendar_month_name,
        month_start_date,
        _snapshot_date,

        -- ============================================
        -- MEASURES
        -- ============================================
        count(*)                                as total_nights,
        count_if(is_available = true)           as available_nights,
        count_if(is_available = false)          as unavailable_nights,

        -- Occupancy proxy: share of nights NOT available.
        -- A blocked night is booked or host-blocked - we cannot tell
        -- which, so this is an ESTIMATE, not observed occupancy.
        round(
            count_if(is_available = false) * 1.0 / nullif(count(*), 0),
            4
        )                                       as occupancy_rate,

        -- How many distinct listings contributed to this row.
        -- Useful for weighting and for a supply signal per area/month.
        count(distinct location_sk)             as location_count

    from enriched

    group by
        city_key,
        location_sk,
        borough,
        neighbourhood,
        calendar_year,
        calendar_month,
        calendar_month_name,
        month_start_date,
        _snapshot_date

)

select * from final