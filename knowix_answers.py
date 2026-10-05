"""Formatação conservadora de respostas geradas para exibição no Knowix."""

from __future__ import annotations

import re

MAX_ENTRADA_CARACTERES = 16000


def resumir_resposta(texto: str, limite_estruturado: int = 4000) -> str:
    """Preserva Markdown útil e resume prosa simples sem reescrever seu conteúdo."""
    texto = str(texto or "")[:MAX_ENTRADA_CARACTERES]
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not texto:
        return ""

    linhas = [linha.rstrip() for linha in texto.splitlines()]
    formatado = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    marcadores = re.compile(
        r"^\s*(?:#{1,6}\s|[-*+]\s|•\s|\d+[.)]\s|\|.*\|)|"
        r"^\s*\*\*[^*]{1,100}\*\*:?\s*$"
    )
    tem_estrutura = any(marcadores.search(linha) for linha in linhas)

    if tem_estrutura:
        if len(formatado) <= limite_estruturado:
            return formatado
        corte = formatado.rfind("\n", 0, limite_estruturado)
        if corte < limite_estruturado // 2:
            corte = limite_estruturado
        return formatado[:corte].rstrip() + "\n\n…"

    prosa = " ".join(formatado.split())
    frases = re.split(r"(?<=[.!?])\s+", prosa)
    resumo = " ".join(frases[:3])
    if len(resumo) <= 620:
        return resumo
    return resumo[:620].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
