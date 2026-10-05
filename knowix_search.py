"""Regras locais para comparar perguntas e organizar resultados de pesquisa."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse


def normalizar_url_http(valor: object, somente_https: bool = False, max_caracteres: int = 2000) -> str:
    """Aceita URLs HTTP(S) válidas e evita credenciais e destinos locais."""
    texto = str(valor or "")[:max_caracteres]
    try:
        url = urlparse(texto)
        hostname = url.hostname
        _ = url.port
    except ValueError:
        return ""

    esquemas = {"https"} if somente_https else {"http", "https"}
    if (
        url.scheme not in esquemas
        or not url.netloc
        or not hostname
        or url.username is not None
        or url.password is not None
        or any(caractere.isspace() or ord(caractere) < 32 for caractere in hostname)
    ):
        return ""

    host_normalizado = hostname.casefold().rstrip(".")
    if host_normalizado == "localhost" or host_normalizado.endswith((".localhost", ".local")):
        return ""
    try:
        endereco = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if not endereco.is_global:
            return ""
    return texto


def classificar_fonte(fonte: dict) -> str:
    """Classifica fontes por sinais explícitos no URL; a categoria é aproximada."""
    url = urlparse(str(fonte.get("url", "")))
    caminho = url.path.casefold()
    dominio = url.netloc.casefold().removeprefix("www.")
    if re.search(r"\.(pdf|docx?|pptx?|xlsx?|csv|rtf|odt)$", caminho):
        return "documents"
    sinais_noticia = ("/noticia", "/news/", "/notícias", "/breaking-news", "/politica/")
    dominios_noticia = (
        "g1.globo.com", "bbc.com", "bbc.co.uk", "cnn.com", "reuters.com",
        "apnews.com", "agenciabrasil.ebc.com.br", "folha.uol.com.br", "estadao.com.br",
    )
    if any(sinal in caminho for sinal in sinais_noticia) or any(
        dominio == item or dominio.endswith("." + item) for item in dominios_noticia
    ):
        return "news"
    if any(sinal in caminho for sinal in ("/artigo/", "/article/", "/journal/", "/research/", "/paper/", "/papers/")):
        return "articles"
    return "site"


def detectar_comparacao(pergunta: str) -> dict[str, str] | None:
    """Extrai dois candidatos apenas quando a pergunta usa uma forma comparativa clara."""
    texto = " ".join(str(pergunta or "").split()).strip()[:1000]
    padroes = (
        r"^(?:compare|comparar|compara)\s+(.+?)\s+(?:e|y|and|com|vs\.?|versus)\s+(.+?)[?!.]*$",
        r"^(.+?)\s+(?:vs\.?|versus|ou|or)\s+(.+?)[?!.]*$",
    )
    for padrao in padroes:
        resultado = re.match(padrao, texto, flags=re.IGNORECASE)
        if resultado:
            opcoes = [
                re.sub(
                    r"^(?:qual é melhor|qual e melhor|which is better|compare|comparar)\s*:?\s*",
                    "", parte, flags=re.IGNORECASE,
                ).strip(" ?!.,:;")[:80]
                for parte in resultado.groups()
            ]
            if all(opcoes) and opcoes[0].casefold() != opcoes[1].casefold():
                return {"opcao_a": opcoes[0], "opcao_b": opcoes[1]}
    return None


def filtros_disponiveis(fontes: list[dict], tem_video: bool, tem_imagens: bool) -> list[str]:
    """Retorna somente filtros com resultados, separando sites genéricos das categorias próprias."""
    categorias = {str(fonte.get("category", "site")) for fonte in fontes if isinstance(fonte, dict)}
    filtros = ["all"]
    if "site" in categorias:
        filtros.append("sites")
    for categoria in ("news", "articles", "documents"):
        if categoria in categorias:
            filtros.append(categoria)
    if tem_video:
        filtros.append("videos")
    if tem_imagens:
        filtros.append("images")
    return filtros


def filtrar_fontes(fontes: list[dict], filtro: str) -> list[dict]:
    """Filtra somente a categoria escolhida; `all` mantém todas as fontes."""
    if filtro == "all":
        return fontes
    categoria = "site" if filtro == "sites" else filtro
    return [fonte for fonte in fontes if fonte.get("category", "site") == categoria]
