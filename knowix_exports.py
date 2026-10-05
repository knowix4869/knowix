"""Exporta uma pesquisa do Knowix sem dependências de conversão externas."""

from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from textwrap import wrap
from zipfile import ZIP_DEFLATED, ZipFile


def conteudo_pesquisa(resultado: dict) -> str:
    assunto = str(resultado.get("assunto") or "Pesquisa do Knowix").strip()
    linhas = [
        f"# {assunto}",
        "",
        f"Consulta exportada em {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M')}.",
        "",
        "## Resposta",
        "",
        str(resultado.get("resposta") or "Nenhuma resposta direta foi gerada."),
        "",
        "## Fontes",
        "",
    ]
    fontes = resultado.get("fontes") or []
    if fontes:
        for indice, fonte in enumerate(fontes, 1):
            linhas.extend([
                f"### {indice}. {fonte.get('title') or 'Fonte'}",
                str(fonte.get("url") or ""),
            ])
            if fonte.get("published_date"):
                linhas.append(f"Publicado: {fonte['published_date']}")
            if fonte.get("consulted_at"):
                linhas.append(f"Consultado: {fonte['consulted_at']}")
            if fonte.get("content"):
                linhas.append(str(fonte["content"]))
            linhas.append("")
    else:
        linhas.extend(["Nenhuma fonte foi retornada para esta pesquisa.", ""])

    imagens = resultado.get("imagens") or []
    if imagens:
        linhas.extend(["## Imagens relacionadas", ""])
        for imagem in imagens:
            if imagem.get("url", "").startswith("https://"):
                linhas.append(f"{imagem.get('description') or 'Imagem relacionada'} — {imagem['url']}")
        linhas.append("")

    video = resultado.get("video")
    if video and video.get("id"):
        linhas.extend([
            "## Vídeo relacionado",
            "",
            str(video.get("title") or "Vídeo relacionado"),
            f"https://www.youtube.com/watch?v={video['id']}",
            "",
        ])
    linhas.append("Resposta de IA gerada a partir das fontes listadas." if resultado.get("resposta_gerada_por_ia") else "Resumo informativo; confira as fontes originais.")
    return "\n".join(linhas).strip() + "\n"


def gerar_docx(conteudo: str) -> bytes:
    """Cria um .docx mínimo válido, com os títulos e parágrafos da pesquisa."""
    paragrafos = []
    for linha in conteudo.splitlines():
        texto = linha.lstrip("# ") if linha.startswith("#") else linha
        if not texto:
            continue
        estilo = "Title" if linha.startswith("# ") else "Heading1" if linha.startswith("## ") else "Heading2" if linha.startswith("### ") else None
        propriedades = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
        paragrafos.append(
            f'<w:p>{propriedades}<w:r><w:t xml:space="preserve">{escape(texto)}</w:t></w:r></w:p>'
        )
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + "".join(paragrafos) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        '</w:body></w:document>'
    )
    estilos = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '</w:styles>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as pacote:
        pacote.writestr("[Content_Types].xml", content_types)
        pacote.writestr("_rels/.rels", rels)
        pacote.writestr("word/document.xml", documento)
        pacote.writestr("word/styles.xml", estilos)
        pacote.writestr("word/_rels/document.xml.rels", doc_rels)
    return buffer.getvalue()


def gerar_pdf(conteudo: str) -> bytes:
    """Gera PDF paginado em WinAnsi, sem instalar conversor ou enviar conteúdo a terceiros."""
    linhas = []
    for linha in conteudo.splitlines():
        limite = 76 if linha.startswith("http") else 88
        linhas.extend(wrap(linha, width=limite, break_long_words=True, break_on_hyphens=True) or [""])
    linhas_por_pagina = 48
    paginas = [linhas[i:i + linhas_por_pagina] for i in range(0, len(linhas), linhas_por_pagina)] or [[]]

    def pdf_texto(texto: str) -> bytes:
        texto = texto.encode("cp1252", "replace").decode("cp1252")
        escapado = texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return f"({escapado}) Tj".encode("cp1252")

    objetos: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    ids_paginas = []
    for indice, linhas_pagina in enumerate(paginas):
        id_pagina = 4 + indice * 2
        id_stream = id_pagina + 1
        ids_paginas.append(id_pagina)
        comandos = [b"BT", b"/F1 10 Tf", b"50 790 Td", b"14 TL"]
        for linha in linhas_pagina:
            comandos.extend([pdf_texto(linha), b"T*"])
        comandos.append(b"ET")
        stream = b"\n".join(comandos)
        objetos[id_pagina] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {id_stream} 0 R >>".encode()
        )
        objetos[id_stream] = f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
    objetos[2] = f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in ids_paginas)}] /Count {len(ids_paginas)} >>".encode()

    documento = bytearray(b"%PDF-1.4\n%Knowix\n")
    offsets = [0] * (max(objetos) + 1)
    for numero in sorted(objetos):
        offsets[numero] = len(documento)
        documento.extend(f"{numero} 0 obj\n".encode())
        documento.extend(objetos[numero])
        documento.extend(b"\nendobj\n")
    inicio_xref = len(documento)
    documento.extend(f"xref\n0 {len(offsets)}\n".encode())
    documento.extend(b"0000000000 65535 f \n")
    for numero in range(1, len(offsets)):
        documento.extend(f"{offsets[numero]:010d} 00000 n \n".encode())
    documento.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    )
    return bytes(documento)
