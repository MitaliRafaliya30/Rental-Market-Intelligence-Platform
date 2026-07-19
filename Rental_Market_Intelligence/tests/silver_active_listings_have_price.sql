/*
    Active listings should have a price.

    Step 2 finding: 'previous scrape' listings are stale carry-forwards
    with 100% null price. 'city scrape' (active) listings had only
    1.27% null - 273 rows. This test asserts that the active-listing
    price coverage stays healthy.

    We allow a small tolerance (up to ~500 nulls) because the 273
    active nulls are real and immaterial. If active nulls spike far
    beyond that, something changed in the source and we want to know.

    A singular test passes when it returns ZERO rows.
    Here we return a row only if the bad count exceeds the threshold.
*/

{{ config(severity='error') }}

select
    count(*) as active_null_price_count
from {{ ref('silver_listings') }}
where is_active_listing = true
  and price_usd is null
having count(*) > 500