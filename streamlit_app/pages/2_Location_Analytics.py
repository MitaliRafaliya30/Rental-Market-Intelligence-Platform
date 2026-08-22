"""
Location Analytics — Pricing, occupancy, and supply-demand by neighbourhood.

Questions answered:
  - What are price levels across neighbourhoods?
  - Which neighbourhoods show highest estimated occupancy and demand?
  - Where is there supply-demand imbalance (investment opportunities)?
"""

import streamlit as st
import plotly.express as px
from datetime import date
from utils.queries import (
    get_snapshot_dates,
    get_boroughs,
    get_price_by_neighbourhood,
    get_occupancy_by_neighbourhood,
    get_supply_demand_matrix,
)

st.set_page_config(layout="wide")
st.title("💰 Location Analytics")

# ============================================================================
# SIDEBAR: Filters
# ============================================================================
with st.sidebar:
    st.subheader("🔍 Filters")

    # Snapshot Date
    snapshot_dates_df = get_snapshot_dates()
    available_dates = sorted(snapshot_dates_df["_snapshot_date"].tolist(), reverse=True)
    selected_snapshot = st.selectbox(
        "Snapshot Date",
        available_dates,
        format_func=lambda d: d.strftime("%B %d, %Y"),
    )

    # Borough Filter
    boroughs_df = get_boroughs()
    available_boroughs = sorted(boroughs_df["borough"].tolist())
    selected_boroughs = st.multiselect(
        "Borough",
        available_boroughs,
        default=available_boroughs,  # Default to all
    )

    if not selected_boroughs:
        st.warning("Select at least one borough")

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=3600)
def fetch_location_data(snapshot_date: date, boroughs: list):
    """Fetch and filter location analytics data."""
    price_df = get_price_by_neighbourhood(snapshot_date)
    occupancy_df = get_occupancy_by_neighbourhood(snapshot_date)
    matrix_df = get_supply_demand_matrix(snapshot_date)

    # Filter by borough
    if boroughs:
        price_df = price_df[price_df["borough"].isin(boroughs)]
        occupancy_df = occupancy_df[occupancy_df["borough"].isin(boroughs)]
        matrix_df = matrix_df[matrix_df["borough"].isin(boroughs)]

    return price_df, occupancy_df, matrix_df


if selected_boroughs:
    price_data, occupancy_data, matrix_data = fetch_location_data(
        selected_snapshot, selected_boroughs
    )

    # ========================================================================
    # PRICE ANALYSIS
    # ========================================================================
    st.markdown("### 💵 Median Price by Neighbourhood (Top 20)")

    if not price_data.empty:
        price_top20 = (
            price_data.sort_values("median_price_usd", ascending=False)
            .head(20)
            .sort_values("median_price_usd", ascending=True)
        )

        fig_price = px.bar(
            price_top20,
            x="median_price_usd",
            y="neighbourhood",
            orientation="h",
            title=None,
            labels={"median_price_usd": "Median Price (USD)", "neighbourhood": ""},
            color="median_price_usd",
            color_continuous_scale="Blues",
            height=400,
        )
        fig_price.update_layout(
            hovermode="closest",
            xaxis_title="Median Price (USD)",
            yaxis_title="",
            coloraxis_showscale=False,
        )
        fig_price.update_traces(
            hovertemplate="<b>%{y}</b><br>Median Price: $%{x:,.0f}<extra></extra>"
        )
        st.plotly_chart(fig_price, use_container_width=True)
    else:
        st.info("No price data available for selected filters.")

    # ========================================================================
    # OCCUPANCY ANALYSIS
    # ========================================================================
    st.markdown("### 📈 Estimated Occupancy by Neighbourhood (Top 20)")

    if not occupancy_data.empty:
        occupancy_top20 = (
            occupancy_data.sort_values("avg_occupancy_rate", ascending=False)
            .head(20)
            .sort_values("avg_occupancy_rate", ascending=True)
            .copy()
        )
        occupancy_top20["occupancy_pct"] = occupancy_top20["avg_occupancy_rate"] * 100

        fig_occupancy = px.bar(
            occupancy_top20,
            x="occupancy_pct",
            y="neighbourhood",
            orientation="h",
            title=None,
            labels={"occupancy_pct": "Estimated Occupancy (%)", "neighbourhood": ""},
            color="occupancy_pct",
            color_continuous_scale="Greens",
            height=400,
        )
        fig_occupancy.update_layout(
            hovermode="closest",
            xaxis_title="Estimated Occupancy (%)",
            yaxis_title="",
            coloraxis_showscale=False,
        )
        fig_occupancy.update_traces(
            hovertemplate="<b>%{y}</b><br>Est. Occupancy: %{x:.1f}%<extra></extra>"
        )
        st.plotly_chart(fig_occupancy, use_container_width=True)
    else:
        st.info("No occupancy data available for selected filters.")

    # ========================================================================
    # SUPPLY-DEMAND QUADRANT
    # ========================================================================
    st.markdown(
        "### 🎯 Supply-Demand Matrix (Investment Opportunity Quadrant)"
    )
    st.markdown(
        "*High occupancy + low supply = underserved market. "
        "High supply + low occupancy = oversupplied.*"
    )

    if not matrix_data.empty:
        # Convert occupancy to percentage for display
        matrix_display = matrix_data.copy()
        matrix_display["occupancy_pct"] = matrix_display["avg_occupancy_rate"] * 100

        # Filter out neighbourhoods with missing prices (no priced listings in snapshot)
        plot_data = matrix_display.dropna(subset=["median_price_usd"])
        excluded = len(matrix_display) - len(plot_data)

        if excluded > 0:
            st.caption(
                f"⚠️ {excluded} neighbourhood(s) excluded from chart — no priced listings "
                "in this snapshot (all listings are marked stale). Full data table below shows all rows."
            )

        if not plot_data.empty:
            fig_scatter = px.scatter(
                plot_data,
                x="listing_count",
                y="occupancy_pct",
                size="median_price_usd",
                color="borough",
                hover_name="neighbourhood",
                hover_data={
                    "listing_count": ":.0f",
                    "occupancy_pct": ":.1f",
                    "median_price_usd": "$:,.0f",
                    "total_reviews": ":.0f",
                },
                labels={
                    "listing_count": "Supply (Listing Count)",
                    "occupancy_pct": "Estimated Occupancy (%)",
                    "borough": "Borough",
                },
                color_discrete_sequence=px.colors.qualitative.Set2,
                size_max=30,
                height=500,
                title=None,
            )
            fig_scatter.update_layout(
                hovermode="closest",
                xaxis_title="Supply (Listing Count)",
                yaxis_title="Estimated Occupancy (%)",
                legend=dict(title="Borough", orientation="v", yanchor="top", y=0.99),
            )
            fig_scatter.update_traces(
                marker=dict(line=dict(width=0.5, color="white"))
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("No neighbourhoods with priced listings available for selected filters.")
    else:
        st.info("No matrix data available for selected filters.")

    # ========================================================================
    # DATA TABLE
    # ========================================================================
    st.markdown("### 📋 Full Neighbourhood Matrix")

    if not matrix_data.empty:
        table_data = matrix_data.copy()
        table_data["occupancy_pct"] = table_data["avg_occupancy_rate"] * 100
        table_data = table_data.sort_values("listing_count", ascending=False)

        display_cols = [
            "neighbourhood",
            "borough",
            "listing_count",
            "median_price_usd",
            "occupancy_pct",
            "total_reviews",
        ]
        table_display = table_data[display_cols].rename(
            columns={
                "neighbourhood": "Neighbourhood",
                "borough": "Borough",
                "listing_count": "Listings",
                "median_price_usd": "Median Price",
                "occupancy_pct": "Est. Occupancy (%)",
                "total_reviews": "Total Reviews",
            }
        )

        # Format columns
        table_display["Median Price"] = table_display["Median Price"].apply(
            lambda x: f"${x:,.0f}"
        )
        table_display["Est. Occupancy (%)"] = table_display[
            "Est. Occupancy (%)"
        ].apply(lambda x: f"{x:.1f}%")
        table_display["Listings"] = table_display["Listings"].apply(lambda x: f"{x:,.0f}")
        table_display["Total Reviews"] = table_display["Total Reviews"].apply(
            lambda x: f"{x:,.0f}"
        )

        st.dataframe(table_display, use_container_width=True, hide_index=True)
    else:
        st.info("No data available for selected filters.")

    # ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown("---")
    st.caption(
        "**Data Notes:** "
        "Estimated Occupancy is derived from availability data (unavailable nights ÷ total nights), "
        "not observed bookings. "
        f"Snapshot: {selected_snapshot.strftime('%B %d, %Y')}. "
        "Median price is used to avoid distortion from luxury outliers."
    )
else:
    st.warning("👈 Select at least one borough from the sidebar to view data.")
