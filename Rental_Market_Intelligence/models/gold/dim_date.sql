{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    dim_date
    --------
    Generated calendar dimension. One row per day, 2009-2027.
    City-agnostic by nature - no multi-city logic needed.
    date_sk = YYYYMMDD integer (unique AND human-readable).
*/

with date_spine as (

    {{ dbt_utils.date_spine(
        datepart = "day",
        start_date = "to_date('2009-01-01')",
        end_date = "to_date('2028-01-01')"
    ) }}

),

final as (

    select
        cast(to_char(date_day, 'YYYYMMDD') as integer) as date_sk,
        date_day                                as full_date,
        year(date_day)                          as year,
        quarter(date_day)                       as quarter,
        month(date_day)                         as month,
        monthname(date_day)                     as month_name,
        day(date_day)                           as day_of_month,
        dayofweek(date_day)                     as day_of_week,
        dayname(date_day)                       as day_name,
        weekofyear(date_day)                    as week_of_year,
        case when dayofweek(date_day) in (0, 6) then true else false end as is_weekend,
        case
            when month(date_day) in (12, 1, 2) then 'Winter'
            when month(date_day) in (3, 4, 5)  then 'Spring'
            when month(date_day) in (6, 7, 8)  then 'Summer'
            else 'Fall'
        end                                     as season
    from date_spine

)

select * from final