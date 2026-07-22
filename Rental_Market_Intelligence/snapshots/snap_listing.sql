{% snapshot snap_listing %}

/*
    snap_listing
    ------------
    SCD Type 2 history for listings. Config in _snapshots.yml.
    Grain: one row per listing version.

    Incremental source filter:
      We only feed snapshots NEWER than what's already captured, so
      re-runs don't re-process old snapshots (which would create bogus
      versions). On first build the snapshot table doesn't exist, so
      we fall back to loading everything up to the earliest snapshot,
      then later runs add newer ones.

      Because both Aug and Sep were pre-loaded, this history was built
      by running twice with explicit date filters. This filter keeps
      future runs (Oct, Nov, LA...) flowing in correctly and safely.
*/

select * from {{ ref('silver_listings') }}

{% if adapter.get_relation(this.database, this.schema, this.name) %}
    -- Snapshot table exists: only feed snapshots newer than the
    -- newest one already captured.
    where _snapshot_date > (
        select max(_snapshot_date) from {{ this }}
    )
{% endif %}

{% endsnapshot %}