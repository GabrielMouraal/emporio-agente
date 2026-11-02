"""Regras de preço: promoção, desconto no PIX, parcelamento e frete local.

Ficam em código, e não no prompt, porque são contas. O modelo recebe o
resultado pronto e só apresenta. Valores em Decimal para não ter erro de
arredondamento de float (0.1 + 0.2 != 0.3).

Pricing rules: promotion, PIX discount, installments and local shipping.
They live in code, not in the prompt, because they are arithmetic. The model
gets the final numbers and only presents them. Decimal avoids float rounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from emporio.data import Produto, Promocao

CENTAVO = Decimal("0.01")
DESCONTO_PIX = Decimal("0.05")
MAX_PARCELAS = 12

# (até N parcelas, parcela mínima). Seção 3.1 do manual.
# (up to N installments, minimum installment). Policy section 3.1.
FAIXAS_PARCELAMENTO = (
    (3, Decimal("50")),
    (6, Decimal("80")),
    (12, Decimal("100")),
)

FRETE_GRATIS_ACIMA_DE = Decimal("500")
FRETE_FIXO_METROPOLITANO = Decimal("35")


def dinheiro(valor: float | int | str | Decimal) -> Decimal:
    # str() antes de Decimal: Decimal(0.1) traz o lixo binário do float.
    # str() first: Decimal(0.1) would carry the float's binary noise.
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def formatar_brl(valor: Decimal) -> str:
    """Decimal("1234.5") -> "R$ 1.234,50"."""
    texto = f"{valor:,.2f}"  # 1,234.50
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


@dataclass(frozen=True)
class Cotacao:
    preco_tabela: Decimal
    preco_a_vista: Decimal          # cartão, débito ou boleto / card, debit or boleto
    preco_pix: Decimal
    desconto_promocional: int = 0   # em % / percent
    nome_promocao: str | None = None

    @property
    def em_promocao(self) -> bool:
        return self.desconto_promocional > 0

    def para_dict(self) -> dict:
        """Formato enviado ao modelo: valores já formatados, sem conta para ele fazer.
        Shape sent to the model: values already formatted, no math left for it."""
        dados = {
            "preco_tabela": formatar_brl(self.preco_tabela),
            "preco_a_vista": formatar_brl(self.preco_a_vista),
            "preco_pix": formatar_brl(self.preco_pix),
            "pix_tem_desconto": self.preco_pix < self.preco_a_vista,
        }
        if self.em_promocao:
            dados["promocao"] = {
                "nome": self.nome_promocao,
                "desconto_percentual": self.desconto_promocional,
            }
        return dados


def cotar(produto: Produto, promocao: Promocao | None = None) -> Cotacao:
    """Preço final de um produto.

    Promoção e PIX não somam (seção 6.2): com promoção ativa, o PIX paga o
    mesmo preço promocional. Sem promoção, o PIX tem 5% sobre o preço de tabela.

    Promotion and PIX don't stack (section 6.2): with an active promotion, PIX
    pays the promotional price. Without one, PIX gets 5% off the list price.
    """
    tabela = dinheiro(produto.preco)
    if promocao is not None and promocao.ativa and promocao.desconto_percentual > 0:
        fator = 1 - Decimal(promocao.desconto_percentual) / 100
        promocional = dinheiro(tabela * fator)
        return Cotacao(
            preco_tabela=tabela,
            preco_a_vista=promocional,
            preco_pix=promocional,
            desconto_promocional=promocao.desconto_percentual,
            nome_promocao=promocao.descricao,
        )
    return Cotacao(
        preco_tabela=tabela,
        preco_a_vista=tabela,
        preco_pix=dinheiro(tabela * (1 - DESCONTO_PIX)),
    )


def parcela_minima(parcelas: int) -> Decimal:
    for limite, minimo in FAIXAS_PARCELAMENTO:
        if parcelas <= limite:
            return minimo
    raise ValueError(f"Máximo de {MAX_PARCELAS} parcelas / max {MAX_PARCELAS} installments")


def opcoes_parcelamento(valor: Decimal) -> list[tuple[int, Decimal]]:
    """Todas as opções sem juros permitidas para o valor, de 1x até o máximo.

    1x sempre vale. Da 2x em diante, a parcela precisa respeitar o mínimo da faixa.
    O valor por parcela é arredondado; na loja a diferença de centavos costuma
    ir para a primeira parcela, aqui mostramos só o valor aproximado.

    All interest-free options for the amount. 1x always works; from 2x on the
    installment must meet the tier minimum. Per-installment value is rounded.
    """
    valor = dinheiro(valor)
    opcoes = [(1, valor)]
    for n in range(2, MAX_PARCELAS + 1):
        parcela = dinheiro(valor / n)
        if parcela >= parcela_minima(n):
            opcoes.append((n, parcela))
    return opcoes


def maximo_de_parcelas(valor: Decimal) -> tuple[int, Decimal]:
    return opcoes_parcelamento(valor)[-1]


def frete_metropolitano(subtotal: Decimal) -> Decimal:
    """Frete na região metropolitana de Campo Grande. O manual diz "acima de
    R$ 500,00", então exatamente R$ 500,00 ainda paga a taxa.
    Local shipping. Policy says "above R$ 500.00", so exactly 500 still pays."""
    return Decimal("0.00") if dinheiro(subtotal) > FRETE_GRATIS_ACIMA_DE else dinheiro(FRETE_FIXO_METROPOLITANO)
