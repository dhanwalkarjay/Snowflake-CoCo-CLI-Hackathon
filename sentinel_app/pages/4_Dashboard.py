import streamlit as st

st.header("Dashboard")

session = st.connection("snowflake").session()

# KPI row
alerts_summary = session.sql("""
    SELECT COUNT(*) AS TOTAL,
           SUM(CASE WHEN SEVERITY='CRITICAL' THEN 1 ELSE 0 END) AS CRITICAL_CNT,
           SUM(CASE WHEN STATUS='OPEN' THEN 1 ELSE 0 END) AS OPEN_CNT
    FROM SENTINEL_DB.RISK.ALERTS
""").to_pandas().iloc[0]

loan_stats = session.sql("""
    SELECT COUNT(*) AS TOTAL_LOANS,
           SUM(CASE WHEN DPD > 90 THEN 1 ELSE 0 END) AS NPA_LOANS
    FROM SENTINEL_DB.RAW.LOANS
""").to_pandas().iloc[0]

lcr_stats = session.sql("""
    SELECT ROUND(MIN(LCR_RATIO), 4) AS MIN_LCR
    FROM SENTINEL_DB.RAW.LIQUIDITY_POSITIONS
    WHERE REPORTING_DATE = (SELECT MAX(REPORTING_DATE) FROM SENTINEL_DB.RAW.LIQUIDITY_POSITIONS)
""").to_pandas().iloc[0]

findings_cnt = session.sql("SELECT COUNT(*) AS CNT FROM SENTINEL_DB.RISK.FINDINGS").to_pandas().iloc[0]["CNT"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Alerts", int(alerts_summary["TOTAL"]))
c2.metric("Critical", int(alerts_summary["CRITICAL_CNT"]))
c3.metric("Findings Logged", int(findings_cnt))
npa_pct = round(loan_stats["NPA_LOANS"] / max(loan_stats["TOTAL_LOANS"], 1) * 100, 2)
c4.metric("NPA Ratio", f"{npa_pct}%")
c5.metric("Min LCR", f"{lcr_stats['MIN_LCR']:.1%}")

st.divider()

# Alerts by type
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Alerts by Type")
    by_type = session.sql("""
        SELECT ALERT_TYPE, COUNT(*) AS CNT
        FROM SENTINEL_DB.RISK.ALERTS
        GROUP BY ALERT_TYPE ORDER BY CNT DESC
    """).to_pandas()
    st.bar_chart(by_type, x="ALERT_TYPE", y="CNT", horizontal=True)

with col_b:
    st.subheader("Alerts by Severity")
    by_sev = session.sql("""
        SELECT SEVERITY, COUNT(*) AS CNT
        FROM SENTINEL_DB.RISK.ALERTS
        GROUP BY SEVERITY ORDER BY CASE SEVERITY
            WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 END
    """).to_pandas()
    st.bar_chart(by_sev, x="SEVERITY", y="CNT")

st.divider()
st.subheader("Precision / Recall by Pattern")
pr = session.sql("""
    WITH truth AS (
        SELECT ACCOUNT_ID, FRAUD_PATTERN FROM SENTINEL_DB.RAW.FRAUD_TRUTH
    ),
    detected AS (
        SELECT DISTINCT ENTITY_ID, ALERT_TYPE FROM SENTINEL_DB.RISK.ALERTS
    )
    SELECT
        t.FRAUD_PATTERN AS PATTERN,
        COUNT(DISTINCT t.ACCOUNT_ID) AS PLANTED,
        COUNT(DISTINCT CASE WHEN d.ENTITY_ID IS NOT NULL THEN t.ACCOUNT_ID END) AS TRUE_POS,
        COUNT(DISTINCT CASE WHEN d.ENTITY_ID IS NOT NULL THEN t.ACCOUNT_ID END)
            || '/' || COUNT(DISTINCT t.ACCOUNT_ID) AS RECALL_FRAC
    FROM truth t
    LEFT JOIN detected d ON t.ACCOUNT_ID = d.ENTITY_ID
    GROUP BY t.FRAUD_PATTERN ORDER BY t.FRAUD_PATTERN
""").to_pandas()
st.dataframe(pr, use_container_width=True, hide_index=True)
