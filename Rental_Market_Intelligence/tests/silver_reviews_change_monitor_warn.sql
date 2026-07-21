{{ config(severity = 'warn') }}

/*
    Monitors how many existing reviews changed between snapshots.

    We keep the EARLIEST version of each review and ignore later edits.
    That's fine while edits are cosmetic (reviewer_name encoding fixes).
    But if the source ever starts editing COMMENT TEXT - which feeds
    sentiment analysis - we need to know, because then "keep earliest"
    would be dropping real corrections and we'd revisit the design.

    This test compares comment text for reviews that appear in more
    than one snapshot in bronze. It warns if any comment text differs.
    Currently expected: ~0 (only names changed, not comments).
*/

with multi_snapshot_reviews as (

    select
        id                            as review_id,
        comments                      as comments,
        _snapshot_date,
        count(*) over (partition by id) as snapshot_count
    from {{ source('bronze', 'bronze_reviews') }}

),

comment_changes as (

    select
        review_id,
        count(distinct comments) as distinct_comment_versions
    from multi_snapshot_reviews
    where snapshot_count > 1        -- only reviews seen in 2+ snapshots
    group by review_id
    having count(distinct comments) > 1   -- comment text actually differs

)

select * from comment_changes   