import streamlit as st
import os
import re
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

# --- 1. UI & THEME ---
st.set_page_config(page_title="NEXUS CORE", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0d1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stChatFloatingInputContainer { background-color: #0d1117; }
</style>
""", unsafe_allow_html=True)

# --- 2. INITIALIZATION ---
@st.cache_resource(show_spinner=False)

def init_system():
    load_dotenv()
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # NEW CLOUD DATABASE CONNECTION
    vector_db = PineconeVectorStore(index_name="nexus-db", embedding=embeddings)
    
    return llm, vector_db
   
llm, db = init_system()

# --- 3. CONSOLIDATED ANALYZER (THE BRAIN) ---
def analyze_query(question):
    """
    Consolidates Guardrail + Router into ONE API call to save rate-limits.
    """
    # Instant Regex Check (Free)
    if re.search(r'\b(?:\d[ -]*?){13,16}\b', question):
        return "BLOCKED", "PII Detected", "NONE"
    
    # Single AI Call for Safety and Intent
    prompt = f"""
    Analyze this corporate query: "{question}"
    1. Safety: Is it business-related? (YES/NO)
    2. Intent: Is it pure MATH or company DATA?
    Return exactly in this format: SAFETY: [YES/NO] | INTENT: [MATH/DATA]
    """
    try:
        res = llm.invoke(prompt).content.strip().upper()
        # Parse the response
        is_safe = "YES" in res.split('|')[0]
        intent = "MATH" if "MATH" in res.split('|')[1] else "DATA"
        
        if not is_safe:
            return "BLOCKED", "Query outside corporate domain", "NONE"
        return "PASSED", "Clearance Granted", intent
    except Exception as e:
        if "429" in str(e): return "LIMIT", "Rate limit hit", "NONE"
        return "ERROR", str(e), "NONE"

# --- 4. SIDEBAR & LOGS ---
with st.sidebar:
    st.title("NEXUS CORE")
    role = st.selectbox("🔐 Access Level", ["finance", "hr", "marketing", "executive"])
    st.markdown("---")
    st.caption("Active Protocols: Agentic + RBAC")
    st.caption("Status: SHIELD ONLINE 🟢")

col_chat, col_logs = st.columns([7, 3])

with col_logs:
    st.subheader("📡 Trace Logs")
    log_box = st.container(height=400)
    def write_log(msg, type="INFO"):
        color = "#2ea043" if type == "INFO" else "#f85149"
        log_box.markdown(f"<code style='color:{color}'>[{time.strftime('%H:%M:%S')}] {msg}</code>", unsafe_allow_html=True)

    
    # ADD THIS FOR DEMO DAY:
    st.markdown("---")
    if st.button("🗑️ Clear Chat Terminal"):
        st.session_state.messages = []
        st.rerun()

# --- 5. MAIN CHAT TERMINAL ---
with col_chat:
    st.title("Secure AI Terminal")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt := st.chat_input("Enter secure query..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("assistant"):
            write_log(f"Process started for {role}")
            
            # PHASE 1: THE BRAIN (Security + Routing in 1 call)
            with st.status("Analyzing intent & security...") as status:
                state, reason, tool = analyze_query(prompt)
                
                if state == "BLOCKED":
                    status.update(label="Access Denied", state="error")
                    st.error(f"❌ {reason}")
                    write_log(f"BLOCKED: {reason}", "ERROR")
                    st.session_state.messages.append({"role": "assistant", "content": f"Blocked: {reason}"})
                    st.stop()
                elif state == "LIMIT":
                    status.update(label="Rate Limit Hit", state="error")
                    st.warning("⚠️ API Cooldown. Please wait 30 seconds.")
                    st.stop()
                
                status.update(label=f"Cleared: Intent detected as {tool}", state="complete")
            
            # PHASE 2: EXECUTION
            try:
                if tool == "MATH":
                    with st.spinner("Calculating..."):
                        ans = llm.invoke(f"Solve math: {prompt}").content
                    st.markdown(ans)
                    st.session_state.messages.append({"role": "assistant", "content": ans})
                
                else:
                    with st.status(f"Retrieving for {role.upper()}...") as status:
                        docs = db.similarity_search(prompt, k=3, filter={"role": role})
                        if not docs:
                            st.warning("❌ No authorized data found.")
                            st.stop()
                        context = "\n".join([d.page_content for d in docs])
                        status.update(label="Context Retrieved", state="complete")
                    
                    with st.spinner("Generating answer..."):
                        ans = llm.invoke(f"Context: {context}\n\nQuestion: {prompt}").content
                        st.markdown(ans)
                        st.session_state.messages.append({"role": "assistant", "content": ans})
                        write_log("Request Successful")
                        
            except Exception as e:
                st.error(f"System Error: {e}")
                write_log(f"Fault: {e}", "ERROR")