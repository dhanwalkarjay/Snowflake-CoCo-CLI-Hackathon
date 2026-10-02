import streamlit as st
import json

st.header("Copilot")

session = st.connection("snowflake").session()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])
        if msg.get("tools"):
            with st.expander("Tools used"):
                for t in msg["tools"]:
                    st.code(t, language="text")
        if msg.get("sql"):
            with st.expander("SQL"):
                st.code(msg["sql"], language="sql")
        if msg.get("citations"):
            with st.expander("Policy citations"):
                for c in msg["citations"]:
                    st.markdown(c)

if prompt := st.chat_input("Ask Sentinel..."):
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            safe_prompt = prompt.replace("'", "''")
            try:
                row = session.sql(f"CALL SENTINEL_DB.APP.AGENT_CHAT('{safe_prompt}')").collect()[0]
                raw = json.loads(row[0])
            except Exception as e:
                st.error(f"Agent error: {e}")
                raw = None

        if raw:
            answer_text = ""
            tools_used = []
            sql_snippets = []
            citations = []

            content = raw.get("content", [])
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    answer_text += block.get("text", "")
                elif btype == "tool_use":
                    tu = block.get("tool_use", {})
                    name = tu.get("name", "unknown")
                    tools_used.append(name)
                elif btype == "tool_result":
                    tr = block.get("tool_result", {})
                    tr_content = tr.get("content", "")
                    if isinstance(tr_content, str) and "SELECT" in tr_content.upper():
                        sql_snippets.append(tr_content)
                    if isinstance(tr_content, list):
                        for item in tr_content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                txt = item.get("text", "")
                                if "SELECT" in txt.upper():
                                    sql_snippets.append(txt)

            st.markdown(answer_text or "(No text response)")

            if tools_used:
                with st.expander("Tools used"):
                    for t in tools_used:
                        st.code(t, language="text")

            if sql_snippets:
                with st.expander("SQL"):
                    for s in sql_snippets:
                        st.code(s, language="sql")

            if raw.get("warnings"):
                with st.expander("Warnings"):
                    for w in raw["warnings"]:
                        st.warning(w.get("message", str(w)))

            st.session_state.messages.append({
                "role": "assistant",
                "text": answer_text or "(No text response)",
                "tools": tools_used,
                "sql": "\n\n".join(sql_snippets) if sql_snippets else None,
                "citations": citations or None,
            })
