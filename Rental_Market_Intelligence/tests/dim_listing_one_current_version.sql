/*
    An SCD2 dimension must have exactly ONE current version per entity.
    Two current versions = broken chaining (the bug we hit in G2).
    This guards against it recurring on future snapshots.
*/

select
    listing_id,
    count(*) as current_versions
from {{ ref('dim_listing') }}
where is_current = true
group by listing_id
having count(*) > 1