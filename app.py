"""
OntoMarket — redirect stub.

The app migrated off Streamlit to a React + FastAPI stack. Older resumes/links
point at the Streamlit URL, so this minimal app forwards visitors to the new
home. Kept deliberately tiny (Streamlit only, no heavy deps) so it boots fast
and reliably — the full former UI lives in git history and now in web/ + api/.
"""

import streamlit as st

REDIRECT_TO = "https://ontomarket.vercel.app"

st.set_page_config(page_title="OntoMarket has moved", page_icon="⬡")

# Instant client-side redirect (fires as soon as the page renders).
st.markdown(
    f'<meta http-equiv="refresh" content="0; url={REDIRECT_TO}">',
    unsafe_allow_html=True,
)

# Visible fallback in case the meta-refresh is blocked or slow.
st.markdown(
    f"""
    <div style="text-align:center; margin-top:18vh; font-family:sans-serif; color:#e8e0d0;">
      <div style="font-size:1.4rem; letter-spacing:.1em; margin-bottom:8px;">
        ONTO<span style="color:#4ec9b0;">MARKET</span>
      </div>
      <p style="color:#9a8f7d;">This project has moved to a new home.</p>
      <p style="margin-top:16px;">
        <a href="{REDIRECT_TO}" style="color:#4ec9b0; font-weight:600;">
          → {REDIRECT_TO}
        </a>
      </p>
      <p style="color:#6b6252; font-size:.85rem; margin-top:8px;">
        Redirecting automatically…
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
