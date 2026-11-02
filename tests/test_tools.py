import json
from datetime import datetime

import pytest

from emporio.config import FUSO_LOJA
from emporio.tools import Ferramentas, schemas


def momento(*args):
    return lambda: datetime(*args, tzinfo=FUSO_LOJA)


@pytest.fixture(scope="module")
def ferramentas():
    return Ferramentas(agora=momento(2026, 3, 18, 10, 0))  # quarta-feira


def chamar(f, nome, **kwargs):
    return json.loads(f.executar(nome, json.dumps(kwargs)))


def test_violoes_ate_mil_so_traz_disponiveis(ferramentas):
    r = chamar(ferramentas, "buscar_produtos", categoria="violão", preco_max=1000)
    assert r["total_disponiveis"] > 0
    assert all(p["disponivel"] and p["categoria"] == "Violões" for p in r["produtos"])
    nomes_fora = {p["id"] for p in r["indisponiveis"]}
    assert {113, 96} <= nomes_fora  # fora de linha e ativo sem estoque


def test_preco_takamine_sem_promocao(ferramentas):
    r = chamar(ferramentas, "buscar_produtos", termo="Takamine GD20")
    takamine = r["produtos"][0]
    assert takamine["preco_a_vista"] == "R$ 2.199,00"
    assert takamine["preco_pix"] == "R$ 2.089,05"
    assert "promocao" not in takamine


def test_produto_em_promocao_mostra_desconto_e_pix_igual(ferramentas):
    r = chamar(ferramentas, "detalhes_produto", produto_id=121)
    assert r["promocao"]["desconto_percentual"] == 20
    assert r["preco_pix"] == r["preco_a_vista"]


def test_produto_fora_de_linha_traz_alternativas_e_esconde_preco(ferramentas):
    r = chamar(ferramentas, "detalhes_produto", produto_id=113)
    assert r["situacao"] == "fora de linha"
    assert "preco_a_vista" not in r
    assert r["alternativas"] and all(a["disponivel"] for a in r["alternativas"])


def test_categoria_inexistente_lista_as_validas(ferramentas):
    r = chamar(ferramentas, "buscar_produtos", categoria="amplificadores")
    assert "erro" in r and "Violões" in r["categorias_da_loja"]


@pytest.mark.parametrize("contato", ["lucas.mendes@jmail.com", "LUCAS.MENDES@jmail.com", "(67) 99812-3456", "+55 67 998123456"])
def test_pedido_aceita_email_ou_telefone(ferramentas, contato):
    r = chamar(ferramentas, "consultar_pedido", pedido_id=4, email_ou_telefone=contato)
    assert r["status"] == "entregue"


@pytest.mark.parametrize("pedido_id, contato", [(4, "outra@pessoa.com"), (999, "lucas.mendes@jmail.com"), (4, "1234")])
def test_pedido_nao_vaza_dados(ferramentas, pedido_id, contato):
    r = chamar(ferramentas, "consultar_pedido", pedido_id=pedido_id, email_ou_telefone=contato)
    assert set(r) == {"erro"}


def test_prazos_do_pedido_entregue():
    # Pedido 4: compra em 10/12/2025, previsão de entrega em 22/12/2025.
    args = dict(pedido_id=4, email_ou_telefone="lucas.mendes@jmail.com")
    prazos = chamar(Ferramentas(agora=momento(2025, 12, 28, 10, 0)), "consultar_pedido", **args)["prazos"]
    assert prazos["arrependimento"] == {"regra": "7 dias após o recebimento", "data_limite": "29/12/2025", "dentro_do_prazo": True}
    assert prazos["troca_por_defeito_na_loja"]["data_limite"] == "09/01/2026"
    assert prazos["garantia_legal"]["data_limite"] == "22/03/2026"

    depois = chamar(Ferramentas(agora=momento(2026, 1, 15, 10, 0)), "consultar_pedido", **args)["prazos"]
    assert not depois["arrependimento"]["dentro_do_prazo"]
    assert not depois["troca_por_defeito_na_loja"]["dentro_do_prazo"]
    assert depois["garantia_legal"]["dentro_do_prazo"]


def test_pedido_nao_entregue_nao_tem_prazos(ferramentas):
    r = chamar(ferramentas, "consultar_pedido", pedido_id=13, email_ou_telefone=_email_do_pedido(ferramentas, 13))
    assert r["status"] == "aguardando pagamento" and "prazos" not in r


def _email_do_pedido(f, pedido_id):
    return f.loja.cliente_do_pedido(f.loja.pedidos[pedido_id]).email


def test_busca_avisa_quantos_ficaram_de_fora(ferramentas):
    r = chamar(ferramentas, "buscar_produtos", categoria="violões", preco_max=1000)
    assert r["listados"] == 5
    assert r["nao_listados"] == r["total_disponiveis"] - 5 > 0


@pytest.mark.parametrize(
    "quando, aberta",
    [
        ((2026, 3, 18, 10, 0), True),    # quarta 10h
        ((2026, 3, 18, 18, 0), False),   # quarta 18h em ponto
        ((2026, 3, 21, 12, 59), True),   # sábado 12h59
        ((2026, 3, 21, 13, 0), False),   # sábado 13h
        ((2026, 3, 22, 10, 0), False),   # domingo
    ],
)
def test_status_loja(quando, aberta):
    assert Ferramentas(agora=momento(*quando)).status_loja()["aberta_agora"] is aberta


def test_proxima_abertura_no_sabado_a_tarde_e_segunda():
    r = Ferramentas(agora=momento(2026, 3, 21, 14, 0)).status_loja()
    assert r["proxima_abertura"] == "segunda às 09:00"


def test_erros_do_modelo_nao_derrubam(ferramentas):
    assert "erro" in json.loads(ferramentas.executar("nao_existe", "{}"))
    assert "erro" in json.loads(ferramentas.executar("detalhes_produto", "{json quebrado"))
    assert "erro" in json.loads(ferramentas.executar("detalhes_produto", '{"id_errado": 1}'))
    assert "erro" in json.loads(ferramentas.executar("detalhes_produto", '{"produto_id": "abc"}'))


def test_toda_ferramenta_tem_schema(ferramentas):
    nomes = {s["function"]["name"] for s in schemas()}
    assert nomes == set(ferramentas._funcoes)
