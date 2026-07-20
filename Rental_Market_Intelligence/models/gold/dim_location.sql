{{
    config(
        materialized = 'table',
        tags = ['gold']
    )
}}

/*
    dim_location
    ------------
    Conformed geographic dimension. One row per (city, borough,
    neighbourhood). Every fact and every city points here.

    NOT SCD2 - location is immutable.

    Metadata-driven: city_key flows from Bronze through Silver into
    this model, then joins to the city_config seed for labels. Adding
    a new city requires NO change here - the new city's rows appear
    automatically once its data flows through Silver, and city_config
    supplies the labels. Zero model changes, zero hardcoded cities.

    Grain includes city_key so identically-named neighbourhoods in
    different cities (e.g. "Downtown" in NYC vs LA) stay distinct.
*/

with locations as (

    -- Distinct geographic points that exist in our data.
    -- city_key comes through from Silver - no hardcoding, no parsing.
    select distinct
        city_key,
        borough,
        neighbourhood
    from {{ ref('silver_listings') }}
    where neighbourhood is not null

),

city_labels as (

    -- Human-readable labels from the metadata seed.
    select
        city_key,
        city_name,
        state,
        country
    from {{ ref('city_config') }}

),

final as (

    select
        -- Surrogate key from the COMPLETE business grain, so the same
        -- (city, borough, neighbourhood) always yields the same key.
        {{ dbt_utils.generate_surrogate_key([
            'locations.city_key',
            'locations.borough',
            'locations.neighbourhood'
        ]) }} as location_sk,

        -- Business (natural) key components
        locations.city_key,
        locations.neighbourhood,
        locations.borough,

        -- Labels resolved from config (metadata-driven)
        city_labels.city_name   as city,
        city_labels.state,
        city_labels.country

    from locations
    inner join city_labels
        on locations.city_key = city_labels.city_key

)

select * from final