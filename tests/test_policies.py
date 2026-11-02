import re

import pytest

from emporio.policies import consultar_politica, temas_disponiveis

TEMAS_ESPERADOS = {
    "loja", "escopo", "horario", "pagamento", "trocas",
    "frete", "promocoes", "garantia", "atendimento", "privacidade",
}


def test_todos_os_temas_carregados():
    assert set(temas_disponiveis()) == TEMAS_ESPERADOS


def test_tema_inexistente_volta_none():
    assert consultar_politica("cafe") is None


@pytest.mark.parametrize(
    "tema, trecho",
    [
        ("horario", "09:00 às 13:00"),
        ("trocas", "7 dias corridos"),
        ("frete", "R$ 500,00"),
        ("loja", "Rua 14 de Maio, 3200"),
    ],
)
def test_secao_traz_o_fato_certo(tema, trecho):
    assert trecho in consultar_politica(tema)


def test_valores_do_md_existem_no_pdf():
    # Proteção contra erro de digitação no politicas.md: todo valor em reais,
    # prazo em dias e horário citado no .md precisa aparecer no texto do PDF.
    # Guards against typos: every amount, day count and time in the .md must exist in the PDF.
    pypdf = pytest.importorskip("pypdf")  # noqa: F841
    from scripts.extrair_politicas import extrair

    # O PDF escreve "90 (noventa) dias"; tira o número por extenso para comparar.
    pdf = re.sub(r" \([a-zç]+\)", "", extrair())
    md = "\n".join(consultar_politica(t) for t in temas_disponiveis())
    padroes = [r"R\$ [\d.]+,\d{2}", r"\d+ dias", r"\d{2}:\d{2}"]
    for padrao in padroes:
        for valor in set(re.findall(padrao, md)):
            assert valor in pdf, f"{valor!r} está no politicas.md mas não no PDF"
