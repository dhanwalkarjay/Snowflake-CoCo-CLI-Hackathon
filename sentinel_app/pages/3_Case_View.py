import streamlit as st
import json

st.header("Case View")

session = st.connection("snowflake").session()

alert_id = st.session_state.get("selected_alert_id", "")
alert_id = st.text_input("Alert ID", value=alert_id, placeholder="e.g. ALRT-MUL-21")

if not alert_id:
    st.info("Enter an alert ID or select one from the Alert Queue.")
    st.stop()

alert_row = session.sql(f"""
    SELECT a.*, r.RULE_NAME, r.REGULATION_REF
    FROM SENTINEL_DB.RISK.ALERTS a
    JOIN SENTINEL_DB.RISK.RULES r ON a.RULE_ID = r.RULE_ID
    WHERE a.ALERT_ID = '{alert_id}'
""").to_pandas()

if alert_row.empty:
    st.error(f"Alert {alert_id} not found.")
    st.stop()

row = alert_row.iloc[0]
entity_id = row["ENTITY_ID"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Severity", row["SEVERITY"])
c2.metric("Score", f"{row['SCORE']:.3f}")
c3.metric("Type", row["ALERT_TYPE"])
c4.metric("Status", row["STATUS"])

st.markdown(f"**Reason:** {row['REASON']}")
st.markdown(f"**Regulation:** {row['REGULATION_REF']}")

st.divider()
st.subheader(f"Evidence for {entity_id}")

evidence = session.sql(f"CALL SENTINEL_DB.APP.GET_ACCOUNT_EVIDENCE('{entity_id}')").collect()[0][0]
ev = json.loads(evidence) if isinstance(evidence, str) else evidence

acct = ev.get("account", {})
col1, col2, col3 = st.columns(3)
col1.markdown(f"**Customer:** {acct.get('customer_name', 'N/A')}")
col2.markdown(f"**KYC:** {acct.get('kyc_status', 'N/A')} | **Risk:** {acct.get('risk_rating', 'N/A')}")
col3.markdown(f"**Balance:** INR {acct.get('balance', 0):,.0f}")

txns = ev.get("recent_transactions", [])
if txns:
    st.markdown("**Recent Transactions**")
    st.dataframe(txns, use_container_width=True, hide_index=True)

alerts_list = ev.get("alerts", [])
if alerts_list:
    st.markdown("**Rule Hits**")
    st.dataframe(alerts_list, use_container_width=True, hide_index=True)

citations = ev.get("policy_citations", [])
if citations:
    st.markdown("**Primary Policy Citations**")
    for cit in citations:
        st.info(f"**{cit.get('doc_name', '')}** (p.{cit.get('page', '?')}, {cit.get('regulation_type', '')})\n\n{cit.get('content_preview', '')}")

st.divider()
col_a, col_b = st.columns(2)

with col_a:
    if st.button("Generate Report", type="primary"):
        with st.spinner("Generating report..."):
            report_raw = session.sql(f"CALL SENTINEL_DB.APP.GENERATE_REPORT('{alert_id}')").collect()[0][0]
            report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
            st.session_state["last_report"] = report
        st.success(f"Report generated: {report.get('case_id', 'N/A')}")

with col_b:
    if st.button("Approve & Log Finding", type="secondary"):
        report = st.session_state.get("last_report")
        if not report:
            st.warning("Generate a report first.")
        else:
            with st.spinner("Logging finding..."):
                result = session.sql(f"""
                    CALL SENTINEL_DB.APP.LOG_FINDING(
                        '{report.get("alert_id", "")}',
                        '{report.get("account_id", "")}',
                        '{report.get("alert_type", "")}',
                        '{report.get("severity", "")}',
                        'SUSPICIOUS',
                        '{report.get("narrative", "").replace("'", "''")}',
                        '{json.dumps(report.get("evidence", {})).replace("'", "''")}',
                        '{json.dumps(report.get("policy_citation", {})).replace("'", "''")}',
                        '{report.get("recommended_action", "")}'
                    )
                """).collect()[0][0]
                log_result = json.loads(result) if isinstance(result, str) else result
            st.success(f"Finding logged: {log_result.get('finding_id', 'done')}")

if st.session_state.get("last_report"):
    rpt = st.session_state["last_report"]
    st.divider()
    st.subheader("Investigation Report")
    st.markdown(f"**Case ID:** {rpt.get('case_id')}")
    st.markdown(f"**Narrative:** {rpt.get('narrative')}")
    st.markdown(f"**Narrative validated:** {rpt.get('narrative_validated')}")
    st.markdown(f"**Recommended action:** {rpt.get('recommended_action')}")
    cit = rpt.get("policy_citation", {})
    st.info(f"**{cit.get('document', '')}** (p.{cit.get('page', '?')}, {cit.get('regulation_type', '')})\n\n{cit.get('excerpt', '')}")
    with st.expander("Full evidence JSON"):
        st.json(rpt.get("evidence", {}))
