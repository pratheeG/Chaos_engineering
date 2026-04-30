import streamlit as st
import requests
import uuid

# Configuration
API_BASE = "http://localhost:8000"
API_URL = f"{API_BASE}/chat"

st.set_page_config(page_title="Chaos Master Orchestrator", page_icon="🌪️")
st.title("Chaos Engineering Master")
st.markdown("Design and execute chaos experiments with the **Chaos Master Orchestrator**.")

# Initialize session state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_agent" not in st.session_state:
    st.session_state.current_agent = "Supervisor"

# Function to render messages
def render_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

render_chat()

def send_to_orchestrator(user_prompt: str):
    """Hits the unified /chat endpoint"""
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    
    # Render the user's message immediately so it doesn't disappear during loading
    with st.chat_message("user"):
        st.markdown(user_prompt)
    
    # Proactively update status if handover is detected
    # ONLY if the current agent is the Planner (we are in the design phase)
    approval_keywords = ["yes", "proceed", "run", "execute", "go"]
    is_approval = any(k in user_prompt.lower() for k in approval_keywords)
    
    if is_approval and st.session_state.current_agent == "Planner Agent":
        st.session_state.current_agent = "Executor Agent"
        status_msg = f"**Planner Agent** has handed over... **Executor Agent** is running..."
    else:
        status_msg = f"**{st.session_state.current_agent}** is thinking..."
    
    with st.spinner(status_msg):
        try:
            resp = requests.post(API_URL, json={
                "thread_id": st.session_state.thread_id,
                "message": user_prompt
            })
            resp.raise_for_status()
            data = resp.json()
            
            ai_msg = data.get("message", "Request completed.")
            st.session_state.messages.append({"role": "assistant", "content": ai_msg})
            
            # Update the agent status for the next turn
            agent_id = data.get("active_agent", "supervisor")
            agent_map = {
                "supervisor": "Supervisor",
                "planner": "Planner Agent",
                "executor": "Executor Agent"
            }
            st.session_state.current_agent = agent_map.get(agent_id, "Supervisor")
            st.rerun()
            
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to backend server. Is FastAPI running on port 8000?")
        except Exception as e:
            st.error(f"Error calling Orchestrator API: {e}")

# Handle chat input
if prompt := st.chat_input("Ask a question or describe a chaos goal..."):
    send_to_orchestrator(prompt)

# Sidebar
with st.sidebar:
    st.header("Session Settings")
    st.write(f"**Current Agent:** `{st.session_state.current_agent}`")
    st.write(f"**Thread ID:** `{st.session_state.thread_id}`")
    
    if st.button("Clear Conversation"):
        try:
            requests.delete(f"{API_BASE}/state/{st.session_state.thread_id}")
        except:
            pass
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.current_agent = "Supervisor"
        st.rerun()
    
    st.divider()
    st.markdown("""
    ### How to use:
    1. **Plan**: Describe what you want to test.
    2. **Review**: The AI will design a plan and ask for your approval.
    3. **Execute**: Simply say 'Go', 'Approved', or 'Run it' to start execution.
    """)
