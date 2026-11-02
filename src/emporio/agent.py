"""Loop do agente: conversa com a OpenAI e executa as ferramentas pedidas.

Fluxo de cada mensagem do cliente:
1. envia histórico + ferramentas para o modelo;
2. se o modelo pedir ferramentas, roda cada uma e devolve o resultado;
3. repete até o modelo responder em texto (ou bater o limite de rodadas).

Agent loop. For each customer message: send history + tools, run any tool the
model asks for, feed results back, repeat until a text answer (or the round cap).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from openai import OpenAI, OpenAIError

from emporio import config
from emporio.prompts import montar_prompt_sistema
from emporio.tools import Ferramentas, schemas

log = logging.getLogger(__name__)

MAX_RODADAS_FERRAMENTA = 5
# Quantas mensagens do cliente ficam no histórico. Conversa de atendimento é curta;
# isso evita que uma sessão longa estoure o contexto e o custo.
# How many customer turns stay in history; keeps long sessions cheap.
MAX_TURNOS_HISTORICO = 10

MENSAGEM_FALHA = (
    "Desculpa, tive um problema técnico aqui e não consegui consultar o sistema. "
    "Pode tentar de novo em instantes?"
)


@dataclass
class ChamadaFerramenta:
    nome: str
    argumentos: dict[str, Any]
    resultado: dict[str, Any]


@dataclass
class Resposta:
    texto: str
    chamadas: list[ChamadaFerramenta] = field(default_factory=list)


class Agente:
    def __init__(
        self,
        cliente: OpenAI | None = None,
        ferramentas: Ferramentas | None = None,
        modelo: str | None = None,
        agora: Callable[[], datetime] = config.agora,
    ) -> None:
        # Cliente injetável: nos testes entra um cliente falso, sem rede e sem custo.
        # Injectable client: tests pass a fake one, no network, no cost.
        self.cliente = cliente or OpenAI()
        # O mesmo relógio vale para o prompt e para as ferramentas; os exemplos fixam uma data.
        # Same clock for prompt and tools; the example script pins a date.
        self._agora = agora
        self.ferramentas = ferramentas or Ferramentas(agora=agora)
        self.modelo = modelo or config.modelo()
        self.historico: list[dict[str, Any]] = []

    def reiniciar(self) -> None:
        self.historico.clear()

    def _mensagens(self) -> list[dict[str, Any]]:
        sistema = {"role": "system", "content": montar_prompt_sistema(self._agora())}
        return [sistema, *self.historico]

    def _aparar_historico(self) -> None:
        # Corta sempre no início de uma mensagem do cliente. Cortar no meio deixaria
        # uma resposta de ferramenta sem a chamada que a originou, e a API recusa isso.
        # Always cut at a user message; cutting mid-turn would orphan tool results.
        inicios = [i for i, m in enumerate(self.historico) if m["role"] == "user"]
        if len(inicios) > MAX_TURNOS_HISTORICO:
            self.historico = self.historico[inicios[-MAX_TURNOS_HISTORICO]:]

    def responder(self, mensagem: str) -> Resposta:
        self.historico.append({"role": "user", "content": mensagem})
        self._aparar_historico()
        chamadas: list[ChamadaFerramenta] = []

        try:
            for _ in range(MAX_RODADAS_FERRAMENTA):
                retorno = self.cliente.chat.completions.create(
                    model=self.modelo,
                    messages=self._mensagens(),
                    tools=schemas(),
                    temperature=0.3,
                )
                msg = retorno.choices[0].message

                if not msg.tool_calls:
                    texto = msg.content or ""
                    self.historico.append({"role": "assistant", "content": texto})
                    return Resposta(texto, chamadas)

                self.historico.append(msg.model_dump(exclude_none=True))
                for chamada in msg.tool_calls:
                    nome = chamada.function.name
                    saida = self.ferramentas.executar(nome, chamada.function.arguments)
                    log.info("ferramenta %s(%s) -> %s", nome, chamada.function.arguments, saida[:200])
                    chamadas.append(ChamadaFerramenta(nome, _json_ou_vazio(chamada.function.arguments), json.loads(saida)))
                    self.historico.append({"role": "tool", "tool_call_id": chamada.id, "content": saida})
        except OpenAIError:
            log.exception("falha na chamada à OpenAI")
            self._descartar_turno_atual()
            return Resposta(MENSAGEM_FALHA, chamadas)

        # O modelo ficou pedindo ferramentas sem responder. Melhor admitir do que travar.
        # The model kept calling tools without answering; admit it instead of looping.
        texto = "Não consegui fechar essa resposta. Pode reformular a pergunta?"
        self.historico.append({"role": "assistant", "content": texto})
        return Resposta(texto, chamadas)

    def _descartar_turno_atual(self) -> None:
        # Remove o turno incompleto para a próxima tentativa começar limpa.
        # Drops the half-finished turn so the retry starts clean.
        while self.historico:
            if self.historico.pop()["role"] == "user":
                break


def _json_ou_vazio(texto: str) -> dict[str, Any]:
    try:
        return json.loads(texto or "{}")
    except json.JSONDecodeError:
        return {}
