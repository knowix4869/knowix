"""Image input validation and server-side vision analysis for Knowix."""

from __future__ import annotations

import io
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
DEFAULT_MODEL = ""


class ErroVisaoKnowix(ValueError):
    """Expected validation or provider error safe to show in the UI."""


def obter_chave_gemini(secrets=None, environ=None):
    """Gemini remains disabled until adult-only access is independently assured."""
    return ""


def obter_modelo_gemini(secrets=None, environ=None):
    """No image provider is enabled until adult eligibility and provider terms are reviewed."""
    return ""


def preparar_imagem(conteudo: bytes, mime_informado: str | None = None):
    """Validate, orient and re-encode a supported image, stripping metadata."""
    if not isinstance(conteudo, bytes) or not conteudo:
        raise ErroVisaoKnowix("Selecione uma imagem válida.")
    if len(conteudo) > MAX_IMAGE_BYTES:
        raise ErroVisaoKnowix("A imagem precisa ter no máximo 8 MB.")
    try:
        with Image.open(io.BytesIO(conteudo)) as original:
            formato = (original.format or "").upper()
            if formato not in ALLOWED_FORMATS:
                raise ErroVisaoKnowix("Use uma imagem JPG, PNG ou WebP.")
            mime_por_formato = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
            mime_real = mime_por_formato[formato]
            if mime_informado and mime_informado.split(";", 1)[0].strip().lower() not in {mime_real, "application/octet-stream"}:
                raise ErroVisaoKnowix("O tipo real do arquivo não corresponde ao formato informado.")
            if original.width * original.height > MAX_IMAGE_PIXELS:
                raise ErroVisaoKnowix("A imagem excede o limite de resolução permitido.")
            original.verify()
        with Image.open(io.BytesIO(conteudo)) as original:
            imagem = ImageOps.exif_transpose(original).convert("RGB")
            limpa = Image.new("RGB", imagem.size)
            limpa.paste(imagem)
            buffer = io.BytesIO()
            limpa.save(buffer, format="JPEG", quality=88, optimize=True)
    except ErroVisaoKnowix:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erro:
        raise ErroVisaoKnowix("O arquivo não parece ser uma imagem válida.") from erro
    return buffer.getvalue(), "image/jpeg"


def analisar_imagem(
    conteudo: bytes,
    pergunta: str,
    chave: str,
    model: str = DEFAULT_MODEL,
    requester=None,
    mime_informado: str | None = None,
):
    """Fail closed until reliable adult age assurance and provider approval are configured."""
    raise ErroVisaoKnowix(
        "A análise de imagem está temporariamente desativada até que a idade adulta seja confirmada de forma adequada "
        "e as condições do provedor sejam atendidas."
    )
