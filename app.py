import os
import json
import hashlib
import queue
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import quote, quote_plus, urlparse

import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from knowix_answers import resumir_resposta
from knowix_accounts import (
    TEXTOS_CONTA, ErroContaKnowix, alterar_senha, carregar_configuracao,
    carregar_dados, cadastrar, entrar, enviar_recuperacao, mesclar_dados_conta,
    sair as sair_conta, salvar_dados,
)
from knowix_exports import conteudo_pesquisa, gerar_docx, gerar_pdf
from knowix_limits import LimitadorPesquisas
from knowix_research import pesquisar_profundamente
from knowix_search import (
    classificar_fonte, detectar_comparacao, filtrar_fontes,
    filtros_disponiveis, normalizar_url_http,
)
from knowix_vision import ErroVisaoKnowix, analisar_imagem


st.set_page_config(
    page_title="Knowix",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

componente_pesquisa_por_voz = components.declare_component(
    "knowix_voice_search",
    path=Path(__file__).parent / "knowix_voice",
)
componente_dados_locais = components.declare_component(
    "knowix_local_storage",
    path=Path(__file__).parent / "knowix_storage",
)
componente_callback_conta = components.declare_component(
    "knowix_account_callback",
    path=Path(__file__).parent / "knowix_account_callback",
)

if "tema_visual" not in st.session_state:
    st.session_state.tema_visual = "Claro"
# Atualiza a preferência de sessões anteriores para evitar que uma configuração
# antiga em inglês faça a tela abrir nesse idioma após a correção.
if st.session_state.get("versao_idioma_visual") != 2:
    st.session_state.idioma_visual = "Português"
    st.session_state.versao_idioma_visual = 2
elif st.session_state.get("idioma_visual") not in {"Português", "English", "Español"}:
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
    .st-key-language-control [data-testid="stSelectbox"] [role="combobox"] {
      background:__COR_CARTAO__; border:1px solid __COR_BORDA__; border-radius:999px;
      box-shadow:0 4px 14px rgba(33,58,99,.08); min-height:34px; padding:0 7px;
    }
    .st-key-language-control [data-testid="stSelectbox"] input[role="combobox"] {
      color:__COR_TEXTO__ !important; font-size:11px; -webkit-text-fill-color:__COR_TEXTO__ !important;
    }
    div[data-testid="stTextInput"] [data-testid="InputInstructions"] { display:none !important; }
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
    .brand-row { align-items:center; display:flex; gap:12px; justify-content:center; margin:1.2rem auto 1.35rem; }
    .brand-mark {
      align-items:center; background:linear-gradient(145deg,#20b6a5 0%,#3278f6 56%,#7658ed 100%);
      border:1px solid #ffffff38; border-radius:17px; box-shadow:0 10px 24px rgba(42,111,205,.24);
      color:#fff; display:flex; height:48px; justify-content:center; width:48px;
    }
    .brand-mark svg { height:27px; width:27px; }
    .brand-name { color:var(--ink); font-size:34px; font-weight:800; letter-spacing:-1.5px; }
    .search-hint { color:var(--muted); font-size:13px; line-height:1.5; margin:10px 4px 0; text-align:center; }
    .st-key-search-hero { margin:0 auto 1rem; max-width:780px; text-align:center; }
    .search-hero-title { color:var(--ink); font-size:clamp(25px,4vw,36px); font-weight:750; letter-spacing:-1.1px; line-height:1.18; margin:0 0 9px; }
    .search-hero-caption { color:var(--muted); font-size:15px; line-height:1.55; margin:0 auto; max-width:610px; }
    .st-key-search-action-row { margin:0 auto; max-width:900px; }
    .st-key-search-action-row [data-testid="stHorizontalBlock"] { align-items:center; gap:12px; }
    .st-key-search-action-row [data-testid="column"] { min-width:0; }
    .st-key-search-action-row .st-key-formulario_pesquisa[data-testid="stForm"] {
      background:__COR_CARTAO__; border:1px solid __COR_BORDA__; border-radius:22px;
      box-shadow:0 14px 40px rgba(33,58,99,.10); margin:0; max-width:none; padding:10px 12px;
      transition:border-color .18s ease, box-shadow .18s ease;
    }
    .st-key-search-action-row .st-key-formulario_pesquisa[data-testid="stForm"]:focus-within {
      border-color:__COR_AZUL__; box-shadow:0 0 0 4px #8db2ff24,0 16px 42px rgba(33,58,99,.12);
    }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stHorizontalBlock"] { align-items:center; gap:8px; }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="column"] { min-width:0; }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stTextInput"] input {
      background:transparent; border:1px solid transparent; border-radius:14px;
      box-shadow:none; font-size:16px; height:50px; padding:0 15px;
    }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stTextInput"] input:focus {
      background:__COR_CAMPO__; border-color:transparent; box-shadow:none;
    }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stFormSubmitButton"] button {
      background:linear-gradient(135deg,#176eae,#485fea 65%,#7557df); border:0; border-radius:14px;
      box-shadow:0 6px 15px rgba(60,100,220,.22); color:#fff !important; min-height:48px;
      padding:0 18px; transition:transform .16s ease,filter .16s ease;
    }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stFormSubmitButton"] button:hover {
      color:#fff !important; filter:brightness(1.06); transform:translateY(-1px);
    }
    .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stFormSubmitButton"] button:active { transform:scale(.98); }
    .st-key-search-mode [data-testid="stRadio"] > div { justify-content:center; }
    .st-key-search-mode { margin-top:.35rem; }
    .st-key-search-action-row iframe { display:block; }
    .st-key-search-action-row [data-testid="stElementContainer"]:has(iframe) { margin:auto 0; }
    .st-key-search-action-row [data-testid="stElementContainer"]:has(iframe) iframe { width:100%; }
    .st-key-search-history { margin:1.7rem auto 0; max-width:820px; }
    .st-key-search-history h4 { color:var(--ink); font-size:15px; font-weight:700; margin-bottom:.65rem; }
    .st-key-search-history [data-testid="stButton"] button {
      background:__COR_CARTAO__; border-color:__COR_BORDA__; border-radius:14px;
      color:var(--muted) !important; font-size:14px; font-weight:550; justify-content:flex-start;
      min-height:46px; padding:0 14px; text-align:left; transition:transform .16s ease,border-color .16s ease;
    }
    .st-key-search-history [data-testid="stButton"] button:hover { border-color:__COR_AZUL__; color:__COR_AZUL__ !important; transform:translateY(-1px); }
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
    [data-testid="stVerticalBlockBorderWrapper"] {
      background:__COR_CARTAO__; border:1px solid __COR_BORDA__ !important; border-radius:19px;
      box-shadow:0 10px 30px rgba(33,58,99,.06); overflow:hidden;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div { background:transparent; }
    .answer-label { color:var(--blue); font-size:12px; font-weight:800; letter-spacing:.08em; margin-bottom:9px; text-transform:uppercase; }
    .section-kicker { color:var(--muted); font-size:11px; font-weight:750; letter-spacing:1.2px; text-transform:uppercase; }
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4 { letter-spacing:-.025em; }
    .video-panel {
      background:#111a2b; border-radius:20px; color:white; overflow:hidden;
      padding:18px;
    }
    @media (max-width:700px) {
      .block-container { padding:.65rem .8rem 1rem; }
      .brand-row { gap:9px; margin:.55rem auto 1rem; }
      .brand-mark { width:42px; height:42px; border-radius:14px; }
      .brand-mark svg { height:24px; width:24px; }
      .brand-name { font-size:29px; }
      .st-key-search-hero { margin-bottom:.8rem; }
      .search-hero-title { font-size:27px; letter-spacing:-.7px; }
      .search-hero-caption { font-size:14px; }
      .search-hint { color:var(--muted); font-size:13px; line-height:1.5; }
      .st-key-language-control [data-testid="stSelectbox"] [role="combobox"] { min-height:34px; }
      [data-testid="stSelectbox"] [role="combobox"] * { font-size:16px; }
      .st-key-language-control [data-testid="stSelectbox"] [role="combobox"] * { font-size:11px; }
      div[data-testid="stButton"] button { font-size:15px; min-height:48px; line-height:1.3; }
      .st-key-search-action-row [data-testid="stHorizontalBlock"] { flex-direction:column; gap:8px; }
      .st-key-search-action-row [data-testid="column"] { flex:1 1 100% !important; width:100% !important; }
      .st-key-search-action-row .st-key-formulario_pesquisa[data-testid="stForm"] { border-radius:18px; padding:8px; }
      .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stHorizontalBlock"] { flex-direction:row; }
      .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="column"]:first-child { flex:1 1 68% !important; width:68% !important; }
      .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="column"]:last-child { flex:0 0 29% !important; width:29% !important; }
      .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stTextInput"] input { font-size:16px; padding:0 10px; }
      .st-key-search-action-row .st-key-formulario_pesquisa [data-testid="stFormSubmitButton"] button { font-size:14px; padding:0 8px; }
      .st-key-search-history { margin-top:1.25rem; }
      .st-key-search-history [data-testid="stHorizontalBlock"] { gap:8px; }
      [data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; }
      div[data-testid="stForm"]:not(.st-key-formulario_pesquisa) { border-radius:16px; padding:10px; }
    }
    @media (prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto !important; transition-duration:.01ms !important; animation-duration:.01ms !important; } }
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
        "section_Pesquisar": "Pesquisar", "section_Nova aba": "Nova aba",
        "section_Histórico": "Histórico", "section_Favoritos": "Favoritos", "section_Pastas": "Pastas", "section_Projetos": "Projetos", "section_Configurações": "Configurações",
        "section_Sobre o app": "Sobre o app", "section_Sugestões": "Sugestões",
        "search_placeholder": "⌕  Pergunte ao Knowix…",
        "search_hero_title": "O que você quer descobrir?",
        "search_hero_caption": "Faça sua pergunta. Encontre respostas organizadas e fontes para explorar.",
        "search_button": "Pesquisar", "new_search_title": "Abra uma nova pesquisa",
        "new_search_caption": "Inicie outra busca sem apagar o histórico desta sessão.",
        "new_search_label": "O que quer pesquisar nesta nova aba?",
        "new_search_placeholder": "Digite outra pergunta ou assunto...",
        "new_search_button": "Pesquisar nesta aba", "search_hint": "Pesquise temas, perguntas, notícias, ciência, tecnologia e muito mais.",
        "history_title": "Pesquisas recentes", "history_empty": "Suas pesquisas aparecerão aqui depois da primeira busca.",
        "history_filter": "Pesquisar no histórico",
        "settings_title": "Configurações", "appearance": "Aparência", "theme_label": "Tema do Knowix",
        "theme_caption": "A aparência muda imediatamente e fica ativa enquanto esta sessão estiver aberta.",
        "privacy": "Privacidade", "history_privacy": "Histórico, favoritos, pastas, projetos e preferências ficam somente neste navegador. Use a opção de apagar para remover o histórico deste dispositivo.",
        "clear_history": "Apagar histórico deste navegador", "history_cleared": "Histórico apagado.",
        "favorite_title": "Favoritos", "favorite_empty": "Salve uma pesquisa ou fonte para encontrá-la aqui.",
        "favorite_research": "☆ Salvar pesquisa", "favorite_research_saved": "★ Pesquisa salva", "favorite_source": "☆",
        "favorite_source_saved": "★", "favorite_save_source_help": "Salvar ou remover esta fonte dos favoritos",
        "favorite_remove": "Remover", "favorite_open": "Abrir pesquisa", "favorite_source_type": "Fonte",
        "favorite_search_type": "Pesquisa", "folder_title": "Pastas", "folder_empty": "Crie uma pasta para organizar seus favoritos.",
        "folder_all": "Todas as pastas",
        "folder_create": "Criar pasta", "folder_name": "Nome da pasta", "folder_default": "Sem pasta", "folder_added": "Pasta criada.", "folder_duplicate": "Essa pasta já existe ou você atingiu o limite de pastas.",
        "folder_assign": "Mover para pasta", "folder_notes": "Anotações da pasta", "folder_save_notes": "Salvar anotações", "folder_notes_saved": "Anotações da pasta salvas.", "local_storage_notice": "Seus dados ficam no armazenamento deste navegador e não são sincronizados com outros dispositivos.",
        "project_title": "Projetos de pesquisa", "project_empty": "Crie um projeto para reunir pesquisas, fontes e anotações.", "project_name": "Nome do projeto", "project_create": "Criar projeto", "project_added": "Projeto criado.", "project_duplicate": "Informe um nome único para o projeto.", "project_select": "Projeto", "project_notes": "Anotações", "project_save_notes": "Salvar anotações", "project_notes_saved": "Anotações salvas.", "project_searches": "Pesquisas reunidas", "project_sources": "Fontes reunidas", "project_add_current": "Adicionar pesquisa atual ao projeto", "project_added_item": "Pesquisa adicionada ao projeto.", "project_export": "Exportar relatório do projeto",
        "storage_error": "O navegador não permitiu ler ou salvar os dados locais. Confira as permissões ou o espaço disponível no navegador.",
        "about_title": "Sobre o Knowix", "about_text": "O Knowix ajuda a encontrar respostas curtas, fontes para conferir e vídeos relacionados.",
        "beta": "VERSÃO ALPHA — o app está em fase inicial de testes. Algumas funções e resultados podem mudar.",
        "more_videos_loading": "Buscando outros vídeos relacionados...",
        "more_videos_results": "Mais vídeos sobre este assunto",
        "more_videos_empty": "Não encontrei outros vídeos agora. Tente novamente mais tarde.",
        "suggestions_title": "Sugestões para o Knowix", "suggestions_text": "Conte sua ideia, problema ou melhoria. Ao clicar no link, o Gmail abrirá uma mensagem para a equipe.",
        "suggestion_label": "Sua sugestão", "suggestion_placeholder": "Escreva sua ideia aqui...",
        "prepare_email": "Preparar sugestão no Gmail", "write_suggestion": "Escreva sua sugestão antes de continuar.",
        "open_email": "Abrir o Gmail para enviar", "email_note": "Por segurança, o Knowix não envia e-mails sozinho: confira a mensagem no Gmail e toque em Enviar.",
        "searching": "Pesquisando páginas e vídeos ao mesmo tempo...", "cached": "Resultado recente carregado da sua sessão.",
        "empty_search": "Digite um assunto para começar a pesquisa.", "results_for": "RESULTADOS PARA",
        "quick_answer": "✦ RESPOSTA DE IA", "answer_caption": "Resposta gerada por IA com base em páginas encontradas. Confira as fontes abaixo.",
        "source_answer": "✦ RESUMO DA FONTE", "source_answer_caption": "Este resumo vem da Wikipédia; configure a busca por IA para gerar uma resposta própria.",
        "answer_unspecified": "✦ RESPOSTA", "answer_unspecified_caption": "Abra as fontes abaixo para conferir os detalhes.",
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
        "recent_home": "Pesquisas recentes", "recent_home_empty": "Suas pesquisas recentes aparecerão aqui depois da primeira busca.",
        "published": "Publicado", "consulted": "Consultado em",
        "temporary_search_error": "A pesquisa está temporariamente indisponível. Tente novamente em instantes.",
        "no_results_detail": "A pesquisa foi concluída, mas nenhuma página correspondente foi encontrada.",
        "export_title": "Exportar pesquisa", "export_md": "Baixar texto", "export_docx": "Baixar documento", "export_pdf": "Baixar PDF",
        "filter_label": "Filtrar resultados", "filter_all": "Todos", "filter_sites": "Sites", "filter_news": "Notícias", "filter_articles": "Artigos", "filter_videos": "Vídeos", "filter_images": "Imagens", "filter_documents": "Documentos",
        "comparison_heading": "Comparação das opções encontradas",
        "research_mode_label": "Modo de pesquisa", "research_mode_quick": "Pesquisa rápida", "research_mode_deep": "Pesquisa profunda",
        "deep_cost_note": "A pesquisa profunda usa o agente da Tavily e vários créditos. Confira o limite e o uso da sua conta antes de iniciar.",
        "deep_running": "A pesquisa profunda está em andamento no serviço. Isso pode levar alguns minutos.",
        "deep_progress": "Pesquisa profunda ainda em andamento — {seconds}s decorridos.",
        "deep_accepted": "Solicitação aceita pelo serviço de pesquisa.",
        "deep_finalizing": "Pesquisa concluída; organizando o relatório e as fontes.",
        "deep_complete": "Pesquisa profunda concluída.", "deep_timeout": "A pesquisa continua no serviço, mas ainda não ficou pronta. Tente novamente mais tarde.",
        "deep_answer_caption": "Relatório sintetizado pelo agente de pesquisa com citações e fontes reunidas.",
        "research_map": "Mapa da pesquisa", "explore_topic": "Aprofundar este tópico",
        "research_map_caption": "Os tópicos abaixo vieram das seções do relatório e iniciam uma nova busca com fontes.",
        "map_custom_topic": "Adicionar um tópico ao mapa",
        "deep_credits": "Uso informado pelo serviço: {credits} créditos.",
        "deep_needs_key": "Pesquisa profunda precisa da configuração TAVILY_API_KEY. Configure-a nos Secrets do Streamlit para habilitar esse modo.",
        "followup_title": "Faça uma pergunta complementar",
        "followup_placeholder": "Ex.: quais são os custos e riscos dessa opção?",
        "followup_button": "Continuar pesquisa",
        "followup_context": "O Knowix usará a pergunta e um trecho da resposta anterior como contexto. A nova resposta será verificada com fontes atuais.",
        "listen_answer": "🔊 Ouvir resposta", "stop_speech": "Parar leitura", "speech_unsupported": "A leitura em voz alta não está disponível neste navegador.",
        "rate_limit_quick": "Você atingiu o limite temporário de pesquisas. Aguarde uma hora e tente novamente.",
        "rate_limit_deep": "Você atingiu o limite temporário de pesquisas profundas. Aguarde uma hora e tente novamente.",
        "image_title": "Pesquisar com uma imagem", "image_caption": "Envie uma foto para perguntar sobre o que aparece nela.",
        "image_upload": "Escolha uma imagem (JPG, PNG ou WebP; até 8 MB)", "image_question": "O que você quer saber sobre a imagem?",
        "image_question_hint": "Ex.: Que objeto é este? Como posso pesquisar por um modelo parecido?",
        "image_privacy": "A análise está pausada. Nenhuma foto será enviada a serviços externos até a confirmação adequada de acesso exclusivo para maiores de 18 anos.",
        "image_analyze": "Análise temporariamente indisponível", "image_missing_key": "A análise de imagem continua desativada até que o acesso exclusivo para maiores de 18 anos seja confirmado adequadamente e as condições do provedor sejam atendidas.",
        "image_analysis": "Análise visual — resposta de IA", "image_web_search": "Pesquisar na web sobre isso",
        "image_error": "Não foi possível analisar a imagem.", "image_rate_limit": "Você atingiu o limite temporário de análises de imagem. Tente novamente em uma hora.",
    },
    "English": {
        "section_Pesquisar": "Search", "section_Nova aba": "New tab", "section_Histórico": "History", "section_Favoritos": "Favorites", "section_Pastas": "Folders", "section_Projetos": "Projects",
        "section_Configurações": "Settings", "section_Sobre o app": "About the app", "section_Sugestões": "Suggestions",
        "search_placeholder": "⌕  Ask Knowix anything…", "search_hero_title": "What would you like to discover?",
        "search_hero_caption": "Ask a question. Explore organized answers and the sources behind them.", "search_button": "Search",
        "new_search_title": "Start a new search", "new_search_caption": "Start another search without clearing this session's history.",
        "new_search_label": "What would you like to search in this new tab?", "new_search_placeholder": "Enter another question or topic...",
        "new_search_button": "Search in this tab", "search_hint": "Explore topics, questions, news, science, technology, and more.",
        "history_title": "Recent searches", "history_empty": "Your searches will appear here after your first search.",
        "history_filter": "Search history",
        "settings_title": "Settings", "appearance": "Appearance", "theme_label": "Knowix theme",
        "theme_caption": "The appearance changes immediately and stays active while this session is open.",
        "privacy": "Privacy", "history_privacy": "History, favorites, folders, projects, and preferences stay in this browser. Use the clear option to remove history from this device.",
        "clear_history": "Clear browser history", "history_cleared": "History cleared.",
        "favorite_title": "Favorites", "favorite_empty": "Save a search or source to find it here.",
        "favorite_research": "☆ Save search", "favorite_research_saved": "★ Search saved", "favorite_source": "☆",
        "favorite_source_saved": "★", "favorite_save_source_help": "Save or remove this source from favorites",
        "favorite_remove": "Remove", "favorite_open": "Open search", "favorite_source_type": "Source",
        "favorite_search_type": "Search", "folder_title": "Folders", "folder_empty": "Create a folder to organize your favorites.",
        "folder_all": "All folders",
        "folder_create": "Create folder", "folder_name": "Folder name", "folder_default": "No folder", "folder_added": "Folder created.", "folder_duplicate": "This folder already exists or you reached the folder limit.",
        "folder_assign": "Move to folder", "folder_notes": "Folder notes", "folder_save_notes": "Save notes", "folder_notes_saved": "Folder notes saved.", "local_storage_notice": "Your data stays in this browser and is not synchronized across devices.",
        "project_title": "Research projects", "project_empty": "Create a project to gather searches, sources, and notes.", "project_name": "Project name", "project_create": "Create project", "project_added": "Project created.", "project_duplicate": "Enter a unique project name.", "project_select": "Project", "project_notes": "Notes", "project_save_notes": "Save notes", "project_notes_saved": "Notes saved.", "project_searches": "Collected searches", "project_sources": "Collected sources", "project_add_current": "Add current search to project", "project_added_item": "Search added to project.", "project_export": "Export project report",
        "storage_error": "The browser could not read or save local data. Check browser permissions or available storage.",
        "about_title": "About Knowix", "about_text": "Knowix helps you find concise answers, sources to check, and related videos.",
        "beta": "ALPHA VERSION — the app is in early testing. Some features and results may change.",
        "more_videos_loading": "Searching for more related videos...",
        "more_videos_results": "More videos about this topic",
        "more_videos_empty": "I couldn't find more videos right now. Try again later.",
        "suggestions_title": "Suggestions for Knowix", "suggestions_text": "Share an idea, issue, or improvement. Gmail will open a message to the team.",
        "suggestion_label": "Your suggestion", "suggestion_placeholder": "Write your idea here...", "prepare_email": "Prepare suggestion in Gmail",
        "write_suggestion": "Write your suggestion before continuing.", "open_email": "Open Gmail to send",
        "email_note": "For your safety, Knowix does not send emails automatically. Review the message in Gmail and press Send.",
        "searching": "Searching pages and videos at the same time...", "cached": "Recent result loaded from your session.",
        "empty_search": "Enter a topic to start searching.", "results_for": "RESULTS FOR", "quick_answer": "✦ AI ANSWER",
        "answer_caption": "AI-generated answer based on found pages. Check the sources below.",
        "source_answer": "✦ SOURCE SUMMARY", "source_answer_caption": "This summary comes from Wikipedia; configure AI search to generate an answer.",
        "answer_unspecified": "✦ ANSWER", "answer_unspecified_caption": "Open the sources below to check the details.",
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
        "recent_home": "Recent searches", "recent_home_empty": "Your recent searches will appear here after your first search.",
        "published": "Published", "consulted": "Consulted",
        "temporary_search_error": "Search is temporarily unavailable. Please try again shortly.",
        "no_results_detail": "The search completed, but no matching pages were found.",
        "export_title": "Export search", "export_md": "Download text", "export_docx": "Download document", "export_pdf": "Download PDF",
        "filter_label": "Filter results", "filter_all": "All", "filter_sites": "Websites", "filter_news": "News", "filter_articles": "Articles", "filter_videos": "Videos", "filter_images": "Images", "filter_documents": "Documents",
        "comparison_heading": "Comparison of the options found",
        "research_mode_label": "Research mode", "research_mode_quick": "Quick search", "research_mode_deep": "Deep research",
        "deep_cost_note": "Deep research uses Tavily's research agent and multiple credits. Check your account's limits and usage before starting.",
        "deep_running": "Deep research is running at the provider. This may take a few minutes.",
        "deep_progress": "Deep research is still running — {seconds}s elapsed.",
        "deep_accepted": "The research request was accepted by the provider.",
        "deep_finalizing": "Research completed; organizing the report and sources.",
        "deep_complete": "Deep research completed.", "deep_timeout": "The research is still running at the provider but is not ready yet. Try again later.",
        "deep_answer_caption": "Report synthesized by the research agent with citations and collected sources.",
        "research_map": "Research map", "explore_topic": "Explore this topic",
        "research_map_caption": "These topics come from the report sections and start a new source-backed search.",
        "map_custom_topic": "Add a topic to the map",
        "deep_credits": "Usage reported by the provider: {credits} credits.",
        "deep_needs_key": "Deep research requires TAVILY_API_KEY. Configure it in Streamlit Secrets to enable this mode.",
        "followup_title": "Ask a follow-up question",
        "followup_placeholder": "For example: what are the costs and risks?",
        "followup_button": "Continue research",
        "followup_context": "Knowix will use your question and part of the previous answer as context. The new answer will be checked against current sources.",
        "listen_answer": "🔊 Listen to answer", "stop_speech": "Stop reading", "speech_unsupported": "Read-aloud is unavailable in this browser.",
        "rate_limit_quick": "You reached the temporary search limit. Wait an hour and try again.",
        "rate_limit_deep": "You reached the temporary deep research limit. Wait an hour and try again.",
        "image_title": "Search with an image", "image_caption": "Upload a photo to ask about what appears in it.",
        "image_upload": "Choose an image (JPG, PNG, or WebP; up to 8 MB)", "image_question": "What would you like to know about the image?",
        "image_question_hint": "For example: What is this object? How can I find a similar model?",
        "image_privacy": "Image analysis is paused. No photo will be sent to external services until adults-only access is adequately assured.",
        "image_analyze": "Temporarily unavailable", "image_missing_key": "Image analysis remains disabled until adults-only access is adequately assured and provider requirements are met.",
        "image_analysis": "Visual analysis — AI response", "image_web_search": "Search the web about this",
        "image_error": "The image could not be analyzed.", "image_rate_limit": "You reached the temporary image analysis limit. Try again in an hour.",
    },
    "Español": {
        "section_Pesquisar": "Buscar", "section_Nova aba": "Nueva pestaña", "section_Histórico": "Historial", "section_Favoritos": "Favoritos", "section_Pastas": "Carpetas", "section_Projetos": "Proyectos",
        "section_Configurações": "Configuración", "section_Sobre o app": "Acerca de la app", "section_Sugestões": "Sugerencias",
        "search_placeholder": "⌕  Pregunta lo que quieras a Knowix…", "search_hero_title": "¿Qué quieres descubrir?",
        "search_hero_caption": "Haz tu pregunta. Explora respuestas organizadas y sus fuentes.", "search_button": "Buscar",
        "new_search_title": "Iniciar una nueva búsqueda", "new_search_caption": "Inicia otra búsqueda sin borrar el historial de esta sesión.",
        "new_search_label": "¿Qué quieres buscar en esta nueva pestaña?", "new_search_placeholder": "Escribe otra pregunta o tema...",
        "new_search_button": "Buscar en esta pestaña", "search_hint": "Explora temas, preguntas, noticias, ciencia, tecnología y mucho más.",
        "history_title": "Búsquedas recientes", "history_empty": "Tus búsquedas aparecerán aquí después de la primera búsqueda.",
        "history_filter": "Buscar en el historial",
        "settings_title": "Configuración", "appearance": "Apariencia", "theme_label": "Tema de Knowix",
        "theme_caption": "La apariencia cambia inmediatamente y permanece activa mientras esta sesión esté abierta.",
        "privacy": "Privacidad", "history_privacy": "El historial, los favoritos, las carpetas, los proyectos y las preferencias quedan en este navegador. Usa la opción de borrar para quitar el historial de este dispositivo.",
        "clear_history": "Borrar el historial de este navegador", "history_cleared": "Historial borrado.",
        "favorite_title": "Favoritos", "favorite_empty": "Guarda una búsqueda o fuente para encontrarla aquí.",
        "favorite_research": "☆ Guardar búsqueda", "favorite_research_saved": "★ Búsqueda guardada", "favorite_source": "☆",
        "favorite_source_saved": "★", "favorite_save_source_help": "Guardar o quitar esta fuente de favoritos",
        "favorite_remove": "Quitar", "favorite_open": "Abrir búsqueda", "favorite_source_type": "Fuente",
        "favorite_search_type": "Búsqueda", "folder_title": "Carpetas", "folder_empty": "Crea una carpeta para organizar tus favoritos.",
        "folder_all": "Todas las carpetas",
        "folder_create": "Crear carpeta", "folder_name": "Nombre de carpeta", "folder_default": "Sin carpeta", "folder_added": "Carpeta creada.", "folder_duplicate": "Esta carpeta ya existe o alcanzaste el límite de carpetas.",
        "folder_assign": "Mover a carpeta", "folder_notes": "Notas de la carpeta", "folder_save_notes": "Guardar notas", "folder_notes_saved": "Notas de la carpeta guardadas.", "local_storage_notice": "Tus datos quedan en este navegador y no se sincronizan con otros dispositivos.",
        "project_title": "Proyectos de investigación", "project_empty": "Crea un proyecto para reunir búsquedas, fuentes y notas.", "project_name": "Nombre del proyecto", "project_create": "Crear proyecto", "project_added": "Proyecto creado.", "project_duplicate": "Escribe un nombre de proyecto único.", "project_select": "Proyecto", "project_notes": "Notas", "project_save_notes": "Guardar notas", "project_notes_saved": "Notas guardadas.", "project_searches": "Búsquedas reunidas", "project_sources": "Fuentes reunidas", "project_add_current": "Añadir la búsqueda actual al proyecto", "project_added_item": "Búsqueda añadida al proyecto.", "project_export": "Exportar informe del proyecto",
        "storage_error": "El navegador no pudo leer o guardar los datos locales. Revisa los permisos o el espacio disponible.",
        "about_title": "Acerca de Knowix", "about_text": "Knowix te ayuda a encontrar respuestas breves, fuentes para consultar y videos relacionados.",
        "beta": "VERSIÓN ALPHA — la app está en fase inicial de pruebas. Algunas funciones y resultados pueden cambiar.",
        "more_videos_loading": "Buscando más videos relacionados...",
        "more_videos_results": "Más videos sobre este tema",
        "more_videos_empty": "No encontré más videos ahora. Inténtalo de nuevo más tarde.",
        "suggestions_title": "Sugerencias para Knowix", "suggestions_text": "Cuéntanos tu idea, problema o mejora. Gmail abrirá un mensaje para el equipo.",
        "suggestion_label": "Tu sugerencia", "suggestion_placeholder": "Escribe tu idea aquí...", "prepare_email": "Preparar sugerencia en Gmail",
        "write_suggestion": "Escribe tu sugerencia antes de continuar.", "open_email": "Abrir Gmail para enviar",
        "email_note": "Por seguridad, Knowix no envía correos automáticamente. Revisa el mensaje en Gmail y pulsa Enviar.",
        "searching": "Buscando páginas y videos al mismo tiempo...", "cached": "Resultado reciente cargado desde tu sesión.",
        "empty_search": "Escribe un tema para comenzar la búsqueda.", "results_for": "RESULTADOS PARA", "quick_answer": "✦ RESPUESTA DE IA",
        "answer_caption": "Respuesta generada por IA a partir de páginas encontradas. Consulta las fuentes abajo.",
        "source_answer": "✦ RESUMEN DE LA FUENTE", "source_answer_caption": "Este resumen proviene de Wikipedia; configura la búsqueda por IA para generar una respuesta.",
        "answer_unspecified": "✦ RESPUESTA", "answer_unspecified_caption": "Abre las fuentes de abajo para revisar los detalles.",
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
        "recent_home": "Búsquedas recientes", "recent_home_empty": "Tus búsquedas recientes aparecerán aquí después de la primera búsqueda.",
        "published": "Publicado", "consulted": "Consultado",
        "temporary_search_error": "La búsqueda no está disponible temporalmente. Inténtalo de nuevo en unos instantes.",
        "no_results_detail": "La búsqueda terminó, pero no se encontraron páginas coincidentes.",
        "export_title": "Exportar búsqueda", "export_md": "Descargar texto", "export_docx": "Descargar documento", "export_pdf": "Descargar PDF",
        "filter_label": "Filtrar resultados", "filter_all": "Todos", "filter_sites": "Sitios", "filter_news": "Noticias", "filter_articles": "Artículos", "filter_videos": "Videos", "filter_images": "Imágenes", "filter_documents": "Documentos",
        "comparison_heading": "Comparación de las opciones encontradas",
        "research_mode_label": "Modo de búsqueda", "research_mode_quick": "Búsqueda rápida", "research_mode_deep": "Investigación profunda",
        "deep_cost_note": "La investigación profunda usa el agente de Tavily y varios créditos. Revisa el límite y el uso de tu cuenta antes de iniciar.",
        "deep_running": "La investigación profunda está en curso en el servicio. Puede tardar unos minutos.",
        "deep_progress": "La investigación profunda sigue en curso: {seconds}s transcurridos.",
        "deep_accepted": "El servicio aceptó la solicitud de investigación.",
        "deep_finalizing": "Investigación completada; organizando el informe y las fuentes.",
        "deep_complete": "Investigación profunda completada.", "deep_timeout": "La investigación continúa en el servicio, pero aún no está lista. Inténtalo más tarde.",
        "deep_answer_caption": "Informe sintetizado por el agente de investigación con citas y fuentes recopiladas.",
        "research_map": "Mapa de investigación", "explore_topic": "Profundizar este tema",
        "research_map_caption": "Estos temas provienen de las secciones del informe e inician una nueva búsqueda con fuentes.",
        "map_custom_topic": "Añadir un tema al mapa",
        "deep_credits": "Uso informado por el servicio: {credits} créditos.",
        "deep_needs_key": "La investigación profunda requiere TAVILY_API_KEY. Configúrala en los Secrets de Streamlit para habilitar este modo.",
        "followup_title": "Haz una pregunta de seguimiento",
        "followup_placeholder": "Ej.: ¿cuáles son los costos y riesgos?",
        "followup_button": "Continuar investigación",
        "followup_context": "Knowix usará tu pregunta y parte de la respuesta anterior como contexto. La nueva respuesta se verificará con fuentes actuales.",
        "listen_answer": "🔊 Escuchar respuesta", "stop_speech": "Detener lectura", "speech_unsupported": "La lectura en voz alta no está disponible en este navegador.",
        "rate_limit_quick": "Alcanzaste el límite temporal de búsquedas. Espera una hora e inténtalo de nuevo.",
        "rate_limit_deep": "Alcanzaste el límite temporal de investigaciones profundas. Espera una hora e inténtalo de nuevo.",
        "image_title": "Buscar con una imagen", "image_caption": "Sube una foto para preguntar sobre lo que aparece en ella.",
        "image_upload": "Elige una imagen (JPG, PNG o WebP; hasta 8 MB)", "image_question": "¿Qué quieres saber sobre la imagen?",
        "image_question_hint": "Ej.: ¿Qué objeto es este? ¿Cómo busco un modelo parecido?",
        "image_privacy": "El análisis está pausado. No se enviará ninguna foto a servicios externos hasta asegurar adecuadamente el acceso exclusivo para mayores de 18 años.",
        "image_analyze": "Temporalmente no disponible", "image_missing_key": "El análisis de imágenes seguirá desactivado hasta asegurar adecuadamente el acceso exclusivo para mayores de 18 años y cumplir las condiciones del proveedor.",
        "image_analysis": "Análisis visual — respuesta de IA", "image_web_search": "Buscar en la web sobre esto",
        "image_error": "No se pudo analizar la imagen.", "image_rate_limit": "Alcanzaste el límite temporal de análisis de imágenes. Vuelve a intentarlo en una hora.",
    },
}


def texto_ui(chave):
    idioma = st.session_state.idioma_visual
    return TRADUCOES_UI[idioma].get(chave, TRADUCOES_UI["Português"].get(chave, chave))


# Knowix is now an adults-only service. This is a self-declaration, not
# independent age verification; no date of birth or identity document is stored.
IDIOMAS_PORTAO_ADULTO = {
    "Português": {
        "title": "Acesso exclusivo para maiores de 18 anos",
        "text": "O Knowix está sendo preparado para uso exclusivo por adultos. Ao continuar, você declara ter 18 anos ou mais.",
        "check": "Confirmo que tenho 18 anos ou mais.",
        "enter": "Continuar para o Knowix",
        "minor": "Se você tem menos de 18 anos, não continue e feche esta página.",
        "verification": "Esta é uma autodeclaração, não uma verificação independente de idade. O Knowix não pede nem armazena sua data de nascimento.",
        "error": "Confirme que tem 18 anos ou mais para continuar.",
    },
    "English": {
        "title": "Access is restricted to adults aged 18 or older",
        "text": "Knowix is being prepared for adults only. By continuing, you declare that you are at least 18 years old.",
        "check": "I confirm that I am 18 or older.",
        "enter": "Continue to Knowix",
        "minor": "If you are under 18, do not continue. Close this page.",
        "verification": "This is a self-declaration, not independent age verification. Knowix does not ask for or store your date of birth.",
        "error": "Confirm that you are at least 18 to continue.",
    },
    "Español": {
        "title": "Acceso exclusivo para mayores de 18 años",
        "text": "Knowix se está preparando para uso exclusivo de adultos. Al continuar, declaras que tienes 18 años o más.",
        "check": "Confirmo que tengo 18 años o más.",
        "enter": "Continuar a Knowix",
        "minor": "Si tienes menos de 18 años, no continúes y cierra esta página.",
        "verification": "Esta es una autodeclaración, no una verificación independiente de edad. Knowix no solicita ni almacena tu fecha de nacimiento.",
        "error": "Confirma que tienes 18 años o más para continuar.",
    },
}

st.session_state.setdefault("knowix_adult_confirmed", False)
if not st.session_state.knowix_adult_confirmed:
    idioma_portao = st.session_state.get("idioma_visual", "Português")
    textos_portao = IDIOMAS_PORTAO_ADULTO.get(idioma_portao, IDIOMAS_PORTAO_ADULTO["Português"])
    st.title(textos_portao["title"])
    st.write(textos_portao["text"])
    with st.form("knowix_adult_age_gate"):
        confirmou_idade = st.checkbox(textos_portao["check"])
        enviou_confirmacao = st.form_submit_button(textos_portao["enter"], use_container_width=True)
    if enviou_confirmacao:
        if confirmou_idade:
            st.session_state.knowix_adult_confirmed = True
            st.rerun()
        st.error(textos_portao["error"])
    st.caption(textos_portao["minor"])
    st.caption(textos_portao["verification"])
    st.stop()


def sincronizar_secao_selecionada():
    """Mantém a navegação interna correta para o rótulo do idioma atual."""
    idioma = st.session_state.idioma_visual
    opcoes = {
        TRADUCOES_UI[idioma].get(f"section_{secao}", secao): secao
        for secao in ["Pesquisar", "Nova aba", "Histórico", "Favoritos", "Pastas", "Projetos", "Configurações", "Sobre o app", "Sugestões"]
    }
    selecionada = st.session_state.get("secao_display")
    if selecionada in opcoes:
        st.session_state.secao_canonica = opcoes[selecionada]


def guardar_preferencias_local():
    if "dados_locais" not in st.session_state:
        return
    idioma = st.session_state.get("idioma_visual", "Português")
    tema = st.session_state.get("tema_visual", "Claro")
    if idioma not in {"Português", "English", "Español"}:
        idioma = "Português"
    if tema not in {"Claro", "Escuro"}:
        tema = "Claro"
    st.session_state.dados_locais["preferences"] = {"language": idioma, "theme": tema}
    st.session_state.preferencias_locais_tocadas = True
    marcar_dados_locais_alterados()


def sincronizar_idioma_selecionado():
    guardar_preferencias_local()


def sincronizar_tema_selecionado():
    """Guarda Claro/Escuro independentemente do idioma do rótulo visível."""
    idioma = st.session_state.idioma_visual
    nomes = {
        "Claro": "Light" if idioma == "English" else "Claro",
        "Escuro": "Dark" if idioma == "English" else "Oscuro" if idioma == "Español" else "Escuro",
    }
    opcoes = {nome: tema for tema, nome in nomes.items()}
    selecionado = st.session_state.get("tema_display")
    if selecionado in opcoes:
        st.session_state.tema_visual = opcoes[selecionado]
        guardar_preferencias_local()


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
            timeout=5,
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
        "imagens": [dict(imagem) for imagem in dados.get("imagens", [])],
        "avisos": list(dados.get("avisos", [])),
    }
    campos = [resultado.get("resposta", "")]
    if resultado["video"]:
        campos.append(resultado["video"].get("title", ""))
    for fonte in resultado["fontes"]:
        campos.extend([fonte.get("title", ""), fonte.get("content", "")])
    for imagem in resultado["imagens"]:
        campos.append(imagem.get("description", ""))
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
    for imagem in resultado["imagens"]:
        imagem["description"] = traducao[indice]
        indice += 1
    resultado["avisos"] = traducao[indice:]
    return resultado, falhou

def estado_local_vazio():
    return {"version": 1, "history": [], "favorites": [], "folders": [], "projects": [],
            "folder_notes": {}, "folder_notes_updated_at": {}, "sync_tombstones": {"history": {}, "favorites": {}},
            "preferences": {"language": "Português", "theme": "Claro"}}


_SAL_RATE_LIMIT = os.urandom(32)
_LIMITADOR_PESQUISAS = LimitadorPesquisas()


def chave_cliente_rate_limit():
    """Gera identificador temporário e opaco para limitar chamadas por IP/sessão."""
    try:
        endereco = st.context.ip_address
    except Exception:
        endereco = None
    if endereco:
        identidade = f"ip:{endereco}"
    else:
        if "id_sessao_rate_limit" not in st.session_state:
            st.session_state.id_sessao_rate_limit = uuid.uuid4().hex
        identidade = f"session:{st.session_state.id_sessao_rate_limit}"
    return hashlib.sha256(_SAL_RATE_LIMIT + identidade.encode("utf-8")).hexdigest()


def reservar_cota_pesquisa(modo, cliente_id=None, agora=None):
    """Aplica limite por hora no processo atual, sem guardar o IP em claro."""
    cliente_id = cliente_id or chave_cliente_rate_limit()
    return _LIMITADOR_PESQUISAS.reservar(cliente_id, modo, agora)


def normalizar_url_local(valor, somente_https=False):
    return normalizar_url_http(valor, somente_https=somente_https)


def chave_tombo_favorito(item):
    if not isinstance(item, dict):
        return ""
    tipo = item.get("type")
    if tipo == "search":
        valor = str(item.get("query", "")).strip().casefold()
    elif tipo == "source":
        valor = normalizar_url_local(item.get("url")).casefold()
    else:
        valor = ""
    return f"{tipo}:{valor}" if valor else ""


def normalizar_dados_locais(valor):
    """Valida dados lidos do navegador antes de os usar na interface do app."""
    valor = valor if isinstance(valor, dict) else {}
    tombstones_raw = valor.get("sync_tombstones") if isinstance(valor.get("sync_tombstones"), dict) else {}
    def normalizar_acoes(categoria, limite, casefold=False):
        bruto = tombstones_raw.get(categoria, {})
        acoes = {}
        if isinstance(bruto, list):
            bruto = {str(item): {"deleted": True, "at": ""} for item in bruto if isinstance(item, str)}
        if not isinstance(bruto, dict):
            return acoes
        for chave, acao in bruto.items():
            chave = str(chave).strip()[:limite]
            if not chave:
                continue
            if casefold:
                chave = chave.casefold()
            if isinstance(acao, dict) and isinstance(acao.get("deleted"), bool):
                acoes[chave] = {"deleted": acao["deleted"], "at": str(acao.get("at", ""))[:48]}
            else:
                acoes[chave] = {"deleted": True, "at": ""}
        return dict(sorted(acoes.items(), key=lambda par: par[1]["at"], reverse=True)[:1000])

    tombstones_historico = normalizar_acoes("history", 1000, casefold=True)
    tombstones_favoritos = normalizar_acoes("favorites", 2100)
    pastas = []
    for pasta in valor.get("folders", []) if isinstance(valor.get("folders"), list) else []:
        nome = str(pasta).strip()[:48]
        if nome and nome.casefold() not in {item.casefold() for item in pastas}:
            pastas.append(nome)
    historico = []
    for item in valor.get("history", []) if isinstance(valor.get("history"), list) else []:
        if not isinstance(item, dict):
            continue
        consulta = str(item.get("query", "")).strip()[:1000]
        resultado = item.get("result") if isinstance(item.get("result"), dict) else {}
        if not consulta:
            continue
        fontes = []
        for fonte in resultado.get("fontes", []) if isinstance(resultado.get("fontes"), list) else []:
            if not isinstance(fonte, dict):
                continue
            url_fonte = normalizar_url_local(fonte.get("url"))
            if url_fonte:
                fontes.append({
                    "title": str(fonte.get("title", "Fonte"))[:240], "url": url_fonte,
                    "content": str(fonte.get("content", ""))[:1200],
                    "domain": str(fonte.get("domain", ""))[:180],
                    "category": str(fonte.get("category", "site"))[:32],
                    "published_date": str(fonte.get("published_date") or "")[:80] or None,
                    "consulted_at": str(fonte.get("consulted_at") or "")[:80] or None,
                })
        imagens = []
        for imagem in resultado.get("imagens", []) if isinstance(resultado.get("imagens"), list) else []:
            if isinstance(imagem, dict):
                url_imagem = normalizar_url_local(imagem.get("url"), somente_https=True)
                if url_imagem:
                    imagens.append({"url": url_imagem, "description": str(imagem.get("description", ""))[:240]})
        video = resultado.get("video") if isinstance(resultado.get("video"), dict) else None
        if video and not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(video.get("id", ""))):
            video = None
        resposta = str(resultado.get("resposta", ""))[:16000]
        resultado_normalizado = {
            "assunto": consulta, "consulta_busca": str(resultado.get("consulta_busca", consulta))[:2200],
            "resposta": resposta, "resposta_gerada_por_ia": resultado.get("resposta_gerada_por_ia") is True,
            "fontes": fontes[:12], "imagens": imagens[:12], "video": video,
            "avisos": [], "status_pesquisa": str(resultado.get("status_pesquisa", "concluida"))[:32],
            "modo_pesquisa": "profunda" if resultado.get("modo_pesquisa") == "profunda" else "rapida",
            "uso_pesquisa": resultado.get("uso_pesquisa") if isinstance(resultado.get("uso_pesquisa"), dict) else {},
            "comparacao": resultado.get("comparacao") if isinstance(resultado.get("comparacao"), dict) else None,
        }
        historico.append({"id": str(item.get("id") or uuid.uuid4().hex)[:64], "query": consulta,
                          "saved_at": str(item.get("saved_at", ""))[:48], "result": resultado_normalizado})
    historico = [item for item in historico if not tombstones_historico.get(item["query"].casefold(), {}).get("deleted", False)]
    favoritos = []
    for item in valor.get("favorites", []) if isinstance(valor.get("favorites"), list) else []:
        if not isinstance(item, dict):
            continue
        tipo = item.get("type")
        consulta = str(item.get("query", "")).strip()[:1000]
        if tipo == "search" and consulta:
            registro = next((h for h in historico if h["query"].casefold() == consulta.casefold()), None)
            resultado_favorito = registro["result"] if registro else normalizar_dados_locais({
                "history": [{"query": consulta, "result": item.get("result", {})}]
            })["history"][0]["result"]
            favoritos.append({"id": str(item.get("id") or uuid.uuid4().hex)[:64], "type": "search",
                              "query": consulta, "folder": str(item.get("folder", ""))[:48],
                              "saved_at": str(item.get("saved_at", ""))[:48],
                              "updated_at": str(item.get("updated_at", ""))[:48],
                              "result": resultado_favorito})
        elif tipo == "source":
            url_fonte = normalizar_url_local(item.get("url"))
            if url_fonte:
                favoritos.append({"id": str(item.get("id") or uuid.uuid4().hex)[:64], "type": "source",
                                  "query": consulta, "title": str(item.get("title", "Fonte"))[:240],
                                  "url": url_fonte, "content": str(item.get("content", ""))[:1200],
                                  "folder": str(item.get("folder", ""))[:48],
                                  "saved_at": str(item.get("saved_at", ""))[:48],
                                  "updated_at": str(item.get("updated_at", ""))[:48]})
    favoritos = [item for item in favoritos if not tombstones_favoritos.get(chave_tombo_favorito(item), {}).get("deleted", False)]
    projetos = []
    for projeto in valor.get("projects", []) if isinstance(valor.get("projects"), list) else []:
        if not isinstance(projeto, dict):
            continue
        nome = str(projeto.get("name", "")).strip()[:64]
        if not nome:
            continue
        buscas_projeto = normalizar_dados_locais({"history": projeto.get("searches", [])}).get("history", [])
        fontes_projeto = []
        for fonte in projeto.get("sources", []) if isinstance(projeto.get("sources"), list) else []:
            if isinstance(fonte, dict):
                url_fonte = normalizar_url_local(fonte.get("url"))
                if url_fonte:
                    fontes_projeto.append({"title": str(fonte.get("title", "Fonte"))[:240], "url": url_fonte,
                                           "content": str(fonte.get("content", ""))[:1200]})
        projetos.append({"id": str(projeto.get("id") or uuid.uuid4().hex)[:64], "name": nome,
                         "created_at": str(projeto.get("created_at", ""))[:48],
                         "updated_at": str(projeto.get("updated_at", ""))[:48],
                         "notes_updated_at": str(projeto.get("notes_updated_at", ""))[:48],
                         "notes": str(projeto.get("notes", ""))[:12000],
                         "searches": buscas_projeto[:30], "sources": fontes_projeto[:100]})
    preferencias = valor.get("preferences") if isinstance(valor.get("preferences"), dict) else {}
    idioma = preferencias.get("language") if preferencias.get("language") in {"Português", "English", "Español"} else "Português"
    tema = preferencias.get("theme") if preferencias.get("theme") in {"Claro", "Escuro"} else "Claro"
    notas_pasta_raw = valor.get("folder_notes") if isinstance(valor.get("folder_notes"), dict) else {}
    notas_pasta = {pasta: str(notas_pasta_raw.get(pasta, ""))[:12000] for pasta in pastas if pasta in notas_pasta_raw}
    notas_pasta_atualizadas_raw = valor.get("folder_notes_updated_at") if isinstance(valor.get("folder_notes_updated_at"), dict) else {}
    notas_pasta_atualizadas = {
        pasta: str(notas_pasta_atualizadas_raw.get(pasta, ""))[:48]
        for pasta in pastas if pasta in notas_pasta_atualizadas_raw
    }
    return {"version": 1, "history": historico[:20], "favorites": favoritos[:100], "folders": pastas[:30],
            "projects": projetos[:20], "folder_notes": notas_pasta,
            "folder_notes_updated_at": notas_pasta_atualizadas,
            "sync_tombstones": {"history": tombstones_historico, "favorites": tombstones_favoritos},
            "preferences": {"language": idioma, "theme": tema}}


def marcar_dados_locais_alterados():
    st.session_state.dados_locais_revisao += 1
    st.session_state.dados_locais_pendente = True


def registrar_tombo_local(categoria, chave):
    if not chave:
        return
    tombstones = st.session_state.dados_locais.setdefault(
        "sync_tombstones", {"history": {}, "favorites": {}}
    )
    acoes = tombstones.setdefault(categoria, {})
    acoes[chave] = {
        "deleted": True, "at": datetime.now().astimezone().isoformat(timespec="seconds")
    }
    tombstones[categoria] = dict(sorted(acoes.items(), key=lambda par: par[1].get("at", ""), reverse=True)[:1000])


def remover_tombo_local(categoria, chave):
    tombstones = st.session_state.dados_locais.setdefault(
        "sync_tombstones", {"history": {}, "favorites": {}}
    )
    acoes = tombstones.setdefault(categoria, {})
    acoes[chave] = {
        "deleted": False, "at": datetime.now().astimezone().isoformat(timespec="seconds")
    }
    tombstones[categoria] = dict(sorted(acoes.items(), key=lambda par: par[1].get("at", ""), reverse=True)[:1000])


def configurar_conta():
    """Lê credenciais públicas apenas dos Secrets ou ambiente do servidor."""
    def segredo(nome):
        try:
            return st.secrets.get(nome)
        except Exception:
            return None
    return carregar_configuracao(segredo)


def iniciar_sessao_conta(sessao):
    st.session_state.conta_sessao = sessao
    dados_remotos = carregar_dados(configurar_conta(), sessao)
    dados_locais = st.session_state.dados_locais
    if dados_remotos is not None:
        remoto_validado = normalizar_dados_locais(dados_remotos)
        mesclado = mesclar_dados_conta(remoto_validado, dados_locais)
        st.session_state.dados_locais = normalizar_dados_locais(mesclado)
    st.session_state.feedback_conta = "signedin"
    st.session_state.erro_sync_conta = ""
    st.session_state.historico_pesquisas = [
        item["query"] for item in st.session_state.dados_locais["history"]
    ]
    marcar_dados_locais_alterados()
    st.rerun()


def sincronizar_conta_agora():
    sessao = st.session_state.get("conta_sessao")
    if not sessao:
        return
    remoto = carregar_dados(configurar_conta(), sessao)
    if remoto is not None:
        remoto_validado = normalizar_dados_locais(remoto)
        st.session_state.dados_locais = normalizar_dados_locais(
            mesclar_dados_conta(remoto_validado, st.session_state.dados_locais)
        )
        st.session_state.historico_pesquisas = [
            item["query"] for item in st.session_state.dados_locais["history"]
        ]
    st.session_state.erro_sync_conta = ""
    marcar_dados_locais_alterados()
    st.rerun()


def abrir_pesquisa_salva(consulta):
    item = next((h for h in st.session_state.dados_locais["history"]
                 if h["query"].casefold() == str(consulta).casefold()), None)
    if item:
        st.session_state.resultado_atual = dict(item["result"])
        st.session_state.fonte_aberta = None
        st.session_state.secao_canonica = "Pesquisar"
        st.session_state.secao_display = texto_ui("section_Pesquisar")
        st.session_state.busca_pendente = None
    else:
        favorito = next((f for f in st.session_state.dados_locais["favorites"]
                         if f["type"] == "search" and f["query"].casefold() == str(consulta).casefold()), None)
        pesquisa_projeto = next((s for p in st.session_state.dados_locais["projects"]
                                 for s in p["searches"] if s["query"].casefold() == str(consulta).casefold()), None)
        resultado_salvo = favorito.get("result") if favorito else pesquisa_projeto.get("result") if pesquisa_projeto else None
        if resultado_salvo:
            st.session_state.resultado_atual = dict(resultado_salvo)
            st.session_state.fonte_aberta = None
            st.session_state.secao_canonica = "Pesquisar"
            st.session_state.secao_display = texto_ui("section_Pesquisar")
            st.session_state.busca_pendente = None
        else:
            preparar_busca_interna(consulta)


def salvar_pesquisa_atual():
    resultado = st.session_state.get("resultado_atual") or {}
    consulta = str(resultado.get("assunto", "")).strip()
    if not consulta:
        return
    favoritos = st.session_state.dados_locais["favorites"]
    existente = next((f for f in favoritos if f["type"] == "search" and f["query"].casefold() == consulta.casefold()), None)
    if existente:
        favoritos.remove(existente)
        registrar_tombo_local("favorites", chave_tombo_favorito(existente))
    else:
        remover_tombo_local("favorites", f"search:{consulta.casefold()}")
        registro = next((h for h in st.session_state.dados_locais["history"]
                         if h["query"].casefold() == consulta.casefold()), None)
        agora = datetime.now().astimezone().isoformat(timespec="seconds")
        favoritos.insert(0, {"id": uuid.uuid4().hex, "type": "search", "query": consulta,
                             "folder": "", "saved_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                             "updated_at": agora,
                             "result": registro["result"] if registro else dict(resultado)})
        del favoritos[100:]
    marcar_dados_locais_alterados()


def salvar_fonte_favorita(fonte, consulta):
    url_fonte = normalizar_url_local(fonte.get("url"))
    if not url_fonte:
        return
    favoritos = st.session_state.dados_locais["favorites"]
    existente = next((f for f in favoritos if f["type"] == "source" and f["url"] == url_fonte), None)
    if existente:
        favoritos.remove(existente)
        registrar_tombo_local("favorites", chave_tombo_favorito(existente))
    else:
        remover_tombo_local("favorites", f"source:{url_fonte.casefold()}")
        agora = datetime.now().astimezone().isoformat(timespec="seconds")
        favoritos.insert(0, {"id": uuid.uuid4().hex, "type": "source", "query": str(consulta)[:1000],
                             "title": str(fonte.get("title", "Fonte"))[:240], "url": url_fonte,
                             "content": str(fonte.get("content", ""))[:1200], "folder": "",
                             "saved_at": agora, "updated_at": agora})
        del favoritos[100:]
    marcar_dados_locais_alterados()


def remover_favorito(id_favorito):
    favorito_removido = next((item for item in st.session_state.dados_locais["favorites"]
                              if item["id"] == id_favorito), None)
    if favorito_removido:
        registrar_tombo_local("favorites", chave_tombo_favorito(favorito_removido))
    st.session_state.dados_locais["favorites"] = [
        item for item in st.session_state.dados_locais["favorites"] if item["id"] != id_favorito
    ]
    marcar_dados_locais_alterados()


def mover_favorito(id_favorito):
    pasta = st.session_state.get(f"pasta_favorito_{id_favorito}", "")
    for item in st.session_state.dados_locais["favorites"]:
        if item["id"] == id_favorito:
            item["folder"] = pasta
            item["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            break
    marcar_dados_locais_alterados()


def registrar_pesquisa_local(resultado):
    consulta = str(resultado.get("assunto", "")).strip()[:1000]
    if not consulta:
        return
    remover_tombo_local("history", consulta.casefold())
    itens = [item for item in st.session_state.dados_locais["history"]
             if item["query"].casefold() != consulta.casefold()]
    itens.insert(0, {"id": uuid.uuid4().hex, "query": consulta,
                     "saved_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                     "result": resultado})
    st.session_state.dados_locais = normalizar_dados_locais({
        **st.session_state.dados_locais, "history": itens[:20]
    })
    st.session_state.historico_pesquisas = [item["query"] for item in st.session_state.dados_locais["history"]]
    marcar_dados_locais_alterados()


def remover_pesquisa_historico(consulta):
    registrar_tombo_local("history", str(consulta).strip().casefold()[:1000])
    st.session_state.dados_locais["history"] = [
        item for item in st.session_state.dados_locais["history"]
        if item["query"].casefold() != str(consulta).casefold()
    ]
    st.session_state.historico_pesquisas = [item["query"] for item in st.session_state.dados_locais["history"]]
    marcar_dados_locais_alterados()


def criar_pasta_local():
    nome = str(st.session_state.get("nome_nova_pasta", "")).strip()[:48]
    pastas = st.session_state.dados_locais["folders"]
    if nome and nome.casefold() not in {pasta.casefold() for pasta in pastas} and len(pastas) < 30:
        pastas.append(nome)
        st.session_state.feedback_pasta = "created"
        marcar_dados_locais_alterados()
    elif nome:
        st.session_state.feedback_pasta = "duplicate"


def limpar_historico_local():
    for item in st.session_state.dados_locais["history"]:
        registrar_tombo_local("history", item["query"].casefold())
    st.session_state.historico_pesquisas = []
    st.session_state.dados_locais["history"] = []
    st.session_state.feedback_historico_apagado = True
    marcar_dados_locais_alterados()


def criar_projeto_local():
    nome = str(st.session_state.get("nome_novo_projeto", "")).strip()[:64]
    projetos = st.session_state.dados_locais["projects"]
    if nome and nome.casefold() not in {p["name"].casefold() for p in projetos} and len(projetos) < 20:
        projeto = {"id": uuid.uuid4().hex, "name": nome,
                   "created_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                   "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                   "notes_updated_at": "", "notes": "", "searches": [], "sources": []}
        projetos.insert(0, projeto)
        st.session_state.projeto_selecionado_id = projeto["id"]
        st.session_state.feedback_projeto = "created"
        marcar_dados_locais_alterados()
    elif nome:
        st.session_state.feedback_projeto = "duplicate"


def adicionar_pesquisa_ao_projeto(id_projeto):
    resultado = st.session_state.get("resultado_atual") or {}
    consulta = str(resultado.get("assunto", "")).strip()
    projeto = next((p for p in st.session_state.dados_locais["projects"] if p["id"] == id_projeto), None)
    if not projeto or not consulta:
        return
    projeto["searches"] = [s for s in projeto["searches"] if s["query"].casefold() != consulta.casefold()]
    projeto["searches"].insert(0, {"id": uuid.uuid4().hex, "query": consulta,
                                  "saved_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                                  "result": normalizar_dados_locais({"history": [{"query": consulta, "result": resultado}]})["history"][0]["result"]})
    projeto["searches"] = projeto["searches"][:30]
    projeto["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    conhecidas = {f["url"] for f in projeto["sources"]}
    for fonte in resultado.get("fontes", []):
        url_fonte = normalizar_url_local(fonte.get("url"))
        if url_fonte and url_fonte not in conhecidas:
            projeto["sources"].append({"title": str(fonte.get("title", "Fonte"))[:240],
                                       "url": url_fonte, "content": str(fonte.get("content", ""))[:1200]})
            conhecidas.add(url_fonte)
    projeto["sources"] = projeto["sources"][:100]
    st.session_state.feedback_projeto = "item_added"
    marcar_dados_locais_alterados()


def salvar_notas_projeto(id_projeto):
    projeto = next((p for p in st.session_state.dados_locais["projects"] if p["id"] == id_projeto), None)
    if projeto:
        projeto["notes"] = str(st.session_state.get(f"notas_projeto_{id_projeto}", ""))[:12000]
        projeto["notes_updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        projeto["updated_at"] = projeto["notes_updated_at"]
        st.session_state.feedback_projeto = "notes_saved"
        marcar_dados_locais_alterados()


def salvar_notas_pasta(nome_pasta):
    notas = st.session_state.get(f"notas_pasta_{nome_pasta}", "")
    st.session_state.dados_locais["folder_notes"][nome_pasta] = str(notas)[:12000]
    st.session_state.dados_locais.setdefault("folder_notes_updated_at", {})[nome_pasta] = datetime.now().astimezone().isoformat(timespec="seconds")
    st.session_state.feedback_pasta = "notes_saved"
    marcar_dados_locais_alterados()


if "historico_pesquisas" not in st.session_state:
    st.session_state.historico_pesquisas = []
if "cache_buscas" not in st.session_state:
    st.session_state.cache_buscas = {}
if "resultado_atual" not in st.session_state:
    st.session_state.resultado_atual = None
if "videos_adicionais" not in st.session_state:
    st.session_state.videos_adicionais = []
if "assunto_videos_adicionais" not in st.session_state:
    st.session_state.assunto_videos_adicionais = None
if "erro_videos_adicionais" not in st.session_state:
    st.session_state.erro_videos_adicionais = False
if "fonte_aberta" not in st.session_state:
    st.session_state.fonte_aberta = None
if "busca_pendente" not in st.session_state:
    st.session_state.busca_pendente = None

if "dados_locais" not in st.session_state:
    st.session_state.dados_locais = estado_local_vazio()
if "dados_locais_carregados" not in st.session_state:
    st.session_state.dados_locais_carregados = False
if "dados_locais_pendente" not in st.session_state:
    st.session_state.dados_locais_pendente = False
if "dados_locais_revisao" not in st.session_state:
    st.session_state.dados_locais_revisao = 0
if "erro_dados_locais" not in st.session_state:
    st.session_state.erro_dados_locais = ""
if "conta_sessao" not in st.session_state:
    st.session_state.conta_sessao = None
if "ultima_revisao_sync_conta" not in st.session_state:
    st.session_state.ultima_revisao_sync_conta = -1
if "erro_sync_conta" not in st.session_state:
    st.session_state.erro_sync_conta = ""
if "feedback_conta" not in st.session_state:
    st.session_state.feedback_conta = ""
if "token_recuperacao_conta" not in st.session_state:
    st.session_state.token_recuperacao_conta = ""
if "id_callback_conta_processado" not in st.session_state:
    st.session_state.id_callback_conta_processado = ""

resultado_callback_conta = componente_callback_conta(default=None, key="knowix_auth_callback", height=1)
if (
    isinstance(resultado_callback_conta, dict)
    and resultado_callback_conta.get("kind") == "password_recovery"
    and resultado_callback_conta.get("id") != st.session_state.id_callback_conta_processado
):
    st.session_state.id_callback_conta_processado = str(resultado_callback_conta.get("id", ""))[:80]
    st.session_state.token_recuperacao_conta = str(resultado_callback_conta.get("access_token", ""))[:4096]
    st.session_state.secao_canonica = "Configurações"
    st.session_state.secao_display = TRADUCOES_UI[st.session_state.idioma_visual]["section_Configurações"]

acao_storage = "load" if not st.session_state.dados_locais_carregados else "save" if st.session_state.dados_locais_pendente else "idle"
resposta_storage = componente_dados_locais(
    action=acao_storage,
    data=st.session_state.dados_locais,
    revision=st.session_state.dados_locais_revisao,
    default=None,
    key="knowix_browser_storage",
    height=1,
)
if isinstance(resposta_storage, dict):
    if resposta_storage.get("kind") == "loaded" and not st.session_state.dados_locais_carregados:
        dados_navegador = normalizar_dados_locais(resposta_storage.get("data"))
        if st.session_state.dados_locais_pendente:
            dados_em_edicao = st.session_state.dados_locais
            historico = list(dados_em_edicao["history"])
            consultas_presentes = {item["query"].casefold() for item in historico}
            historico.extend(item for item in dados_navegador["history"] if item["query"].casefold() not in consultas_presentes)
            favoritos = list(dados_em_edicao["favorites"])
            ids_presentes = {item["id"] for item in favoritos}
            favoritos.extend(item for item in dados_navegador["favorites"] if item["id"] not in ids_presentes)
            pastas = list(dados_em_edicao["folders"])
            pastas.extend(item for item in dados_navegador["folders"] if item.casefold() not in {p.casefold() for p in pastas})
            projetos = st.session_state.dados_locais.get("projects", [])
            ids_projetos = {p["id"] for p in projetos}
            nomes_projetos = {p["name"].casefold() for p in projetos}
            projetos.extend(p for p in dados_navegador["projects"]
                            if p["id"] not in ids_projetos and p["name"].casefold() not in nomes_projetos)
            notas_pasta = {**dados_navegador["folder_notes"], **dados_em_edicao.get("folder_notes", {})}
            notas_pasta_atualizadas = {
                **dados_navegador.get("folder_notes_updated_at", {}),
                **dados_em_edicao.get("folder_notes_updated_at", {}),
            }
            tombstones_navegador = dados_navegador.get("sync_tombstones", {})
            tombstones_em_edicao = dados_em_edicao.get("sync_tombstones", {})
            tombstones = {}
            for categoria in ("history", "favorites"):
                combinados = dict(tombstones_navegador.get(categoria, {}))
                for chave, acao in tombstones_em_edicao.get(categoria, {}).items():
                    anterior = combinados.get(chave)
                    if anterior is None or str(acao.get("at", "")) >= str(anterior.get("at", "")):
                        combinados[chave] = acao
                tombstones[categoria] = dict(sorted(
                    combinados.items(), key=lambda par: par[1].get("at", ""), reverse=True
                )[:1000])
            preferencia_local = (
                dados_em_edicao.get("preferences", {})
                if st.session_state.get("preferencias_locais_tocadas")
                else dados_navegador.get("preferences", {})
            )
            st.session_state.dados_locais = normalizar_dados_locais({
                "history": historico, "favorites": favoritos, "folders": pastas,
                "projects": projetos, "folder_notes": notas_pasta,
                "folder_notes_updated_at": notas_pasta_atualizadas,
                "sync_tombstones": tombstones, "preferences": preferencia_local,
            })
        else:
            st.session_state.dados_locais = dados_navegador
        preferencias_salvas = st.session_state.dados_locais["preferences"]
        preferencia_mudou = (
            st.session_state.idioma_visual != preferencias_salvas["language"]
            or st.session_state.tema_visual != preferencias_salvas["theme"]
        )
        st.session_state.idioma_visual = preferencias_salvas["language"]
        st.session_state.tema_visual = preferencias_salvas["theme"]
        st.session_state.dados_locais_carregados = True
        st.session_state.historico_pesquisas = [item["query"] for item in st.session_state.dados_locais["history"]]
        if st.session_state.dados_locais_pendente or preferencia_mudou:
            st.rerun()
    elif resposta_storage.get("kind") == "saved" and resposta_storage.get("revision") == st.session_state.dados_locais_revisao:
        st.session_state.dados_locais_pendente = False
        sessao_conta = st.session_state.get("conta_sessao")
        if sessao_conta and st.session_state.ultima_revisao_sync_conta != st.session_state.dados_locais_revisao:
            try:
                salvar_dados(configurar_conta(), sessao_conta, st.session_state.dados_locais)
                st.session_state.ultima_revisao_sync_conta = st.session_state.dados_locais_revisao
                st.session_state.erro_sync_conta = ""
            except ErroContaKnowix as erro:
                st.session_state.ultima_revisao_sync_conta = st.session_state.dados_locais_revisao
                st.session_state.erro_sync_conta = str(erro)
    elif resposta_storage.get("kind") == "error":
        st.session_state.erro_dados_locais = resposta_storage.get("reason", "storage")

with st.container(key="language-control", horizontal=True, horizontal_alignment="right", gap=0):
    st.selectbox(
        "🌐 Idioma" if st.session_state.idioma_visual != "English" else "🌐 Language",
        ["Português", "English", "Español"],
        key="idioma_visual",
        format_func=lambda idioma: f"🌐 {idioma}",
        label_visibility="collapsed",
        width=124,
        on_change=sincronizar_idioma_selecionado,
    )

st.markdown(
    f"""
    <div class="brand-row">
      <div class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 24V8m0 9 9-9m-9 9 10 7" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><path d="m23 10 1.25 3.75L28 15l-3.75 1.25L23 20l-1.25-3.75L18 15l3.75-1.25L23 10Z" fill="currentColor"/></svg></div><div class="brand-name">Knowix</div>
    </div>
    """,
    unsafe_allow_html=True,
)
if st.session_state.erro_dados_locais:
    st.warning(texto_ui("storage_error"))


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
    comparacao = detectar_comparacao(pergunta)
    consulta = f"{pergunta}. Responda de forma direta e em português brasileiro."
    if comparacao:
        consulta = (
            f"Compare {comparacao['opcao_a']} e {comparacao['opcao_b']} com as informações atuais encontradas. "
            "Organize em tabela quando houver dados para isso, indique claramente o que não foi localizado, "
            "não invente valores nem especificações e conclua conforme diferentes perfis de uso. Responda em português brasileiro."
        )
    dados = {
        "query": consulta,
        "topic": "general",
        "search_depth": "basic",
        # Menos resultados reduz a resposta do serviço e mantém fontes suficientes.
        "max_results": 5,
        "include_answer": "advanced" if comparacao else "basic",
        "include_raw_content": False,
        "include_published_date": True,
        "include_images": True,
        "include_image_descriptions": True,
        "country": "brazil",
        "language": "pt",
        "filter_by_language": False,
        "safe_search": True,
    }
    resposta = requests.post(url, headers=cabecalhos, json=dados, timeout=(3, 9))
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
        timeout=(3, 9),
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


def pesquisar_videos_youtube(assunto, limite=8, rapido=False):
    """Retorna vídeos do YouTube para mostrar prévias dentro do Knowix."""
    opcoes = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist" if rapido else False,
        "ignoreerrors": True,
        "noplaylist": True,
        "socket_timeout": 4,
        "retries": 0,
        "extractor_retries": 0,
        "fragment_retries": 0,
    }
    with yt_dlp.YoutubeDL(opcoes) as youtube:
        resultado = youtube.extract_info(f"ytsearch{limite}:{assunto}", download=False)
    videos = []
    vistos = set()
    for item in (resultado or {}).get("entries", []):
        if not item or not re.fullmatch(r"[A-Za-z0-9_-]{11}", item.get("id", "")):
            continue
        if item["id"] in vistos:
            continue
        vistos.add(item["id"])
        videos.append({
            "id": item["id"],
            "title": item.get("title") or texto_ui("related_video"),
            "channel": item.get("channel") or item.get("uploader"),
            "view_count": item.get("view_count"),
        })
    return sorted(videos, key=lambda item: item.get("view_count") or 0, reverse=True)


@st.cache_data(ttl=1800, show_spinner=False)
def pesquisar_video_youtube(assunto):
    """Guarda por 30 minutos a prévia pública para acelerar buscas repetidas."""
    videos = pesquisar_videos_youtube(assunto, limite=5, rapido=True)
    if not videos:
        return None
    return videos[0]


def encurtar(texto, limite):
    texto = " ".join((texto or "").split())
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def html_leitura_em_voz_alta(texto, idioma, rotulo_ouvir, rotulo_parar, rotulo_indisponivel):
    """Leitura local no navegador com SpeechSynthesis; o texto não é enviado a serviços."""
    texto_seguro = json.dumps(texto or "").replace("<", "\\u003c")
    idioma_seguro = json.dumps(idioma)
    ouvir_seguro = json.dumps(rotulo_ouvir)
    indisponivel_seguro = json.dumps(rotulo_indisponivel)
    return f"""<div class="knowix-speech-controls">
<style>.knowix-speech-controls{{font:500 14px Arial,sans-serif}}.knowix-speech-controls button{{border:1px solid #d6deeb;border-radius:12px;background:#fff;color:#193458;padding:10px 14px;margin-right:8px;cursor:pointer}}.knowix-speech-controls #status{{color:#52627a}}</style>
<button id="play" type="button">{escape(rotulo_ouvir)}</button><button id="stop" type="button">{escape(rotulo_parar)}</button><span id="status" role="status" aria-live="polite"></span>
<script>
const answer={texto_seguro}, lang={idioma_seguro}, unavailable={indisponivel_seguro};
const status=document.getElementById('status');
document.getElementById('play').addEventListener('click',()=>{{
 if(!('speechSynthesis' in window)){{status.textContent=unavailable;return;}}
 window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(answer);utterance.lang=lang;
 utterance.onerror=()=>{{status.textContent=unavailable;}};window.speechSynthesis.speak(utterance);
}});
document.getElementById('stop').addEventListener('click',()=>{{if('speechSynthesis' in window)window.speechSynthesis.cancel();}});
</script></div>"""


def preparar_busca_interna(assunto):
    """Agenda uma busca sugerida sem sair do Knowix."""
    st.session_state.busca_pendente = assunto
    st.session_state.pergunta_principal = assunto
    st.session_state.fonte_aberta = None
    st.session_state.secao_canonica = "Pesquisar"
    st.session_state.secao_display = texto_ui("section_Pesquisar")


def preparar_pergunta_complementar(assunto_anterior):
    """Continua a pesquisa com contexto limitado e sempre exige uma nova busca de fontes."""
    pergunta = str(st.session_state.get("pergunta_complementar", "")).strip()[:500]
    if not pergunta:
        return
    resultado = st.session_state.get("resultado_atual") or {}
    resposta_anterior = str(resultado.get("resposta", "")).strip()[:700]
    titulos_fontes = "; ".join(
        str(fonte.get("title", ""))[:100]
        for fonte in (resultado.get("fontes") or [])[:3]
        if fonte.get("title")
    )
    contexto = f"Pergunta anterior: {assunto_anterior}. "
    if resposta_anterior:
        contexto += f"Contexto da resposta anterior (confirme em fontes novas): {resposta_anterior}. "
    if titulos_fontes:
        contexto += f"Fontes consultadas antes: {titulos_fontes}. "
    contexto += f"Pergunta complementar: {pergunta}. Valide a resposta com as fontes desta nova pesquisa."
    st.session_state.busca_pendente = {"consulta": contexto[:2200], "exibicao": pergunta}
    st.session_state.pergunta_principal = pergunta
    st.session_state.fonte_aberta = None
    st.session_state.secao_canonica = "Pesquisar"
    st.session_state.secao_display = texto_ui("section_Pesquisar")


def abrir_fonte_no_knowix(fonte):
    st.session_state.fonte_aberta = fonte


def buscar_resultados(assunto, chave_tavily, modo="rapida", progresso=None):
    """Busca web e vídeo em paralelo e mantém cache por modo na sessão por 10 minutos."""
    modo = "profunda" if modo == "profunda" and chave_tavily else "rapida"
    chave_cache = f"{modo}:{assunto.strip().casefold()}"
    cache = st.session_state.cache_buscas
    agora = time.monotonic()
    item_cache = cache.get(chave_cache)
    if item_cache and agora - item_cache["instante"] < 600:
        return item_cache["dados"], True
    if item_cache:
        cache.pop(chave_cache, None)

    if not reservar_cota_pesquisa(modo):
        chave_aviso = "rate_limit_deep" if modo == "profunda" else "rate_limit_quick"
        return {
            "assunto": assunto,
            "comparacao": detectar_comparacao(assunto),
            "modo_pesquisa": modo,
            "uso_pesquisa": {},
            "pesquisa_expirada_na_sessao": False,
            "resposta": "",
            "resposta_gerada_por_ia": False,
            "fontes": [],
            "imagens": [],
            "video": None,
            "avisos": [texto_ui(chave_aviso)],
            "status_pesquisa": "erro",
        }, False

    resposta_direta = ""
    resposta_gerada_por_ia = False
    fontes = []
    imagens = []
    video = None
    avisos = []
    falha_busca = False
    falha_timeout = False
    busca_concluida = False
    consultado_em = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
    comparacao = detectar_comparacao(assunto)
    pesquisa_profunda = False
    uso_pesquisa = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        if chave_tavily and modo == "profunda":
            fila_progresso = queue.Queue()
            busca_web = executor.submit(pesquisar_profundamente, assunto, chave_tavily, fila_progresso)
            pesquisa_profunda = True
        elif chave_tavily:
            busca_web = executor.submit(pesquisar_na_web, assunto, chave_tavily)
        else:
            busca_web = executor.submit(pesquisar_wikipedia, assunto)
        busca_video = executor.submit(pesquisar_video_youtube, f"{assunto} em português")

        try:
            if pesquisa_profunda:
                while not busca_web.done():
                    try:
                        mensagem = fila_progresso.get(timeout=0.3)
                        if progresso:
                            progresso(mensagem)
                    except queue.Empty:
                        continue
                while not fila_progresso.empty():
                    if progresso:
                        progresso(fila_progresso.get_nowait())
                    else:
                        fila_progresso.get_nowait()
            dados_web = busca_web.result()
            busca_concluida = True
            if pesquisa_profunda:
                resposta_direta = dados_web.get("answer", "")
                resposta_gerada_por_ia = bool(resposta_direta)
                fontes = dados_web.get("results", [])
                uso_pesquisa = dados_web.get("usage", {})
                if not fontes:
                    resposta_direta = ""
                    resposta_gerada_por_ia = False
            elif chave_tavily:
                resposta_direta = (dados_web.get("answer") or "").strip()
                resposta_gerada_por_ia = bool(resposta_direta)
                for item in dados_web.get("results", []):
                    url_fonte = normalizar_url_http(item.get("url", ""))
                    if url_fonte:
                        fonte = {
                            "title": item.get("title") or "Abrir resultado",
                            "url": url_fonte,
                            "content": item.get("content", ""),
                            "domain": urlparse(url_fonte).netloc.removeprefix("www."),
                            "published_date": item.get("published_date"),
                            "consulted_at": consultado_em,
                        }
                        fonte["category"] = classificar_fonte(fonte)
                        fontes.append(fonte)
                for item in dados_web.get("images", []):
                    imagem_bruta = item.get("url", "") if isinstance(item, dict) else str(item)
                    url_imagem = normalizar_url_http(imagem_bruta, somente_https=True)
                    if url_imagem:
                        imagens.append({
                            "url": url_imagem,
                            "description": str(item.get("description", ""))[:300] if isinstance(item, dict) else "",
                        })
                    if len(imagens) >= 12:
                        break
                if not fontes:
                    resposta_direta = ""
                    resposta_gerada_por_ia = False
            elif dados_web:
                pagina = escolher_pagina_principal(dados_web, assunto)
                resposta_direta = (pagina.get("extract") or "").strip()
                fontes = [
                    {
                        "title": item.get("title", "Abrir resultado"),
                        "url": normalizar_url_http(item.get("fullurl", "")),
                        "content": item.get("extract", ""),
                        "domain": "pt.wikipedia.org",
                        "category": "site",
                        "published_date": None,
                        "consulted_at": consultado_em,
                    }
                    for item in dados_web
                    if normalizar_url_http(item.get("fullurl", ""))
                ]
                avisos.append(
                    "A pesquisa geral ainda não está configurada. No momento, mostro resultados da Wikipédia em português."
                )
        except TimeoutError:
            falha_busca = True
            falha_timeout = True
            avisos.append("A pesquisa profunda ainda está sendo processada pelo serviço; tente novamente mais tarde.")
        except ValueError as erro:
            falha_busca = True
            avisos.append(str(erro))
        except requests.exceptions.RequestException:
            falha_busca = True
            avisos.append("A pesquisa de fontes está indisponível no momento.")
        except Exception:
            falha_busca = True
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
        "comparacao": comparacao,
        "modo_pesquisa": modo,
        "uso_pesquisa": uso_pesquisa,
        "pesquisa_expirada_na_sessao": falha_timeout,
        "resposta": resposta_direta,
        "resposta_gerada_por_ia": resposta_gerada_por_ia,
        "fontes": fontes,
        "imagens": imagens,
        "video": video,
        "avisos": avisos,
        "status_pesquisa": "erro" if falha_busca else "concluida" if fontes or imagens else "sem_resultados" if busca_concluida else "erro",
    }
    if not falha_timeout:
        cache[chave_cache] = {"instante": time.monotonic(), "dados": dados}
    if len(cache) > 20:
        cache.pop(next(iter(cache)))
    return dados, False


SECOES_APP = ["Pesquisar", "Nova aba", "Histórico", "Favoritos", "Pastas", "Projetos", "Configurações", "Sobre o app", "Sugestões"]
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
modo_pesquisa_selecionado = "rapida"
chave_tavily_configurada = obter_chave_tavily()
if secao_app in ("Pesquisar", "Nova aba"):
    rotulo_modo_rapido = texto_ui("research_mode_quick")
    rotulo_modo_profundo = texto_ui("research_mode_deep")
    modos_disponiveis = [rotulo_modo_rapido, rotulo_modo_profundo] if chave_tavily_configurada else [rotulo_modo_rapido]
    if st.session_state.get("modo_pesquisa_opcao") not in modos_disponiveis:
        st.session_state.modo_pesquisa_opcao = rotulo_modo_rapido


    if secao_app in ("Pesquisar", "Nova aba") and not st.session_state.resultado_atual:
        with st.container(key="search-hero"):
            st.markdown(
                f'<h1 class="search-hero-title">{escape(texto_ui("search_hero_title"))}</h1>'
                f'<p class="search-hero-caption">{escape(texto_ui("search_hero_caption"))}</p>',
                unsafe_allow_html=True,
            )

if secao_app == "Pesquisar":
    # Fail closed: no image provider is enabled before adult-only access is assured.
    chave_visao = ""
    with st.expander(f"🖼️ {texto_ui('image_title')}"):
        st.caption(texto_ui("image_caption"))
        st.caption(texto_ui("image_missing_key"))
        imagem_enviada = st.file_uploader(
            texto_ui("image_upload"),
            type=["jpg", "jpeg", "png", "webp"],
            max_upload_size=8,
            disabled=True,
            key="knowix_image_upload",
        )
        pergunta_imagem = st.text_input(
            texto_ui("image_question"),
            placeholder=texto_ui("image_question_hint"),
            max_chars=1000,
            key="knowix_image_question",
        )
        analisar = st.button(
            texto_ui("image_analyze"),
            disabled=True,
            key="knowix_analyze_image",
            use_container_width=True,
        )
        if analisar:
            if not reservar_cota_pesquisa("imagem"):
                st.warning(texto_ui("image_rate_limit"))
            else:
                try:
                    with st.spinner(texto_ui("image_analyze") + "…"):
                        st.session_state.analise_imagem = analisar_imagem(
                            imagem_enviada.getvalue(), pergunta_imagem, chave_visao,
                            model=modelo_visao, mime_informado=imagem_enviada.type,
                        )
                        st.session_state.analise_imagem_consulta = pergunta_imagem.strip()
                except ErroVisaoKnowix as erro:
                    st.session_state.analise_imagem = ""
                    st.error(str(erro))
                except Exception:
                    st.session_state.analise_imagem = ""
                    st.error(texto_ui("image_error"))
        analise_atual = st.session_state.get("analise_imagem", "")
        if analise_atual:
            st.markdown(f"#### {texto_ui('image_analysis')}")
            st.markdown(analise_atual)
            consulta_visual = st.text_input(
                texto_ui("search_placeholder"),
                value=st.session_state.get("analise_imagem_consulta") or analise_atual[:180],
                max_chars=500,
                key="knowix_image_web_query",
            )
            if st.button(texto_ui("image_web_search"), key="knowix_image_web_search") and consulta_visual.strip():
                st.session_state.busca_pendente = {
                    "consulta": consulta_visual.strip(),
                    "exibicao": consulta_visual.strip(),
                }
                st.session_state.resultado_atual = None
                st.rerun()
    codigo_idioma_voz = {
        "Português": "pt-BR",
        "English": "en-US",
        "Español": "es-ES",
    }[st.session_state.idioma_visual]
    textos_voz = {
        "Português": {
            "button": "Pesquisar por voz", "listening": "Ouvindo…", "stop": "Parar de ouvir",
            "recognized": "Fala reconhecida. Confira o texto e toque em Pesquisar.",
            "unsupported": "Este navegador não oferece pesquisa por voz.",
            "permission": "Permita o microfone para usar a pesquisa por voz.",
            "error": "Não consegui reconhecer sua fala. Tente novamente.",
            "privacy": "O áudio pode ser enviado ao serviço de reconhecimento do navegador ou dispositivo. O Knowix recebe o texto e só pesquisa após sua confirmação.",
        },
        "English": {
            "button": "Search by voice", "listening": "Listening…", "stop": "Stop listening",
            "recognized": "Speech recognized. Review the text and select Search.",
            "unsupported": "Voice search is unavailable in this browser.",
            "permission": "Allow microphone access to use voice search.",
            "error": "I couldn't recognize your speech. Please try again.",
            "privacy": "Audio may be sent to your browser's or device's recognition service. Knowix receives the text and searches only after you confirm.",
        },
        "Español": {
            "button": "Buscar por voz", "listening": "Escuchando…", "stop": "Dejar de escuchar",
            "recognized": "Voz reconocida. Revisa el texto y pulsa Buscar.",
            "unsupported": "Este navegador no ofrece búsqueda por voz.",
            "permission": "Permite el micrófono para usar la búsqueda por voz.",
            "error": "No pude reconocer tu voz. Inténtalo de nuevo.",
            "privacy": "El audio puede enviarse al servicio de reconocimiento del navegador o dispositivo. Knowix recibe el texto y busca solo cuando confirmes.",
        },
    }[st.session_state.idioma_visual]
    textos_voz["theme"] = "dark" if tema_escuro else "light"
    textos_voz["privacy_note"] = {
        "Português": "O áudio pode ser enviado ao serviço de reconhecimento do navegador ou dispositivo. O Knowix recebe apenas a transcrição e pesquisa após sua confirmação.",
        "English": "Audio may be sent to your browser's or device's recognition service. Knowix receives only the transcript and searches after you confirm.",
        "Español": "El audio puede enviarse al servicio de reconocimiento del navegador o dispositivo. Knowix recibe solo la transcripción y busca cuando confirmes.",
    }[st.session_state.idioma_visual]
    with st.container(key="search-action-row"):
        col_busca, col_voz = st.columns([8, 2], vertical_alignment="center", gap="small")
        # Keep the voice bridge before the query widget so Android transcripts
        # can initialize the input before Streamlit creates it.
        with col_voz:
            resultado_voz = componente_pesquisa_por_voz(
                language=codigo_idioma_voz,
                labels=textos_voz,
                default=None,
                key="pesquisa_por_voz",
                height=80,
            )
        if isinstance(resultado_voz, dict):
            texto_reconhecido = str(resultado_voz.get("transcript", "")).strip()
            id_reconhecimento = resultado_voz.get("id")
            if texto_reconhecido and id_reconhecimento != st.session_state.get("voz_processada_id"):
                st.session_state.pergunta_principal = texto_reconhecido[:1000]
                st.session_state.voz_processada_id = id_reconhecimento

        with col_busca:
            with st.form("formulario_pesquisa", clear_on_submit=False):
                campo_busca, coluna_botao = st.columns([7.2, 2], vertical_alignment="center", gap="small")
                with campo_busca:
                    pergunta = st.text_input(
                        "Search" if st.session_state.idioma_visual == "English" else "Buscar" if st.session_state.idioma_visual == "Español" else "Pesquisa",
                        label_visibility="collapsed",
                        placeholder=texto_ui("search_placeholder"),
                        max_chars=1000,
                        key="pergunta_principal",
                    )
                with coluna_botao:
                    buscar = st.form_submit_button(texto_ui("search_button"), use_container_width=True)
        st.caption(textos_voz["privacy_note"])


elif secao_app == "Nova aba":
    st.markdown(f"### {texto_ui('new_search_title')}")
    st.caption(texto_ui("new_search_caption"))
    with st.form("formulario_nova_aba", clear_on_submit=False):
        pergunta_nova = st.text_input(
            "What would you like to search?" if st.session_state.idioma_visual == "English" else "¿Qué quieres buscar?" if st.session_state.idioma_visual == "Español" else texto_ui("new_search_label"),
            placeholder=texto_ui("new_search_placeholder"),
            max_chars=1000,
            key="pergunta_nova_aba",
        )
        buscar_nova = st.form_submit_button(texto_ui("new_search_button"), use_container_width=True)
    if buscar_nova:
        pergunta = pergunta_nova
        buscar = True

    with st.container(key="search-mode"):
        modo_escolhido = st.radio(
            texto_ui("research_mode_label"),
            modos_disponiveis,
            horizontal=True,
            key="modo_pesquisa_opcao",
        )
        modo_pesquisa_selecionado = "profunda" if modo_escolhido == rotulo_modo_profundo else "rapida"
        if modo_pesquisa_selecionado == "profunda":
            st.caption(texto_ui("deep_cost_note"))
        elif not chave_tavily_configurada:
            st.caption(texto_ui("deep_needs_key"))
if secao_app == "Pesquisar" and not st.session_state.resultado_atual:
    with st.container(key="search-history"):
        st.markdown(f"#### {texto_ui('recent_home')}")
        pesquisas_recentes = st.session_state.historico_pesquisas[:4]
        if pesquisas_recentes:
            colunas_recentes = st.columns(min(2, len(pesquisas_recentes)), gap="small")
            for indice, pesquisa_recente in enumerate(pesquisas_recentes):
                with colunas_recentes[indice % len(colunas_recentes)]:
                    st.button(
                        encurtar(pesquisa_recente, 64),
                        key=f"pesquisa_recente_inicio_{indice}",
                        on_click=abrir_pesquisa_salva,
                        args=(pesquisa_recente,),
                        use_container_width=True,
                    )
        else:
            st.caption(texto_ui("recent_home_empty"))

busca_pendente = st.session_state.busca_pendente
if busca_pendente:
    if isinstance(busca_pendente, dict):
        pergunta = busca_pendente.get("consulta", "")
        pergunta_exibida = busca_pendente.get("exibicao", pergunta)
    else:
        pergunta = busca_pendente
        pergunta_exibida = pergunta
    buscar = True
    st.session_state.busca_pendente = None
else:
    pergunta_exibida = pergunta

if buscar and pergunta.strip():
    st.session_state.videos_adicionais = []
    st.session_state.assunto_videos_adicionais = None
    st.session_state.erro_videos_adicionais = False
    st.session_state.filtro_resultados = "all"
    termo_historico = pergunta_exibida.strip()
    historico_atualizado = [termo_historico] + [
        item for item in st.session_state.historico_pesquisas
        if item.casefold() != termo_historico.casefold()
    ]
    st.session_state.historico_pesquisas = historico_atualizado[:20]

elif secao_app == "Histórico":
    st.markdown(f"### {texto_ui('history_title')}")
    st.caption(texto_ui("local_storage_notice"))
    filtro_historico = st.text_input(texto_ui("history_filter"), key="filtro_historico")
    if st.session_state.historico_pesquisas:
        itens_visiveis = [item for item in st.session_state.historico_pesquisas
                          if filtro_historico.casefold() in item.casefold()]
        for indice, item in enumerate(itens_visiveis):
            col_abrir, col_apagar = st.columns([7, 1], gap="small")
            with col_abrir:
                st.button(
                    f"{indice + 1}. {item}", key=f"historico_{indice}",
                    on_click=abrir_pesquisa_salva, args=(item,), use_container_width=True,
                )
            with col_apagar:
                st.button(
                    "×", key=f"apagar_historico_{indice}", help=texto_ui("favorite_remove"),
                    on_click=remover_pesquisa_historico, args=(item,), use_container_width=True,
                )
    else:
        st.caption(texto_ui("history_empty"))

elif secao_app == "Favoritos":
    st.markdown(f"### {texto_ui('favorite_title')}")
    st.caption(texto_ui("local_storage_notice"))
    favoritos = st.session_state.dados_locais["favorites"]
    pastas_disponiveis = ["__all__", ""] + st.session_state.dados_locais["folders"]
    filtro_pasta = st.selectbox(
        texto_ui("folder_assign"), pastas_disponiveis,
        format_func=lambda pasta: texto_ui("folder_all") if pasta == "__all__" else texto_ui("folder_default") if not pasta else pasta,
        key="filtro_pasta_favoritos",
    )
    favoritos_visiveis = [item for item in favoritos if filtro_pasta == "__all__" or item["folder"] == filtro_pasta]
    if favoritos_visiveis:
        opcoes_pasta = [""] + st.session_state.dados_locais["folders"]
        for indice, item in enumerate(favoritos_visiveis):
            with st.container(border=True):
                st.caption(texto_ui("favorite_search_type") if item["type"] == "search" else texto_ui("favorite_source_type"))
                st.markdown(f"**{escape(item.get('query') or item.get('title', ''))}**")
                if item["type"] == "search":
                    st.button(texto_ui("favorite_open"), key=f"abrir_favorito_{item['id']}",
                              on_click=abrir_pesquisa_salva, args=(item["query"],), use_container_width=True)
                else:
                    st.link_button(item.get("title", texto_ui("favorite_source_type")), item["url"], use_container_width=True)
                    if item.get("content"):
                        st.write(encurtar(item["content"], 220))
                col_pasta, col_remover = st.columns([5, 1], gap="small")
                with col_pasta:
                    atual = item.get("folder", "")
                    if atual not in opcoes_pasta:
                        atual = ""
                    st.selectbox(
                        texto_ui("folder_assign"), opcoes_pasta, index=opcoes_pasta.index(atual),
                        format_func=lambda pasta: texto_ui("folder_default") if not pasta else pasta,
                        key=f"pasta_favorito_{item['id']}",
                        on_change=mover_favorito, args=(item["id"],),
                    )
                with col_remover:
                    st.button("×", key=f"remover_favorito_{item['id']}", help=texto_ui("favorite_remove"),
                              on_click=remover_favorito, args=(item["id"],), use_container_width=True)
    else:
        st.caption(texto_ui("favorite_empty"))

elif secao_app == "Pastas":
    st.markdown(f"### {texto_ui('folder_title')}")
    st.caption(texto_ui("local_storage_notice"))
    with st.form("form_criar_pasta", clear_on_submit=True):
        st.text_input(texto_ui("folder_name"), max_chars=48, key="nome_nova_pasta")
        st.form_submit_button(texto_ui("folder_create"), on_click=criar_pasta_local)
    if st.session_state.get("feedback_pasta") == "created":
        st.success(texto_ui("folder_added"))
        st.session_state.feedback_pasta = ""
    elif st.session_state.get("feedback_pasta") == "duplicate":
        st.info(texto_ui("folder_duplicate"))
        st.session_state.feedback_pasta = ""
    elif st.session_state.get("feedback_pasta") == "notes_saved":
        st.success(texto_ui("folder_notes_saved"))
        st.session_state.feedback_pasta = ""
    pastas = st.session_state.dados_locais["folders"]
    if pastas:
        for pasta in pastas:
            quantidade = sum(item.get("folder") == pasta for item in st.session_state.dados_locais["favorites"])
            st.markdown(f"📁 **{escape(pasta)}** · {quantidade}")
            nota_key = f"notas_pasta_{pasta}"
            if nota_key not in st.session_state:
                st.session_state[nota_key] = st.session_state.dados_locais["folder_notes"].get(pasta, "")
            with st.form(f"form_notas_pasta_{uuid.uuid5(uuid.NAMESPACE_URL, pasta).hex}"):
                st.text_area(texto_ui("folder_notes"), key=nota_key, max_chars=12000,
                             label_visibility="collapsed", height=110)
                st.form_submit_button(texto_ui("folder_save_notes"),
                                      on_click=salvar_notas_pasta, args=(pasta,))
    else:
        st.caption(texto_ui("folder_empty"))

elif secao_app == "Projetos":
    st.markdown(f"### {texto_ui('project_title')}")
    st.caption(texto_ui("local_storage_notice"))
    with st.form("form_criar_projeto", clear_on_submit=True):
        st.text_input(texto_ui("project_name"), max_chars=64, key="nome_novo_projeto")
        st.form_submit_button(texto_ui("project_create"), on_click=criar_projeto_local)
    if st.session_state.get("feedback_projeto") == "created":
        st.success(texto_ui("project_added"))
        st.session_state.feedback_projeto = ""
    elif st.session_state.get("feedback_projeto") == "duplicate":
        st.info(texto_ui("project_duplicate"))
        st.session_state.feedback_projeto = ""

    projetos = st.session_state.dados_locais["projects"]
    if projetos:
        projeto_atual_id = st.session_state.get("projeto_selecionado_id")
        if projeto_atual_id not in {p["id"] for p in projetos}:
            projeto_atual_id = projetos[0]["id"]
        projeto_atual = st.selectbox(
            texto_ui("project_select"), projetos,
            format_func=lambda p: p["name"],
            index=next(i for i, p in enumerate(projetos) if p["id"] == projeto_atual_id),
            key="projeto_selecionado",
        )
        st.session_state.projeto_selecionado_id = projeto_atual["id"]
        if st.session_state.get("feedback_projeto") == "item_added":
            st.success(texto_ui("project_added_item"))
            st.session_state.feedback_projeto = ""
        if st.session_state.get("feedback_projeto") == "notes_saved":
            st.success(texto_ui("project_notes_saved"))
            st.session_state.feedback_projeto = ""
        resultado = st.session_state.get("resultado_atual")
        if resultado and resultado.get("assunto"):
            ja_adicionada = any(s["query"].casefold() == resultado["assunto"].casefold()
                                for s in projeto_atual["searches"])
            rotulo_adicionar = texto_ui("project_add_current")
            if ja_adicionada:
                rotulo_adicionar = f"✓ {rotulo_adicionar}"
            st.button(rotulo_adicionar, key=f"adicionar_pesquisa_projeto_{projeto_atual['id']}",
                      on_click=adicionar_pesquisa_ao_projeto, args=(projeto_atual["id"],),
                      use_container_width=True)
        st.markdown(f"#### {texto_ui('project_notes')}")
        chave_notas = f"notas_projeto_{projeto_atual['id']}"
        if chave_notas not in st.session_state:
            st.session_state[chave_notas] = projeto_atual["notes"]
        with st.form(f"form_notas_projeto_{projeto_atual['id']}"):
            st.text_area(texto_ui("project_notes"), key=chave_notas, max_chars=12000,
                         label_visibility="collapsed", height=160)
            st.form_submit_button(texto_ui("project_save_notes"),
                                  on_click=salvar_notas_projeto, args=(projeto_atual["id"],))
        st.markdown(f"#### {texto_ui('project_searches')} · {len(projeto_atual['searches'])}")
        for indice, pesquisa in enumerate(projeto_atual["searches"]):
            st.button(pesquisa["query"], key=f"abrir_pesquisa_projeto_{projeto_atual['id']}_{indice}",
                      on_click=abrir_pesquisa_salva, args=(pesquisa["query"],), use_container_width=True)
        st.markdown(f"#### {texto_ui('project_sources')} · {len(projeto_atual['sources'])}")
        for indice, fonte in enumerate(projeto_atual["sources"]):
            st.link_button(fonte["title"], fonte["url"], key=f"fonte_projeto_{projeto_atual['id']}_{indice}",
                           use_container_width=True)
        if projeto_atual["searches"]:
            blocos_relatorio = [f"# {projeto_atual['name']}", "", f"## {texto_ui('project_notes')}",
                                "", projeto_atual["notes"] or "—", ""]
            for pesquisa in projeto_atual["searches"]:
                blocos_relatorio.append(conteudo_pesquisa(pesquisa["result"]))
            relatorio_projeto = "\n\n---\n\n".join(blocos_relatorio)
            nome_projeto = re.sub(r"[^\w-]+", "-", projeto_atual["name"], flags=re.UNICODE).strip("-")[:56] or "projeto"
            st.markdown(f"#### {texto_ui('project_export')}")
            col_md, col_docx, col_pdf = st.columns(3, gap="small")
            with col_md:
                st.download_button(texto_ui("export_md"), relatorio_projeto, f"knowix-projeto-{nome_projeto}.md",
                                   mime="text/markdown; charset=utf-8", key="exportar_projeto_md", use_container_width=True)
            with col_docx:
                st.download_button(texto_ui("export_docx"), gerar_docx(relatorio_projeto), f"knowix-projeto-{nome_projeto}.docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   key="exportar_projeto_docx", use_container_width=True)
            with col_pdf:
                st.download_button(texto_ui("export_pdf"), gerar_pdf(relatorio_projeto), f"knowix-projeto-{nome_projeto}.pdf",
                                   mime="application/pdf", key="exportar_projeto_pdf", use_container_width=True)
    else:
        st.caption(texto_ui("project_empty"))

elif secao_app == "Configurações":
    st.markdown(f"### {texto_ui('settings_title')}")
    textos_conta = TEXTOS_CONTA.get(st.session_state.idioma_visual, TEXTOS_CONTA["Português"])
    configuracao_conta = configurar_conta()
    st.markdown(f"#### {textos_conta['title']}")
    if not configuracao_conta.get("configured"):
        st.info(textos_conta["setup"])
    else:
        st.caption(textos_conta["privacy"])
        if st.session_state.get("token_recuperacao_conta"):
            st.markdown(f"##### {textos_conta['reset_title']}")
            with st.form("form_definir_nova_senha"):
                senha_nova = st.text_input(textos_conta["reset_password"], type="password", max_chars=128)
                confirmar_nova = st.text_input(textos_conta["confirm_new"], type="password", max_chars=128)
                redefinir = st.form_submit_button(textos_conta["reset_title"], use_container_width=True)
            if redefinir:
                if senha_nova != confirmar_nova:
                    st.error(textos_conta["password_mismatch"])
                else:
                    try:
                        alterar_senha(configuracao_conta, st.session_state.token_recuperacao_conta, senha_nova)
                        st.session_state.token_recuperacao_conta = ""
                        st.session_state.conta_sessao = None
                        st.session_state.feedback_conta = "reset_done"
                        st.rerun()
                    except ErroContaKnowix as erro:
                        st.error(str(erro))
        elif st.session_state.get("conta_sessao"):
            conta_atual = st.session_state.conta_sessao
            st.success(f"{textos_conta['logged']}: {escape(conta_atual.get('email', ''))}")
            if st.session_state.get("erro_sync_conta"):
                st.warning(f"{textos_conta['sync_fail']} {st.session_state.erro_sync_conta}")
            elif st.session_state.get("ultima_revisao_sync_conta", -1) >= 0:
                st.caption(textos_conta["sync_ok"])
            if st.session_state.get("feedback_conta"):
                chave_feedback = st.session_state.feedback_conta
                if chave_feedback in textos_conta:
                    st.success(textos_conta[chave_feedback])
                st.session_state.feedback_conta = ""
            col_sync, col_logout = st.columns(2)
            with col_sync:
                if st.button(textos_conta["sync"], key="sincronizar_conta_agora", use_container_width=True):
                    try:
                        sincronizar_conta_agora()
                    except ErroContaKnowix as erro:
                        st.session_state.erro_sync_conta = str(erro)
                        st.error(f"{textos_conta['sync_fail']} {erro}")
            with col_logout:
                if st.button(textos_conta["logout"], key="sair_conta_knowix", use_container_width=True):
                    try:
                        sair_conta(configuracao_conta, conta_atual)
                    except ErroContaKnowix:
                        pass
                    st.session_state.conta_sessao = None
                    st.session_state.ultima_revisao_sync_conta = -1
                    st.session_state.feedback_conta = "signedout"
                    st.rerun()
        else:
            if st.session_state.get("feedback_conta") == "signedout":
                st.success(textos_conta["signedout"])
                st.session_state.feedback_conta = ""
            elif st.session_state.get("feedback_conta") == "reset_done":
                st.success(textos_conta["reset_done"])
                st.session_state.feedback_conta = ""
            aba_login, aba_cadastro, aba_recuperar = st.tabs([
                textos_conta["login"], textos_conta["signup"], textos_conta["recover"]
            ])
            with aba_login:
                with st.form("form_entrar_conta"):
                    email_login = st.text_input(textos_conta["email"], key="email_entrar_conta", max_chars=254)
                    senha_login = st.text_input(textos_conta["password"], type="password", key="senha_entrar_conta", max_chars=128)
                    enviar_login = st.form_submit_button(textos_conta["login"], use_container_width=True)
                if enviar_login:
                    try:
                        iniciar_sessao_conta(entrar(configuracao_conta, email_login, senha_login))
                    except ErroContaKnowix as erro:
                        st.error(str(erro))
            with aba_cadastro:
                with st.form("form_criar_conta"):
                    email_cadastro = st.text_input(textos_conta["email"], key="email_criar_conta", max_chars=254)
                    senha_cadastro = st.text_input(textos_conta["password"], type="password", key="senha_criar_conta", max_chars=128)
                    confirmar_cadastro = st.text_input(textos_conta["confirm"], type="password", key="confirmar_criar_conta", max_chars=128)
                    enviar_cadastro = st.form_submit_button(textos_conta["signup"], use_container_width=True)
                if enviar_cadastro:
                    if senha_cadastro != confirmar_cadastro:
                        st.error(textos_conta["password_mismatch"])
                    else:
                        try:
                            resultado_cadastro = cadastrar(configuracao_conta, email_cadastro, senha_cadastro)
                            if resultado_cadastro.get("access_token"):
                                iniciar_sessao_conta(entrar(configuracao_conta, email_cadastro, senha_cadastro))
                            st.success(textos_conta["created"] if resultado_cadastro.get("access_token") else textos_conta["verify"])
                        except ErroContaKnowix as erro:
                            st.error(str(erro))
            with aba_recuperar:
                st.caption(textos_conta["recover_caption"])
                with st.form("form_recuperar_conta"):
                    email_recuperacao = st.text_input(textos_conta["email"], key="email_recuperar_conta", max_chars=254)
                    enviar_link = st.form_submit_button(textos_conta["recover"], use_container_width=True)
                if enviar_link:
                    try:
                        enviar_recuperacao(configuracao_conta, email_recuperacao)
                        st.success(textos_conta["reset_sent"])
                    except ErroContaKnowix as erro:
                        st.error(str(erro))

    st.markdown(f"#### {texto_ui('appearance')}")
    nomes_temas = {
        "Claro": "Light" if st.session_state.idioma_visual == "English" else "Claro",
        "Escuro": "Dark" if st.session_state.idioma_visual == "English" else "Oscuro" if st.session_state.idioma_visual == "Español" else "Escuro",
    }
    tema_exibido = nomes_temas[st.session_state.tema_visual]
    if st.session_state.get("tema_display") != tema_exibido:
        st.session_state.tema_display = tema_exibido
    st.radio(
        texto_ui("theme_label"),
        list(nomes_temas.values()),
        key="tema_display",
        on_change=sincronizar_tema_selecionado,
        horizontal=True,
    )
    st.caption(texto_ui("theme_caption"))
    st.markdown(f"#### {texto_ui('privacy')}")
    st.caption(texto_ui("history_privacy"))
    st.button(texto_ui("clear_history"), key="apagar_historico", on_click=limpar_historico_local)
    if st.session_state.get("feedback_historico_apagado"):
        st.success(texto_ui("history_cleared"))
        st.session_state.feedback_historico_apagado = False

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

if secao_app == "Nova aba" or (secao_app == "Pesquisar" and st.session_state.resultado_atual):
    st.markdown(
        f'<p class="search-hint">{escape(texto_ui("search_hint"))}</p>',
        unsafe_allow_html=True,
    )

if buscar:
    consulta_busca = pergunta.strip()
    assunto = pergunta_exibida.strip() or consulta_busca
    if not consulta_busca:
        st.warning(texto_ui("empty_search"))
    else:
        if modo_pesquisa_selecionado == "profunda":
            with st.status(texto_ui("deep_running"), expanded=True) as estado_pesquisa:
                dados_busca, veio_do_cache = buscar_resultados(
                    consulta_busca,
                    chave_tavily_configurada,
                    modo="profunda",
                    progresso=lambda mensagem: estado_pesquisa.write(
                        texto_ui("deep_progress").format(seconds=mensagem.split(":", 1)[1])
                        if mensagem.startswith("andamento:") else
                        texto_ui("deep_accepted") if mensagem == "accepted" else
                        texto_ui("deep_finalizing")
                    ),
                )
                estado_final = "complete" if dados_busca.get("status_pesquisa") == "concluida" else "error"
                estado_pesquisa.update(
                    label=(texto_ui("deep_complete") if estado_final == "complete" else
                           texto_ui("deep_timeout") if dados_busca.get("pesquisa_expirada_na_sessao") else
                           texto_ui("temporary_search_error")),
                    state=estado_final,
                    expanded=False,
                )
        else:
            with st.spinner(texto_ui("searching")):
                dados_busca, veio_do_cache = buscar_resultados(
                    consulta_busca, chave_tavily_configurada, modo="rapida"
                )
        dados_busca = {**dados_busca, "assunto": assunto, "consulta_busca": consulta_busca}
        st.session_state.resultado_atual = dados_busca
        registrar_pesquisa_local(dados_busca)
        st.rerun()
        st.session_state.fonte_aberta = None
        if veio_do_cache:
            st.caption(texto_ui("cached"))
        avisos_exibidos, falha_avisos = traduzir_textos(dados_busca["avisos"])
        for aviso in avisos_exibidos:
            st.info(aviso)
        if dados_busca.get("status_pesquisa") == "erro" and not dados_busca.get("pesquisa_expirada_na_sessao"):
            st.error(texto_ui("temporary_search_error"))
        elif dados_busca.get("status_pesquisa") == "sem_resultados":
            st.info(texto_ui("no_results_detail"))
        if falha_avisos:
            st.warning(texto_ui("translation_error"))
        if dados_busca.get("pesquisa_expirada_na_sessao"):
            st.warning(texto_ui("deep_timeout"))

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
    imagens = resultado_atual.get("imagens", [])

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

        tipos_disponiveis = filtros_disponiveis(
            fontes, bool(video or st.session_state.videos_adicionais), bool(imagens)
        )
        if st.session_state.get("filtro_resultados") not in tipos_disponiveis:
            st.session_state.filtro_resultados = "all"
        st.selectbox(
            texto_ui("filter_label"),
            tipos_disponiveis,
            format_func=lambda tipo: texto_ui(f"filter_{tipo}"),
            key="filtro_resultados",
        )
        filtro_resultados = st.session_state.filtro_resultados

        if filtro_resultados in {"all", "videos"}:
            col_resposta, col_video = st.columns([1.1, 0.9], gap="large")
        else:
            col_resposta = st.container()
            col_video = None
        with col_resposta:
            with st.container(border=True):
                origem_resposta = resultado_atual.get("resposta_gerada_por_ia")
                chave_resposta = (
                    "quick_answer" if origem_resposta is True else
                    "source_answer" if origem_resposta is False else
                    "answer_unspecified"
                )
                chave_legenda = (
                    "answer_caption" if origem_resposta is True else
                    "source_answer_caption" if origem_resposta is False else
                    "answer_unspecified_caption"
                )
                rotulo_resposta = texto_ui(chave_resposta)
                legenda_resposta = texto_ui(chave_legenda)
                st.markdown(f'<div class="answer-label">{rotulo_resposta}</div>', unsafe_allow_html=True)
                if resultado_atual["resposta"]:
                    if resultado_atual.get("comparacao") and origem_resposta is True:
                        st.markdown(f"#### {texto_ui('comparison_heading')}")
                        st.markdown(resultado_atual["resposta"][:4000])
                    elif resultado_atual.get("modo_pesquisa") == "profunda":
                        st.markdown(resultado_atual["resposta"][:16000])
                        st.caption(texto_ui("deep_answer_caption"))
                        creditos = resultado_atual.get("uso_pesquisa", {}).get("credits")
                        if creditos is not None:
                            st.caption(texto_ui("deep_credits").format(credits=creditos))
                    else:
                        st.markdown(resumir_resposta(resultado_atual["resposta"]))
                    if resultado_atual.get("modo_pesquisa") != "profunda":
                        st.caption(legenda_resposta)
                    idioma_voz_resposta = {"Português": "pt-BR", "English": "en-US", "Español": "es-ES"}[st.session_state.idioma_visual]
                    st.html(
                        html_leitura_em_voz_alta(
                            resultado_atual["resposta"], idioma_voz_resposta,
                            texto_ui("listen_answer"), texto_ui("stop_speech"), texto_ui("speech_unsupported"),
                        ),
                        unsafe_allow_javascript=True,
                    )
                else:
                    st.write(texto_ui("no_answer"))

                favorito_pesquisa = any(
                    item["type"] == "search" and item["query"].casefold() == assunto.casefold()
                    for item in st.session_state.dados_locais["favorites"]
                )
                st.button(
                    texto_ui("favorite_research_saved") if favorito_pesquisa else texto_ui("favorite_research"),
                    key="alternar_favorito_pesquisa",
                    on_click=salvar_pesquisa_atual,
                    use_container_width=True,
                )

            st.markdown(f"#### {texto_ui('export_title')}")
            conteudo_exportacao = conteudo_pesquisa(resultado_atual)
            nome_exportacao = re.sub(r"[^\w-]+", "-", assunto, flags=re.UNICODE).strip("-")[:56] or "pesquisa"
            col_export_md, col_export_docx, col_export_pdf = st.columns(3, gap="small")
            with col_export_md:
                st.download_button(
                    texto_ui("export_md"), conteudo_exportacao, f"knowix-{nome_exportacao}.md",
                    mime="text/markdown; charset=utf-8", key="exportar_markdown", use_container_width=True,
                )
            with col_export_docx:
                st.download_button(
                    texto_ui("export_docx"), gerar_docx(conteudo_exportacao), f"knowix-{nome_exportacao}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="exportar_docx", use_container_width=True,
                )
            with col_export_pdf:
                st.download_button(
                    texto_ui("export_pdf"), gerar_pdf(conteudo_exportacao), f"knowix-{nome_exportacao}.pdf",
                    mime="application/pdf", key="exportar_pdf", use_container_width=True,
                )

        if col_video:
            with col_video:
                with st.container(border=True):
                    st.markdown(f'<div class="section-kicker">{texto_ui("featured_video")}</div>', unsafe_allow_html=True)
                    if filtro_resultados in {"all", "videos"} and video and re.fullmatch(r"[A-Za-z0-9_-]{11}", video.get("id", "")):
                        st.text(encurtar(video.get("title", texto_ui("related_video")), 90))
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
                    elif filtro_resultados in {"all", "videos"}:
                        st.info(texto_ui("no_video"))
                    if st.button(texto_ui("more_videos"), key="mais_videos_interno"):
                        with st.spinner(texto_ui("more_videos_loading")):
                            try:
                                videos_encontrados = pesquisar_videos_youtube(
                                    f"{assunto} em português", limite=12, rapido=True
                                )
                                video_atual_id = (video or {}).get("id")
                                st.session_state.videos_adicionais = [
                                    item for item in videos_encontrados
                                    if item["id"] != video_atual_id
                                ][:6]
                                st.session_state.erro_videos_adicionais = False
                            except Exception:
                                st.session_state.videos_adicionais = []
                                st.session_state.erro_videos_adicionais = True
                            st.session_state.assunto_videos_adicionais = assunto

        if st.session_state.assunto_videos_adicionais == assunto and filtro_resultados in {"all", "videos"}:
            if st.session_state.erro_videos_adicionais or not st.session_state.videos_adicionais:
                st.info(texto_ui("more_videos_empty"))
            else:
                st.markdown(f"### {texto_ui('more_videos_results')}")
                colunas_videos = st.columns(2, gap="medium")
                for indice, outro_video in enumerate(st.session_state.videos_adicionais):
                    with colunas_videos[indice % 2]:
                        with st.container(border=True):
                            st.text(encurtar(outro_video.get("title", texto_ui("related_video")), 100))
                            if outro_video.get("channel"):
                                st.caption(f"{texto_ui('channel')}: {outro_video['channel']}")
                            st.iframe(
                                f"https://www.youtube-nocookie.com/embed/{outro_video['id']}?rel=0&playsinline=1",
                                height=250,
                            )

        fontes_exibidas = filtrar_fontes(fontes, filtro_resultados)
        if filtro_resultados in {"all", "sites", "news", "articles", "documents"}:
            st.markdown(f"### {texto_ui('sites_found')}")
        if fontes_exibidas and filtro_resultados in {"all", "sites", "news", "articles", "documents"}:
            colunas_sites = st.columns(2, gap="medium")
            for indice, fonte in enumerate(fontes_exibidas[:8]):
                with colunas_sites[indice % 2]:
                    with st.container(border=True):
                        if fonte.get("domain"):
                            detalhes_fonte = [f"●  {fonte['domain']}"]
                            if fonte.get("published_date"):
                                detalhes_fonte.append(f"{texto_ui('published')}: {fonte['published_date']}")
                            if fonte.get("consulted_at"):
                                detalhes_fonte.append(f"{texto_ui('consulted')}: {fonte['consulted_at']}")
                            st.caption(" • ".join(detalhes_fonte))
                        col_titulo_fonte, col_favorito_fonte = st.columns([7, 1], gap="small")
                        with col_titulo_fonte:
                            st.button(
                                encurtar(fonte.get("title", texto_ui("read_source")), 76),
                                key=f"fonte_interna_{indice}",
                                on_click=abrir_fonte_no_knowix,
                                args=(fonte,),
                                use_container_width=True,
                            )
                        with col_favorito_fonte:
                            fonte_salva = any(
                                item["type"] == "source" and item["url"] == fonte.get("url")
                                for item in st.session_state.dados_locais["favorites"]
                            )
                            chave_favorito_fonte = uuid.uuid5(uuid.NAMESPACE_URL, fonte.get("url", str(indice))).hex
                            st.button(
                                texto_ui("favorite_source_saved") if fonte_salva else texto_ui("favorite_source"),
                                key=f"alternar_fonte_{chave_favorito_fonte}",
                                help=texto_ui("favorite_save_source_help"),
                                on_click=salvar_fonte_favorita,
                                args=(fonte, assunto),
                                use_container_width=True,
                            )
                        trecho = encurtar(fonte.get("content", ""), 210)
                        if trecho:
                            st.write(trecho)
        elif filtro_resultados in {"all", "sites", "news", "articles", "documents"}:
            if resultado_atual.get("status_pesquisa") != "erro":
                st.info(texto_ui("no_sources"))

        if (filtro_resultados in {"all", "sites", "news", "articles", "documents"}
                and resultado_atual.get("modo_pesquisa") == "profunda" and resultado_atual.get("resposta")):
            titulos_mapa = list(dict.fromkeys(
                titulo.strip().strip("#* ")
                for titulo in re.findall(r"^#{2,4}\s+(.+)$", resultado_atual["resposta"], flags=re.MULTILINE)
                if titulo.strip()
            ))
            if titulos_mapa:
                st.markdown(f"### {texto_ui('research_map')}")
                st.caption(texto_ui("research_map_caption"))
                botoes_mapa = st.columns(min(3, len(titulos_mapa)), gap="small")
                for indice, topico in enumerate(titulos_mapa[:12]):
                    with botoes_mapa[indice % len(botoes_mapa)]:
                        st.button(
                            encurtar(topico, 60),
                            key=f"mapa_pesquisa_{indice}",
                            on_click=preparar_busca_interna,
                            args=(f"{assunto} — {texto_ui('explore_topic')}: {topico}",),
                            use_container_width=True,
                        )
                with st.form("form_topico_mapa", clear_on_submit=True):
                    novo_topico = st.text_input(texto_ui("map_custom_topic"), max_chars=200)
                    aprofundar_topico = st.form_submit_button(texto_ui("explore_topic"))
                if aprofundar_topico and novo_topico.strip():
                    preparar_busca_interna(f"{assunto} — {texto_ui('explore_topic')}: {novo_topico.strip()}")
                    st.rerun()

        if imagens and filtro_resultados in {"all", "images"}:
            st.markdown(f"### {texto_ui('filter_images')}")
            colunas_imagens = st.columns(3, gap="small")
            for indice, imagem in enumerate(imagens):
                with colunas_imagens[indice % 3]:
                    imagem_url_segura = escape(imagem["url"], quote=True)
                    descricao_segura = escape(imagem.get("description") or texto_ui("filter_images"), quote=True)
                    st.markdown(
                        f'<a href="{imagem_url_segura}" target="_blank" rel="noopener noreferrer">'
                        f'<img src="{imagem_url_segura}" alt="{descricao_segura}" loading="lazy" '
                        'style="width:100%;height:180px;object-fit:cover;border-radius:12px"></a>',
                        unsafe_allow_html=True,
                    )
                    if imagem.get("description"):
                        st.caption(imagem["description"])

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

        if fontes or resultado_atual.get("resposta"):
            st.markdown(f"### {texto_ui('followup_title')}")
            st.caption(texto_ui("followup_context"))
            with st.form("form_pergunta_complementar", clear_on_submit=True):
                st.text_input(
                    texto_ui("followup_title"),
                    placeholder=texto_ui("followup_placeholder"),
                    max_chars=500,
                    key="pergunta_complementar",
                )
                st.form_submit_button(
                    texto_ui("followup_button"),
                    on_click=preparar_pergunta_complementar,
                    args=(assunto,),
                    use_container_width=True,
                )

