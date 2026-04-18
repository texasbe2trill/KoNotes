"""Chat view — conversational interface for exploring reading data."""
from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from models.activity import ReadingSession
    from models.book import Book

# Prefixes for models that support chat completions
_CHAT_PREFIXES = ("gpt-", "o1-", "o3-", "o4-", "chatgpt-")
# Substrings that indicate non-chat models
_EXCLUDE = ("realtime", "audio", "image", "tts", "whisper", "dall-e", "embedding", "moderation", "search")


def _fetch_chat_models(api_key: str) -> list[str]:
    """Retrieve available chat-capable models for the given API key."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    models = client.models.list()
    chat_models: list[str] = []
    for m in models:
        mid = m.id.lower()
        if not any(mid.startswith(p) for p in _CHAT_PREFIXES):
            continue
        if any(x in mid for x in _EXCLUDE):
            continue
        chat_models.append(m.id)
    chat_models.sort()
    return chat_models


def render_chat(
    books: list[Book],
    sessions: list[ReadingSession] | None = None,
) -> None:
    st.markdown("## Chat")
    st.caption("Ask questions about your reading data using your own OpenAI API key.")

    # ── API key setup ────────────────────────────────────────────
    api_key = st.session_state.get("openai_api_key", "")

    if not api_key:
        st.info(
            "Enter your OpenAI API key to start chatting about your reading data. "
            "Your key is only stored in this browser session and is never saved.",
            icon="🔑",
        )
        with st.form("api_key_form"):
            key_input = st.text_input(
                "OpenAI API key",
                type="password",
                placeholder="sk-...",
                help="Get a key at https://platform.openai.com/api-keys",
            )
            submitted = st.form_submit_button("Connect", type="primary")
            if submitted and key_input.strip():
                try:
                    models = _fetch_chat_models(key_input.strip())
                except Exception as exc:
                    st.error(f"Could not connect: {exc}")
                    return
                if not models:
                    st.error("No chat-capable models available for this key.")
                    return
                st.session_state["openai_api_key"] = key_input.strip()
                st.session_state["openai_models"] = models
                st.session_state.pop("chat_model", None)
                st.rerun()
            elif submitted:
                st.error("Please enter a valid API key.")
        return

    # ── Model selection (after key, before chat) ─────────────────
    available_models: list[str] = st.session_state.get("openai_models", [])
    model = st.session_state.get("chat_model", "")

    if not model:
        st.success("Connected. Choose a model to start chatting.", icon="✅")
        default_idx = 0
        for i, m in enumerate(available_models):
            if m == "gpt-4o-mini":
                default_idx = i
                break
        chosen = st.selectbox(
            "Model",
            available_models,
            index=default_idx,
            help="Models retrieved from your OpenAI account.",
        )
        if st.button("Start chatting", type="primary"):
            st.session_state["chat_model"] = chosen
            st.rerun()
        return

    # ── Connected state ──────────────────────────────────────────
    model = st.session_state.get("chat_model", "gpt-4o-mini")

    col_status, col_model, col_disconnect = st.columns([2, 2, 1])
    with col_status:
        st.markdown(
            f'<div style="font-size:0.8rem; color:#94a3b8;">'
            f'Connected · <strong>{model}</strong></div>',
            unsafe_allow_html=True,
        )
    with col_model:
        new_model = st.selectbox(
            "Switch model",
            available_models,
            index=available_models.index(model) if model in available_models else 0,
            label_visibility="collapsed",
            key="chat_model_switcher",
        )
        if new_model != model:
            st.session_state["chat_model"] = new_model
            st.rerun()
    with col_disconnect:
        if st.button("Disconnect", key="chat_disconnect"):
            for k in ("openai_api_key", "chat_model", "chat_messages", "chat_context", "openai_models"):
                st.session_state.pop(k, None)
            st.rerun()

    # ── Build reading context (once per data load) ───────────────
    if "chat_context" not in st.session_state or st.session_state.get("_chat_book_count") != len(books):
        from services.chat import build_context
        st.session_state["chat_context"] = build_context(books, sessions)
        st.session_state["_chat_book_count"] = len(books)

    system_prompt = st.session_state["chat_context"]

    # ── Chat history ─────────────────────────────────────────────
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    # Render existing messages
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Starter suggestions ──────────────────────────────────────
    if not st.session_state["chat_messages"]:
        st.markdown(
            '<div style="color:#94a3b8; font-size:0.85rem; margin:1rem 0 0.5rem;">Try asking:</div>',
            unsafe_allow_html=True,
        )
        suggestions = [
            "What are my reading habits like?",
            "Which book did I highlight the most?",
            "Summarize my reading activity",
            "What themes appear across my highlights?",
        ]
        cols = st.columns(2)
        for i, suggestion in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                    _handle_user_message(suggestion, system_prompt, model, api_key)
                    st.rerun()

    # ── Chat input ───────────────────────────────────────────────
    if prompt := st.chat_input("Ask about your reading data..."):
        _handle_user_message(prompt, system_prompt, model, api_key)
        st.rerun()


def _handle_user_message(
    prompt: str,
    system_prompt: str,
    model: str,
    api_key: str,
) -> None:
    """Send user message to OpenAI and store the response."""
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state["chat_messages"]
        )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
        )
        content = response.choices[0].message.content or ""

    except Exception as exc:
        error_str = str(exc)
        if "api_key" in error_str.lower() or "auth" in error_str.lower():
            content = "Invalid API key. Please disconnect and try again with a valid key."
            st.session_state.pop("openai_api_key", None)
        else:
            content = f"Error communicating with OpenAI: {error_str}"

    st.session_state["chat_messages"].append({"role": "assistant", "content": content})
