"""Tela de chat em Streamlit, usada para demonstrar o agente.
Ao lado de cada resposta aparece quais ferramentas a Lia consultou, para ficar
claro de onde veio cada preço ou prazo. O agente é o mesmo da linha de comando.

Streamlit chat used to demo the agent. Each answer shows which tools Lia called,
so it's clear where each price or deadline came from. Same agent as the CLI.

Uso / Usage:
    pip install -e ".[ui]"
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import os

import streamlit as st

from emporio.agent import Agente

st.set_page_config(page_title="Empório da Música · Lia", page_icon="🎸")


def mostrar_chamadas(chamadas: list[dict]) -> None:
    if not chamadas:
        return
    nomes = ", ".join(c["nome"] for c in chamadas)
    with st.expander(f"Consultas: {nomes}"):
        for chamada in chamadas:
            st.markdown(f"`{chamada['nome']}({json.dumps(chamada['argumentos'], ensure_ascii=False)})`")
            st.json(chamada["resultado"], expanded=False)


if not os.getenv("OPENAI_API_KEY"):
    st.error("Defina OPENAI_API_KEY no arquivo .env e reinicie. / Set OPENAI_API_KEY in .env and restart.")
    st.stop()

# O Streamlit roda o script inteiro a cada interação; o agente e as mensagens
# ficam no session_state para sobreviver entre uma execução e outra.
# Streamlit reruns the whole script on every interaction; agent and messages
# live in session_state so they survive between runs.
if "agente" not in st.session_state:
    st.session_state.agente = Agente()
    st.session_state.mensagens = []

with st.sidebar:
    st.markdown("**Empório da Música**  \nAtendimento virtual · Campo Grande (MS)")
    st.caption(f"Modelo: {st.session_state.agente.modelo}")
    if st.button("Nova conversa"):
        st.session_state.agente.reiniciar()
        st.session_state.mensagens = []
        st.rerun()
    st.caption(
        "Experimente: violões até R$ 1000 · quanto custa o Takamine GD20 · "
        "me arrependi da compra (pedido 7, leticia.rocha@jmail.com) · vocês vendem pedal?"
    )

st.markdown("### Oi! Eu sou a Lia, da Empório da Música 🎸")

for mensagem in st.session_state.mensagens:
    with st.chat_message(mensagem["papel"]):
        st.markdown(mensagem["texto"])
        mostrar_chamadas(mensagem.get("chamadas", []))

if pergunta := st.chat_input("Escreva sua mensagem"):
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando..."):
            resposta = st.session_state.agente.responder(pergunta)
        chamadas = [
            {"nome": c.nome, "argumentos": c.argumentos, "resultado": c.resultado} for c in resposta.chamadas
        ]
        st.markdown(resposta.texto)
        mostrar_chamadas(chamadas)

    st.session_state.mensagens.append({"papel": "assistant", "texto": resposta.texto, "chamadas": chamadas})
