import streamlit as st

st.header("Audit Trail")

session = st.connection("snowflake").session()

st.subheader("Recent Findings")
findings = session.sql("""
    SELECT FINDING_ID, ALERT_ID, ENTITY_ID, TYPOLOGY, SEVERITY,
           CLASSIFICATION, RECOMMENDED_ACTION, CREATED_AT
    FROM SENTINEL_DB.RISK.FINDINGS
    ORDER BY CREATED_AT DESC
    LIMIT 50
""").to_pandas()

if findings.empty:
    st.info("No findings logged yet. Use Case View to generate and approve findings.")
else:
    st.dataframe(findings, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Audit Log")
audit = session.sql("""
    SELECT LOG_ID, EVENT_TYPE, ACTOR, ENTITY_TYPE, ENTITY_ID, EVENT_TIMESTAMP
    FROM SENTINEL_DB.AUDIT.AUDIT_LOG
    ORDER BY EVENT_TIMESTAMP DESC
    LIMIT 50
""").to_pandas()

if audit.empty:
    st.info("No audit events yet.")
else:
    st.dataframe(audit, use_container_width=True, hide_index=True)
