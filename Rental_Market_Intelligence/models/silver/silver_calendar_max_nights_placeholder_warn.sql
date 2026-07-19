{{ config(severity = 'warn') }}

-- Monitors implausibly large maximum_nights (the per-host placeholder
-- values like 20000000, in exact multiples of 365). We do NOT correct
-- these - they're unprovable human entries, and any cap is a Gold-layer
-- judgment. This test keeps them visible so we notice if they grow.
select
    maximum_nights,
    count(*) as cnt
from {{ ref('silver_calendar') }}
where maximum_nights > 1125
group by 1