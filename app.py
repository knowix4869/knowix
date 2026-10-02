import os
import re
from html import escape
from urllib.parse import quote_plus, urlparse

import requests
import streamlit as st
import yt_dlp


st.set_page_config(
    page_title="Knowix — Pesquisa na web",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
    :root { --ink:#14213d; --muted:#69758c; --blue:#246bfe; --line:#e2e8f2; }
    [data-testid="stAppViewContainer"] { background:#f4f7fc; color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    .block-container { max-width:1180px; padding-top:1.25rem; padding-bottom:3rem; }
    html, body, [class*="css"] { font-family:'DM Sans',Arial,sans-serif; }
    .browser-bar {
      align-items:center; background:#fff; border:1px solid #e4e9f1;
      border-radius:18px; box-shadow:0 5px 22px rgba(32,57,94,.07);
      display:flex; gap:16px; margin:0 auto 2.2rem; max-width:900px;
      padding:12px 18px;
    }
    .browser-dots { color:#fa665c; font-size:17px; letter-spacing:4px; white-space:nowrap; }
    .browser-address {
      background:#f3f6fa; border:1px solid #edf0f5; border-radius:999px;
      color:#5c6980; flex:1; font-size:13px; padding:9px 18px; text-align:center;
    }
    .brand-row { align-items:center; display:flex; gap:14px; justify-content:center; }
    .brand-mark {
      align-items:center; background:linear-gradient(135deg,#3478ff,#7d55f6);
      border-radius:16px; box-shadow:0 9px 22px rgba(54,105,240,.25);
      color:#fff; display:flex; font-size:25px; height:52px; justify-content:center; width:52px;
    }
    .brand-name { color:#17233f; font-size:35px; font-weight:800; letter-spacing:-1.5px; }
    .hero-copy { color:#71809a; font-size:15px; margin:7px 0 20px; text-align:center; }
    .search-hint { color:#8490a5; font-size:12px; margin:10px 4px 0; text-align:center; }
    div[data-testid="stForm"] {
      background:#fff; border:1px solid #e1e7f0; border-radius:22px;
      box-shadow:0 12px 36px rgba(33,58,99,.09); margin:0 auto; max-width:900px;
      padding:12px 14px;
    }
    div[data-testid="stTextInput"] input {
      background:#f4f7fb; border:1px solid transparent; border-radius:14px;
      color:#1a2947; font-size:16px; height:52px; padding:0 18px;
    }
    div[data-testid="stTextInput"] input:focus {
      background:#fff; border-color:#8db2ff; box-shadow:0 0 0 3px #e7efff;
    }
    div[data-testid="stFormSubmitButton"] button, div[data-testid="stLinkButton"] a {
      border-radius:12px; font-weight:700; min-height:44px;
    }
    div[data-testid="stFormSubmitButton"] button {
      background:linear-gradient(135deg,#246bfe,#594ff5); border:0; color:white;
    }
    .section-kicker { color:#71809a; font-size:12px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; }
    .answer-card {
      background:linear-gradient(135deg,#eef4ff,#fff); border:1px solid #dce7fb;
      border-radius:20px; margin:16px 0 20px; padding:24px 26px;
    }
    .answer-label { color:#246bfe; font-size:13px; font-weight:800; margin-bottom:8px; }
    .video-panel {
      background:#111a2b; border-radius:20px; color:white; overflow:hidden;
      padding:18px;
    }
    .soft-note {
      background:#eef4ff; border:1px solid #dce7fb; border-radius:14px;
      color:#496385; font-size:13px; padding:13px 16px;
    }
    @media (max-width:700px) {
      .block-container { padding-left:1rem; padding-right:1rem; }
      .browser-bar { gap:8px; padding:8px 10px; }
      .browser-address { font-size:11px; padding:8px; }
      .brand-name { font-size:30px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="browser-bar">
      <span class="browser-dots">● ● ●</span>
      <span class="browser-address">🔒 &nbsp; knowix — pesquisa na web</span>
      <span style="color:#8290a7;font-size:18px">⋮</span>
    </div>
    <div class="brand-row">
      <div class="brand-mark">⌕</div><div class="brand-name">Knowix</div>
    </div>
      <p class="hero-copy">Uma pergunta. Uma resposta clara. Descubra páginas e vídeos sobre o assunto.</p>
    """,
    unsafe_allow_html=True,
)


def obter_chave_tavily():
    """Lê a chave guardada nas configurações privadas do Streamlit."""
    try:
        return st.secrets.get("TAVILY_API_KEY", "")
    except Exception:
        return os.environ.get("TAVILY_API_KEY", "")


def pesquisar_na_web(pergunta, chave):
    """Busca em páginas públicas indexadas na web aberta."""
    url = "https://api.tavily.com/search"
    cabecalhos = {
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    dados = {
        "query": (
            f"{pergunta}. Responda de forma direta e em português brasileiro."
        ),
        "topic": "general",
        "search_depth": "basic",
        "max_results": 8,
        "include_answer": "basic",
        "include_raw_content": False,
        "country": "brazil",
        "language": "pt",
        "filter_by_language": False,
        "safe_search": True,
    }
    resposta = requests.post(url, headers=cabecalhos, json=dados, timeout=35)
    if resposta.status_code == 401:
        raise ValueError("A chave de busca não foi aceita. Confira TAVILY_API_KEY nas configurações.")
    if resposta.status_code == 429:
        raise ValueError("O limite de buscas foi atingido. Tente novamente mais tarde.")
    resposta.raise_for_status()
    return resposta.json()


def pesquisar_wikipedia(assunto):
    """Usa a Wikipédia em português como modo alternativo sem chave Tavily."""
    url = "https://pt.wikipedia.org/w/api.php"
    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": assunto,
        "gsrlimit": 6,
        "prop": "extracts|info",
        "exintro": 1,
        "explaintext": 1,
        "inprop": "url",
        "format": "json",
        "formatversion": 2,
    }
    resposta = requests.get(
        url,
        params=parametros,
        headers={"User-Agent": "Knowix/2.0 (aplicativo de pesquisa)"},
        timeout=20,
    )
    resposta.raise_for_status()
    return resposta.json().get("query", {}).get("pages", [])


def escolher_pagina_principal(paginas, assunto):
    termos = [
        termo.casefold().strip("?!.,:;")
        for termo in assunto.split()
        if len(termo.strip("?!.,:;")) >= 3
    ]
    if not termos:
        return paginas[0]

    def pontuacao(pagina):
        titulo = pagina.get("title", "").casefold()
        correspondencias = sum(1 for termo in set(termos) if termo in titulo)
        palavras_extras = max(0, len(titulo.split()) - correspondencias)
        return correspondencias - 2 * palavras_extras

    return max(paginas, key=pontuacao)


def pesquisar_video_youtube(assunto):
    """Escolhe o vídeo mais visto entre os primeiros resultados relevantes."""
    opcoes = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "ignoreerrors": True,
        "noplaylist": True,
        "socket_timeout": 12,
    }
    with yt_dlp.YoutubeDL(opcoes) as youtube:
        resultado = youtube.extract_info(f"ytsearch8:{assunto}", download=False)
    videos = [
        video
        for video in (resultado or {}).get("entries", [])
        if video and video.get("id")
    ]
    if not videos:
        return None
    return max(videos, key=lambda video: video.get("view_count") or 0)


def encurtar(texto, limite):
    texto = " ".join((texto or "").split())
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def resumir_resposta(texto):
    texto = " ".join((texto or "").split())
    frases = re.split(r"(?<=[.!?])\s+", texto)
    return encurtar(" ".join(frases[:3]), 620)


with st.form("formulario_pesquisa", clear_on_submit=False):
    col_busca, col_botao = st.columns([8, 1.35], vertical_alignment="bottom")
    with col_busca:
        pergunta = st.text_input(
            "Pesquisa",
            label_visibility="collapsed",
            placeholder="🔎  Pesquise qualquer assunto, dúvida ou pergunta...",
        )
    with col_botao:
        buscar = st.form_submit_button("Pesquisar", use_container_width=True)

st.markdown(
    '<p class="search-hint">Pesquise temas, perguntas, notícias, ciência, tecnologia e muito mais.</p>',
    unsafe_allow_html=True,
)

if buscar:
    assunto = pergunta.strip()
    if not assunto:
        st.warning("Digite um assunto para começar a pesquisa.")
    else:
        chave_tavily = obter_chave_tavily()
        resposta_direta = ""
        fontes = []
        modo_web = bool(chave_tavily)

        if chave_tavily:
            with st.spinner("Pesquisando na web aberta..."):
                try:
                    resultado_web = pesquisar_na_web(assunto, chave_tavily)
                    resposta_direta = (resultado_web.get("answer") or "").strip()
                    for item in resultado_web.get("results", []):
                        url_fonte = item.get("url", "")
                        if urlparse(url_fonte).scheme in {"http", "https"}:
                            fontes.append(
                                {
                                    "title": item.get("title") or "Abrir resultado",
                                    "url": url_fonte,
                                    "content": item.get("content", ""),
                                    "domain": urlparse(url_fonte).netloc.removeprefix("www."),
                                }
                            )
                except (ValueError, requests.exceptions.RequestException) as erro:
                    st.warning(f"{erro} Ainda vou tentar encontrar um vídeo e sugestões.")
        else:
            with st.spinner("Pesquisando na Wikipédia em português..."):
                try:
                    paginas = pesquisar_wikipedia(assunto)
                    if paginas:
                        pagina = escolher_pagina_principal(paginas, assunto)
                        resposta_direta = (pagina.get("extract") or "").strip()
                        fontes = [
                            {
                                "title": item.get("title", "Abrir resultado"),
                                "url": item.get("fullurl", ""),
                                "content": item.get("extract", ""),
                                "domain": "pt.wikipedia.org",
                            }
                            for item in paginas
                            if item.get("fullurl")
                        ]
                except requests.exceptions.RequestException:
                    st.warning("A pesquisa de fontes está indisponível no momento.")
            st.info(
                "A pesquisa geral ainda não está configurada. No momento, mostro resultados da "
                "Wikipédia em português."
            )

        assunto_seguro = escape(assunto)
        st.markdown(
            f'<div class="section-kicker">Resultados para “{assunto_seguro}”</div>',
            unsafe_allow_html=True,
        )

        col_resposta, col_video = st.columns([1.1, 0.9], gap="large")
        with col_resposta:
            with st.container(border=True):
                st.markdown('<div class="answer-label">✦ RESPOSTA RÁPIDA</div>', unsafe_allow_html=True)
                if resposta_direta:
                    st.markdown(resumir_resposta(resposta_direta))
                    st.caption("Resumo automático da busca. Abra as páginas abaixo para conferir os detalhes.")
                else:
                    st.write("Não consegui montar uma resposta direta agora. Veja os sites encontrados abaixo.")

        with col_video:
            with st.container(border=True):
                st.markdown('<div class="section-kicker">▶ VÍDEO EM DESTAQUE</div>', unsafe_allow_html=True)
                try:
                    video = pesquisar_video_youtube(f"{assunto} em português")
                    if video:
                        video_id = video["id"]
                        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                            st.markdown(f"**{encurtar(video.get('title', 'Vídeo relacionado'), 90)}**")
                            canal = video.get("channel") or video.get("uploader")
                            if canal:
                                visualizacoes = video.get("view_count")
                                detalhes_video = [f"Canal: {canal}"]
                                if visualizacoes is not None:
                                    detalhes_video.append(
                                        f"Visualizações: {visualizacoes:,}".replace(",", ".")
                                    )
                                st.caption(" • ".join(detalhes_video))
                            st.iframe(
                                f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&playsinline=1",
                                height=300,
                            )
                            st.link_button(
                                "Abrir vídeo no YouTube",
                                f"https://www.youtube.com/watch?v={video_id}",
                                use_container_width=True,
                            )
                        else:
                            st.info("Não consegui abrir a prévia deste vídeo. Veja os resultados no YouTube.")
                    else:
                        st.info("Ainda não encontrei uma prévia para este assunto.")
                except Exception:
                    st.info("A prévia está indisponível agora. Você ainda pode buscar vídeos no YouTube.")
                st.link_button(
                    "Ver mais vídeos",
                    f"https://www.youtube.com/results?search_query={quote_plus(assunto)}",
                    use_container_width=True,
                )

        st.markdown("### 🌐 Sites encontrados")
        if fontes:
            colunas_sites = st.columns(2, gap="medium")
            for indice, fonte in enumerate(fontes[:8]):
                with colunas_sites[indice % 2]:
                    with st.container(border=True):
                        if fonte.get("domain"):
                            st.caption(f"●  {fonte['domain']}")
                        st.link_button(
                            encurtar(fonte.get("title", "Abrir resultado"), 76),
                            fonte["url"],
                            use_container_width=True,
                        )
                        trecho = encurtar(fonte.get("content", ""), 210)
                        if trecho:
                            st.write(trecho)
        else:
            st.info("Não encontrei páginas para esta pergunta.")

        tema = re.sub(
            r"^(o que é|o que e|como funciona|quem foi|quem é|quem e|qual é|qual e|benefícios de|beneficios de)\s+",
            "",
            assunto,
            flags=re.IGNORECASE,
        ).strip(" ?!")
        sugestoes = [
            f"Principais fatos sobre {tema}",
            f"Aplicações de {tema}",
            f"Vantagens e desvantagens de {tema}",
            f"História e evolução de {tema}",
            f"Novidades sobre {tema}",
            f"Vídeos explicativos sobre {tema}",
        ]
        st.markdown("### ✨ Continue explorando")
        st.caption("Sugestões de buscas relacionadas")
        colunas_sugestoes = st.columns(3, gap="small")
        for indice, sugestao in enumerate(sugestoes):
            with colunas_sugestoes[indice % 3]:
                st.link_button(
                    sugestao,
                    f"https://www.google.com/search?q={quote_plus(sugestao)}",
                    use_container_width=True,
                )

st.markdown(
    '<div class="soft-note">O Knowix pesquisa páginas públicas indexadas na web. Compare as fontes antes de usar informações importantes.</div>',
    unsafe_allow_html=True,
)
