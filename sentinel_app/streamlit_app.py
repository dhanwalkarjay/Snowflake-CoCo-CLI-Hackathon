import streamlit as st

st.set_page_config(page_title="Sentinel", page_icon="\U0001F6E1", layout="wide")

st.title("Sentinel")
st.caption("Banking Fraud, AML & Regulatory Reporting Copilot")

st.markdown("""
Navigate using the sidebar:

- **Copilot** — Chat with the Sentinel agent
- **Alert Queue** — Browse and filter alerts
- **Case View** — Investigate a specific alert
- **Dashboard** — KPIs and detection metrics
- **Audit** — Findings and audit log
""")
