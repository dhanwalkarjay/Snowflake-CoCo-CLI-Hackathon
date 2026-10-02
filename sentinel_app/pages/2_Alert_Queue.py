import streamlit as st

st.header("Alert Queue")

session = st.connection("snowflake").session()

rules = session.sql("SELECT DISTINCT RULE_NAME FROM SENTINEL_DB.RISK.RULES ORDER BY 1").to_pandas()
rule_options = rules["RULE_NAME"].tolist()

col1, col2, col3 = st.columns(3)
with col1:
    sel_rules = st.multiselect("Rule", rule_options, default=rule_options)
with col2:
    sel_severity = st.multiselect("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], default=["CRITICAL", "HIGH", "MEDIUM", "LOW"])
with col3:
    sel_status = st.selectbox("Status", ["OPEN", "CLOSED", "ALL"], index=0)

where = ["1=1"]
if sel_rules and len(sel_rules) < len(rule_options):
    quoted = ",".join([f"'{r}'" for r in sel_rules])
    where.append(f"r.RULE_NAME IN ({quoted})")
if sel_severity and len(sel_severity) < 4:
    quoted = ",".join([f"'{s}'" for s in sel_severity])
    where.append(f"a.SEVERITY IN ({quoted})")
if sel_status != "ALL":
    where.append(f"a.STATUS = '{sel_status}'")

sql = f"""
    SELECT a.ALERT_ID, r.RULE_NAME, a.ALERT_TYPE, a.SEVERITY, a.SCORE,
           a.ENTITY_ID, a.STATUS, a.CREATED_AT
    FROM SENTINEL_DB.RISK.ALERTS a
    JOIN SENTINEL_DB.RISK.RULES r ON a.RULE_ID = r.RULE_ID
    WHERE {' AND '.join(where)}
    ORDER BY a.SCORE DESC, a.CREATED_AT DESC
    LIMIT 200
"""

df = session.sql(sql).to_pandas()
st.metric("Matching alerts", len(df))

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "SCORE": st.column_config.ProgressColumn("Score", min_value=0, max_value=1, format="%.3f"),
    },
)

st.divider()
st.subheader("Investigate an alert")
if len(df) > 0:
    selected = st.selectbox("Pick an alert", df["ALERT_ID"].tolist())
    if st.button("Open in Case View", type="primary"):
        st.session_state["selected_alert_id"] = selected
        st.switch_page("pages/3_Case_View.py")
