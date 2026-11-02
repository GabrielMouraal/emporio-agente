"""Testa o loop do agente com um cliente OpenAI falso: sem rede, sem chave, sem custo.
Tests the agent loop with a fake OpenAI client: no network, key or cost."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from openai import APIConnectionError

from emporio.agent import MAX_TURNOS_HISTORICO, MENSAGEM_FALHA, Agente
from emporio.config import FUSO_LOJA
from emporio.tools import Ferramentas


class Mensagem(SimpleNamespace):
    def model_dump(self, exclude_none=True):
        dados = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            dados["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in self.tool_calls
            ]
        return {k: v for k, v in dados.items() if v is not None}


def texto(conteudo):
    return Mensagem(content=conteudo, tool_calls=None)


def ferramenta(nome, **argumentos):
    chamada = SimpleNamespace(id=f"call_{nome}", function=SimpleNamespace(name=nome, arguments=json.dumps(argumentos)))
    return Mensagem(content=None, tool_calls=[chamada])


class ClienteFalso:
    """Devolve as mensagens roteirizadas, na ordem, e guarda o que recebeu."""

    def __init__(self, *roteiro):
        self.roteiro = list(roteiro)
        self.pedidos = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._criar))

    def _criar(self, **kwargs):
        self.pedidos.append(kwargs)
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=item)])


@pytest.fixture
def ferramentas():
    return Ferramentas(agora=lambda: datetime(2026, 3, 18, 10, 0, tzinfo=FUSO_LOJA))


def test_resposta_direta_sem_ferramenta(ferramentas):
    agente = Agente(ClienteFalso(texto("Oi! Como posso ajudar?")), ferramentas, modelo="teste")
    r = agente.responder("oi")
    assert r.texto == "Oi! Como posso ajudar?" and r.chamadas == []


def test_executa_ferramenta_e_devolve_resultado_ao_modelo(ferramentas):
    cliente = ClienteFalso(ferramenta("buscar_produtos", termo="Takamine GD20"), texto("Sai por R$ 2.199,00."))
    r = Agente(cliente, ferramentas, modelo="teste").responder("quanto custa o Takamine GD20?")

    assert [c.nome for c in r.chamadas] == ["buscar_produtos"]
    assert r.chamadas[0].resultado["produtos"][0]["preco_a_vista"] == "R$ 2.199,00"
    # A segunda chamada ao modelo precisa levar o resultado da ferramenta.
    ultima = cliente.pedidos[-1]["messages"][-1]
    assert ultima["role"] == "tool" and "2.199,00" in ultima["content"]


def test_falha_da_api_vira_mensagem_amigavel_e_limpa_turno(ferramentas):
    erro = APIConnectionError(request=None)
    agente = Agente(ClienteFalso(erro), ferramentas, modelo="teste")
    assert agente.responder("oi").texto == MENSAGEM_FALHA
    assert agente.historico == []


def test_limite_de_rodadas(ferramentas):
    roteiro = [ferramenta("status_loja") for _ in range(10)]
    r = Agente(ClienteFalso(*roteiro), ferramentas, modelo="teste").responder("aberto?")
    assert "reformular" in r.texto
    assert len(r.chamadas) == 5


def test_historico_aparado_comeca_em_mensagem_do_cliente(ferramentas):
    roteiro = []
    for _ in range(MAX_TURNOS_HISTORICO + 3):
        roteiro += [ferramenta("status_loja"), texto("ok")]
    agente = Agente(ClienteFalso(*roteiro), ferramentas, modelo="teste")
    for i in range(MAX_TURNOS_HISTORICO + 3):
        agente.responder(f"mensagem {i}")

    assert agente.historico[0]["role"] == "user"
    assert sum(m["role"] == "user" for m in agente.historico) == MAX_TURNOS_HISTORICO


def test_limpar_markdown():
    from emporio.agent import limpar_markdown

    assert limpar_markdown("## Opções\n1. **Yamaha C40**: R$ 599,90") == "Opções\n1. Yamaha C40: R$ 599,90"
