"""KoNotes brand logo and wordmark component."""
from __future__ import annotations

import base64

import streamlit as st

_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="KoNotes">'
    '<defs>'
    '<linearGradient id="kn-bg" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">'
    '<stop offset="0%" stop-color="#1D4ED8"/>'
    '<stop offset="100%" stop-color="#4338CA"/>'
    '</linearGradient>'
    '<linearGradient id="kn-hl" x1="0" y1="0" x2="1" y2="0">'
    '<stop offset="0%" stop-color="#38BDF8"/>'
    '<stop offset="100%" stop-color="#818CF8"/>'
    '</linearGradient>'
    '<linearGradient id="kn-pr" x1="0" y1="0" x2="1" y2="0">'
    '<stop offset="0%" stop-color="rgba(255,255,255,0.27)"/>'
    '<stop offset="100%" stop-color="rgba(255,255,255,0.15)"/>'
    '</linearGradient>'
    '</defs>'
    '<rect width="64" height="64" rx="14" fill="url(#kn-bg)"/>'
    '<rect x="7" y="11" width="22" height="42" rx="3" fill="rgba(255,255,255,0.16)" stroke="rgba(255,255,255,0.20)" stroke-width="0.5"/>'
    '<rect x="29" y="11" width="6" height="42" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="35" y="11" width="22" height="42" rx="3" fill="url(#kn-pr)" stroke="rgba(255,255,255,0.22)" stroke-width="0.5"/>'
    '<line x1="11" y1="21" x2="27" y2="21" stroke="rgba(255,255,255,0.55)" stroke-width="1.6" stroke-linecap="round"/>'
    '<line x1="11" y1="27" x2="26" y2="27" stroke="rgba(255,255,255,0.30)" stroke-width="1.3" stroke-linecap="round"/>'
    '<line x1="11" y1="33" x2="22" y2="33" stroke="rgba(255,255,255,0.18)" stroke-width="1.3" stroke-linecap="round"/>'
    '<rect x="37" y="21" width="16" height="6" rx="3" fill="url(#kn-hl)" opacity="0.68"/>'
    '<line x1="38" y1="24" x2="52" y2="24" stroke="white" stroke-width="1.6" stroke-linecap="round"/>'
    '<line x1="38" y1="31" x2="51" y2="31" stroke="rgba(255,255,255,0.32)" stroke-width="1.3" stroke-linecap="round"/>'
    '<line x1="38" y1="37" x2="47" y2="37" stroke="rgba(255,255,255,0.18)" stroke-width="1.3" stroke-linecap="round"/>'
    '</svg>'
)


def mark_html(size: int = 32) -> str:
    """Return the logo mark SVG element at the given pixel size."""
    return (
        f'<div style="width:{size}px;height:{size}px;flex-shrink:0;">{_LOGO_SVG}</div>'
    )


def favicon_link_html() -> str:
    """Return a <link rel="icon"> tag with the SVG logo as a data URI."""
    b64 = base64.b64encode(_LOGO_SVG.encode()).decode()
    return f'<link rel="shortcut icon" href="data:image/svg+xml;base64,{b64}" type="image/svg+xml">'


def render_brand(*, variant: str = "default") -> None:
    """Render the KoNotes brand lockup (mark + wordmark).

    variant:
        "header"  — main page top, larger mark, full subtitle
        "sidebar" — compact sidebar, centred
    """
    if variant == "header":
        mark_size = 36
        title_size = "1.50rem"
        subtitle = "Turn your Kobo &amp; Kindle reading data into structured insight"
        align = "flex-start"
    else:
        mark_size = 28
        title_size = "1.32rem"
        subtitle = "Reading Intelligence"
        align = "center"

    st.markdown(
        f'<div class="kn-brand kn-brand--{variant}" style="justify-content:{align};">'
        f'{mark_html(mark_size)}'
        '<div class="kn-brand__text">'
        f'<div class="kn-brand__title" style="font-size:{title_size};">'
        '<span class="kn-brand__ko">Ko</span>Notes'
        '</div>'
        f'<div class="kn-brand__subtitle">{subtitle}</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
