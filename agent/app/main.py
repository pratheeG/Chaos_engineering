"""ChaosBot – Streamlit chat interface for the LitmusChaos Agent."""

from __future__ import annotations

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

from graph import build_graph
from config import settings

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ChaosBot – LitmusChaos Agent",
    page_icon="🔥",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    st.divider()

    st.markdown("**LLM Provider**")
    provider = st.selectbox(
        "Provider",
        ["groq", "openai"],
        index=0 if settings.llm_provider == "groq" else 1,
        label_visibility="collapsed",
    )

    st.markdown("**LitmusChaos**")
    litmus_url = st.text_input("API URL", value=settings.litmus_api_url)
    project_id = st.text_input("Project ID", value=settings.litmus_project_id)
    access_token = st.text_input(
        "Access Token",
        value=settings.litmus_access_token,
        type="password",
    )

    # Allow runtime override
    if litmus_url != settings.litmus_api_url:
        settings.litmus_api_url = litmus_url
    if project_id != settings.litmus_project_id:
        settings.litmus_project_id = project_id
    if access_token != settings.litmus_access_token:
        settings.litmus_access_token = access_token

    st.divider()
    st.caption(f"Provider: **{provider}**")

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.agent_messages = []
        st.rerun()

# ── Init session state ───────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []          # display messages
    st.session_state.agent_messages = []    # LangGraph message history

# ── Build agent ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_agent():
    return build_graph()

agent = get_agent()

# ── Chat header ──────────────────────────────────────────────────────────────
st.title("🔥 ChaosBot")
st.caption("Your AI-powered LitmusChaos assistant  •  Ask me to list experiments, environments, probes, or run an experiment.")

# ── Render chat history ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Handle user input ────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask ChaosBot something..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Invoke agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Build input with full history
            st.session_state.agent_messages.append(HumanMessage(content=prompt))
            result = agent.invoke({"messages": st.session_state.agent_messages})

            # Extract assistant reply
            agent_messages = result["messages"]
            st.session_state.agent_messages = agent_messages

            # Find the last AI message (skip tool calls/results)
            reply = ""
            for msg in reversed(agent_messages):
                if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                    reply = msg.content
                    break

            if not reply:
                reply = "I processed the request but have no additional response. Check the results above."

            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
