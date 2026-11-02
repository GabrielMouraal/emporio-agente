"""Leitura das políticas da loja a partir de data/politicas.md.

O documento é pequeno (8 páginas), então não há busca vetorial: cada seção tem
um tema fixo e o modelo escolhe o tema pela ferramenta `consultar_politica`.
Isso deixa a resposta previsível e fácil de testar.

Reads store policies from data/politicas.md. The document is small, so there is
no vector search: each section has a fixed topic and the model picks one through
the `consultar_politica` tool. Predictable and easy to test.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from emporio.data import DATA_DIR

ARQUIVO_POLITICAS = DATA_DIR / "politicas.md"

# "## [frete] Frete e entregas" -> tema "frete", título "Frete e entregas"
_CABECALHO = re.compile(r"^## \[(?P<tema>[a-z_]+)\] (?P<titulo>.+)$", re.MULTILINE)


@lru_cache(maxsize=1)
def carregar_politicas(caminho: Path = ARQUIVO_POLITICAS) -> dict[str, str]:
    """Devolve {tema: texto da seção, com o título na primeira linha}.
    Returns {topic: section text, title on the first line}."""
    texto = caminho.read_text(encoding="utf-8")
    cabecalhos = list(_CABECALHO.finditer(texto))
    secoes: dict[str, str] = {}
    for atual, proximo in zip(cabecalhos, cabecalhos[1:] + [None]):
        fim = proximo.start() if proximo else len(texto)
        corpo = texto[atual.end():fim].strip()
        secoes[atual["tema"]] = f"{atual['titulo']}\n{corpo}"
    return secoes


def temas_disponiveis() -> list[str]:
    return list(carregar_politicas())


def consultar_politica(tema: str) -> str | None:
    return carregar_politicas().get(tema)
