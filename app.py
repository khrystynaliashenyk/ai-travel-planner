import streamlit as st
from agent import TravelAgent, MODEL_DEFAULT

st.set_page_config(page_title="AI Travel Planner", page_icon="✈️", layout="centered")
st.title("✈️ AI Travel Planner")
st.caption("Плануй подорож у діалозі: відповідай на питання, уточнюй деталі та змінюй маршрут.")

with st.sidebar:
    st.header("Налаштування")
    api_key = st.text_input("Groq API key", type="password",
                            help="Створи ключ. Не надсилай його іншим.")
    model = st.text_input("Модель Groq", value=MODEL_DEFAULT)
    start_button = st.button("Почати планування", use_container_width=True)

if "agent" not in st.session_state:
    st.session_state.agent = None
if "chat_started" not in st.session_state:
    st.session_state.chat_started = False

if start_button:
    if not api_key.strip():
        st.sidebar.error("Введи Groq API key.")
    elif not api_key.strip().startswith("gsk_"):
        st.sidebar.error("Перевір ключ.")
    else:
        try:
            st.session_state.agent = TravelAgent(api_key.strip(), model.strip())
            st.session_state.chat_started = True
            with st.spinner("Починаємо розмову..."):
                st.session_state.agent.start()
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Не вдалося запустити агента: {exc}")

if st.session_state.chat_started and st.session_state.agent:
    for item in st.session_state.agent.history:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and content:
            with st.chat_message(role):
                st.markdown(content)

    user_input = st.chat_input("Напиши відповідь або попроси змінити план...")
    if user_input:
        with st.spinner("Планую..."):
            try:
                st.session_state.agent.respond(user_input)
                st.rerun()
            except Exception as exc:
                st.error(f"Не вдалося отримати відповідь: {exc}")
else:
    st.info("Введи Groq API key у бічній панелі та натисни «Почати планування».")

