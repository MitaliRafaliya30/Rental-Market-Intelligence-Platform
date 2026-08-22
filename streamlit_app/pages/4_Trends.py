"""
Trends — Price, occupancy, and demand over time; seasonality patterns.

Questions answered:
  - How are prices trending across snapshots by borough?
  - How is estimated occupancy trending?
  - What is the long-term demand signal (review volume 2009–present)?
  - What are seasonality patterns (busy/slow months)?
"""

import streamlit as st
import plotly.express as px
from utils.queries import (
    get_price_trend,
    get_occupancy_trend,
    get_review_volume_trend,
    get_seasonality,
    get_boroughs,
)

st.set_page_config(layout="wide")
st.title("📈 Trends")

# ============================================================================
# SIDEBAR: Filter by borough for trend lines
# ============================================================================
with st.sidebar:
    st.subheader("📊 Trends Filters")

    # Borough selector (optional - shows all by default)
    boroughs_df = get_boroughs()
    available_boroughs = sorted(boroughs_df["borough"].tolist())
    selected_borough = st.selectbox(
        "Borough (optional, shows all if not selected)",
        ["All"] + available_boroughs,
    )
    if selected_borough == "All":
        selected_borough = None

# ============================================================================
# PRICE TREND
# ============================================================================
st.markdown("### 💰 Median Price Trend by Borough")

price_trend = get_price_trend(borough=selected_borough)
if not price_trend.empty:
    fig_price_trend = px.line(
        price_trend,
        x="_snapshot_date",
        y="median_price_usd",
        color="borough",
        markers=True,
        title=None,
        labels={
            "_snapshot_date": "Snapshot Date",
            "median_price_usd": "Median Price (USD)",
            "borough": "Borough",
        },
        color_discrete_sequence=px.colors.qualitative.Set2,
        height=400,
    )
    fig_price_trend.update_layout(
        hovermode="x unified",
        xaxis_title="Snapshot Date",
        yaxis_title="Median Price (USD)",
        legend=dict(title="Borough", orientation="v", yanchor="top", y=0.99),
    )
    fig_price_trend.update_traces(
        hovertemplate="<b>%{customdata[0]}</b><br>Price: $%{y:,.0f}<extra></extra>",
        customdata=price_trend[["borough"]],
    )
    st.plotly_chart(fig_price_trend, use_container_width=True)
    st.caption(
        "⚠️ With only 2 snapshots, trend lines show just 2 points. "
        "More frequent snapshots will reveal richer patterns over time."
    )
else:
    st.info("No price trend data available.")

# ============================================================================
# OCCUPANCY TREND
# ============================================================================
st.markdown("### 📊 Estimated Occupancy Trend by Borough")

occupancy_trend = get_occupancy_trend(borough=selected_borough)
if not occupancy_trend.empty:
    # Convert to percentage for display
    occupancy_trend_pct = occupancy_trend.copy()
    occupancy_trend_pct["occupancy_pct"] = occupancy_trend_pct["avg_occupancy_rate"] * 100

    fig_occupancy_trend = px.line(
        occupancy_trend_pct,
        x="_snapshot_date",
        y="occupancy_pct",
        color="borough",
        markers=True,
        title=None,
        labels={
            "_snapshot_date": "Snapshot Date",
            "occupancy_pct": "Est. Occupancy (%)",
            "borough": "Borough",
        },
        color_discrete_sequence=px.colors.qualitative.Set2,
        height=400,
    )
    fig_occupancy_trend.update_layout(
        hovermode="x unified",
        xaxis_title="Snapshot Date",
        yaxis_title="Estimated Occupancy (%)",
        legend=dict(title="Borough", orientation="v", yanchor="top", y=0.99),
    )
    fig_occupancy_trend.update_traces(
        hovertemplate="<b>%{customdata[0]}</b><br>Est. Occupancy: %{y:.1f}%<extra></extra>",
        customdata=occupancy_trend_pct[["borough"]],
    )
    st.plotly_chart(fig_occupancy_trend, use_container_width=True)
    st.caption(
        "⚠️ With only 2 snapshots, trend lines show just 2 points. "
        "More frequent snapshots will reveal richer patterns over time."
    )
else:
    st.info("No occupancy trend data available.")

# ============================================================================
# REVIEW VOLUME TREND (Long-term signal)
# ============================================================================
st.markdown("### 🔍 Review Volume Trend (2009–Present)")
st.markdown(
    "*This is the genuine long-term demand signal, covering 10+ years of data. "
    "Snapshot-based trends above show only weeks. This gives the full historical context.*"
)

review_trend = get_review_volume_trend()
if not review_trend.empty:
    review_trend["date"] = (
        review_trend["calendar_year"].astype(str)
        + "-"
        + review_trend["calendar_month"].astype(str).str.zfill(2)
    )

    fig_review_trend = px.line(
        review_trend,
        x="date",
        y="review_count",
        markers=True,
        title=None,
        labels={
            "date": "Year-Month",
            "review_count": "Review Count",
        },
        height=450,
    )
    fig_review_trend.update_layout(
        hovermode="x unified",
        xaxis_title="Year-Month",
        yaxis_title="Monthly Review Count",
    )
    # Thin out x-axis labels for readability
    fig_review_trend.update_xaxes(
        tickmode="linear",
        tick0=0,
        dtick=12,
    )
    st.plotly_chart(fig_review_trend, use_container_width=True)
else:
    st.info("No review trend data available.")

# ============================================================================
# SEASONALITY
# ============================================================================
st.markdown("### 🌞 Seasonality: Estimated Occupancy by Month")
st.markdown("*(Averaged across all available years)*")

seasonality = get_seasonality()
if not seasonality.empty:
    seasonality_pct = seasonality.copy()
    seasonality_pct["occupancy_pct"] = seasonality_pct["avg_occupancy_rate"] * 100

    fig_seasonality = px.bar(
        seasonality_pct.sort_values("calendar_month"),
        x="calendar_month_name",
        y="occupancy_pct",
        title=None,
        labels={
            "calendar_month_name": "Month",
            "occupancy_pct": "Est. Occupancy (%)",
        },
        color="occupancy_pct",
        color_continuous_scale="Blues",
        height=400,
    )
    fig_seasonality.update_layout(
        hovermode="closest",
        xaxis_title="Month",
        yaxis_title="Estimated Occupancy (%)",
        coloraxis_showscale=False,
    )
    fig_seasonality.update_traces(
        hovertemplate="<b>%{x}</b><br>Est. Occupancy: %{y:.1f}%<extra></extra>"
    )
    st.plotly_chart(fig_seasonality, use_container_width=True)
else:
    st.info("No seasonality data available.")
