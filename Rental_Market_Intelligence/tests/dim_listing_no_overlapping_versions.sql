/*
    SCD2 version date ranges must not overlap for the same listing.
    Each version owns a distinct time slice; one ends where the next
    begins. Overlaps = a fact could match two versions (double-count).
*/

with versions as (
    select
        listing_id,
        effective_from,
        effective_to,
        lead(effective_from) over (
            partition by listing_id order by effective_from
        ) as next_effective_from
    from {{ ref('dim_listing') }}
)

select listing_id, effective_from, effective_to, next_effective_from
from versions
where next_effective_from is not null
  and effective_to > next_effective_from   -- overlap detected