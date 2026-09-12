import streamlit as st
import pandas as pd 
import plotly.express as px
import time
import os

st.set_page_config(page_title="ZeroNoise Dashboard", layout="wide")
st.markdown("""
    <style>
        .metric-card {
            background-color: #1e293b;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #3b82f6;
            text-align: center;
        }
        .stMetric {
            background-color: transparent !important;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=2) # Cache for 2 seconds to allow auto-refresh without excessive IO
def load_data():
    if os.path.exists("live_alerts.csv") and os.path.getsize("live_alerts.csv") > 0:
        try:
            df = pd.read_csv("live_alerts.csv", low_memory=False, on_bad_lines='skip')
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], format='mixed', errors="coerce")
            return df
        except Exception as e:
            st.error(f"Error loading live data: {e}")
            return pd.DataFrame()
    else:
        return pd.DataFrame()

st.title("🔴 ZeroNoise: Security Incident & Alert Dashboard")

# Auto-refresh mechanism
col_title, col_refresh = st.columns([3, 1])
with col_refresh:
    auto_refresh = st.toggle("Live Auto-Refresh", value=True)

df = load_data()

if df.empty:
    st.info("Waiting for live telemetry data. Start the Live Stream in the ZeroNoise Operational Console.")
else:
    st.sidebar.header("Filter Parameters")
    grade_filter = st.sidebar.multiselect("Select Incident Grade:", options=df["IncidentGrade"].dropna().unique(), default=df["IncidentGrade"].dropna().unique())
    category_filter = st.sidebar.multiselect("Select Category:", options=df["Category"].dropna().unique())
    entity_filter = st.sidebar.multiselect("Select Entity Type:", options=df["EntityType"].dropna().unique())

    filtered_df = df[df["IncidentGrade"].isin(grade_filter)]
    if category_filter: filtered_df = filtered_df[filtered_df["Category"].isin(category_filter)]
    if entity_filter: filtered_df = filtered_df[filtered_df["EntityType"].isin(entity_filter)]

    total_alerts = len(filtered_df)
    true_positives = len(filtered_df[filtered_df["IncidentGrade"] == "TruePositive"])
    false_positives = len(filtered_df[filtered_df["IncidentGrade"] == "FalsePositive"])
    unique_devices = filtered_df["DeviceId"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Processed", f"{total_alerts:,}")
    col2.metric("True Positives", f"{true_positives:,}")
    col3.metric("False Positives", f"{false_positives:,}")
    col4.metric("Unique Devices", f"{unique_devices:,}")

    st.markdown("---")
    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("Live Alert Timeline")
        recent_df = filtered_df.tail(500) # Only chart recent ones for performance
        timeline = recent_df.groupby(recent_df["Timestamp"].dt.floor('S')).size().reset_index(name="Alert Count")
        if not timeline.empty:
            fig_trend = px.line(timeline, x="Timestamp", y="Alert Count", markers=True, template="plotly_dark")
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No timeline data yet.")

    with c2:
        st.subheader("Incident Grade Distribution")
        grade_counts = filtered_df.groupby("IncidentGrade").size().reset_index(name="Count")
        if not grade_counts.empty:
            fig_grade = px.pie(grade_counts, values="Count", names="IncidentGrade", hole=0.6, template="plotly_dark")
            st.plotly_chart(fig_grade, use_container_width=True)

    st.subheader("Alerts by Category")
    category_counts = filtered_df.groupby("Category").size().reset_index(name="Count")
    if not category_counts.empty:
        fig_cat = px.bar(category_counts, x="Category", y="Count", color="Category", text_auto=True, template="plotly_dark")
        st.plotly_chart(fig_cat, use_container_width=True)

    with st.expander("View Detailed Live Alert Logs (Latest 100)"):
        st.dataframe(filtered_df.sort_values(by="Timestamp", ascending=False).head(100), use_container_width=True)

    st.subheader("Summary Report")
    summary = filtered_df.groupby("Category").agg(
        Total_Alerts=("AlertId", "count"),
        Unique_Entities=("EntityType", "nunique"),
        Unique_Devices=("DeviceId", "nunique")
    ).reset_index()
    st.dataframe(summary, use_container_width=True)

    csv = summary.to_csv(index=False).encode()
    st.download_button("Download Summary Report (CSV)", csv, "Incident_Summary.csv", "text/csv")

if auto_refresh:
    time.sleep(2)
    st.rerun()