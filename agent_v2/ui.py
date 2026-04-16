import streamlit as st
import requests
import uuid

# Configuration
API_BASE = "http://localhost:8000"
API_URL_PLAN = f"{API_BASE}/chat/plan"
API_URL_EXECUTE = f"{API_BASE}/chat/execute"

st.set_page_config(page_title="Chaos Engineering Multi-Agent", page_icon="🌪️")
st.title("Chaos Engineering Hub")
st.markdown("Talk to the **Planner Agent** to formulate an experiment, and hand it off to the **Executor** when ready!")

# Initialize session state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_execute_button" not in st.session_state:
    st.session_state.show_execute_button = False

# Function to render messages
def render_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

render_chat()

def call_execute_api():
    """Hits the Executor endpoint"""
    user_prompt = "Go ahead and execute the plan!"
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    
    with st.spinner("Executor Agent is initializing and running..."):
        try:
            resp = requests.post(API_URL_EXECUTE, json={
                "thread_id": st.session_state.thread_id,
                "message": user_prompt
            })
            resp.raise_for_status()
            data = resp.json()
            
            ai_msg = data.get("message", "Execution complete!")
            st.session_state.messages.append({"role": "assistant", "content": ai_msg})
            # Hide the execute button since we already triggered it
            st.session_state.show_execute_button = False 
            st.rerun()
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to backend server. Is FastAPI running on port 8000?")
        except Exception as e:
            st.error(f"Error calling Executor API: {e}")

# Handle chat input for Planner
if prompt := st.chat_input("What reliability concern do you want to test?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Planner Agent is analysing and searching..."):
        try:
            response = requests.post(API_URL_PLAN, json={
                "thread_id": st.session_state.thread_id,
                "message": prompt
            })
            response.raise_for_status()
            data = response.json()
            
            ai_msg = data.get("message", "")
            # Read the condition to display execution button
            st.session_state.show_execute_button = data.get("show_execute_button", False)
            
            st.session_state.messages.append({"role": "assistant", "content": ai_msg})
            st.rerun()
            
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to backend server. Is FastAPI running on port 8000?")
        except Exception as e:
            st.error(f"Error calling Planner API: {e}")

# Draw execution button at the bottom of the dialogue if flagged by planner
if st.session_state.show_execute_button:
    st.markdown("---")
    st.info("🎯 The Planner Agent has finalized the plan and is ready to hand over execution.")
    if st.button("🚀 Start Execution", use_container_width=True):
        call_execute_api()

WITH_SIDEBAR = True
if WITH_SIDEBAR:
    with st.sidebar:
        st.header("Debug Menu")
        st.write(f"**Thread ID:** `{st.session_state.thread_id}`")
        if st.button("Clear Conversation"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.show_execute_button = False
            st.rerun()
