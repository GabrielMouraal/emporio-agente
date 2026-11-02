import pytest

from emporio.data import Loja, normalizar


@pytest.fixture(scope="module")
def loja():
    return Loja()


def test_carrega_todas_as_tabelas(loja):
    assert len(loja.produtos) == 65
    assert len(loja.pedidos) == 20
    assert len(loja.clientes) == 50
    assert len(loja.categorias) == 9


def test_normalizar_ignora_acento_e_pontuacao():
    assert normalizar("Violão GD-20!") == "violao gd 20"


def test_busca_por_modelo_com_ou_sem_hifen(loja):
    assert [p.id for p in loja.buscar_produtos("takamine gd20")] == [95]
    assert [p.id for p in loja.buscar_produtos("Takamine GD-20")] == [95]


def test_busca_por_categoria_e_preco(loja):
    violoes = loja.categoria_por_nome("violão")
    resultado = loja.buscar_produtos(categoria_id=violoes.id, preco_max=1000)
    assert resultado
    assert all(p.preco <= 1000 and p.disponivel for p in resultado)


def test_produto_sem_estoque_fica_fora_da_busca_padrao(loja):
    # Giannini GF-3D está ativo, mas com estoque zero.
    assert 96 not in [p.id for p in loja.buscar_produtos("giannini")]
    assert 96 in [p.id for p in loja.buscar_produtos("giannini", incluir_indisponiveis=True)]


def test_promocao_ativa(loja):
    assert loja.promocao_ativa(121).desconto_percentual == 20
    assert loja.promocao_ativa(95) is None  # só tem promoção vencida


def test_auditoria_encontra_inconsistencias_conhecidas(loja):
    avisos = "\n".join(loja.auditar())
    assert "Pedido 3" in avisos
    assert "Pedido 20" in avisos
    assert "Sopro" in avisos
    assert "bruno.martins@jmail.com" in avisos


@pytest.mark.parametrize(
    "termo, esperado",
    [("violão", "Violões"), ("guitarra", "Guitarras"), ("piano", "Teclados e Pianos"), ("baixo", "Baixos")],
)
def test_categoria_aceita_singular_e_plural(loja, termo, esperado):
    assert loja.categoria_por_nome(termo).nome == esperado


def test_categoria_inexistente(loja):
    assert loja.categoria_por_nome("pedal") is None


def test_auditoria_pega_parcela_abaixo_do_minimo(loja):
    avisos = " ".join(loja.auditar())
    assert "Pedido 9: 6x" in avisos and "Pedido 16: 6x" in avisos
