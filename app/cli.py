"""Chat com a Lia no terminal. / Chat with Lia in the terminal.

Uso / Usage:
    python app/cli.py            # conversa normal / normal chat
    python app/cli.py --debug    # mostra as ferramentas chamadas / shows tool calls

Comandos: /sair encerra, /novo começa outra conversa.
Commands: /sair quits, /novo starts a new conversation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from emporio.agent import Agente


def main() -> int:
    parser = argparse.ArgumentParser(description="Atendente virtual da Empório da Música")
    parser.add_argument("--debug", action="store_true", help="mostra as ferramentas chamadas / show tool calls")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Defina OPENAI_API_KEY no arquivo .env / Set OPENAI_API_KEY in .env", file=sys.stderr)
        return 1

    agente = Agente()
    print(f"Empório da Música — atendimento ({agente.modelo}). /sair para encerrar, /novo para recomeçar.\n")

    while True:
        try:
            mensagem = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not mensagem:
            continue
        if mensagem == "/sair":
            return 0
        if mensagem == "/novo":
            agente.reiniciar()
            print("(nova conversa)\n")
            continue

        resposta = agente.responder(mensagem)
        if args.debug:
            for chamada in resposta.chamadas:
                print(f"  [ferramenta] {chamada.nome}({json.dumps(chamada.argumentos, ensure_ascii=False)})")
        print(f"Lia: {resposta.texto}\n")


if __name__ == "__main__":
    raise SystemExit(main())
