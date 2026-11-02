"""Configuração lida do ambiente (.env).
Settings read from the environment (.env)."""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

FUSO_LOJA = ZoneInfo("America/Campo_Grande")
MODELO_PADRAO = "gpt-4o-mini"


def modelo() -> str:
    return os.getenv("OPENAI_MODEL") or MODELO_PADRAO


def agora() -> datetime:
    """Hora atual no fuso da loja. EMPORIO_AGORA (ISO, ex. 2026-03-20T10:30) fixa
    um momento, útil para demonstração e testes: os pedidos da base vão até março de 2026.

    Current time in the store's timezone. EMPORIO_AGORA pins a moment, handy for
    demos and tests since the sample orders end in March 2026."""
    fixo = os.getenv("EMPORIO_AGORA")
    if fixo:
        momento = datetime.fromisoformat(fixo)
        return momento if momento.tzinfo else momento.replace(tzinfo=FUSO_LOJA)
    return datetime.now(FUSO_LOJA)


def hoje() -> date:
    return agora().date()
