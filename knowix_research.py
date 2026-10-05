"""Integração da pesquisa profunda com a API Tavily, sem dependência da interface."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from urllib.parse import quote, urlparse

import requests

from knowix_search import classificar_fonte, normalizar_url_http


def pesquisar_profundamente(pergunta: str, chave: str, fila_progresso) -> dict:
    """Inicia e acompanha uma tarefa Tavily, retornando apenas dados de fontes validadas."""
    base_url = "https://api.tavily.com/research"
    cabecalhos = {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
    instrucoes = (
        f"Pesquise profundamente: {pergunta}. Divida em subtópicos, consulte fontes diversas, compare evidências, "
        "aponte divergências e limites do que foi encontrado, organize o relatório em seções claras e inclua citações "
        "numeradas ligadas às fontes. Não invente fatos nem fontes; diferencie evidência de conclusão. Responda em português brasileiro."
    )
    resposta = requests.post(
        base_url,
        headers=cabecalhos,
        json={"input": instrucoes, "model": "auto", "stream": False,
              "citation_format": "numbered", "output_length": "standard"},
        timeout=(3, 15),
    )
    if resposta.status_code == 401:
        raise ValueError("A chave de pesquisa profunda não foi aceita. Confira TAVILY_API_KEY nas configurações.")
    if resposta.status_code == 429:
        raise ValueError("O limite de pesquisas profundas foi atingido. Tente novamente mais tarde.")
    resposta.raise_for_status()
    tarefa = resposta.json()
    request_id = str(tarefa.get("request_id", ""))[:128]
    if not re.fullmatch(r"[A-Za-z0-9-]{1,128}", request_id):
        raise ValueError("O serviço não confirmou a criação da pesquisa profunda.")

    inicio = time.monotonic()
    fila_progresso.put("accepted")
    while time.monotonic() - inicio < 300:
        time.sleep(3)
        estado = requests.get(
            f"{base_url}/{quote(request_id, safe='')}",
            headers={"Authorization": f"Bearer {chave}"},
            params={"include_usage": "true"},
            timeout=(3, 15),
        )
        if estado.status_code == 401:
            raise ValueError("A chave de pesquisa profunda não foi aceita ao consultar o resultado.")
        estado.raise_for_status()
        dados_estado = estado.json()
        if not isinstance(dados_estado, dict):
            raise ValueError("O serviço retornou um estado inválido para a pesquisa profunda.")
        status = dados_estado.get("status")
        if status == "completed":
            fila_progresso.put("finalizing")
            fontes = []
            consultado_em = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
            fontes_api = dados_estado.get("sources", [])
            if isinstance(fontes_api, list):
                for item in fontes_api:
                    if not isinstance(item, dict):
                        continue
                    url_fonte = normalizar_url_http(item.get("url", ""))
                    if not url_fonte:
                        continue
                    fonte = {
                        "title": str(item.get("title") or "Abrir resultado")[:240],
                        "url": url_fonte,
                        "content": str(item.get("content") or "")[:1200],
                        "domain": urlparse(url_fonte).netloc.removeprefix("www.")[:180],
                        "published_date": str(item.get("published_date") or "")[:80] or None,
                        "consulted_at": consultado_em,
                    }
                    fonte["category"] = classificar_fonte(fonte)
                    fontes.append(fonte)
                    if len(fontes) >= 12:
                        break
            conteudo = dados_estado.get("content", "")
            if isinstance(conteudo, dict):
                conteudo = json.dumps(conteudo, ensure_ascii=False, indent=2)
            uso = dados_estado.get("usage", {})
            return {
                "answer": str(conteudo or "").strip()[:16000],
                "results": fontes,
                "images": [],
                "usage": uso if isinstance(uso, dict) else {},
                "research_mode": True,
                "request_id": request_id,
            }
        if status in {"failed", "error"}:
            raise ValueError("O serviço não conseguiu concluir esta pesquisa profunda.")
        fila_progresso.put(f"andamento:{int(time.monotonic() - inicio)}")
    raise TimeoutError("deep_research_timeout")
