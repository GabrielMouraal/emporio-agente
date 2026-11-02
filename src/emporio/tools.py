"""Ferramentas que o modelo pode chamar (function calling da OpenAI).

Cada ferramenta tem duas partes: o schema JSON que o modelo enxerga e a função
Python que roda de verdade. As funções devolvem dicionários pequenos e já
formatados. Erros voltam como {"erro": "..."} para o modelo explicar ao
cliente, em vez de derrubar a conversa.

Tools the model can call (OpenAI function calling). Each tool has a JSON schema
the model sees and the Python function that actually runs. Functions return
small, pre-formatted dicts. Errors come back as {"erro": "..."} so the model
can explain them instead of crashing the conversation.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Callable

from emporio import config
from emporio.data import Loja, Pedido, Produto, normalizar, so_digitos
from emporio.policies import consultar_politica, temas_disponiveis
from emporio.pricing import cotar, dinheiro, formatar_brl, maximo_de_parcelas

# Em conversa de WhatsApp, mais de 5 opções vira parede de texto.
# In a chat, more than 5 options becomes a wall of text.
LIMITE_RESULTADOS = 5

# Prazos da política (seções 4.1, 4.2 e 8.1). / Policy deadlines.
PRAZO_ARREPENDIMENTO_DIAS = 7     # após o recebimento / after receipt
PRAZO_TROCA_DEFEITO_DIAS = 30     # após a compra / after purchase
PRAZO_GARANTIA_LEGAL_DIAS = 90    # após o recebimento / after receipt

STATUS_PEDIDO = {
    "pending": "aguardando pagamento",
    "confirmed": "pagamento confirmado, em separação",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

STATUS_PRODUTO = {
    "active": "ativo",
    "discontinued": "fora de linha",
    "coming_soon": "lançamento em breve",
}

# (abre, fecha) por dia da semana; segunda = 0. Domingo fechado.
# (opens, closes) per weekday; Monday = 0. Closed on Sunday.
HORARIO = {d: (time(9), time(18)) for d in range(5)} | {5: (time(9), time(13))}
NOMES_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _forma_pagamento(codigo: str) -> str:
    if codigo.startswith("credit_"):
        return f"cartão de crédito em {codigo.removeprefix('credit_')}"
    return {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto"}.get(codigo, codigo)


class Ferramentas:
    def __init__(self, loja: Loja | None = None, agora: Callable[[], datetime] = config.agora) -> None:
        self.loja = loja or Loja()
        self._agora = agora
        self._funcoes: dict[str, Callable[..., dict]] = {
            "buscar_produtos": self.buscar_produtos,
            "detalhes_produto": self.detalhes_produto,
            "consultar_pedido": self.consultar_pedido,
            "consultar_politica": self.consultar_politica,
            "status_loja": self.status_loja,
        }

    # ---- Execução / Dispatch ---------------------------------------------------

    def executar(self, nome: str, argumentos_json: str) -> str:
        """Roda a ferramenta pedida pelo modelo e devolve JSON em texto.
        Runs the tool the model asked for and returns JSON text."""
        funcao = self._funcoes.get(nome)
        if funcao is None:
            return json.dumps({"erro": f"ferramenta desconhecida: {nome}"})
        try:
            argumentos = json.loads(argumentos_json or "{}")
            resultado = funcao(**argumentos)
        except (json.JSONDecodeError, TypeError, ValueError) as erro:
            # Argumento inválido gerado pelo modelo. Devolve o erro para ele corrigir.
            # Bad arguments from the model. Send the error back so it can retry.
            resultado = {"erro": f"argumentos inválidos: {erro}"}
        return json.dumps(resultado, ensure_ascii=False)

    # ---- Produtos / Products ---------------------------------------------------

    def _resumo(self, produto: Produto) -> dict:
        cotacao = cotar(produto, self.loja.promocao_ativa(produto.id))
        return {
            "id": produto.id,
            "nome": produto.nome,
            "categoria": self.loja.categorias[produto.categoria_id].nome,
            "disponivel": produto.disponivel,
            **cotacao.para_dict(),
        }

    def buscar_produtos(
        self,
        termo: str | None = None,
        categoria: str | None = None,
        preco_min: float | None = None,
        preco_max: float | None = None,
    ) -> dict:
        categoria_id = None
        if categoria:
            encontrada = self.loja.categoria_por_nome(categoria)
            if encontrada is None:
                return {
                    "erro": f"categoria '{categoria}' não existe",
                    "categorias_da_loja": [c.nome for c in self.loja.categorias.values()],
                }
            categoria_id = encontrada.id

        # O filtro de preço usa o preço de tabela. Produto em promoção que fica
        # abaixo do teto só com desconto não aparece; ver README (limitações).
        # Price filter uses list price; see README limitations.
        encontrados = self.loja.buscar_produtos(
            termo=termo, categoria_id=categoria_id,
            preco_min=preco_min, preco_max=preco_max, incluir_indisponiveis=True,
        )
        disponiveis = [p for p in encontrados if p.disponivel]
        indisponiveis = [p for p in encontrados if not p.disponivel]
        listados = disponiveis[:LIMITE_RESULTADOS]
        return {
            "total_disponiveis": len(disponiveis),
            "listados": len(listados),
            # Campo explícito: no primeiro teste real o modelo ignorou que havia mais opções.
            # Explicit field: in the first real test the model hid the extra options.
            "nao_listados": len(disponiveis) - len(listados),
            "produtos": [self._resumo(p) for p in listados],
            # Mostrados para o agente poder explicar "esse saiu de linha", não para oferecer.
            # Shown so the agent can explain "that one is out", not to offer them.
            "indisponiveis": [
                {"id": p.id, "nome": p.nome, "situacao": self._situacao(p)} for p in indisponiveis[:LIMITE_RESULTADOS]
            ],
        }

    @staticmethod
    def _situacao(produto: Produto) -> str:
        if produto.status != "active":
            return STATUS_PRODUTO.get(produto.status, produto.status)
        return "sem estoque no momento"

    def _alternativas(self, produto: Produto, quantidade: int = 3) -> list[dict]:
        # Mesma categoria, disponíveis, ordenados pela proximidade de preço.
        # Same category, available, sorted by closeness in price.
        candidatos = [
            p for p in self.loja.produtos.values()
            if p.categoria_id == produto.categoria_id and p.disponivel and p.id != produto.id
        ]
        candidatos.sort(key=lambda p: abs(p.preco - produto.preco))
        return [self._resumo(p) for p in candidatos[:quantidade]]

    def detalhes_produto(self, produto_id: int) -> dict:
        produto = self.loja.produtos.get(int(produto_id))
        if produto is None:
            return {"erro": f"produto {produto_id} não encontrado"}

        detalhes = self._resumo(produto) | {
            "descricao": produto.descricao,
            "especificacoes": produto.specs,
            "situacao": "disponível" if produto.disponivel else self._situacao(produto),
        }
        if produto.disponivel:
            cotacao = cotar(produto, self.loja.promocao_ativa(produto.id))
            parcelas, valor = maximo_de_parcelas(cotacao.preco_a_vista)
            detalhes["parcelamento_maximo"] = f"{parcelas}x de {formatar_brl(valor)} sem juros"
            if produto.estoque <= 3:
                detalhes["ultimas_unidades"] = produto.estoque
        else:
            # Não informa preço de item indisponível para não parecer oferta.
            # No price for unavailable items so it doesn't read as an offer.
            for chave in ("preco_tabela", "preco_a_vista", "preco_pix", "pix_tem_desconto", "promocao"):
                detalhes.pop(chave, None)
            detalhes["alternativas"] = self._alternativas(produto)
        return detalhes

    # ---- Pedidos / Orders ------------------------------------------------------

    def _confere_identidade(self, pedido: Pedido, email_ou_telefone: str) -> bool:
        """LGPD: só mostra o pedido se o cliente provar que é o dono.
        Aceita o e-mail do cadastro ou o telefone (comparando os 8 últimos dígitos,
        para tolerar DDD, +55 e formatação).

        LGPD: only shows the order if the customer proves ownership, by email or
        phone (last 8 digits, to tolerate area code, +55 and formatting)."""
        cliente = self.loja.cliente_do_pedido(pedido)
        if cliente is None:
            return False
        informado = email_ou_telefone.strip().lower()
        if "@" in informado:
            return informado == cliente.email.lower()
        digitos = so_digitos(informado)
        return len(digitos) >= 8 and digitos[-8:] == so_digitos(cliente.telefone)[-8:]

    def _prazos(self, pedido: Pedido) -> dict | None:
        """Prazos de devolução, troca e garantia de um pedido entregue, já calculados.
        Return, exchange and warranty deadlines for a delivered order."""
        if pedido.status != "delivered" or pedido.previsao_entrega is None:
            return None
        hoje = self._agora().date()
        # A base não tem a data real de recebimento; usamos a previsão de entrega.
        # The data has no actual delivery date; we use the estimated one.
        recebimento = pedido.previsao_entrega

        def prazo(base: date, dias: int, regra: str) -> dict:
            limite = base + timedelta(days=dias)
            return {"regra": regra, "data_limite": limite.strftime("%d/%m/%Y"), "dentro_do_prazo": hoje <= limite}

        return {
            "arrependimento": prazo(recebimento, PRAZO_ARREPENDIMENTO_DIAS, "7 dias após o recebimento"),
            "troca_por_defeito_na_loja": prazo(pedido.data, PRAZO_TROCA_DEFEITO_DIAS, "30 dias após a compra"),
            "garantia_legal": prazo(recebimento, PRAZO_GARANTIA_LEGAL_DIAS, "90 dias após o recebimento"),
            "observacao": (
                "datas calculadas pela previsão de entrega, porque a data real de recebimento "
                "não está registrada; depois desses prazos vale a garantia do fabricante"
            ),
        }

    def consultar_pedido(self, pedido_id: int, email_ou_telefone: str) -> dict:
        pedido = self.loja.pedidos.get(int(pedido_id))
        # Mesma resposta para "não existe" e "não confere": não revela quais números são pedidos válidos.
        # Same answer for "missing" and "mismatch": doesn't leak which order ids exist.
        if pedido is None or not self._confere_identidade(pedido, email_ou_telefone):
            return {"erro": "não encontrei pedido com esse número e esses dados de contato"}

        cliente = self.loja.cliente_do_pedido(pedido)
        itens = []
        for item in pedido.itens:
            produto = self.loja.produtos.get(item.produto_id)
            itens.append({"produto": produto.nome if produto else f"produto {item.produto_id}", "quantidade": item.quantidade})

        resposta: dict[str, Any] = {
            "pedido": pedido.id,
            "primeiro_nome": cliente.nome.split()[0],
            "data_da_compra": pedido.data.strftime("%d/%m/%Y"),
            "status": STATUS_PEDIDO.get(pedido.status, pedido.status),
            "itens": itens,
            "total": formatar_brl(dinheiro(pedido.total)),
            "pagamento": _forma_pagamento(pedido.forma_pagamento),
        }
        if pedido.codigo_rastreio:
            resposta["codigo_rastreio"] = pedido.codigo_rastreio
        if pedido.previsao_entrega:
            # Nome explícito: o modelo chegou a tratar a data da compra como data de entrega.
            # Explicit name: the model once read the purchase date as the delivery date.
            resposta["previsao_de_entrega"] = pedido.previsao_entrega.strftime("%d/%m/%Y")
        if pedido.observacao:
            resposta["observacao"] = pedido.observacao
        if (prazos := self._prazos(pedido)) is not None:
            resposta["prazos"] = prazos
        return resposta

    # ---- Políticas e loja / Policies and store ---------------------------------

    def consultar_politica(self, tema: str) -> dict:
        texto = consultar_politica(tema)
        if texto is None:
            return {"erro": f"tema '{tema}' não existe", "temas": temas_disponiveis()}
        return {"tema": tema, "texto": texto}

    def status_loja(self) -> dict:
        agora = self._agora()
        dia = agora.weekday()
        aberto = dia in HORARIO and HORARIO[dia][0] <= agora.time() < HORARIO[dia][1]
        resposta = {
            "agora": f"{NOMES_DIAS[dia]}, {agora:%d/%m/%Y %H:%M} (horário de Campo Grande)",
            "aberta_agora": aberto,
            "aviso": "feriados não estão no sistema; em feriado a loja fecha",
        }
        if not aberto:
            resposta["proxima_abertura"] = self._proxima_abertura(agora)
        else:
            resposta["fecha_hoje_as"] = HORARIO[dia][1].strftime("%H:%M")
        return resposta

    @staticmethod
    def _proxima_abertura(agora: datetime) -> str:
        for avanco in range(0, 8):
            dia = (agora + timedelta(days=avanco)).date()
            if dia.weekday() not in HORARIO:
                continue
            abre = HORARIO[dia.weekday()][0]
            if avanco == 0 and agora.time() >= abre:
                continue
            quando = "hoje" if avanco == 0 else "amanhã" if avanco == 1 else NOMES_DIAS[dia.weekday()]
            return f"{quando} às {abre:%H:%M}"
        return "consulte a loja"


# ---- Schemas enviados ao modelo / Schemas sent to the model ------------------

def schemas() -> list[dict]:
    """Descrições escritas para o modelo: dizem QUANDO usar cada ferramenta.
    Descriptions are written for the model: they say WHEN to use each tool."""
    return [
        {
            "type": "function",
            "function": {
                "name": "buscar_produtos",
                "description": (
                    "Busca instrumentos no catálogo com preço e disponibilidade atuais. "
                    "Use sempre que o cliente perguntar por produtos, modelos, marcas, faixas de preço "
                    "ou disponibilidade. Nunca cite preço ou estoque sem chamar esta ferramenta ou detalhes_produto."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "termo": {"type": "string", "description": "Marca, modelo ou característica. Ex.: 'Takamine', 'eletroacústico', 'nylon'."},
                        "categoria": {"type": "string", "description": "Ex.: violões, guitarras, baixos, teclados, baterias, ukuleles."},
                        "preco_min": {"type": "number", "description": "Preço mínimo em reais."},
                        "preco_max": {"type": "number", "description": "Preço máximo em reais."},
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "detalhes_produto",
                "description": (
                    "Detalhes de um produto pelo id: especificações, preço no cartão e no PIX, parcelamento, "
                    "situação de estoque e alternativas se estiver indisponível. Use depois de buscar_produtos."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"produto_id": {"type": "integer"}},
                    "required": ["produto_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_pedido",
                "description": (
                    "Status, itens, rastreio e prazo de arrependimento de um pedido. Exige o número do pedido "
                    "E o e-mail ou telefone do cadastro. Se o cliente não informou os dois, peça antes de chamar."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pedido_id": {"type": "integer"},
                        "email_ou_telefone": {"type": "string"},
                    },
                    "required": ["pedido_id", "email_ou_telefone"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_politica",
                "description": (
                    "Texto oficial das políticas da loja sobre um tema. Use para endereço e contato, horário, "
                    "pagamento, trocas/devoluções, frete, promoções, garantia, privacidade e o que a loja vende."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"tema": {"type": "string", "enum": temas_disponiveis()}},
                    "required": ["tema"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "status_loja",
                "description": "Diz se a loja está aberta agora e quando abre. Use para 'vocês estão abertos?' e similares.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
    ]
