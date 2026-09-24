"""AssureX premium UI kit - shared components that render the custom
HTML/CSS design system in static/style.css. Every page imports these so
the whole app looks identical and professional.

Pure-display components only (no widgets) - safe HTML rendering with
escaped values throughout.
"""
import html
from pathlib import Path

import streamlit as st

CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "style.css"

TONES = ("valid", "invalid", "review", "info", "neutral")

# claim status -> (tone, emoji)
STATUS_MAP = {
    "Approved": ("valid", "✅"),
    "Rejected": ("invalid", "⛔"),
    "Manual Review": ("review", "👤"),
    "Additional Information Required": ("review", "📨"),
    "Draft": ("neutral", "📝"),
    "Submitted": ("info", "📤"),
    "Under Evaluation": ("info", "⏳"),
    "Closed": ("neutral", "🔒"),
    "Likely Valid": ("valid", "✅"),
    "Likely Invalid": ("invalid", "⛔"),
    "Manual Review Required": ("review", "👤"),
}

DECISION_TONE = {"Likely Valid": "valid", "Likely Invalid": "invalid",
                 "Manual Review Required": "review"}

CLASS_TONE = {"Valid Claim": "valid", "Invalid Claim": "invalid",
              "Manual Review": "review"}


def inject_css():
    """Load the design system once per page render."""
    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def page_header(icon: str, title: str, subtitle: str = ""):
    st.markdown(
        f"""<div class="ax-hero">
  <div class="ax-hero-icon">{esc(icon)}</div>
  <h1>{esc(title)}</h1>
  <p>{esc(subtitle)}</p>
</div>""", unsafe_allow_html=True)


def section(icon: str, title: str):
    st.markdown(
        f"""<div class="ax-section">
  <span class="ax-section-icon">{esc(icon)}</span>
  <h3>{esc(title)}</h3>
</div>""", unsafe_allow_html=True)


def stat_row(items):
    """items: list of dicts {label, value, icon, tone} - renders a responsive
    grid of stat cards (replaces plain st.metric for the premium look)."""
    cards = []
    for it in items:
        tone = it.get("tone", "neutral")
        if tone not in TONES:
            tone = "neutral"
        cards.append(f"""<div class="ax-stat">
  <div class="ax-stat-icon ax-icon--{tone}">{esc(it.get('icon', ''))}</div>
  <div>
    <div class="ax-stat-value">{esc(it.get('value', ''))}</div>
    <div class="ax-stat-label">{esc(it.get('label', ''))}</div>
  </div>
</div>""")
    st.markdown(f'<div class="ax-stats">{"".join(cards)}</div>',
                unsafe_allow_html=True)


def badge(text: str, tone: str = "neutral"):
    if tone not in TONES:
        tone = "neutral"
    return (f'<span class="ax-badge ax-badge--{tone}">{esc(text)}</span>')


def status_badge(status: str) -> str:
    tone, emoji = STATUS_MAP.get(status, ("neutral", "•"))
    return (f'<span class="ax-badge ax-badge--{tone}">'
            f'{emoji}&nbsp;{esc(status)}</span>')


def decision_banner(final: str, subtitle: str = ""):
    tone = DECISION_TONE.get(final, "review")
    emoji = {"Likely Valid": "✅", "Likely Invalid": "⛔",
             "Manual Review Required": "👤"}.get(final, "👤")
    st.markdown(
        f"""<div class="ax-decision ax-decision--{tone}">
  <div class="ax-decision-title">{emoji} {esc(final)}</div>
  <div class="ax-decision-sub">{esc(subtitle)}</div>
</div>""", unsafe_allow_html=True)


def alert(message: str, tone: str = "info"):
    if tone not in TONES:
        tone = "info"
    st.markdown(f'<div class="ax-alert ax-alert--{tone}">{esc(message)}</div>',
                unsafe_allow_html=True)


def prob_bars(probs: dict, fixed_order=True):
    """Animated probability bars for the three classes, tone-colored,
    top class highlighted. Prettier and more informative than st.progress."""
    order = ["Valid Claim", "Invalid Claim", "Manual Review"] if fixed_order \
        else list(probs)
    rows = []
    top = max(probs, key=probs.get) if probs else None
    for cls in order:
        if cls not in probs:
            continue
        p = probs[cls]
        tone = CLASS_TONE.get(cls, "neutral")
        top_cls = " ax-bar-top" if cls == top else ""
        star = " ⭐" if cls == top else ""
        rows.append(f"""<div class="ax-bar-row">
  <div class="ax-bar-label{top_cls}">{esc(cls)}{star}</div>
  <div class="ax-bar-track"><div class="ax-bar-fill ax-bar-fill--{tone}" style="width:{p*100:.1f}%"></div></div>
  <div class="ax-bar-pct">{p*100:.1f}%</div>
</div>""")
    st.markdown("".join(rows), unsafe_allow_html=True)


def kv_grid(pairs):
    """pairs: list of (label, value) - responsive key-value grid."""
    items = [f"""<div><div class="ax-kv-label">{esc(k)}</div>
<div class="ax-kv-value">{esc(v)}</div></div>""" for k, v in pairs]
    st.markdown(f'<div class="ax-kv">{"".join(items)}</div>',
                unsafe_allow_html=True)


def timeline(events):
    """events: list of dicts {ts, event, actor} - vertical timeline."""
    items = []
    for t in events:
        items.append(f"""<li>
  <div class="ax-tl-time">{esc(t.get('ts', ''))}</div>
  <div class="ax-tl-event">{esc(t.get('event', ''))}</div>
  <div class="ax-tl-actor">by {esc(t.get('actor', ''))}</div>
</li>""")
    st.markdown(f'<ul class="ax-timeline">{"".join(items)}</ul>',
                unsafe_allow_html=True)


def empty_state(icon: str, title: str, hint: str = ""):
    st.markdown(
        f"""<div class="ax-empty">
  <div class="ax-empty-icon">{esc(icon)}</div>
  <div class="ax-empty-title">{esc(title)}</div>
  <div>{esc(hint)}</div>
</div>""", unsafe_allow_html=True)