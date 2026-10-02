import requests
import streamlit as st
import yt_dlp
from urllib.parse import quote_plus


st.set_page_config(page_title="Knowix", page_icon="🔎")
st.title("🔎 Knowix")
st.subheader("Pesquise, confira as fontes e encontre vídeos")
st.write(
    "Digite sua pergunta ou assunto para ver um resumo direto, as fontes e vídeos relacionados."
)
st.info(
    "As páginas são fontes para você conferir. A Wikipédia pode conter erros e não substitui fontes oficiais ou especializadas."
)


def pesquisar_wikipedia(assunto):
    """Busca páginas e pequenos trechos na Wikipédia em português."""
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
    cabecalhos = {"User-Agent": "PesquisaComFontes/1.0 (app educacional)"}
    resposta = requests.get(url, params=parametros, headers=cabecalhos, timeout=20)
    resposta.raise_for_status()
    dados = resposta.json()
    return dados.get("query", {}).get("pages", [])


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

    # Se o número de visualizações não estiver disponível, mantém o primeiro resultado.
    return max(videos, key=lambda video: video.get("view_count") or 0)


def escolher_pagina_principal(paginas, assunto):
    """Prefere a página cujo título corresponde melhor ao assunto pesquisado."""
    termos = [termo.casefold().strip("?!.,:;") for termo in assunto.split() if len(termo.strip("?!.,:;")) >= 3]
    if not termos:
        return paginas[0]

    ultimo_termo = termos[-1]

    def pontuacao(pagina):
        titulo = pagina.get("title", "").casefold()
        correspondencias = sum(1 for termo in set(termos) if termo in titulo)
        inclui_ultimo_termo = ultimo_termo in titulo
        palavras_titulo = len(titulo.split())
        palavras_correspondidas = sum(1 for termo in set(termos) if termo in titulo)
        palavras_extras = max(0, palavras_titulo - palavras_correspondidas)
        return (correspondencias + (3 if inclui_ultimo_termo else 0) - 2 * palavras_extras, -palavras_titulo)

    return max(paginas, key=pontuacao)


with st.form("formulario_pesquisa"):
    assunto = st.text_input("O que você quer pesquisar?", placeholder="Ex.: como funciona a energia solar")
    buscar = st.form_submit_button("Pesquisar")

if buscar:
    if not assunto.strip():
        st.warning("Digite um assunto antes de pesquisar.")
    else:
        with st.spinner("Procurando informações..."):
            try:
                paginas = pesquisar_wikipedia(assunto.strip())
                if not paginas:
                    st.warning("Não encontrei páginas. Tente outras palavras.")
                else:
                    pagina_principal = escolher_pagina_principal(paginas, assunto.strip())
                    resumo = pagina_principal.get("extract", "").strip()

                    st.subheader("Resposta em resumo")
                    st.caption("Resumo da página cujo título mais corresponde à sua pesquisa; abra a fonte para ler o contexto completo.")
                    if resumo:
                        limite = 650
                        if len(resumo) > limite:
                            resumo = resumo[:limite].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
                        st.write(resumo)
                        st.markdown(f"**Fonte principal:** [{pagina_principal['title']}]({pagina_principal['fullurl']})")
                    else:
                        st.info("Não encontrei um resumo curto para este assunto. Confira as fontes abaixo.")

                    st.subheader("Vídeos relacionados")
                    busca_youtube = quote_plus(assunto.strip())
                    link_youtube = f"https://www.youtube.com/results?search_query={busca_youtube}"
                    st.link_button("Ver vídeos no YouTube", link_youtube, type="primary")
                    try:
                        video = pesquisar_video_youtube(assunto.strip())
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
                            st.caption("O vídeo é selecionado entre os primeiros resultados; visualizações não garantem que seja viral ou correto.")
                        else:
                            st.info("Não consegui carregar a prévia agora. Use o botão para abrir os resultados no YouTube.")
                    except Exception:
                        st.info("O YouTube não disponibilizou a prévia agora. Use o botão para abrir os resultados.")

                    st.subheader("Fontes para conferir")
                    for pagina in paginas:
                        st.markdown(f"### [{pagina['title']}]({pagina['fullurl']})")
                        trecho = pagina.get("extract", "").strip()
                        if trecho:
                            limite_trecho = 350
                            if len(trecho) > limite_trecho:
                                trecho = trecho[:limite_trecho].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
                        st.write(trecho if trecho else "A página não trouxe um resumo.")

                    sugestoes = [
                        f"Características de {assunto.strip()}",
                        f"Como funciona {assunto.strip()}",
                        f"Importância de {assunto.strip()}",
                        f"Curiosidades sobre {assunto.strip()}",
                    ]
                    st.subheader("Sugestões de pesquisas relacionadas")
                    if sugestoes:
                        colunas = st.columns(2)
                        for indice, sugestao in enumerate(sugestoes):
                            pesquisa_relacionada = quote_plus(sugestao)
                            url_relacionada = f"https://pt.wikipedia.org/w/index.php?search={pesquisa_relacionada}"
                            with colunas[indice % 2]:
                                st.link_button(sugestao, url_relacionada, use_container_width=True)
            except requests.exceptions.RequestException:
                st.error("Não consegui acessar a Wikipédia. Confira sua internet e tente novamente.")
            except (ValueError, KeyError):
                st.error("A resposta veio em um formato inesperado. Tente pesquisar novamente.")

st.caption("Este programa não inventa uma resposta: ele mostra trechos de páginas e links para você verificar.")
