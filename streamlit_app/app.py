"""
Rental Market Intelligence Platform — Home Page

Multi-page Streamlit app analyzing short-term rental markets across cities.
Powered by a dbt-built Kimball star schema (Bronze → Silver → Gold).
"""

import streamlit as st
from utils.connection import run_query

st.set_page_config(
    page_title="Rental Market Intelligence",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Header
st.title("🏠 Rental Market Intelligence Platform")
st.markdown(
    """
    Market analytics for short-term rental investment. Analyze supply,
    pricing, occupancy, and demand across neighbourhoods.
    """
)

# Quick intro
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Cities", "1", "New York")

with col2:
    st.metric("Snapshots", "2", "Aug & Sep 2025")

with col3:
    st.metric("Listings", "~37K", "distinct")

# Navigation guide
st.markdown("---")
st.subheader("📊 Pages")

st.markdown(
    """
    - **Market Overview** — Supply distribution by property type & borough
    - **Location Analytics** — Pricing & occupancy by neighbourhood
    - **Listing Explorer** — Drill into individual listings and hosts
    - **Trends** — Occupancy & demand over time (Aug → Sep)
    """
)

# Connection test (temporary — remove after S1 verification)
st.markdown("---")
st.subheader("🔧 Connection Test")
if st.button("Test Snowflake Connection"):
    try:
        df = run_query(
            "select count(distinct listing_id) as listings from gold.dim_listing"
        )
        st.success("✅ Connection working!")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")

# Data note
st.info(
    """
    **Data Note:** Occupancy and demand are *estimates* derived from
    availability data and review counts, not observed bookings.
    All analysis is as of the most recent snapshot.
    """
)

st.markdown("---")
st.caption(
    "Built with dbt (data warehouse) + Streamlit. "
    "Data: Inside Airbnb."
)
