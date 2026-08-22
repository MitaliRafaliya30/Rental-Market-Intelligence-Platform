"""
Market Overview — Supply distribution by borough, room type, and property type.

Questions answered:
  - Which neighbourhoods/boroughs have the highest supply?
  - How is supply distributed by property type and room type?
  - Market-wide pricing and demand statistics.
"""

import streamlit as st
import plotly.express as px
from datetime import date
from utils.queries import (
    get_snapshot_dates,
    get_market_summary,
    get_supply_by_borough,
    get_supply_by_room_type,
    get_supply_by_property_type,
)

st.set_page_config(layout="wide")
st.title("📍 Market Overview")

# ============================================================================
# SIDEBAR: Snapshot Date Selector
# ============================================================================
with st.sidebar:
    st.subheader("📅 Data")
    snapshot_dates_df = get_snapshot_dates()
    available_dates = sorted(snapshot_dates_df["_snapshot_date"].tolist(), reverse=True)
    selected_snapshot = st.selectbox(
        "Snapshot Date",
        available_dates,
        format_func=lambda d: d.strftime("%B %d, %Y"),
    )

# ============================================================================
# KPI ROW
# ============================================================================
st.markdown("### 📊 Market Summary")

kpi_data = get_market_summary(selected_snapshot)
if not kpi_data.empty:
    row = kpi_data.iloc[0]

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Distinct Listings", f"{int(row['distinct_listings']):,}")

    with col2:
        st.metric("Distinct Hosts", f"{int(row['distinct_hosts']):,}")

    with col3:
        st.metric(
            "Median Price",
            f"${row['median_price_usd']:,.0f}",
        )

    with col4:
        occupancy = row["avg_estimated_occupancy"] * 100
        st.metric("Est. Occupancy", f"{occupancy:.1f}%")

    with col5:
        st.metric("Total Reviews", f"{int(row['total_reviews']):,}")
else:
    st.warning("No data available for selected snapshot.")

# ============================================================================
# CHARTS: Supply Distribution
# ============================================================================
st.markdown("---")

# Supply by Borough
supply_borough = get_supply_by_borough(selected_snapshot)
if not supply_borough.empty:
    st.markdown("### Supply by Borough")

    fig_borough = px.bar(
        supply_borough.sort_values("listing_count", ascending=True),
        x="listing_count",
        y="borough",
        orientation="h",
        title=None,
        labels={"listing_count": "Listing Count", "borough": "Borough"},
        color="borough",
        color_discrete_sequence=px.colors.qualitative.Set2,
        height=300,
    )
    fig_borough.update_layout(
        showlegend=False,
        hovermode="closest",
        xaxis_title="Listing Count",
        yaxis_title="",
    )
    st.plotly_chart(fig_borough, use_container_width=True)
else:
    st.info("No data available for selected filters.")

# Supply by Room Type
col1, col2 = st.columns(2)

with col1:
    supply_room_type = get_supply_by_room_type(selected_snapshot)
    if not supply_room_type.empty:
        st.markdown("### Supply by Room Type")

        fig_room_type = px.bar(
            supply_room_type.sort_values("listing_count", ascending=False),
            x="room_type",
            y="listing_count",
            title=None,
            labels={"listing_count": "Listing Count (log scale)", "room_type": "Room Type"},
            color="room_type",
            color_discrete_sequence=px.colors.qualitative.Set2,
            height=350,
        )
        fig_room_type.update_layout(
            showlegend=False,
            hovermode="closest",
            yaxis_title="Listing Count (log scale)",
            xaxis_title="",
            yaxis_type="log",
        )
        st.plotly_chart(fig_room_type, use_container_width=True)
    else:
        st.info("No data available for selected filters.")

# Top Property Types
with col2:
    property_types = get_supply_by_property_type(top_n=10, snapshot_date=selected_snapshot)
    if not property_types.empty:
        st.markdown("### Top 10 Property Types")

        fig_property = px.bar(
            property_types.sort_values("listing_count", ascending=True),
            x="listing_count",
            y="property_type",
            orientation="h",
            title=None,
            labels={"listing_count": "Listing Count", "property_type": "Property Type"},
            color_discrete_sequence=px.colors.sequential.Blues,
            height=350,
        )
        fig_property.update_layout(
            showlegend=False,
            hovermode="closest",
            xaxis_title="Listing Count",
            yaxis_title="",
        )
        st.plotly_chart(fig_property, use_container_width=True)
    else:
        st.info("No data available for selected filters.")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.caption(
    "**Data Note:** "
    "Estimated Occupancy is derived from availability data, not observed bookings. "
    f"Snapshot: {selected_snapshot.strftime('%B %d, %Y')}"
)
