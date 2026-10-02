import requests
import streamlit as st
import yt_dlp
from urllib.parse import quote_plus


st.set_page_config(page_title="Knowix", page_icon="🔎")
st.title("🔎 Knowix")
st.subheader("Pesquise, confira as fontes e encontre vídeos")
st.write(
    "Digite um assunto para ver páginas da Wikipédia em português e encontrar vídeos relacionados no YouTube."
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
                    st.subheader("Fontes para conferir")
                    for pagina in paginas:
                        st.markdown(f"### [{pagina['title']}]({pagina['fullurl']})")
                        trecho = pagina.get("extract", "").strip()
                        st.write(trecho if trecho else "A página não trouxe um resumo.")

                    st.subheader("Vídeos relacionados")
                    busca_youtube = quote_plus(assunto.strip())
                    link_youtube = f"https://www.youtube.com/results?search_query={busca_youtube}"
                    st.link_button("Ver todos os vídeos no YouTube", link_youtube, type="primary")
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
                            st.caption("A prévia é um dos primeiros resultados; quando as visualizações estão disponíveis, mostramos o mais visto entre eles. Isso não garante que seja viral ou correto.")
                        else:
                            st.info("Não consegui carregar a prévia agora. Use o botão acima para ver os resultados no YouTube.")
                    except Exception:
                        st.info("O YouTube não disponibilizou a prévia agora. Use o botão acima para ver os resultados.")
            except requests.exceptions.RequestException:
                st.error("Não consegui acessar a Wikipédia. Confira sua internet e tente novamente.")
            except (ValueError, KeyError):
                st.error("A resposta veio em um formato inesperado. Tente pesquisar novamente.")

st.caption("Este programa não inventa uma resposta: ele mostra trechos de páginas e links para você verificar.")
