import streamlit as st
import pandas as pd
import plotly.express as px
import time
import requests
from sqlalchemy import create_engine

st.set_page_config(page_title="ZeroNoise SOC", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        .stApp { background-color: #0b1121; color: #e2e8f0; }
        [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1f2937; }
        .metric-container { background-color: #1f2937; border-radius: 8px; padding: 15px; border-top: 3px solid #3b82f6; }
        .sev-critical { color: #ef4444; font-weight: bold; }
        .sev-high { color: #f97316; font-weight: bold; }
        .sev-medium { color: #eab308; font-weight: bold; }
        .sev-low { color: #22c55e; font-weight: bold; }
        .right-panel { background-color: #111827; padding: 20px; border-radius: 10px; border: 1px solid #374151; }
    </style>
""", unsafe_allow_html=True)

DATABASE_URL = "sqlite:///./zeronoise.db"
engine = create_engine(DATABASE_URL)

@st.cache_data(ttl=2)
def load_data():
    try:
        query_alerts = "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 2000"
        query_incidents = "SELECT * FROM incidents ORDER BY updated_at DESC"
        df_alerts = pd.read_sql(query_alerts, engine)
        df_incidents = pd.read_sql(query_incidents, engine)
        if not df_alerts.empty: df_alerts["timestamp"] = pd.to_datetime(df_alerts["timestamp"])
        if not df_incidents.empty: df_incidents["updated_at"] = pd.to_datetime(df_incidents["updated_at"])
        return df_alerts, df_incidents
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

df, df_inc = load_data()

st.sidebar.image("https://img.icons8.com/fluency/48/000000/shield.png", width=40)
st.sidebar.title("ZeroNoise")
st.sidebar.caption("Security Operations Center")

st.sidebar.markdown("### COMMAND")
nav = st.sidebar.radio("Navigate", ["Overview", "Live SOC", "Incidents", "Assets"], label_visibility="collapsed", index=1)

API_URL = "http://localhost:5053"

t1, t2, t3 = st.columns([6, 2, 2])
with t1:
    st.markdown(f"## {nav}")
with t2:
    st.markdown("<div style='margin-top: 20px; color: #22c55e;'>● All systems operational</div>", unsafe_allow_html=True)
with t3:
    auto_refresh = st.checkbox("Live Auto-Refresh", value=True)
    if st.button("Toggle Telemetry Generator"):
        try:
            requests.post(f"{API_URL}/api/toggle_stream", json={"streaming": True})
            st.toast("Telemetry Generator Started!")
        except:
            st.error("Backend API not reachable.")

st.markdown("---")

if nav == "Live SOC":
    if df.empty:
        st.info("No alerts ingested yet.")
        st.stop()

    # HERO METRICS
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"""
        <div class="metric-container">
            <div style="color: #9ca3af; font-size: 0.9rem;">ACTIVE ALERTS</div>
            <div style="font-size: 2rem; font-weight: bold;">{len(df):,}</div>
        </div>
    """, unsafe_allow_html=True)

    col2.markdown(f"""
        <div class="metric-container" style="border-color: #f97316;">
            <div style="color: #9ca3af; font-size: 0.9rem;">OPEN INCIDENTS</div>
            <div style="font-size: 2rem; font-weight: bold;">{len(df_inc) if not df_inc.empty else 0}</div>
        </div>
    """, unsafe_allow_html=True)

    high_risk = len(df[df["risk_score"] >= 60])
    col3.markdown(f"""
        <div class="metric-container" style="border-color: #ef4444;">
            <div style="color: #9ca3af; font-size: 0.9rem;">HIGH RISK</div>
            <div style="font-size: 2rem; font-weight: bold;">{high_risk}</div>
        </div>
    """, unsafe_allow_html=True)

    assets = df['device_id'].nunique()
    col4.markdown(f"""
        <div class="metric-container" style="border-color: #06b6d4;">
            <div style="color: #9ca3af; font-size: 0.9rem;">IMPACTED ASSETS</div>
            <div style="font-size: 2rem; font-weight: bold;">{assets:,}</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    left_col, right_col = st.columns([7, 3])

    with left_col:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### EVENTS BY SEVERITY")
            sev_counts = df["severity"].value_counts().reset_index()
            sev_counts.columns = ["Severity", "Count"]
            color_map = {"Critical": "#ef4444", "High": "#f97316", "Medium": "#eab308", "Low": "#22c55e"}
            fig1 = px.pie(sev_counts, names="Severity", values="Count", hole=0.7, color="Severity", color_discrete_map=color_map)
            fig1.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), showlegend=False)
            st.plotly_chart(fig1, use_container_width=True)
            
        with c2:
            st.markdown("#### TOP ALERT SOURCES")
            src_counts = df["source"].value_counts().head(5).reset_index()
            src_counts.columns = ["Source", "Count"]
            fig2 = px.bar(src_counts, x="Count", y="Source", orientation='h')
            fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"))
            fig2.update_traces(marker_color='#3b82f6')
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### LIVE ALERT STREAM")
        display_df = df[["timestamp", "risk_score", "category", "source", "action", "event_id", "status"]].head(20).copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime('%H:%M:%S')
        
        st.dataframe(
            display_df,
            column_config={
                "timestamp": "TIME",
                "risk_score": st.column_config.NumberColumn("RISK", format="%d"),
                "category": "ALERT",
                "source": "SOURCE",
                "action": "ACTION",
                "status": "STATUS",
                "event_id": None
            },
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="alert_table"
        )

    with right_col:
        selected_rows = st.session_state.alert_table.selection.rows
        if selected_rows:
            selected_idx = selected_rows[0]
            selected_event_id = display_df.iloc[selected_idx]["event_id"]
            alert = df[df["event_id"] == selected_event_id].iloc[0]
            
            st.markdown(f"""
            <div class="right-panel">
                <div style="display:flex; justify-content: space-between;">
                    <div style="font-size: 0.8rem; color: #9ca3af;">ALERT #{alert['event_id']}</div>
                    <div class="sev-{alert['severity'].lower()}">{alert['severity'].upper()}</div>
                </div>
                <h3 style="margin-top: 5px;">{alert['category']}</h3>
                
                <div style="display:flex; gap: 20px; margin-top: 15px;">
                    <div>
                        <div style="font-size: 0.8rem; color: #9ca3af;">Risk Score</div>
                        <div style="font-size: 2rem; font-weight: bold; color: {'#ef4444' if alert['risk_score'] > 75 else '#f97316'};">{int(alert['risk_score'])}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.8rem; color: #9ca3af;">Confidence</div>
                        <div style="font-size: 1.5rem; margin-top:5px;">{alert['confidence']*100:.1f}%</div>
                    </div>
                </div>
                
                <hr style="border-color: #374151;">
                
                <h5 style="color: #9ca3af;">WHY THIS ALERT?</h5>
                <div style="font-size: 0.9rem; line-height: 1.8;">
                    <div style="display:flex; justify-content: space-between;"><span>MITRE Technique</span></div>
                    <div style="color: #9ca3af; font-size: 0.8rem;">{alert['mitre_techniques']}</div>
                    
                    <div style="display:flex; justify-content: space-between; margin-top:10px;"><span>Asset Criticality</span></div>
                    <div style="color: #9ca3af; font-size: 0.8rem;">{alert['asset_criticality']}</div>
                </div>
                
                <hr style="border-color: #374151;">
                
                <h5 style="color: #9ca3af;">ML FEATURE IMPORTANCE (SHAP)</h5>
                <div style="font-size: 0.85rem; line-height: 1.8;">
            """, unsafe_allow_html=True)
            
            # Extract SHAP from raw_message
            try:
                import json
                raw_data = json.loads(alert['raw_message'])
                shap_exp = raw_data.get("shap_explanation", {})
                
                if not shap_exp:
                    st.markdown("<span style='color: #9ca3af;'>SHAP explanations not available for this alert (Legacy).</span>", unsafe_allow_html=True)
                else:
                    # Render feature importance bars
                    for feat, val in sorted(shap_exp.items(), key=lambda x: abs(x[1]), reverse=True):
                        color = "#ef4444" if val > 0 else "#3b82f6"
                        bar_width = min(abs(val) * 50, 100) # scale for demo
                        st.markdown(f"""
                            <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                                <span style="color: #9ca3af; width: 40%;">{feat}</span>
                                <div style="width: 50%; background-color: #1f2937; border-radius: 3px; height: 10px;">
                                    <div style="width: {bar_width}%; background-color: {color}; height: 10px; border-radius: 3px;"></div>
                                </div>
                                <span style="color: {color}; font-size: 0.7rem; width: 10%; text-align: right;">{val:+.2f}</span>
                            </div>
                        """, unsafe_allow_html=True)
            except Exception as e:
                st.markdown("<span style='color: #9ca3af;'>SHAP explanations not available for this alert.</span>", unsafe_allow_html=True)

            st.markdown(f"""
                </div>
                
                <hr style="border-color: #374151;">
                
                <h5 style="color: #9ca3af;">ALERT DETAILS</h5>
                <div style="font-size: 0.85rem; line-height: 1.8;">
                    <table style="width: 100%;">
                        <tr><td style="color: #9ca3af; width: 40%;">User</td><td>{alert['user']}</td></tr>
                        <tr><td style="color: #9ca3af;">Asset</td><td>{alert['device_id']}</td></tr>
                        <tr><td style="color: #9ca3af;">Incident Group</td><td>{alert['incident_id']}</td></tr>
                        <tr><td style="color: #9ca3af;">Current Status</td><td>{alert['status']}</td></tr>
                    </table>
                </div>
                
                <div style="margin-top: 20px;">
                    <h6 style="color: #9ca3af;">ANALYST ACTION</h6>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # P1 Feedback Buttons
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Confirm", use_container_width=True):
                    requests.post(f"{API_URL}/api/alerts/{alert['event_id']}/feedback", json={"status": "CONFIRMED"})
                    st.toast(f"Alert {alert['event_id']} confirmed!")
            with b2:
                if st.button("False Pos", use_container_width=True):
                    requests.post(f"{API_URL}/api/alerts/{alert['event_id']}/feedback", json={"status": "FALSE_POSITIVE"})
                    st.toast(f"Alert marked as false positive.")
            with b3:
                if st.button("Suppress", use_container_width=True):
                    requests.post(f"{API_URL}/api/alerts/{alert['event_id']}/feedback", json={"status": "SUPPRESSED"})
                    st.toast(f"Alert suppressed.")
            
        else:
            st.markdown("""<div class="right-panel" style="text-align: center; color: #9ca3af; padding: 50px 20px;">
                <p>Select an alert from the table to view details.</p></div>""", unsafe_allow_html=True)

elif nav == "Incidents":
    st.markdown("### Incident Command Center")
    if df_inc.empty:
        st.info("No incidents detected.")
    else:
        # Show Incidents
        display_inc = df_inc[["updated_at", "incident_id", "title", "severity", "risk_score", "status"]].copy()
        display_inc["updated_at"] = display_inc["updated_at"].dt.strftime('%H:%M:%S')
        st.dataframe(
            display_inc,
            hide_index=True,
            use_container_width=True
        )
        
        st.markdown("---")
        st.markdown("### Interactive Attack Progression Graph")
        
        selected_inc = st.selectbox("Select Incident to Analyze:", df_inc["incident_id"].tolist())
        if selected_inc:
            # Fetch alerts for this incident
            inc_alerts = df[df["incident_id"] == selected_inc].sort_values("timestamp")
            
            if not inc_alerts.empty:
                # Generate a Mermaid Graph based on the MITRE techniques
                mermaid_code = "graph TD;\n"
                prev_node = "Initial Access"
                mermaid_code += f"    Start((Alert Stream)) --> {prev_node};\n"
                
                for idx, row in inc_alerts.iterrows():
                    tech = row["mitre_techniques"]
                    if tech and tech != "None":
                        # Clean up strings for Mermaid
                        clean_tech = tech.replace(" ", "_").replace("-", "_")
                        mermaid_code += f"    {prev_node} -->|{row['timestamp'].strftime('%H:%M:%S')}| {clean_tech}[{tech}];\n"
                        prev_node = clean_tech
                
                # Render using a custom HTML component to load Mermaid.js
                html_code = f"""
                <div class="mermaid" style="background-color: #111827; padding: 20px; border-radius: 10px; color: white;">
                    {mermaid_code}
                </div>
                <script type="module">
                    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                    mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
                </script>
                """
                import streamlit.components.v1 as components
                components.html(html_code, height=400)
            else:
                st.info("No alerts linked to this incident yet.")

if auto_refresh:
    time.sleep(2.5)
    st.rerun()