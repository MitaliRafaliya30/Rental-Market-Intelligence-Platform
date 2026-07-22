{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    dim_host
    --------
    SCD Type 2 host dimension. One row per host VERSION.

    Built from snap_host. Same pattern as dim_listing:
      - surrogate key per version
      - honest effective dates from _snapshot_date via LEAD()
      - business-friendly names

    Grain: one row per (host_id, _snapshot_date) = one version.
*/

with snapshot_data as (

    select * from {{ ref('snap_host') }}

),

versioned as (

    select
        host_id,
        _snapshot_date,

        host_name,
        host_since_date,
        is_superhost,
        host_response_time,
        host_response_rate_pct,
        host_acceptance_rate_pct,
        is_host_identity_verified,
        host_listings_count,
        host_total_listings_count,

        _snapshot_date as effective_from,

        lead(_snapshot_date) over (
            partition by host_id
            order by _snapshot_date
        ) as effective_to,

        case
            when lead(_snapshot_date) over (
                partition by host_id
                order by _snapshot_date
            ) is null then true
            else false
        end as is_current

    from snapshot_data

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['host_id', '_snapshot_date']) }} as host_sk,

        host_id,

        host_name,
        host_since_date,
        is_superhost,
        host_response_time,
        host_response_rate_pct,
        host_acceptance_rate_pct,
        is_host_identity_verified,
        host_listings_count,
        host_total_listings_count,

        effective_from,
        coalesce(effective_to, '9999-12-31'::date) as effective_to,
        is_current

    from versioned

)

select * from final