"""Roda conversas roteirizadas com o modelo real e salva em conversas/.

Serve para duas coisas: gerar os exemplos pedidos no desafio e funcionar como
um teste de comportamento simples. Cada cenário declara quais ferramentas o
agente deveria chamar; o script avisa quando alguma não foi usada.

Runs scripted conversations against the real model and saves them to
conversas/. It produces the examples the challenge asks for and works as a
light behavior check: each scenario lists the tools the agent should call.

Uso / Usage:
    python scripts/gerar_conversas.py          # todos / all
    python scripts/gerar_conversas.py 3        # só o cenário 3 / scenario 3 only

Precisa de OPENAI_API_KEY no .env e gasta alguns centavos.
Needs OPENAI_API_KEY in .env and costs a few cents.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from emporio.agent import Agente
from emporio.config import FUSO_LOJA

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "conversas"


@dataclass(frozen=True)
class Cenario:
    arquivo: str
    titulo: str
    objetivo: str
    agora: datetime
    mensagens: tuple[str, ...]
    ferramentas_esperadas: frozenset[str]


def momento(ano, mes, dia, hora, minuto=0) -> datetime:
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO_LOJA)


# As datas são fixas porque os pedidos de exemplo vão até março de 2026.
# Dates are pinned because the sample orders end in March 2026.
CENARIOS = (
    Cenario(
        "01_busca_violoes.md",
        "Busca de violões por faixa de preço",
        "Pergunta do enunciado. Deve consultar o catálogo, mostrar só itens disponíveis e ajudar a filtrar.",
        momento(2026, 3, 18, 10, 30),
        ("Oi! Quais opções de violões disponíveis custando até R$1000?", "Prefiro nylon, é pro meu filho que tá começando"),
        frozenset({"buscar_produtos"}),
    ),
    Cenario(
        "02_preco_promocao_parcelas.md",
        "Preço, promoção e parcelamento",
        "Produto sem promoção (PIX com 5%), produto em promoção (PIX sem desconto extra) e parcelamento pela regra da loja.",
        momento(2026, 3, 18, 15, 0),
        ("Quanto custa o Takamine GD20?", "E o Crafter HT-100, tá com desconto?", "Dá pra parcelar o Crafter em quantas vezes?"),
        frozenset({"buscar_produtos", "detalhes_produto"}),
    ),
    Cenario(
        "03_devolucao_dentro_do_prazo.md",
        "Devolução por arrependimento dentro do prazo",
        "Exige número do pedido e e-mail antes de consultar (LGPD) e aplica os prazos da política.",
        momento(2026, 2, 20, 11, 0),
        ("Me arrependi da minha compra, posso devolver meu pedido?", "pedido 7, leticia.rocha@jmail.com"),
        frozenset({"consultar_pedido"}),
    ),
    Cenario(
        "04_indisponivel_e_dados_errados.md",
        "Produto sem estoque e pedido com dados que não conferem",
        "Não confirma disponibilidade de item sem estoque, oferece alternativas e não revela dados de pedido de outra pessoa.",
        momento(2026, 3, 18, 16, 0),
        ("Vocês têm o Giannini GF-3D?", "Ok. Outra coisa: qual o status do pedido 8? meu email é joao@gmail.com"),
        frozenset({"buscar_produtos", "consultar_pedido"}),
    ),
    Cenario(
        "05_fora_do_escopo_e_horario.md",
        "Fora do escopo, horário e endereço",
        "Domingo à tarde: loja fechada. Recusa acessórios e assuntos alheios sem inventar, e passa endereço e horário pela política.",
        momento(2026, 3, 22, 15, 0),
        ("Vocês vendem pedal de distorção?", "Quem ganhou o jogo ontem?", "Vocês tão abertos agora? Qual o endereço?"),
        frozenset({"status_loja", "consultar_politica"}),
    ),
)


def rodar(cenario: Cenario) -> tuple[str, set[str]]:
    agente = Agente(agora=lambda: cenario.agora)
    usadas: set[str] = set()
    linhas = [
        f"# {cenario.titulo}",
        "",
        f"**Objetivo:** {cenario.objetivo}",
        f"**Momento simulado:** {cenario.agora:%d/%m/%Y %H:%M} (Campo Grande) · **Modelo:** {agente.modelo}",
        "",
        "---",
        "",
    ]
    for mensagem in cenario.mensagens:
        resposta = agente.responder(mensagem)
        linhas += [f"**Cliente:** {mensagem}", ""]
        for chamada in resposta.chamadas:
            usadas.add(chamada.nome)
            args = json.dumps(chamada.argumentos, ensure_ascii=False)
            linhas.append(f"> `{chamada.nome}({args})`")
        if resposta.chamadas:
            linhas.append("")
        linhas += [f"**Lia:** {resposta.texto}", ""]
    return "\n".join(linhas), usadas


def main() -> int:
    escolhidos = CENARIOS
    if len(sys.argv) > 1:
        escolhidos = (CENARIOS[int(sys.argv[1]) - 1],)

    PASTA_SAIDA.mkdir(exist_ok=True)
    falhas = 0
    for cenario in escolhidos:
        texto, usadas = rodar(cenario)
        (PASTA_SAIDA / cenario.arquivo).write_text(texto, encoding="utf-8")
        faltaram = cenario.ferramentas_esperadas - usadas
        situacao = "ok" if not faltaram else f"faltou chamar: {', '.join(sorted(faltaram))}"
        falhas += bool(faltaram)
        print(f"{cenario.arquivo:40} {situacao}")

    print(f"\nConversas salvas em / saved to: {PASTA_SAIDA}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
