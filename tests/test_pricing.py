from datetime import date
from decimal import Decimal

import pytest

from emporio.data import Produto, Promocao
from emporio.pricing import (
    cotar,
    dinheiro,
    formatar_brl,
    frete_metropolitano,
    maximo_de_parcelas,
    opcoes_parcelamento,
)


def produto(preco: float) -> Produto:
    return Produto(
        id=1, nome="Teste", preco=preco, categoria_id=1, descricao="",
        estoque=3, status="active", specs={}, criado_em=date(2025, 1, 1),
    )


def promo(pct: int, ativa: bool = True) -> Promocao:
    return Promocao(id=1, produto_id=1, desconto_percentual=pct, descricao="Teste", ativa=ativa)


def test_formatar_brl():
    assert formatar_brl(Decimal("1234.5")) == "R$ 1.234,50"
    assert formatar_brl(Decimal("99")) == "R$ 99,00"
    assert formatar_brl(Decimal("1234567.891").quantize(Decimal("0.01"))) == "R$ 1.234.567,89"


def test_sem_promocao_pix_tem_5_por_cento():
    c = cotar(produto(2199))
    assert c.preco_a_vista == Decimal("2199.00")
    assert c.preco_pix == Decimal("2089.05")
    assert not c.em_promocao


def test_promocao_nao_acumula_com_pix():
    c = cotar(produto(1000), promo(20))
    assert c.preco_a_vista == Decimal("800.00")
    assert c.preco_pix == Decimal("800.00")


def test_promocao_inativa_e_ignorada():
    c = cotar(produto(1000), promo(20, ativa=False))
    assert c.preco_a_vista == Decimal("1000.00")
    assert c.preco_pix == Decimal("950.00")


def test_dinheiro_arredonda_meio_para_cima():
    assert dinheiro("10.005") == Decimal("10.01")


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (40, 1),      # menos de 2 x R$ 50 só vai em 1x
        (100, 2),     # 2 x 50
        (150, 3),     # 3 x 50; 4x daria 37,50 < 80
        (480, 6),     # 6 x 80
        (700, 7),     # 7 x 100
        (2199, 12),   # 12 x 183,25
        (1100, 11),   # 12x daria 91,67 < 100
    ],
)
def test_maximo_de_parcelas(valor, esperado):
    assert maximo_de_parcelas(dinheiro(valor))[0] == esperado


def test_opcoes_pulam_faixa_quando_minimo_nao_fecha():
    # R$ 300: 3x de 100 ok; 4x de 75 < 80, 5x e 6x também não; 7x+ abaixo de 100.
    assert [n for n, _ in opcoes_parcelamento(dinheiro(300))] == [1, 2, 3]


def test_frete_metropolitano():
    assert frete_metropolitano(dinheiro(500)) == Decimal("35.00")
    assert frete_metropolitano(dinheiro("500.01")) == Decimal("0.00")
