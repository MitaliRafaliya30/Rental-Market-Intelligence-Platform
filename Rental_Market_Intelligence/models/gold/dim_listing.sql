{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    dim_listing
    -----------
    SCD Type 2 listing dimension. One row per listing VERSION.

    Built from snap_listing (the SCD2 engine). This model turns dbt's
    raw snapshot into a clean, business-facing dimension:
      - proper surrogate key per version
      - HONEST effective dates from _snapshot_date (not dbt's run-time
        dbt_valid_from columns)
      - business-friendly column names
      - foreign keys to dim_host and dim_location

    Effective dating:
      dbt's snapshot chains versions correctly but stamps them with
      run-time. We rebuild the dates from _snapshot_date - the honest
      "when this was true in the world" date - using LEAD() to find
      when each version was superseded.

    Grain: one row per (listing_id, _snapshot_date) = one version.
*/

with snapshot_data as (

    select * from {{ ref('snap_listing') }}

),

versioned as (

    select
        listing_id,
        host_id,
        _snapshot_date,

        -- descriptive attributes
        listing_name,
        neighbourhood,
        borough,
        latitude,
        longitude,
        property_type,
        room_type,
        accommodates,
        bathrooms,
        bathroom_type,
        bedrooms,
        beds,
        price_usd,
        minimum_nights,
        maximum_nights,
        is_instant_bookable,
        is_active_listing,
        city_key,

        -- HONEST effective dating from _snapshot_date:
        -- effective_from = when this version's snapshot was taken
        _snapshot_date as effective_from,

        -- effective_to = the NEXT version's snapshot date.
        -- LEAD looks ahead to the next version of THIS listing.
        -- If there's no next version, this is the current one.
        lead(_snapshot_date) over (
            partition by listing_id
            order by _snapshot_date
        ) as effective_to,

        -- is_current = true if no later version exists
        case
            when lead(_snapshot_date) over (
                partition by listing_id
                order by _snapshot_date
            ) is null then true
            else false
        end as is_current

    from snapshot_data

),

final as (

    select
        -- Surrogate key: unique per VERSION (listing + snapshot date).
        -- The Aug and Sep versions of the same listing get different
        -- keys - this is what facts join to.
        {{ dbt_utils.generate_surrogate_key(['listing_id', '_snapshot_date']) }} as listing_sk,

        -- Foreign keys to other dimensions.
        -- dim_host is also SCD2, so we join to the host VERSION that
        -- was current at this listing's snapshot date (handled in G-join
        -- logic - for now we generate the host SK the same way).
        {{ dbt_utils.generate_surrogate_key(['host_id', '_snapshot_date']) }} as host_sk,
        {{ dbt_utils.generate_surrogate_key(['city_key', 'borough', 'neighbourhood']) }} as location_sk,

        -- Natural key (for reference / debugging)
        listing_id,

        -- Descriptive attributes
        listing_name,
        property_type,
        room_type,
        accommodates,
        bathrooms,
        bathroom_type,
        bedrooms,
        beds,
        price_usd,
        minimum_nights,
        maximum_nights,
        is_instant_bookable,
        is_active_listing,

        -- Location attributes (lat/long live here - untracked, stable)
        latitude,
        longitude,

        -- SCD2 columns
        effective_from,
        -- Far-future sentinel for the current version, so date-range
        -- BETWEEN queries work cleanly (no nulls to special-case).
        coalesce(effective_to, '9999-12-31'::date) as effective_to,
        is_current,

        city_key

    from versioned

)

select * from final