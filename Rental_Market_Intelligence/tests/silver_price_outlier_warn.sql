/*
    Warn (not error) if prices climb into absurd territory.

    Step 2 DEFER: the $50,052 max is probably a real penthouse, so we
    do NOT remove it in Silver. But we watch it. If prices appeared
    above, say, $100,000, that would suggest a parsing bug in
    clean_price (e.g. a comma mis-handled), not a real listing.

    Configured as warn in the yml is not possible for singular tests
    inline, so we set severity via config() here.
*/

{{ config(severity = 'warn') }}

select
    listing_id,
    price_usd
from {{ ref('silver_listings') }}
where price_usd > 100000