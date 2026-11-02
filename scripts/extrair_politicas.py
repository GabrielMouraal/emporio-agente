"""Extrai o texto do PDF de políticas para um .txt legível.

O pypdf devolve o PDF palavra por palavra, com quebras de linha entre elas.
Este script junta tudo, tira cabeçalho/rodapé de página e quebra o texto
antes de cada seção numerada. O resultado (data/politicas_brutas.txt) serve
de base para revisar data/politicas.md, que é o arquivo que o agente usa.

Extracts the policy PDF into readable text. pypdf returns one word per line,
so this joins the words, drops page headers/footers and breaks before each
numbered section. The output is the reference used to review
data/politicas.md, which is what the agent actually reads.

Uso / Usage:
    python scripts/extrair_politicas.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parent.parent
PDF = RAIZ / "data" / "políticas_da_loja.pdf"
SAIDA = RAIZ / "data" / "politicas_brutas.txt"

CABECALHO = "Empório da Música Manual de Políticas e Procedimentos"


def texto_da_pagina(pagina) -> str:
    palavras = pagina.extract_text().split()
    texto = " ".join(palavras)
    texto = texto.replace(CABECALHO, "")
    texto = re.sub(r"Página \d+\s*$", "", texto)
    return texto.strip()


def quebrar_secoes(texto: str) -> str:
    # "4. Política de Trocas" e "4.1 Direito de..." viram início de linha.
    # Exige letra maiúscula depois do número para não quebrar valores como "R$ 2.000,00".
    # Numbered headings start a new line; requires an uppercase letter after the number
    # so prices like "2.000,00" are not split.
    texto = re.sub(r"\s(\d{1,2}\.(?:\d\s)?\s?[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", r"\n\n\1", texto)
    texto = texto.replace(" • ", "\n- ")
    return texto


def extrair(pdf: Path = PDF) -> str:
    leitor = PdfReader(str(pdf))
    paginas = [texto_da_pagina(p) for p in leitor.pages]
    return quebrar_secoes(" ".join(paginas)).strip() + "\n"


def main() -> int:
    if not PDF.exists():
        print(f"PDF não encontrado / PDF not found: {PDF}", file=sys.stderr)
        return 1
    SAIDA.write_text(extrair(), encoding="utf-8")
    print(f"Gerado / Written: {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
