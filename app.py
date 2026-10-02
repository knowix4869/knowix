import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import quote_plus, urlparse

import requests
import streamlit as st
import yt_dlp


st.set_page_config(
    page_title="Knowix",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "tema_visual" not in st.session_state:
    st.session_state.tema_visual = "Claro"
if "idioma_visual" not in st.session_state:
    st.session_state.idioma_visual = "Português"
if "cache_traducoes" not in st.session_state:
    st.session_state.cache_traducoes = {}

tema_escuro = st.session_state.tema_visual == "Escuro"
cor_fundo = "#0d1422" if tema_escuro else "#f4f7fc"
cor_cartao = "#172235" if tema_escuro else "#ffffff"
cor_texto = "#eef3ff" if tema_escuro else "#14213d"
cor_secundaria = "#adbad0" if tema_escuro else "#69758c"
cor_borda = "#33425a" if tema_escuro else "#e2e8f2"
cor_campo = "#202d43" if tema_escuro else "#f4f7fb"
cor_azul = "#8db4ff" if tema_escuro else "#246bfe"
cor_texto_botao = "#eef3ff" if tema_escuro else "#14213d"

estilo = (
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
    :root { --ink:__COR_TEXTO__; --muted:__COR_SECUNDARIA__; --blue:__COR_AZUL__; --line:__COR_BORDA__; }
    [data-testid="stAppViewContainer"] { background:__COR_FUNDO__; color:var(--ink); }
    [data-testid="stMain"] { color:var(--ink); }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
      color:var(--muted) !important; opacity:1 !important;
    }
    [data-testid="stMarkdownContainer"] p { color:var(--ink); }
    a { color:var(--blue); }
    [data-testid="stHeader"] { background:transparent; }
    footer, [data-testid="stFooter"], [data-testid="stDecoration"],
    [data-testid="stToolbar"], [data-testid="stAppDeployButton"],
    .viewerBadge_container__1QSob, #MainMenu { display:none !important; }
    .block-container { max-width:1180px; padding-top:1rem; padding-bottom:1.25rem; }
    html, body, [class*="css"] { font-family:'DM Sans',Arial,sans-serif; }
    [data-testid="stTabs"] [role="tablist"] { gap:.35rem; overflow-x:auto; }
    [data-testid="stTabs"] button[role="tab"] { white-space:nowrap; }
    [data-testid="stSelectbox"] [role="combobox"] {
      background:__COR_CARTAO__; border:1px solid __COR_BORDA__; border-radius:13px; min-height:48px;
    }
    [data-testid="stSelectbox"] input[role="combobox"] {
      color:__COR_TEXTO__ !important; -webkit-text-fill-color:__COR_TEXTO__ !important; opacity:1 !important;
    }
    [data-testid="stSelectbox"] [role="combobox"] * { color:__COR_TEXTO__ !important; font-size:15px; }
    [data-testid="stSelectbox"] [role="listbox"],
    [data-testid="stSelectbox"] [role="option"], [role="listbox"] {
      background:__COR_CARTAO__ !important; color:__COR_TEXTO__ !important;
    }
    [data-testid="stSelectbox"] [role="option"] *,
    [role="listbox"] * { color:__COR_TEXTO__ !important; }
    [data-testid="stSelectbox"] [role="option"]:hover,
    [role="listbox"] [role="option"]:hover {
      background:__COR_CAMPO__ !important;
    }
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] label * { color:__COR_TEXTO__ !important; }
    div[data-testid="stButton"] button {
      background:__COR_CARTAO__; border:1px solid __COR_BORDA__; border-radius:12px;
      color:__COR_TEXTO_BOTAO__ !important; font-size:15px; font-weight:650;
      min-height:48px; white-space:normal;
    }
    div[data-testid="stButton"] button:hover { border-color:__COR_AZUL__; color:__COR_AZUL__ !important; }
    .brand-row { align-items:center; display:flex; gap:14px; justify-content:center; }
    .brand-mark {
      align-items:center; background:linear-gradient(135deg,#3478ff,#7d55f6);
      border-radius:16px; box-shadow:0 9px 22px rgba(54,105,240,.25);
      color:#fff; display:flex; font-size:25px; height:52px; justify-content:center; width:52px;
    }
    .brand-name { color:var(--ink); font-size:35px; font-weight:800; letter-spacing:-1.5px; }
    .hero-copy { color:var(--muted); font-size:15px; margin:7px 0 20px; text-align:center; }
    .search-hint { color:var(--muted); font-size:12px; margin:10px 4px 0; text-align:center; }
    div[data-testid="stForm"] {
      background:__COR_CARTAO__; border:1px solid __COR_BORDA__; border-radius:22px;
      box-shadow:0 12px 36px rgba(33,58,99,.09); margin:0 auto; max-width:900px;
      padding:12px 14px;
    }
    div[data-testid="stTextInput"] input {
      background:__COR_CAMPO__; border:1px solid transparent; border-radius:14px;
      color:__COR_TEXTO__; font-size:16px; height:52px; padding:0 18px;
    }
    div[data-testid="stTextInput"] input::placeholder { color:__COR_SECUNDARIA__; opacity:1; }
    div[data-testid="stTextInput"] input:focus {
      background:__COR_CARTAO__; border-color:__COR_AZUL__; box-shadow:0 0 0 3px #8db2ff33;
    }
    div[data-testid="stFormSubmitButton"] button, div[data-testid="stLinkButton"] a {
      border-radius:12px; font-weight:700; min-height:44px;
    }
    div[data-testid="stFormSubmitButton"] button {
      background:linear-gradient(135deg,#246bfe,#594ff5); border:0; color:white;
    }
    .section-kicker { color:var(--muted); font-size:12px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; }
    .answer-card {
      background:linear-gradient(135deg,__COR_CAMPO__,__COR_CARTAO__); border:1px solid __COR_BORDA__;
      border-radius:20px; margin:16px 0 20px; padding:24px 26px;
    }
    .answer-label { color:var(--blue); font-size:13px; font-weight:800; margin-bottom:8px; }
    .video-panel {
      background:#111a2b; border-radius:20px; color:white; overflow:hidden;
      padding:18px;
    }
    .soft-note {
      background:__COR_CAMPO__; border:1px solid __COR_BORDA__; border-radius:14px;
      color:var(--muted); font-size:13px; padding:13px 16px;
    }
    @media (max-width:700px) {
      .block-container { padding:.65rem .8rem 1rem; }
      .brand-row { gap:10px; }
      .brand-mark { width:44px; height:44px; }
      .brand-name { font-size:28px; }
      .hero-copy { font-size:14px; margin-bottom:14px; }
      .search-hint { color:var(--muted); font-size:14px; line-height:1.5; }
      [data-testid="stSelectbox"] [role="combobox"] { min-height:52px; }
      [data-testid="stSelectbox"] [role="combobox"] * { font-size:16px; }
      div[data-testid="stButton"] button { font-size:16px; min-height:52px; line-height:1.35; }
      div[data-testid="stForm"] { border-radius:16px; padding:10px; }
    }
    </style>
    """
)
for marcador, valor in {
    "__COR_FUNDO__": cor_fundo,
    "__COR_CARTAO__": cor_cartao,
    "__COR_TEXTO__": cor_texto,
    "__COR_SECUNDARIA__": cor_secundaria,
    "__COR_BORDA__": cor_borda,
    "__COR_CAMPO__": cor_campo,
    "__COR_AZUL__": cor_azul,
    "__COR_TEXTO_BOTAO__": cor_texto_botao,
}.items():
    estilo = estilo.replace(marcador, valor)
st.markdown(estilo, unsafe_allow_html=True)

TRADUCOES_UI = {
    "Português": {
        "subtitle": "Uma pergunta. Uma resposta clara. Descubra páginas e vídeos sobre o assunto.",
        "section_Pesquisar": "Pesquisar", "section_Nova aba": "Nova aba",
        "section_Histórico": "Histórico", "section_Configurações": "Configurações",
        "section_Sobre o app": "Sobre o app", "section_Sugestões": "Sugestões",
        "search_placeholder": "🔎  Pesquise qualquer assunto, dúvida ou pergunta...",
        "search_button": "Pesquisar", "new_search_title": "Abra uma nova pesquisa",
        "new_search_caption": "Inicie outra busca sem apagar o histórico desta sessão.",
        "new_search_label": "O que quer pesquisar nesta nova aba?",
        "new_search_placeholder": "Digite outra pergunta ou assunto...",
        "new_search_button": "Pesquisar nesta aba", "search_hint": "Pesquise temas, perguntas, notícias, ciência, tecnologia e muito mais.",
        "history_title": "Pesquisas recentes", "history_empty": "Suas pesquisas aparecerão aqui enquanto esta sessão estiver aberta.",
        "settings_title": "Configurações", "appearance": "Aparência", "theme_label": "Tema do Knowix",
        "theme_caption": "A aparência muda imediatamente e fica ativa enquanto esta sessão estiver aberta.",
        "privacy": "Privacidade", "history_privacy": "O histórico fica nesta sessão e não é compartilhado com outras pessoas.",
        "clear_history": "Apagar histórico desta sessão", "history_cleared": "Histórico apagado.",
        "about_title": "Sobre o Knowix", "about_text": "O Knowix ajuda a encontrar respostas curtas, fontes para conferir e vídeos relacionados.",
        "beta": "VERSÃO BETA — o app está em desenvolvimento. Algumas funções e resultados podem mudar.",
        "suggestions_title": "Sugestões para o Knowix", "suggestions_text": "Conte sua ideia, problema ou melhoria. Ao clicar no link, o Gmail abrirá uma mensagem para a equipe.",
        "suggestion_label": "Sua sugestão", "suggestion_placeholder": "Escreva sua ideia aqui...",
        "prepare_email": "Preparar sugestão no Gmail", "write_suggestion": "Escreva sua sugestão antes de continuar.",
        "open_email": "Abrir o Gmail para enviar", "email_note": "Por segurança, o Knowix não envia e-mails sozinho: confira a mensagem no Gmail e toque em Enviar.",
        "searching": "Pesquisando páginas e vídeos ao mesmo tempo...", "cached": "Resultado recente carregado da sua sessão.",
        "empty_search": "Digite um assunto para começar a pesquisa.", "results_for": "RESULTADOS PARA",
        "quick_answer": "✦ RESPOSTA RÁPIDA", "answer_caption": "Resumo automático da busca. Abra as páginas abaixo para conferir os detalhes.",
        "no_answer": "Não consegui montar uma resposta direta agora. Veja os sites encontrados abaixo.",
        "featured_video": "▶ VÍDEO EM DESTAQUE", "related_video": "Vídeo relacionado", "no_video": "Não encontrei uma prévia de vídeo para este assunto.",
        "video_caption": "A prévia é reproduzida dentro do Knowix. Os controles do YouTube podem oferecer links externos.",
        "more_videos": "Buscar mais vídeos no Knowix", "sites_found": "🌐 Sites encontrados", "read_source": "Ler fonte no Knowix",
        "no_sources": "Não encontrei páginas para esta pergunta.", "keep_exploring": "✨ Continue explorando",
        "suggestions_inside": "Sugestões de buscas dentro do Knowix", "source_back": "← Voltar aos resultados",
        "source_summary": "Resumo disponível no Knowix", "no_excerpt": "Esta fonte não forneceu um trecho de texto para prévia.",
        "page_preview": "Prévia da página", "preview_note": "Alguns sites bloqueiam a exibição incorporada. Se a página não carregar, o resumo acima continua disponível.",
        "open_source": "Abrir esta fonte fora do Knowix (opcional)", "source_page": "Fonte da web",
        "translation_wait": "Traduzindo a resposta e as fontes...", "translation_error": "O serviço de tradução não respondeu desta vez; parte do conteúdo pode continuar em português.",
        "channel": "Canal", "views": "Visualizações",
        "footer_note": "O Knowix pesquisa páginas públicas indexadas na web. Compare as fontes antes de usar informações importantes.",
    },
    "English": {
        "subtitle": "One question. One clear answer. Discover pages and videos about the topic.",
        "section_Pesquisar": "Search", "section_Nova aba": "New tab", "section_Histórico": "History",
        "section_Configurações": "Settings", "section_Sobre o app": "About the app", "section_Sugestões": "Suggestions",
        "search_placeholder": "🔎  Search any topic, question, or idea...", "search_button": "Search",
        "new_search_title": "Start a new search", "new_search_caption": "Start another search without clearing this session's history.",
        "new_search_label": "What would you like to search in this new tab?", "new_search_placeholder": "Enter another question or topic...",
        "new_search_button": "Search in this tab", "search_hint": "Explore topics, questions, news, science, technology, and more.",
        "history_title": "Recent searches", "history_empty": "Your searches will appear here while this session is open.",
        "settings_title": "Settings", "appearance": "Appearance", "theme_label": "Knowix theme",
        "theme_caption": "The appearance changes immediately and stays active while this session is open.",
        "privacy": "Privacy", "history_privacy": "History stays in this session and is not shared with other people.",
        "clear_history": "Clear this session's history", "history_cleared": "History cleared.",
        "about_title": "About Knowix", "about_text": "Knowix helps you find concise answers, sources to check, and related videos.",
        "beta": "BETA VERSION — the app is under development. Some features and results may change.",
        "suggestions_title": "Suggestions for Knowix", "suggestions_text": "Share an idea, issue, or improvement. Gmail will open a message to the team.",
        "suggestion_label": "Your suggestion", "suggestion_placeholder": "Write your idea here...", "prepare_email": "Prepare suggestion in Gmail",
        "write_suggestion": "Write your suggestion before continuing.", "open_email": "Open Gmail to send",
        "email_note": "For your safety, Knowix does not send emails automatically. Review the message in Gmail and press Send.",
        "searching": "Searching pages and videos at the same time...", "cached": "Recent result loaded from your session.",
        "empty_search": "Enter a topic to start searching.", "results_for": "RESULTS FOR", "quick_answer": "✦ QUICK ANSWER",
        "answer_caption": "Automatic search summary. Open the pages below to check the details.",
        "no_answer": "I couldn't create a direct answer right now. See the websites found below.", "featured_video": "▶ FEATURED VIDEO",
        "related_video": "Related video", "no_video": "I couldn't find a video preview for this topic.",
        "video_caption": "The preview plays inside Knowix. YouTube controls may offer external links.",
        "more_videos": "Find more videos in Knowix", "sites_found": "🌐 Websites found", "read_source": "Read source in Knowix",
        "no_sources": "I couldn't find pages for this question.", "keep_exploring": "✨ Keep exploring", "suggestions_inside": "Search suggestions inside Knowix",
        "source_back": "← Back to results", "source_summary": "Summary available in Knowix", "no_excerpt": "This source did not provide a text excerpt for preview.",
        "page_preview": "Page preview", "preview_note": "Some websites block embedded viewing. If the page does not load, the summary above is still available.",
        "open_source": "Open this source outside Knowix (optional)", "source_page": "Web source",
        "translation_wait": "Translating the answer and sources...", "translation_error": "The translation service did not respond this time; some content may remain in Portuguese.",
        "channel": "Channel", "views": "Views",
        "footer_note": "Knowix searches public pages indexed on the web. Compare sources before using important information.",
    },
    "Español": {
        "subtitle": "Una pregunta. Una respuesta clara. Descubre páginas y videos sobre el tema.",
        "section_Pesquisar": "Buscar", "section_Nova aba": "Nueva pestaña", "section_Histórico": "Historial",
        "section_Configurações": "Configuración", "section_Sobre o app": "Acerca de la app", "section_Sugestões": "Sugerencias",
        "search_placeholder": "🔎  Busca cualquier tema, duda o pregunta...", "search_button": "Buscar",
        "new_search_title": "Iniciar una nueva búsqueda", "new_search_caption": "Inicia otra búsqueda sin borrar el historial de esta sesión.",
        "new_search_label": "¿Qué quieres buscar en esta nueva pestaña?", "new_search_placeholder": "Escribe otra pregunta o tema...",
        "new_search_button": "Buscar en esta pestaña", "search_hint": "Explora temas, preguntas, noticias, ciencia, tecnología y mucho más.",
        "history_title": "Búsquedas recientes", "history_empty": "Tus búsquedas aparecerán aquí mientras esta sesión esté abierta.",
        "settings_title": "Configuración", "appearance": "Apariencia", "theme_label": "Tema de Knowix",
        "theme_caption": "La apariencia cambia inmediatamente y permanece activa mientras esta sesión esté abierta.",
        "privacy": "Privacidad", "history_privacy": "El historial permanece en esta sesión y no se comparte con otras personas.",
        "clear_history": "Borrar el historial de esta sesión", "history_cleared": "Historial borrado.",
        "about_title": "Acerca de Knowix", "about_text": "Knowix te ayuda a encontrar respuestas breves, fuentes para consultar y videos relacionados.",
        "beta": "VERSIÓN BETA — la app está en desarrollo. Algunas funciones y resultados pueden cambiar.",
        "suggestions_title": "Sugerencias para Knowix", "suggestions_text": "Cuéntanos tu idea, problema o mejora. Gmail abrirá un mensaje para el equipo.",
        "suggestion_label": "Tu sugerencia", "suggestion_placeholder": "Escribe tu idea aquí...", "prepare_email": "Preparar sugerencia en Gmail",
        "write_suggestion": "Escribe tu sugerencia antes de continuar.", "open_email": "Abrir Gmail para enviar",
        "email_note": "Por seguridad, Knowix no envía correos automáticamente. Revisa el mensaje en Gmail y pulsa Enviar.",
        "searching": "Buscando páginas y videos al mismo tiempo...", "cached": "Resultado reciente cargado desde tu sesión.",
        "empty_search": "Escribe un tema para comenzar la búsqueda.", "results_for": "RESULTADOS PARA", "quick_answer": "✦ RESPUESTA RÁPIDA",
        "answer_caption": "Resumen automático de la búsqueda. Abre las páginas de abajo para revisar los detalles.",
        "no_answer": "No pude preparar una respuesta directa ahora. Consulta los sitios encontrados abajo.", "featured_video": "▶ VIDEO DESTACADO",
        "related_video": "Video relacionado", "no_video": "No encontré una vista previa de video para este tema.",
        "video_caption": "La vista previa se reproduce dentro de Knowix. Los controles de YouTube pueden ofrecer enlaces externos.",
        "more_videos": "Buscar más videos en Knowix", "sites_found": "🌐 Sitios encontrados", "read_source": "Leer fuente en Knowix",
        "no_sources": "No encontré páginas para esta pregunta.", "keep_exploring": "✨ Sigue explorando", "suggestions_inside": "Búsquedas sugeridas dentro de Knowix",
        "source_back": "← Volver a los resultados", "source_summary": "Resumen disponible en Knowix", "no_excerpt": "Esta fuente no proporcionó un fragmento de texto para la vista previa.",
        "page_preview": "Vista previa de la página", "preview_note": "Algunos sitios bloquean la visualización integrada. Si la página no carga, el resumen de arriba seguirá disponible.",
        "open_source": "Abrir esta fuente fuera de Knowix (opcional)", "source_page": "Fuente web",
        "translation_wait": "Traduciendo la respuesta y las fuentes...", "translation_error": "El servicio de traducción no respondió esta vez; parte del contenido puede seguir en portugués.",
        "channel": "Canal", "views": "Visualizaciones",
        "footer_note": "Knowix busca páginas públicas indexadas en la web. Compara las fuentes antes de usar información importante.",
    },
}


def texto_ui(chave):
    idioma = st.session_state.idioma_visual
    return TRADUCOES_UI[idioma].get(chave, TRADUCOES_UI["Português"].get(chave, chave))


def sincronizar_secao_selecionada():
    """Mantém a navegação interna correta para o rótulo do idioma atual."""
    idioma = st.session_state.idioma_visual
    opcoes = {
        TRADUCOES_UI[idioma].get(f"section_{secao}", secao): secao
        for secao in ["Pesquisar", "Nova aba", "Histórico", "Configurações", "Sobre o app", "Sugestões"]
    }
    selecionada = st.session_state.get("secao_display")
    if selecionada in opcoes:
        st.session_state.secao_canonica = opcoes[selecionada]


def traduzir_textos(textos):
    """Traduz textos de resultados e conserva traduções durante a sessão."""
    destino = {"Português": None, "English": "en", "Español": "es"}[st.session_state.idioma_visual]
    if not destino:
        return list(textos), False

    cache = st.session_state.cache_traducoes
    originais = list(textos)
    pendentes = list(dict.fromkeys(
        texto for texto in originais
        if texto and (destino, texto) not in cache
    ))
    falhou = False

    def traduzir_um(texto):
        resposta = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": destino, "dt": "t", "q": texto},
            headers={"User-Agent": "Knowix/2.0"},
            timeout=12,
        )
        resposta.raise_for_status()
        partes = resposta.json()[0]
        traducao = "".join(parte[0] for parte in partes if parte and parte[0])
        if not traducao:
            raise ValueError("A tradução veio vazia")
        return traducao

    if pendentes:
        with ThreadPoolExecutor(max_workers=min(6, len(pendentes))) as executor:
            futuros = {texto: executor.submit(traduzir_um, texto) for texto in pendentes}
            for texto, futuro in futuros.items():
                try:
                    cache[(destino, texto)] = futuro.result()
                except Exception:
                    cache[(destino, texto)] = texto
                    falhou = True
        if len(cache) > 500:
            for chave_antiga in list(cache)[:len(cache) - 500]:
                cache.pop(chave_antiga, None)

    return [cache.get((destino, texto), texto) if texto else texto for texto in originais], falhou


def traduzir_resultado(dados):
    """Aplica a tradução escolhida à resposta, aos trechos e aos títulos."""
    resultado = {
        **dados,
        "video": dict(dados["video"]) if dados.get("video") else None,
        "fontes": [dict(fonte) for fonte in dados.get("fontes", [])],
        "avisos": list(dados.get("avisos", [])),
    }
    campos = [resultado.get("resposta", "")]
    if resultado["video"]:
        campos.append(resultado["video"].get("title", ""))
    for fonte in resultado["fontes"]:
        campos.extend([fonte.get("title", ""), fonte.get("content", "")])
    campos.extend(resultado["avisos"])
    traducao, falhou = traduzir_textos(campos)

    indice = 0
    resultado["resposta"] = traducao[indice]
    indice += 1
    if resultado["video"]:
        resultado["video"]["title"] = traducao[indice]
        indice += 1
    for fonte in resultado["fontes"]:
        fonte["title"], fonte["content"] = traducao[indice:indice + 2]
        indice += 2
    resultado["avisos"] = traducao[indice:]
    return resultado, falhou

if "historico_pesquisas" not in st.session_state:
    st.session_state.historico_pesquisas = []
if "cache_buscas" not in st.session_state:
    st.session_state.cache_buscas = {}
if "resultado_atual" not in st.session_state:
    st.session_state.resultado_atual = None
if "fonte_aberta" not in st.session_state:
    st.session_state.fonte_aberta = None
if "busca_pendente" not in st.session_state:
    st.session_state.busca_pendente = None

col_espaco_idioma, col_idioma = st.columns([7, 2])
with col_idioma:
    st.selectbox(
        "🌐 Idioma" if st.session_state.idioma_visual != "English" else "🌐 Language",
        ["Português", "English", "Español"],
        key="idioma_visual",
    )

st.markdown(
    f"""
    <div class="brand-row">
      <div class="brand-mark">⌕</div><div class="brand-name">Knowix</div>
    </div>
      <p class="hero-copy">{escape(texto_ui("subtitle"))}</p>
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


def preparar_busca_interna(assunto):
    """Agenda uma busca sugerida sem sair do Knowix."""
    st.session_state.busca_pendente = assunto
    st.session_state.pergunta_principal = assunto
    st.session_state.fonte_aberta = None
    st.session_state.secao_canonica = "Pesquisar"
    st.session_state.secao_display = texto_ui("section_Pesquisar")


def abrir_fonte_no_knowix(fonte):
    st.session_state.fonte_aberta = fonte


def buscar_resultados(assunto, chave_tavily):
    """Busca web e vídeo em paralelo e mantém cache privado da sessão por 10 minutos."""
    chave_cache = assunto.strip().casefold()
    cache = st.session_state.cache_buscas
    agora = time.monotonic()
    item_cache = cache.get(chave_cache)
    if item_cache and agora - item_cache["instante"] < 600:
        return item_cache["dados"], True
    if item_cache:
        cache.pop(chave_cache, None)

    resposta_direta = ""
    fontes = []
    video = None
    avisos = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        if chave_tavily:
            busca_web = executor.submit(pesquisar_na_web, assunto, chave_tavily)
        else:
            busca_web = executor.submit(pesquisar_wikipedia, assunto)
        busca_video = executor.submit(pesquisar_video_youtube, f"{assunto} em português")

        try:
            dados_web = busca_web.result()
            if chave_tavily:
                resposta_direta = (dados_web.get("answer") or "").strip()
                for item in dados_web.get("results", []):
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
            elif dados_web:
                pagina = escolher_pagina_principal(dados_web, assunto)
                resposta_direta = (pagina.get("extract") or "").strip()
                fontes = [
                    {
                        "title": item.get("title", "Abrir resultado"),
                        "url": item.get("fullurl", ""),
                        "content": item.get("extract", ""),
                        "domain": "pt.wikipedia.org",
                    }
                    for item in dados_web
                    if item.get("fullurl")
                ]
                avisos.append(
                    "A pesquisa geral ainda não está configurada. No momento, mostro resultados da Wikipédia em português."
                )
        except ValueError as erro:
            avisos.append(str(erro))
        except requests.exceptions.RequestException:
            avisos.append("A pesquisa de fontes está indisponível no momento.")

        try:
            video_encontrado = busca_video.result()
            if video_encontrado:
                video = {
                    "id": video_encontrado.get("id"),
                    "title": video_encontrado.get("title", "Vídeo relacionado"),
                    "channel": video_encontrado.get("channel") or video_encontrado.get("uploader"),
                    "view_count": video_encontrado.get("view_count"),
                }
        except Exception:
            avisos.append("Não consegui buscar um vídeo agora; as fontes continuam disponíveis.")

    dados = {
        "assunto": assunto,
        "resposta": resposta_direta,
        "fontes": fontes,
        "video": video,
        "avisos": avisos,
    }
    cache[chave_cache] = {"instante": time.monotonic(), "dados": dados}
    if len(cache) > 20:
        cache.pop(next(iter(cache)))
    return dados, False


SECOES_APP = ["Pesquisar", "Nova aba", "Histórico", "Configurações", "Sobre o app", "Sugestões"]
nomes_secoes = {
    secao: texto_ui(f"section_{secao}")
    for secao in SECOES_APP
}
if "secao_canonica" not in st.session_state:
    st.session_state.secao_canonica = "Pesquisar"
if "secao_display" not in st.session_state or st.session_state.secao_canonica not in nomes_secoes:
    st.session_state.secao_display = nomes_secoes[st.session_state.secao_canonica]
elif st.session_state.secao_display != nomes_secoes[st.session_state.secao_canonica]:
    st.session_state.secao_display = nomes_secoes[st.session_state.secao_canonica]
opcoes_secoes = {nome: secao for secao, nome in nomes_secoes.items()}
rotulo_secoes = "Escolha uma seção do Knowix" if st.session_state.idioma_visual == "Português" else "Choose a Knowix section" if st.session_state.idioma_visual == "English" else "Elige una sección de Knowix"
secao_selecionada = st.selectbox(
    rotulo_secoes,
    list(opcoes_secoes),
    key="secao_display",
    on_change=sincronizar_secao_selecionada,
    label_visibility="collapsed",
)
secao_app = opcoes_secoes[secao_selecionada]
st.session_state.secao_canonica = secao_app

buscar = False
pergunta = ""
buscar_nova = False
pergunta_nova = ""
if secao_app == "Pesquisar":
    with st.form("formulario_pesquisa", clear_on_submit=False):
        col_busca, col_botao = st.columns([8, 1.35], vertical_alignment="bottom")
        with col_busca:
            pergunta = st.text_input(
                "Search" if st.session_state.idioma_visual == "English" else "Buscar" if st.session_state.idioma_visual == "Español" else "Pesquisa",
                label_visibility="collapsed",
                placeholder=texto_ui("search_placeholder"),
                key="pergunta_principal",
            )
        with col_botao:
            buscar = st.form_submit_button(texto_ui("search_button"), use_container_width=True)

elif secao_app == "Nova aba":
    st.markdown(f"### {texto_ui('new_search_title')}")
    st.caption(texto_ui("new_search_caption"))
    with st.form("formulario_nova_aba", clear_on_submit=False):
        pergunta_nova = st.text_input(
            "What would you like to search?" if st.session_state.idioma_visual == "English" else "¿Qué quieres buscar?" if st.session_state.idioma_visual == "Español" else texto_ui("new_search_label"),
            placeholder=texto_ui("new_search_placeholder"),
            key="pergunta_nova_aba",
        )
        buscar_nova = st.form_submit_button(texto_ui("new_search_button"), use_container_width=True)
    if buscar_nova:
        pergunta = pergunta_nova
        buscar = True

busca_pendente = st.session_state.busca_pendente
if busca_pendente:
    pergunta = busca_pendente
    buscar = True
    st.session_state.busca_pendente = None

if buscar and pergunta.strip():
    termo_historico = pergunta.strip()
    historico_atualizado = [termo_historico] + [
        item for item in st.session_state.historico_pesquisas
        if item.casefold() != termo_historico.casefold()
    ]
    st.session_state.historico_pesquisas = historico_atualizado[:20]

elif secao_app == "Histórico":
    st.markdown(f"### {texto_ui('history_title')}")
    if st.session_state.historico_pesquisas:
        for indice, item in enumerate(st.session_state.historico_pesquisas):
            st.button(
                f"{indice + 1}. {item}",
                key=f"historico_{indice}",
                on_click=preparar_busca_interna,
                args=(item,),
                use_container_width=True,
            )
    else:
        st.caption(texto_ui("history_empty"))

elif secao_app == "Configurações":
    st.markdown(f"### {texto_ui('settings_title')}")
    st.markdown(f"#### {texto_ui('appearance')}")
    st.radio(
        texto_ui("theme_label"),
        ["Claro", "Escuro"],
        format_func=lambda tema: tema if st.session_state.idioma_visual == "Português" else {"Claro": "Light", "Escuro": "Dark"}.get(tema, tema) if st.session_state.idioma_visual == "English" else {"Claro": "Claro", "Escuro": "Oscuro"}.get(tema, tema),
        key="tema_visual",
        horizontal=True,
    )
    st.caption(texto_ui("theme_caption"))
    st.markdown(f"#### {texto_ui('privacy')}")
    st.caption(texto_ui("history_privacy"))
    if st.button(texto_ui("clear_history"), key="apagar_historico"):
        st.session_state.historico_pesquisas = []
        st.success(texto_ui("history_cleared"))

elif secao_app == "Sobre o app":
    st.markdown(f"### {texto_ui('about_title')}")
    st.write(texto_ui("about_text"))
    st.info(texto_ui("beta"))

elif secao_app == "Sugestões":
    st.markdown(f"### {texto_ui('suggestions_title')}")
    st.write(texto_ui("suggestions_text"))
    with st.form("formulario_sugestao", clear_on_submit=True):
        sugestao_usuario = st.text_area(texto_ui("suggestion_label"), placeholder=texto_ui("suggestion_placeholder"), max_chars=3000)
        enviar_sugestao = st.form_submit_button(texto_ui("prepare_email"))
    if enviar_sugestao:
        if sugestao_usuario.strip():
            assunto_email = quote_plus("Sugestão para o Knowix")
            corpo_email = quote_plus(sugestao_usuario.strip())
            link_gmail = (
                "https://mail.google.com/mail/?view=cm&fs=1"
                f"&to=gustavoferreira3476%40gmail.com&su={assunto_email}&body={corpo_email}"
            )
            st.link_button(texto_ui("open_email"), link_gmail, use_container_width=True)
            st.caption(texto_ui("email_note"))
        else:
            st.warning(texto_ui("write_suggestion"))

if secao_app in ("Pesquisar", "Nova aba"):
    st.markdown(
        f'<p class="search-hint">{escape(texto_ui("search_hint"))}</p>',
        unsafe_allow_html=True,
    )

if buscar:
    assunto = pergunta.strip()
    if not assunto:
        st.warning(texto_ui("empty_search"))
    else:
        with st.spinner(texto_ui("searching")):
            dados_busca, veio_do_cache = buscar_resultados(assunto, obter_chave_tavily())
        st.session_state.resultado_atual = dados_busca
        st.session_state.fonte_aberta = None
        if veio_do_cache:
            st.caption(texto_ui("cached"))
        avisos_exibidos, falha_avisos = traduzir_textos(dados_busca["avisos"])
        for aviso in avisos_exibidos:
            st.info(aviso)
        if falha_avisos:
            st.warning(texto_ui("translation_error"))

resultado_atual = st.session_state.resultado_atual
if resultado_atual and secao_app in ("Pesquisar", "Nova aba"):
    falha_traducao = False
    if st.session_state.idioma_visual != "Português":
        with st.spinner(texto_ui("translation_wait")):
            resultado_atual, falha_traducao = traduzir_resultado(resultado_atual)
        if falha_traducao:
            st.warning(texto_ui("translation_error"))
    assunto = resultado_atual["assunto"]
    fontes = resultado_atual["fontes"]
    video = resultado_atual["video"]

    if st.session_state.fonte_aberta:
        fonte_aberta = st.session_state.fonte_aberta
        fonte = next(
            (item for item in fontes if item.get("url") == fonte_aberta.get("url")),
            fonte_aberta,
        )
        st.button(texto_ui("source_back"), on_click=lambda: setattr(st.session_state, "fonte_aberta", None))
        st.markdown(f"### {fonte['title']}")
        st.caption(fonte.get("domain", texto_ui("source_page")))
        st.markdown(f"#### {texto_ui('source_summary')}")
        st.write(fonte.get("content") or texto_ui("no_excerpt"))
        st.markdown(f"#### {texto_ui('page_preview')}")
        st.caption(texto_ui("preview_note"))
        st.iframe(fonte["url"], height=600)
        st.link_button(texto_ui("open_source"), fonte["url"], use_container_width=True)
    else:
        assunto_seguro = escape(assunto)
        st.markdown(
            f'<div class="section-kicker">{texto_ui("results_for")} “{assunto_seguro}”</div>',
            unsafe_allow_html=True,
        )

        col_resposta, col_video = st.columns([1.1, 0.9], gap="large")
        with col_resposta:
            with st.container(border=True):
                st.markdown(f'<div class="answer-label">{texto_ui("quick_answer")}</div>', unsafe_allow_html=True)
                if resultado_atual["resposta"]:
                    st.markdown(resumir_resposta(resultado_atual["resposta"]))
                    st.caption(texto_ui("answer_caption"))
                else:
                    st.write(texto_ui("no_answer"))

        with col_video:
            with st.container(border=True):
                st.markdown(f'<div class="section-kicker">{texto_ui("featured_video")}</div>', unsafe_allow_html=True)
                if video and re.fullmatch(r"[A-Za-z0-9_-]{11}", video.get("id", "")):
                    st.markdown(f"**{encurtar(video.get('title', texto_ui('related_video')), 90)}**")
                    detalhes_video = []
                    if video.get("channel"):
                        detalhes_video.append(f"{texto_ui('channel')}: {video['channel']}")
                    if video.get("view_count") is not None:
                        visualizacoes = f"{video['view_count']:,}".replace(",", ".")
                        detalhes_video.append(f"{texto_ui('views')}: {visualizacoes}")
                    if detalhes_video:
                        st.caption(" • ".join(detalhes_video))
                    st.iframe(
                        f"https://www.youtube-nocookie.com/embed/{video['id']}?rel=0&playsinline=1",
                        height=300,
                    )
                    st.caption(texto_ui("video_caption"))
                else:
                    st.info(texto_ui("no_video"))
                if st.button(texto_ui("more_videos"), key="mais_videos_interno"):
                    preparar_busca_interna(f"vídeos sobre {assunto}")
                    st.rerun()

        st.markdown(f"### {texto_ui('sites_found')}")
        if fontes:
            colunas_sites = st.columns(2, gap="medium")
            for indice, fonte in enumerate(fontes[:8]):
                with colunas_sites[indice % 2]:
                    with st.container(border=True):
                        if fonte.get("domain"):
                            st.caption(f"●  {fonte['domain']}")
                        st.button(
                            encurtar(fonte.get("title", texto_ui("read_source")), 76),
                            key=f"fonte_interna_{indice}",
                            on_click=abrir_fonte_no_knowix,
                            args=(fonte,),
                            use_container_width=True,
                        )
                        trecho = encurtar(fonte.get("content", ""), 210)
                        if trecho:
                            st.write(trecho)
        else:
            st.info(texto_ui("no_sources"))

        tema = re.sub(
            r"^(o que é|o que e|como funciona|quem foi|quem é|quem e|qual é|qual e|benefícios de|beneficios de|principais fatos sobre|aplicações de|aplicacoes de|vantagens e desvantagens de|história e evolução de|historia e evolucao de|novidades sobre|vídeos explicativos sobre|videos explicativos sobre)\s+",
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
        sugestoes, falha_sugestoes = traduzir_textos(sugestoes)
        if falha_sugestoes:
            st.warning(texto_ui("translation_error"))
        st.markdown(f"### {texto_ui('keep_exploring')}")
        st.caption(texto_ui("suggestions_inside"))
        colunas_sugestoes = st.columns(3, gap="small")
        for indice, sugestao in enumerate(sugestoes):
            with colunas_sugestoes[indice % 3]:
                st.button(
                    sugestao,
                    key=f"sugestao_interna_{indice}",
                    on_click=preparar_busca_interna,
                    args=(sugestao,),
                    use_container_width=True,
                )

st.markdown(
    f'<div class="soft-note">{escape(texto_ui("footer_note"))}</div>',
    unsafe_allow_html=True,
)
