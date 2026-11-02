"""Camada de dados da loja.
Store data layer.

Lê os CSVs uma vez e expõe consultas simples para as ferramentas do agente.
O modelo nunca vê os CSVs inteiros, só o resultado dessas consultas.

Reads the CSVs once and exposes simple queries for the agent tools.
The model never sees the raw CSVs, only the result of these queries.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PREFIXO_ARQUIVO = "desafio_tecnico_ai_eng - "


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação. "Violão GD-20" -> "violao gd 20".
    Lowercase, no accents, no punctuation."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


_PALAVRAS_VAZIAS = {"de", "da", "do", "e", "para", "com"}
# Ordem importa: sufixos maiores primeiro. / Order matters: longest suffix first.
_SUFIXOS = ("oes", "aes", "ao", "os", "as", "es", "s", "o", "a", "e")


def radical(palavra: str) -> str:
    """Corte simples de plural/gênero, suficiente para nomes de categoria.
    Não é um stemmer de verdade. "violoes" e "violao" -> "viol".
    Naive plural/gender trimming, good enough for category names. Not a real stemmer."""
    if len(palavra) <= 3:
        return palavra
    for sufixo in _SUFIXOS:
        if palavra.endswith(sufixo) and len(palavra) - len(sufixo) >= 3:
            return palavra[: -len(sufixo)]
    return palavra


def radicais(texto: str) -> set[str]:
    return {radical(p) for p in normalizar(texto).split() if p not in _PALAVRAS_VAZIAS}


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def _data_ou_none(valor: str) -> date | None:
    return date.fromisoformat(valor) if valor else None


@dataclass(frozen=True)
class Categoria:
    id: int
    nome: str
    descricao: str


@dataclass(frozen=True)
class Produto:
    id: int
    nome: str
    preco: float
    categoria_id: int
    descricao: str
    estoque: int
    status: str  # active | discontinued | coming_soon
    specs: dict
    criado_em: date

    @property
    def disponivel(self) -> bool:
        # Só vende o que está ativo e tem estoque. O manual proíbe confirmar
        # disponibilidade sem olhar o estoque.
        # Only sells what is active and in stock. The manual forbids confirming
        # availability without checking stock.
        return self.status == "active" and self.estoque > 0


@dataclass(frozen=True)
class Promocao:
    id: int
    produto_id: int
    desconto_percentual: int
    descricao: str
    ativa: bool


@dataclass(frozen=True)
class Cliente:
    id: int
    nome: str
    telefone: str
    email: str
    cidade: str


@dataclass(frozen=True)
class ItemPedido:
    produto_id: int
    quantidade: int


@dataclass(frozen=True)
class Pedido:
    id: int
    cliente_id: int
    data: date
    status: str  # pending | confirmed | shipped | delivered | cancelled
    total: float
    forma_pagamento: str
    codigo_rastreio: str | None
    previsao_entrega: date | None
    observacao: str | None
    itens: tuple[ItemPedido, ...]


def _ler_csv(pasta: Path, nome: str) -> list[dict[str, str]]:
    caminho = pasta / f"{PREFIXO_ARQUIVO}{nome}.csv"
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


class Loja:
    """Repositório em memória com os dados da loja.
    In-memory repository with the store data."""

    def __init__(self, pasta: Path = DATA_DIR) -> None:
        self.categorias = {
            int(l["category_id"]): Categoria(int(l["category_id"]), l["name"], l["description"])
            for l in _ler_csv(pasta, "categories")
        }
        self.produtos = {
            int(l["product_id"]): Produto(
                id=int(l["product_id"]),
                nome=l["name"].strip(),
                preco=float(l["price_brl"]),
                categoria_id=int(l["category_id"]),
                descricao=l["description"].strip(),
                estoque=int(l["stock_quantity"]),
                status=l["status"].strip(),
                specs=json.loads(l["specs"]) if l["specs"] else {},
                criado_em=date.fromisoformat(l["created_at"]),
            )
            for l in _ler_csv(pasta, "products")
        }
        self.promocoes = [
            Promocao(
                id=int(l["promotion_id"]),
                produto_id=int(l["product_id"]),
                desconto_percentual=int(l["discount_percent"]),
                descricao=l["description"],
                ativa=l["is_active"] == "1",
            )
            for l in _ler_csv(pasta, "promotions")
        ]
        self.clientes = {
            int(l["customer_id"]): Cliente(int(l["customer_id"]), l["name"], l["phone"], l["email"], l["city"])
            for l in _ler_csv(pasta, "customers")
        }

        itens_por_pedido: dict[int, list[ItemPedido]] = {}
        for l in _ler_csv(pasta, "order_items"):
            itens_por_pedido.setdefault(int(l["order_id"]), []).append(
                ItemPedido(int(l["product_id"]), int(l["quantity"]))
            )
        self.pedidos = {
            int(l["order_id"]): Pedido(
                id=int(l["order_id"]),
                cliente_id=int(l["customer_id"]),
                data=date.fromisoformat(l["order_date"]),
                status=l["status"],
                total=float(l["total_brl"]),
                forma_pagamento=l["payment_method"],
                codigo_rastreio=l["tracking_code"] or None,
                previsao_entrega=_data_ou_none(l["estimated_delivery"]),
                observacao=l["notes"] or None,
                itens=tuple(itens_por_pedido.get(int(l["order_id"]), [])),
            )
            for l in _ler_csv(pasta, "orders")
        }

        # Índice de busca pré-calculado: nome, categoria, descrição e specs.
        # Precomputed search index: name, category, description and specs.
        self._indice = {
            p.id: normalizar(
                " ".join([p.nome, self.categorias[p.categoria_id].nome, p.descricao, *map(str, p.specs.values())])
            )
            for p in self.produtos.values()
        }

    # ---- Consultas / Queries ------------------------------------------------

    def categoria_por_nome(self, nome: str) -> Categoria | None:
        # Compara radicais para aceitar singular/plural: "violão" acha "Violões".
        # Compares word stems so singular/plural both work.
        alvo = radicais(nome)
        if not alvo:
            return None
        for categoria in self.categorias.values():
            if alvo <= radicais(categoria.nome):
                return categoria
        return None

    def promocao_ativa(self, produto_id: int) -> Promocao | None:
        # Promoções não são cumulativas: se houver mais de uma ativa, vale a maior.
        # Promotions don't stack: if more than one is active, the biggest wins.
        ativas = [p for p in self.promocoes if p.produto_id == produto_id and p.ativa]
        return max(ativas, key=lambda p: p.desconto_percentual, default=None)

    def buscar_produtos(
        self,
        termo: str | None = None,
        categoria_id: int | None = None,
        preco_min: float | None = None,
        preco_max: float | None = None,
        incluir_indisponiveis: bool = False,
    ) -> list[Produto]:
        tokens = normalizar(termo).split() if termo else []
        resultado = []
        for produto in self.produtos.values():
            if categoria_id is not None and produto.categoria_id != categoria_id:
                continue
            if preco_min is not None and produto.preco < preco_min:
                continue
            if preco_max is not None and produto.preco > preco_max:
                continue
            if not incluir_indisponiveis and not produto.disponivel:
                continue
            indice = self._indice[produto.id]
            compacto = indice.replace(" ", "")
            # Todo token precisa aparecer. A versão sem espaços resolve "gd 20" vs "gd20".
            # Every token must match. The no-space version handles "gd 20" vs "gd20".
            if all(t in indice or t in compacto for t in tokens):
                resultado.append(produto)
        return sorted(resultado, key=lambda p: p.preco)

    def cliente_do_pedido(self, pedido: Pedido) -> Cliente | None:
        return self.clientes.get(pedido.cliente_id)

    # ---- Qualidade dos dados / Data quality -------------------------------------

    def auditar(self) -> list[str]:
        """Lista inconsistências encontradas nos dados.
        Lists inconsistencies found in the data."""
        avisos: list[str] = []

        for pedido in self.pedidos.values():
            soma = sum(self.produtos[i.produto_id].preco * i.quantidade for i in pedido.itens if i.produto_id in self.produtos)
            if abs(soma - pedido.total) > 0.01:
                avisos.append(f"Pedido {pedido.id}: total R$ {pedido.total:.2f} difere da soma dos itens R$ {soma:.2f}")
            for item in pedido.itens:
                produto = self.produtos.get(item.produto_id)
                if produto is None:
                    avisos.append(f"Pedido {pedido.id}: produto {item.produto_id} não existe no catálogo")
                elif produto.status == "coming_soon" and pedido.status == "delivered":
                    avisos.append(f"Pedido {pedido.id}: entregue com produto em pré-lançamento ({produto.nome})")
            if pedido.status in {"shipped", "delivered"} and not pedido.codigo_rastreio:
                avisos.append(f"Pedido {pedido.id}: enviado sem código de rastreio")

        for produto in self.produtos.values():
            if produto.status == "active" and produto.estoque == 0:
                avisos.append(f"Produto {produto.id} ({produto.nome}): ativo, mas sem estoque")

        vazias = set(self.categorias) - {p.categoria_id for p in self.produtos.values()}
        for categoria_id in sorted(vazias):
            avisos.append(f"Categoria {categoria_id} ({self.categorias[categoria_id].nome}): sem produtos no catálogo")

        emails = Counter(c.email.lower() for c in self.clientes.values())
        for email, total in emails.items():
            if total > 1:
                avisos.append(f"E-mail {email} aparece em {total} clientes diferentes")

        return avisos
