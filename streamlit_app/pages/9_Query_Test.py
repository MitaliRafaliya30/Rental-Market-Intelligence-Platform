"""
TEMPORARY — query layer smoke test.
Runs every function in queries.py and shows the result.
Delete after S2 verification.
"""

import streamlit as st
import utils.queries as q

st.title("Query Layer Test")

tests = [
    ("get_boroughs",                  lambda: q.get_boroughs()),
    ("get_room_types",                lambda: q.get_room_types()),
    ("get_snapshot_dates",            lambda: q.get_snapshot_dates()),
    ("get_neighbourhoods",            lambda: q.get_neighbourhoods()),
    ("get_market_summary",            lambda: q.get_market_summary()),
    ("get_supply_by_borough",         lambda: q.get_supply_by_borough()),
    ("get_supply_by_room_type",       lambda: q.get_supply_by_room_type()),
    ("get_supply_by_property_type",   lambda: q.get_supply_by_property_type()),
    ("get_price_by_neighbourhood",    lambda: q.get_price_by_neighbourhood()),
    ("get_occupancy_by_neighbourhood",lambda: q.get_occupancy_by_neighbourhood()),
    ("get_supply_demand_matrix",      lambda: q.get_supply_demand_matrix()),
    ("search_listings",               lambda: q.search_listings()),
    ("get_price_trend",               lambda: q.get_price_trend()),
    ("get_occupancy_trend",           lambda: q.get_occupancy_trend()),
    ("get_review_volume_trend",       lambda: q.get_review_volume_trend()),
    ("get_seasonality",               lambda: q.get_seasonality()),
]

for name, fn in tests:
    with st.expander(name, expanded=False):
        try:
            df = fn()
            st.success(f"OK — {len(df)} rows")
            st.dataframe(df.head(20))
        except Exception as e:
            st.error(f"FAILED: {e}")