import os
from urllib.parse import quote_plus, urlparse

import requests
import streamlit as st
import yt_dlp


st.set_page_config(page_title="Knowix", page_icon="🔎")
st.title("🔎 Knowix")
st.subheader("Pesquise, confira as fontes e encontre vídeos")
st.write("Faça uma pergunta para receber uma resposta curta baseada em fontes da web.")
st.info(
    "O Knowix prioriza fontes oficiais e especializadas quando possível, e sempre mostra links para você conferir. "
    "Nenhum mecanismo consegue garantir que toda página seja confiável."
)


def obter_chave_tavily():
    """Lê a chave salva com segurança nas configurações do Streamlit."""
    try:
        return st.secrets.get("TAVILY_API_KEY", "")
    except Exception:
        return os.environ.get("TAVILY_API_KEY", "")


def pesquisar_na_web(pergunta, chave):
    """Pede ao Tavily uma resposta curta e resultados de busca com links."""
    url = "https://api.tavily.com/search"
    cabecalhos = {
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    dados = {
        "query": (
            "Pesquise a pergunta a seguir e escreva a resposta em português brasileiro: "
            f"{pergunta}"
        ),
        "topic": "general",
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": "basic",
        "include_raw_content": False,
        "include_domains": [
            "gov.br",
            "edu.br",
            "fiocruz.br",
            "scielo.br",
            "who.int",
            "un.org",
            "europa.eu",
            "nasa.gov",
            "nih.gov",
            "cdc.gov",
            "britannica.com",
        ],
        "include_domains_mode": "prefer",
        "country": "brazil",
        "language": "pt",
        "filter_by_language": True,
        "safe_search": True,
    }
    resposta = requests.post(url, headers=cabecalhos, json=dados, timeout=30)
    if resposta.status_code == 401:
        raise ValueError("A chave de busca não foi aceita. Confira a configuração TAVILY_API_KEY.")
    if resposta.status_code == 429:
        raise ValueError("O limite de buscas foi atingido ou o serviço está ocupado. Tente mais tarde.")
    resposta.raise_for_status()
    return resposta.json()


def pesquisar_wikipedia(assunto):
    """Busca páginas e trechos na Wikipédia para o modo sem chave de busca."""
    url = "https://pt.wikipedia.org/w/api.php"
    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": assunto,
        "gsrlimit": 5,
        "prop": "extracts|info",
        "exintro": 1,
        "explaintext": 1,
        "inprop": "url",
        "format": "json",
        "formatversion": 2,
    }
    cabecalhos = {"User-Agent": "Knowix/1.0 (aplicativo educacional)"}
    resposta = requests.get(url, params=parametros, headers=cabecalhos, timeout=20)
    resposta.raise_for_status()
    dados = resposta.json()
    return dados.get("query", {}).get("pages", [])


def escolher_pagina_principal(paginas, assunto):
    """Prefere a página cujo título corresponde melhor ao assunto pesquisado."""
    termos = [
        termo.casefold().strip("?!.,:;")
        for termo in assunto.split()
        if len(termo.strip("?!.,:;")) >= 3
    ]
    if not termos:
        return paginas[0]

    ultimo_termo = termos[-1]

    def pontuacao(pagina):
        titulo = pagina.get("title", "").casefold()
        correspondencias = sum(1 for termo in set(termos) if termo in titulo)
        inclui_ultimo_termo = ultimo_termo in titulo
        palavras_titulo = len(titulo.split())
        palavras_extras = max(0, palavras_titulo - correspondencias)
        return (
            correspondencias + (3 if inclui_ultimo_termo else 0) - 2 * palavras_extras,
            -palavras_titulo,
        )

    return max(paginas, key=pontuacao)


def pesquisar_video_youtube(assunto):
    """Procura cinco vídeos e escolhe o mais visto entre esses resultados."""
    opcoes = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "ignoreerrors": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opcoes) as youtube:
        resultado = youtube.extract_info(f"ytsearch5:{assunto}", download=False)

    videos = [video for video in (resultado or {}).get("entries", []) if video and video.get("id")]
    if not videos:
        return None
    return max(videos, key=lambda video: video.get("view_count") or 0)


with st.form("formulario_pesquisa"):
    pergunta = st.text_input(
        "O que você quer saber?",
        placeholder="Ex.: quais são os benefícios da energia solar?",
    )
    buscar = st.form_submit_button("Pesquisar")

if buscar:
    if not pergunta.strip():
        st.warning("Digite uma pergunta antes de pesquisar.")
    else:
        chave_tavily = obter_chave_tavily()
        with st.spinner("Pesquisando na web e reunindo fontes..."):
            try:
                if chave_tavily:
                    resultado_web = pesquisar_na_web(pergunta.strip(), chave_tavily)
                    resposta_direta = resultado_web.get("answer", "").strip()
                    resultados = resultado_web.get("results", [])
                    fontes = [
                        {
                            "title": item.get("title") or "Fonte da web",
                            "url": item.get("url", ""),
                            "content": item.get("content", ""),
                            "domain": urlparse(item.get("url", "")).netloc,
                        }
                        for item in resultados
                        if item.get("url")
                    ]
                    modo_web = True
                else:
                    paginas = pesquisar_wikipedia(pergunta.strip())
                    if not paginas:
                        st.warning("Não encontrei fontes. Tente reformular a pergunta.")
                        fontes = []
                        resposta_direta = ""
                    else:
                        pagina_principal = escolher_pagina_principal(paginas, pergunta.strip())
                        resposta_direta = pagina_principal.get("extract", "").strip()
                        fontes = [
                            {
                                "title": pagina.get("title", "Fonte"),
                                "url": pagina.get("fullurl", ""),
                                "content": pagina.get("extract", ""),
                                "domain": "pt.wikipedia.org",
                            }
                            for pagina in paginas
                            if pagina.get("fullurl")
                        ]
                    modo_web = False

                if not chave_tavily:
                    st.warning(
                        "A busca na web ainda não está configurada. Mostrando a Wikipédia por enquanto; "
                        "adicione uma chave Tavily nas configurações do Streamlit para buscar em outros sites."
                    )

                if resposta_direta:
                    st.subheader("Resposta direta")
                    limite = 1200 if modo_web else 650
                    if len(resposta_direta) > limite:
                        resposta_direta = resposta_direta[:limite].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
                    st.write(resposta_direta)
                    if modo_web:
                        st.caption(
                            "Resposta gerada a partir dos resultados da busca. Confira as fontes antes de usar "
                            "informações importantes."
                        )
                    elif fontes:
                        st.caption("Resumo da página cujo título mais corresponde à pergunta.")

                st.subheader("Vídeos relacionados")
                busca_youtube = quote_plus(pergunta.strip())
                link_youtube = f"https://www.youtube.com/results?search_query={busca_youtube}"
                st.link_button("Ver vídeos no YouTube", link_youtube, type="primary")
                try:
                    video = pesquisar_video_youtube(pergunta.strip())
                    if video:
                        st.markdown(f"**Prévia: {video.get('title', 'Vídeo relacionado')}**")
                        canal = video.get("channel") or video.get("uploader")
                        visualizacoes = video.get("view_count")
                        detalhes = []
                        if canal:
                            detalhes.append(f"Canal: {canal}")
                        if visualizacoes is not None:
                            detalhes.append(f"Visualizações: {visualizacoes:,}".replace(",", "."))
                        if detalhes:
                            st.caption(" • ".join(detalhes))
                        st.video(f"https://www.youtube.com/watch?v={video['id']}")
                        st.caption("Visualizações não garantem que um vídeo seja viral ou que esteja correto.")
                    else:
                        st.info("Não consegui carregar a prévia agora. Use o botão para abrir os resultados no YouTube.")
                except Exception:
                    st.info("O YouTube não disponibilizou a prévia agora. Use o botão para abrir os resultados.")

                st.subheader("Fontes para conferir")
                if fontes:
                    for fonte in fontes:
                        st.markdown(f"### [{fonte['title']}]({fonte['url']})")
                        if fonte.get("domain"):
                            st.caption(f"Site: {fonte['domain']}")
                        trecho = (fonte.get("content") or "").strip()
                        if trecho:
                            limite_trecho = 650 if modo_web else 350
                            if len(trecho) > limite_trecho:
                                trecho = trecho[:limite_trecho].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
                            st.write(trecho)
                        else:
                            st.caption("Abra o link para consultar a página original.")
                else:
                    st.info("Não encontrei fontes para mostrar.")

                sugestoes = [
                    f"Características de {pergunta.strip()}",
                    f"Como funciona {pergunta.strip()}",
                    f"Importância de {pergunta.strip()}",
                    f"Curiosidades sobre {pergunta.strip()}",
                ]
                st.subheader("Sugestões de pesquisas relacionadas")
                colunas = st.columns(2)
                for indice, sugestao in enumerate(sugestoes):
                    pesquisa_relacionada = quote_plus(sugestao)
                    url_relacionada = f"https://www.google.com/search?q={pesquisa_relacionada}"
                    with colunas[indice % 2]:
                        st.link_button(sugestao, url_relacionada, use_container_width=True)
            except ValueError as erro:
                st.error(str(erro))
            except requests.exceptions.RequestException:
                st.error("Não consegui acessar o serviço de busca. Confira a conexão e tente novamente.")
            except (KeyError, TypeError):
                st.error("A resposta da busca veio em um formato inesperado. Tente novamente.")

st.caption("Compare as fontes, confira a data e consulte um profissional para decisões importantes.")
