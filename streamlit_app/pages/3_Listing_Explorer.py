"""
Listing Explorer — Search and inspect individual listings; view SCD2 price history.

Questions answered:
  - Find listings matching specific criteria (location, price, room type)
  - How has a listing's price changed over time? (SCD2 history)
"""

import streamlit as st
import plotly.express as px
from datetime import date
from utils.queries import (
    get_snapshot_dates,
    get_boroughs,
    get_neighbourhoods,
    get_room_types,
    search_listings,
    get_listing_detail,
)

st.set_page_config(layout="wide")
st.title("🔍 Listing Explorer")

# ============================================================================
# SIDEBAR: Filters
# ============================================================================
with st.sidebar:
    st.subheader("🔎 Search Filters")

    # Snapshot Date
    snapshot_dates_df = get_snapshot_dates()
    available_dates = sorted(snapshot_dates_df["_snapshot_date"].tolist(), reverse=True)
    selected_snapshot = st.selectbox(
        "Snapshot Date",
        available_dates,
        format_func=lambda d: d.strftime("%B %d, %Y"),
    )

    # Borough
    boroughs_df = get_boroughs()
    available_boroughs = sorted(boroughs_df["borough"].tolist())
    selected_borough = st.selectbox("Borough", available_boroughs)

    # Neighbourhood (dependent on borough)
    if selected_borough:
        neighbourhoods_df = get_neighbourhoods(borough=selected_borough)
        available_neighbourhoods = sorted(neighbourhoods_df["neighbourhood"].tolist())
        selected_neighbourhood = st.selectbox("Neighbourhood", available_neighbourhoods, key="neighbourhood_select")
    else:
        selected_neighbourhood = None

    # Room Type
    room_types_df = get_room_types()
    available_room_types = sorted(room_types_df["room_type"].tolist())
    selected_room_type = st.selectbox(
        "Room Type",
        ["All"] + available_room_types,
    )
    if selected_room_type == "All":
        selected_room_type = None

    # Price Range Slider
    price_range = st.slider(
        "Price Range (USD)",
        min_value=0,
        max_value=1000,
        value=(0, 1000),
        step=10,
    )
    min_price, max_price = price_range

# ============================================================================
# SEARCH RESULTS
# ============================================================================
st.markdown("### Search Results")

if selected_borough and selected_neighbourhood:
    results = search_listings(
        limit=100,
        borough=selected_borough,
        room_type=selected_room_type,
        min_price=min_price,
        max_price=max_price,
        snapshot_date=selected_snapshot,
    )

    if not results.empty:
        st.markdown(f"**Found {len(results)} listings**")

        # Format results table
        results_display = results.copy()
        results_display["price_usd"] = results_display["price_usd"].apply(lambda x: f"${x:,.0f}")
        results_display["occupancy_rate"] = results_display["occupancy_rate"].apply(
            lambda x: f"{x*100:.1f}%"
        )
        results_display["number_of_reviews"] = results_display["number_of_reviews"].astype(int)

        display_cols = [
            "listing_id",
            "listing_name",
            "neighbourhood",
            "room_type",
            "price_usd",
            "number_of_reviews",
            "occupancy_rate",
        ]
        results_table = results_display[display_cols].rename(
            columns={
                "listing_id": "Listing ID",
                "listing_name": "Name",
                "neighbourhood": "Neighbourhood",
                "room_type": "Room Type",
                "price_usd": "Price",
                "number_of_reviews": "Reviews",
                "occupancy_rate": "Est. Occupancy",
            }
        )

        st.dataframe(results_table, use_container_width=True, hide_index=True)

        # ====================================================================
        # LISTING DETAIL
        # ====================================================================
        st.markdown("---")
        st.markdown("### Listing Details & Price History")

        # Selectbox to pick a listing
        listing_options = {row["listing_name"]: row["listing_id"] for _, row in results.iterrows()}
        selected_listing_name = st.selectbox(
            "Select a listing to view details:",
            listing_options.keys(),
        )
        selected_listing_id = listing_options[selected_listing_name]

        if selected_listing_id:
            listing_detail = get_listing_detail(selected_listing_id)

            if not listing_detail.empty:
                # Display current version info
                current = listing_detail[listing_detail["is_current"] == True]
                if not current.empty:
                    row = current.iloc[0]
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Property Type", row["property_type"])
                    with col2:
                        st.metric("Accommodates", int(row["accommodates"]))
                    with col3:
                        st.metric("Bedrooms", int(row["bedrooms"]) if row["bedrooms"] else "—")
                    with col4:
                        st.metric("Bathrooms", f"{row['bathrooms']:.1f}" if row["bathrooms"] else "—")

                # Price history table
                st.markdown("#### Price History (SCD2)")
                history_display = listing_detail.copy()
                history_display["price_usd"] = history_display["price_usd"].apply(
                    lambda x: f"${x:,.0f}"
                )
                history_display["effective_from"] = history_display["effective_from"].astype(str)
                history_display["effective_to"] = history_display["effective_to"].astype(str)

                history_cols = [
                    "effective_from",
                    "effective_to",
                    "is_current",
                    "property_type",
                    "price_usd",
                    "beds",
                ]
                history_table = history_display[history_cols].rename(
                    columns={
                        "effective_from": "Effective From",
                        "effective_to": "Effective To",
                        "is_current": "Current",
                        "property_type": "Property Type",
                        "price_usd": "Price",
                        "beds": "Beds",
                    }
                )
                st.dataframe(history_table, use_container_width=True, hide_index=True)

                st.caption(
                    "SCD Type 2 tracks every version of this listing. "
                    "effective_from/to show when each version was active. "
                    "is_current=true means this is the latest version."
                )
            else:
                st.info("No history found for this listing.")
    else:
        st.warning("No listings match the selected filters.")
else:
    st.info("👈 Select a borough and neighbourhood to search.")
