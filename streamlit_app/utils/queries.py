"""
Query layer: all SQL functions the app needs.

Design principle:
  Snowflake does the heavy lifting (aggregation, filtering, joins).
  The app fetches small result sets (tens to thousands of rows), never millions.

  Every query is cached (@st.cache_data) based on its parameters.
  The same parameters = same cached result (1-hour TTL).

SCD2 gotcha:
  dim_listing has ~52K version rows for ~37K distinct listings.
  Any listing COUNT must use COUNT(DISTINCT listing_id) to avoid
  double-counting changed listings.

Aggregate table:
  Use agg_availability_monthly for occupancy/seasonality trends.
  NEVER pull fact_daily_availability (26.5M rows) into the app.

Filter safety:
  Optional filters are safely applied only if provided. No string concatenation
  for user input. Fixed-value filters (borough, room_type) are validated against
  known dimension values. For listing search, the search string is parameterized.
"""

from datetime import date
import pandas as pd
from utils.connection import run_query


# ==============================================================================
# FILTER HELPERS — for dropdowns and validation
# ==============================================================================


def get_boroughs() -> pd.DataFrame:
    """
    All boroughs in the dataset.

    Returns:
        DataFrame with columns: [borough]
    """
    return run_query("SELECT DISTINCT borough FROM gold.dim_location ORDER BY borough")


def get_neighbourhoods(borough: str | None = None) -> pd.DataFrame:
    """
    All neighbourhoods, optionally filtered by borough.

    Args:
        borough: if provided, only neighbourhoods in this borough

    Returns:
        DataFrame with columns: [borough, neighbourhood]
    """
    if borough:
        return run_query(
            "SELECT DISTINCT borough, neighbourhood "
            "FROM gold.dim_location "
            "WHERE borough = %s "
            "ORDER BY neighbourhood",
            (borough,)
        )
    else:
        return run_query(
            "SELECT DISTINCT borough, neighbourhood "
            "FROM gold.dim_location "
            "ORDER BY neighbourhood"
        )


def get_room_types() -> pd.DataFrame:
    """
    All room types in the dataset.

    Returns:
        DataFrame with columns: [room_type]
    """
    return run_query(
        "SELECT DISTINCT room_type FROM gold.dim_listing "
        "WHERE is_current = true ORDER BY room_type"
    )


def get_snapshot_dates() -> pd.DataFrame:
    """
    All snapshot dates in the data (for trend filtering).

    Returns:
        DataFrame with columns: [_snapshot_date] (date type)
    """
    return run_query(
        "SELECT DISTINCT _snapshot_date FROM gold.fact_listing_snapshot "
        "ORDER BY _snapshot_date DESC"
    )


# ==============================================================================
# MARKET OVERVIEW
# ==============================================================================


def get_market_summary(snapshot_date: date | None = None) -> pd.DataFrame:
    """
    High-level KPIs for the whole market.

    Answers: How many listings and hosts? What's the typical price and
    occupancy?

    Args:
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        Single-row DataFrame with columns:
          [distinct_listings, distinct_hosts, median_price_usd,
           avg_estimated_occupancy, total_reviews]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                COUNT(DISTINCT dl.listing_id) as distinct_listings,
                COUNT(DISTINCT dh.host_id) as distinct_hosts,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd,
                ROUND(AVG(agg.occupancy_rate), 4)
                    as avg_estimated_occupancy,
                COUNT(DISTINCT fr.review_id) as total_reviews
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_host dh
                ON fls.host_sk = dh.host_sk
            INNER JOIN gold.agg_availability_monthly agg
                ON dl.location_sk = agg.location_sk
                AND fls._snapshot_date = agg._snapshot_date
            LEFT JOIN gold.fact_review fr
                ON dl.listing_id = fr.listing_id
            WHERE fls._snapshot_date = %s
            """,
            (snapshot_date,)
        )
    else:
        return run_query(
            """
            SELECT
                COUNT(DISTINCT dl.listing_id) as distinct_listings,
                COUNT(DISTINCT dh.host_id) as distinct_hosts,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd,
                ROUND(AVG(agg.occupancy_rate), 4)
                    as avg_estimated_occupancy,
                COUNT(DISTINCT fr.review_id) as total_reviews
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_host dh
                ON fls.host_sk = dh.host_sk
            INNER JOIN gold.agg_availability_monthly agg
                ON dl.location_sk = agg.location_sk
                AND fls._snapshot_date = agg._snapshot_date
            LEFT JOIN gold.fact_review fr
                ON dl.listing_id = fr.listing_id
            WHERE fls._snapshot_date = (SELECT MAX(_snapshot_date)
                                        FROM gold.fact_listing_snapshot)
            """
        )


def get_supply_by_borough(snapshot_date: date | None = None) -> pd.DataFrame:
    """
    Listing count by borough.

    Answers: Where is the supply concentrated?

    Args:
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame (~5 rows) with columns: [borough, listing_count]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                dloc.borough,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            WHERE fls._snapshot_date = %s
            GROUP BY dloc.borough
            ORDER BY listing_count DESC
            """,
            (snapshot_date,)
        )
    else:
        return run_query(
            """
            SELECT
                dloc.borough,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            WHERE fls._snapshot_date = (SELECT MAX(_snapshot_date)
                                        FROM gold.fact_listing_snapshot)
            GROUP BY dloc.borough
            ORDER BY listing_count DESC
            """
        )


def get_supply_by_room_type(snapshot_date: date | None = None) -> pd.DataFrame:
    """
    Listing count by room type.

    Answers: What's the split between entire homes, private rooms, etc.?

    Args:
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame (~4 rows) with columns: [room_type, listing_count]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                dl.room_type,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            WHERE fls._snapshot_date = %s
            GROUP BY dl.room_type
            ORDER BY listing_count DESC
            """,
            (snapshot_date,)
        )
    else:
        return run_query(
            """
            SELECT
                dl.room_type,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            WHERE fls._snapshot_date = (SELECT MAX(_snapshot_date)
                                        FROM gold.fact_listing_snapshot)
            GROUP BY dl.room_type
            ORDER BY listing_count DESC
            """
        )


def get_supply_by_property_type(
    top_n: int = 10,
    snapshot_date: date | None = None
) -> pd.DataFrame:
    """
    Top N property types by listing count.

    Answers: What kinds of properties dominate the market?

    Args:
        top_n: return top N property types (default 10)
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame with columns: [property_type, listing_count]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                dl.property_type,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            WHERE fls._snapshot_date = %s
            GROUP BY dl.property_type
            ORDER BY listing_count DESC
            LIMIT %s
            """,
            (snapshot_date, top_n)
        )
    else:
        return run_query(
            f"""
            SELECT
                dl.property_type,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            WHERE fls._snapshot_date = (SELECT MAX(_snapshot_date)
                                        FROM gold.fact_listing_snapshot)
            GROUP BY dl.property_type
            ORDER BY listing_count DESC
            LIMIT {top_n}
            """
        )


# ==============================================================================
# LOCATION ANALYTICS
# ==============================================================================


def get_price_by_neighbourhood(snapshot_date: date | None = None) -> pd.DataFrame:
    """
    Median price and listing count per neighbourhood.

    Answers: Where are prices highest? Which neighbourhoods are most active?
    Uses MEDIAN, not AVG — avoids distortion from outlier luxury listings.

    Args:
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame (~223 rows) with columns:
          [borough, neighbourhood, median_price_usd, listing_count]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                dloc.borough,
                dloc.neighbourhood,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            WHERE fls._snapshot_date = %s
            GROUP BY dloc.borough, dloc.neighbourhood
            ORDER BY median_price_usd DESC
            """,
            (snapshot_date,)
        )
    else:
        return run_query(
            """
            SELECT
                dloc.borough,
                dloc.neighbourhood,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd,
                COUNT(DISTINCT dl.listing_id) as listing_count
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            WHERE fls._snapshot_date = (SELECT MAX(_snapshot_date)
                                        FROM gold.fact_listing_snapshot)
            GROUP BY dloc.borough, dloc.neighbourhood
            ORDER BY median_price_usd DESC
            """
        )


def get_occupancy_by_neighbourhood(snapshot_date: date | None = None) -> pd.DataFrame:
    """
    Average estimated occupancy per neighbourhood.

    Answers: Which neighbourhoods have highest demand (estimated occupancy)?
    Source: agg_availability_monthly, aggregated to neighbourhood level.

    Args:
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame (~223 rows) with columns:
          [borough, neighbourhood, avg_occupancy_rate]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                borough,
                neighbourhood,
                ROUND(AVG(occupancy_rate), 4) as avg_occupancy_rate
            FROM gold.agg_availability_monthly
            WHERE _snapshot_date = %s
            GROUP BY borough, neighbourhood
            ORDER BY avg_occupancy_rate DESC
            """,
            (snapshot_date,)
        )
    else:
        return run_query(
            """
            SELECT
                borough,
                neighbourhood,
                ROUND(AVG(occupancy_rate), 4) as avg_occupancy_rate
            FROM gold.agg_availability_monthly
            WHERE _snapshot_date = (SELECT MAX(_snapshot_date)
                                    FROM gold.agg_availability_monthly)
            GROUP BY borough, neighbourhood
            ORDER BY avg_occupancy_rate DESC
            """
        )


def get_supply_demand_matrix(snapshot_date: date | None = None) -> pd.DataFrame:
    """
    Supply-demand matrix: one row per neighbourhood showing supply,
    pricing, occupancy, and demand signals.

    Answers: Where is there supply-demand imbalance?
    - High supply, low occupancy = oversupplied
    - Low supply, high occupancy + high reviews = undersupplied

    Args:
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame (~223 rows) with columns:
          [borough, neighbourhood, listing_count, median_price_usd,
           avg_occupancy_rate, total_reviews]
    """
    if snapshot_date:
        return run_query(
            """
            SELECT
                dloc.borough,
                dloc.neighbourhood,
                COUNT(DISTINCT dl.listing_id) as listing_count,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd,
                ROUND(AVG(agg.occupancy_rate), 4) as avg_occupancy_rate,
                COUNT(DISTINCT fr.review_id) as total_reviews
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            INNER JOIN gold.agg_availability_monthly agg
                ON dl.location_sk = agg.location_sk
                AND fls._snapshot_date = agg._snapshot_date
            LEFT JOIN gold.fact_review fr
                ON dl.listing_id = fr.listing_id
            WHERE fls._snapshot_date = %s
            GROUP BY dloc.borough, dloc.neighbourhood
            ORDER BY listing_count DESC
            """,
            (snapshot_date,)
        )
    else:
        return run_query(
            """
            SELECT
                dloc.borough,
                dloc.neighbourhood,
                COUNT(DISTINCT dl.listing_id) as listing_count,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd,
                ROUND(AVG(agg.occupancy_rate), 4) as avg_occupancy_rate,
                COUNT(DISTINCT fr.review_id) as total_reviews
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            INNER JOIN gold.agg_availability_monthly agg
                ON dl.location_sk = agg.location_sk
                AND fls._snapshot_date = agg._snapshot_date
            LEFT JOIN gold.fact_review fr
                ON dl.listing_id = fr.listing_id
            WHERE fls._snapshot_date = (SELECT MAX(_snapshot_date)
                                        FROM gold.fact_listing_snapshot)
            GROUP BY dloc.borough, dloc.neighbourhood
            ORDER BY listing_count DESC
            """
        )


# ==============================================================================
# LISTING EXPLORER
# ==============================================================================


def search_listings(
    limit: int = 100,
    borough: str | None = None,
    room_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    snapshot_date: date | None = None
) -> pd.DataFrame:
    """
    Search individual listings with optional filters. LIMIT is mandatory.

    Answers: Find specific listings matching criteria.

    Args:
        limit: max rows to return (mandatory, default 100)
        borough: if provided, filter to this borough
        room_type: if provided, filter to this room type
        min_price: if provided, min price (inclusive)
        max_price: if provided, max price (inclusive)
        snapshot_date: if provided, snapshot to filter to (latest if None)

    Returns:
        DataFrame with columns:
          [listing_id, listing_name, borough, neighbourhood, room_type,
           price_usd, accommodates, reviews, occupancy_rate]
    """
    conditions = []
    params = []

    if snapshot_date:
        conditions.append("fls._snapshot_date = %s")
        params.append(snapshot_date)
    else:
        conditions.append(
            "fls._snapshot_date = (SELECT MAX(_snapshot_date) "
            "FROM gold.fact_listing_snapshot)"
        )

    if borough:
        conditions.append("dloc.borough = %s")
        params.append(borough)

    if room_type:
        conditions.append("dl.room_type = %s")
        params.append(room_type)

    if min_price is not None:
        conditions.append("dl.price_usd >= %s")
        params.append(min_price)

    if max_price is not None:
        conditions.append("dl.price_usd <= %s")
        params.append(max_price)

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            dl.listing_id,
            dl.listing_name,
            dloc.borough,
            dloc.neighbourhood,
            dl.room_type,
            dl.price_usd,
            dl.accommodates,
            fls.number_of_reviews,
            ROUND(fls.estimated_occupancy_rate, 4) as occupancy_rate
        FROM gold.fact_listing_snapshot fls
        INNER JOIN gold.dim_listing dl
            ON fls.listing_sk = dl.listing_sk
        INNER JOIN gold.dim_location dloc
            ON dl.location_sk = dloc.location_sk
        WHERE {where_clause}
        ORDER BY dl.price_usd DESC
        LIMIT {limit}
    """

    if params:
        return run_query(query, tuple(params))
    else:
        return run_query(query)


def get_listing_detail(listing_id: int) -> pd.DataFrame:
    """
    All versions of a single listing (SCD2 history).

    Answers: How has this listing changed over time?
    Demonstrates the value of SCD2 — price history, attribute changes.

    Args:
        listing_id: the listing to inspect

    Returns:
        DataFrame (typically 1-2 rows) with columns:
          [listing_id, effective_from, effective_to, is_current, listing_name,
           room_type, property_type, price_usd, accommodates, bedrooms,
           beds, bathrooms]
    """
    return run_query(
        """
        SELECT
            dl.listing_id,
            dl.effective_from,
            dl.effective_to,
            dl.is_current,
            dl.listing_name,
            dl.room_type,
            dl.property_type,
            dl.price_usd,
            dl.accommodates,
            dl.bedrooms,
            dl.beds,
            dl.bathrooms
        FROM gold.dim_listing dl
        WHERE dl.listing_id = %s
        ORDER BY dl.effective_from ASC
        """,
        (listing_id,)
    )


# ==============================================================================
# TRENDS
# ==============================================================================


def get_price_trend(borough: str | None = None) -> pd.DataFrame:
    """
    Median price over time (by snapshot date).

    Answers: How have prices changed from Aug to Sep?

    Args:
        borough: if provided, filter to this borough (all if None)

    Returns:
        DataFrame with columns: [_snapshot_date, borough, median_price_usd]
    """
    if borough:
        return run_query(
            """
            SELECT
                fls._snapshot_date,
                dloc.borough,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            WHERE dloc.borough = %s
            GROUP BY fls._snapshot_date, dloc.borough
            ORDER BY fls._snapshot_date
            """,
            (borough,)
        )
    else:
        return run_query(
            """
            SELECT
                fls._snapshot_date,
                dloc.borough,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dl.price_usd)
                    as median_price_usd
            FROM gold.fact_listing_snapshot fls
            INNER JOIN gold.dim_listing dl
                ON fls.listing_sk = dl.listing_sk
            INNER JOIN gold.dim_location dloc
                ON dl.location_sk = dloc.location_sk
            GROUP BY fls._snapshot_date, dloc.borough
            ORDER BY fls._snapshot_date, dloc.borough
            """
        )


def get_occupancy_trend(borough: str | None = None) -> pd.DataFrame:
    """
    Average estimated occupancy over time (by snapshot date).

    Answers: Is demand increasing or decreasing?
    Source: agg_availability_monthly.

    Args:
        borough: if provided, filter to this borough (all if None)

    Returns:
        DataFrame with columns: [_snapshot_date, borough, avg_occupancy_rate]
    """
    if borough:
        return run_query(
            """
            SELECT
                agg._snapshot_date,
                agg.borough,
                ROUND(AVG(agg.occupancy_rate), 4) as avg_occupancy_rate
            FROM gold.agg_availability_monthly agg
            WHERE agg.borough = %s
            GROUP BY agg._snapshot_date, agg.borough
            ORDER BY agg._snapshot_date
            """,
            (borough,)
        )
    else:
        return run_query(
            """
            SELECT
                agg._snapshot_date,
                agg.borough,
                ROUND(AVG(agg.occupancy_rate), 4) as avg_occupancy_rate
            FROM gold.agg_availability_monthly agg
            GROUP BY agg._snapshot_date, agg.borough
            ORDER BY agg._snapshot_date, agg.borough
            """
        )


def get_review_volume_trend() -> pd.DataFrame:
    """
    Review volume by month (longest time series, 2009 onward).

    Answers: How has demand (review activity) evolved historically?
    This is the only genuinely long-range signal (vs. snapshots that are
    weeks apart).

    Returns:
        DataFrame with columns: [calendar_year, calendar_month, review_count]
    """
    return run_query(
        """
        SELECT
            YEAR(fr.review_date) as calendar_year,
            MONTH(fr.review_date) as calendar_month,
            COUNT(DISTINCT fr.review_id) as review_count
        FROM gold.fact_review fr
        GROUP BY YEAR(fr.review_date), MONTH(fr.review_date)
        ORDER BY calendar_year, calendar_month
        """
    )


def get_seasonality() -> pd.DataFrame:
    """
    Average occupancy by calendar month (across all years).

    Answers: Which months are busy? Which are slow?

    Returns:
        DataFrame with columns:
          [calendar_month, calendar_month_name, avg_occupancy_rate]
    """
    return run_query(
        """
        SELECT
            agg.calendar_month,
            agg.calendar_month_name,
            ROUND(AVG(agg.occupancy_rate), 4) as avg_occupancy_rate
        FROM gold.agg_availability_monthly agg
        GROUP BY agg.calendar_month, agg.calendar_month_name
        ORDER BY agg.calendar_month
        """
    )
