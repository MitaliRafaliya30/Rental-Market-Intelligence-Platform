{% snapshot snap_host %}

/*
    snap_host
    ---------
    SCD Type 2 history for hosts. Config in _snapshots.yml.
    Deduplicated to one row per host per snapshot.

    Same incremental source filter as snap_listing: only feed
    snapshots newer than what's already captured, so re-runs don't
    re-process old data.
*/

with host_per_snapshot as (

    select
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
        _snapshot_date,
        row_number() over (
            partition by host_id, _snapshot_date
            order by listing_id
        ) as rn
    from {{ ref('silver_listings') }}
    where host_id is not null

    {% if adapter.get_relation(this.database, this.schema, this.name) %}
        and _snapshot_date > (
            select max(_snapshot_date) from {{ this }}
        )
    {% endif %}

)

select
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
    _snapshot_date
from host_per_snapshot
where rn = 1

{% endsnapshot %}