import streamlit as st

from src import auth
from ui.components import alert, inject_css


def view():
    inject_css()
    st.markdown(
        """<div class="ax-hero" style="padding:34px 36px; margin-top:1rem;">
  <div class="ax-hero-icon">🛡️</div>
  <h1>AssureX Claim Engine</h1>
  <p>AI-powered warranty claim validation · NextWave AI &amp; ML</p>
</div>""", unsafe_allow_html=True)

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.markdown(
            """<div class="ax-card">
  <h4>⚡ How a claim is evaluated</h4>
  <div class="ax-kv">
    <div><div class="ax-kv-label">Step 1</div><div class="ax-kv-value">📄 Documents &amp; details collected</div></div>
    <div><div class="ax-kv-label">Step 2</div><div class="ax-kv-value">⚖️ Warranty rule engine validates policy rules</div></div>
    <div><div class="ax-kv-label">Step 3</div><div class="ax-kv-value">🐍 Python ML model scores the claim</div></div>
    <div><div class="ax-kv-label">Step 4</div><div class="ax-kv-value">🖼️ Claim Summary Card → Teachable Machine model</div></div>
    <div><div class="ax-kv-label">Step 5</div><div class="ax-kv-value">🔀 Fusion engine combines everything → decision</div></div>
  </div>
</div>
<div style="margin-top:10px;">
  <span class="ax-badge ax-badge--valid">Dual AI models</span>
  <span class="ax-badge ax-badge--info">Configurable rules</span>
  <span class="ax-badge ax-badge--neutral">Full audit trail</span>
  <span class="ax-badge ax-badge--review">Human review queue</span>
</div>""", unsafe_allow_html=True)

    with right:
        tab_login, tab_register = st.tabs(["🔑 Log in", "🆕 Register"])
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", use_container_width=True,
                                         type="primary"):
                    user, err = auth.login(email, password)
                    if err:
                        alert(err, "invalid")
                    else:
                        st.session_state["user"] = user
                        st.rerun()
        with tab_register:
            with st.form("register_form"):
                name = st.text_input("Full name")
                email = st.text_input("Email")
                password = st.text_input("Password (min 6 characters)",
                                         type="password")
                role = st.selectbox("Register as",
                                    ["customer", "service_center", "reviewer"],
                                    format_func=lambda r: {
                                        "customer": "🧑 Customer",
                                        "service_center": "🔧 Service center",
                                        "reviewer": "🧑‍⚖️ Claim reviewer"}
                                    [r])
                if st.form_submit_button("Create account",
                                         use_container_width=True,
                                         type="primary"):
                    user, err = auth.register(name, email, password, role)
                    if err:
                        alert(err, "invalid")
                    else:
                        st.session_state["user"] = user
                        st.rerun()

    st.markdown(
        """<div class="ax-card" style="margin-top:14px;">
  <h4>🎭 Demo accounts <span class="ax-badge ax-badge--info">after seeding</span></h4>
  <div class="ax-kv">
    <div><div class="ax-kv-label">Admin</div><div class="ax-kv-value">admin@assurex.com / Admin@123</div></div>
    <div><div class="ax-kv-label">Reviewer</div><div class="ax-kv-value">reviewer@assurex.com / Reviewer@123</div></div>
    <div><div class="ax-kv-label">Customer</div><div class="ax-kv-value">demo@assurex.com / Demo@123</div></div>
    <div><div class="ax-kv-label">Service center</div><div class="ax-kv-value">service@assurex.com / Service@123</div></div>
  </div>
</div>""", unsafe_allow_html=True)