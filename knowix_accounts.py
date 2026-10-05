"""Integração segura de conta e sincronização com Supabase Auth/Data API."""

from __future__ import annotations

import json
import base64
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urlparse

import requests


class ErroContaKnowix(Exception):
    """Falha de conta traduzida para uma mensagem segura para a interface."""


def carregar_configuracao(obter_segredo=None) -> dict:
    """Lê somente URL e chave publicável; nunca aceita chave administrativa."""
    obter_segredo = obter_segredo or (lambda nome: None)
    url = str(obter_segredo("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).strip().rstrip("/")
    chave = str(
        obter_segredo("SUPABASE_PUBLISHABLE_KEY")
        or obter_segredo("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        or os.environ.get("SUPABASE_ANON_KEY", "")
    ).strip()
    if not url or not chave or len(chave) > 500:
        return {"configured": False}
    if chave.startswith("sb_secret_"):
        return {"configured": False}
    partes_jwt = chave.split(".")
    if len(partes_jwt) == 3:
        try:
            payload_jwt = partes_jwt[1] + "=" * (-len(partes_jwt[1]) % 4)
            papel = json.loads(base64.urlsafe_b64decode(payload_jwt)).get("role")
            if papel == "service_role":
                return {"configured": False}
        except (ValueError, json.JSONDecodeError, TypeError):
            pass
    try:
        partes = urlparse(url)
        hostname = partes.hostname or ""
        permitido_local = hostname.casefold() in {"localhost", "127.0.0.1", "::1"} and partes.scheme == "http"
        valido = (
            partes.scheme == "https" or permitido_local
        ) and bool(partes.netloc and hostname) and not any((
            partes.username, partes.password, partes.query, partes.fragment, partes.path not in ("", "/")
        )) and (partes.port in (None, 443) or permitido_local and partes.port == 54321)
    except ValueError:
        valido = False
    if not valido or any(c.isspace() or ord(c) < 32 for c in url):
        return {"configured": False}
    return {"configured": True, "url": url, "key": chave}


def _mensagem_erro(resposta) -> str:
    status = getattr(resposta, "status_code", 0)
    if status == 400:
        return "Confira o e-mail e a senha e tente novamente. Se o cadastro exigir confirmação, verifique sua caixa de entrada."
    if status == 401 or status == 403:
        return "Não foi possível validar sua sessão. Entre na conta novamente."
    if status == 404:
        return "A sincronização ainda não está configurada no banco de dados. Confira a tabela e as políticas RLS do Knowix."
    if status == 409:
        return "Já existe um registro incompatível para esta conta. Seus dados locais continuam preservados."
    if status == 413:
        return "Seus dados ultrapassam o limite permitido para sincronização. Exporte ou reduza o histórico e tente novamente."
    if status == 429:
        return "Muitas tentativas em pouco tempo. Aguarde um pouco e tente novamente."
    if status >= 500:
        return "O serviço de contas está temporariamente indisponível. Tente novamente mais tarde."
    return "Não foi possível concluir a operação de conta. Confira a configuração e tente novamente."


def _requisitar(config: dict, metodo: str, caminho: str, sessao: dict | None = None,
                *, payload=None, params=None, headers_extra=None):
    if not config.get("configured"):
        raise ErroContaKnowix("A conta ainda não está configurada neste app.")
    token = str((sessao or {}).get("access_token") or "")
    cabecalhos = {"apikey": config["key"], "Accept": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    if payload is not None:
        cabecalhos["Content-Type"] = "application/json"
    if headers_extra:
        cabecalhos.update(headers_extra)
    url = f"{config['url']}{caminho}"
    try:
        resposta = requests.request(
            metodo, url, headers=cabecalhos, json=payload, params=params, timeout=(3, 12)
        )
    except requests.exceptions.Timeout as erro:
        raise ErroContaKnowix("O serviço de contas demorou para responder. Tente novamente.") from erro
    except requests.exceptions.RequestException as erro:
        raise ErroContaKnowix("Não foi possível conectar ao serviço de contas.") from erro
    if resposta.status_code == 401 and sessao and sessao.get("refresh_token") and caminho != "/auth/v1/logout":
        try:
            renovacao = requests.post(
                f"{config['url']}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": config["key"], "Content-Type": "application/json"},
                json={"refresh_token": sessao["refresh_token"]}, timeout=(3, 12),
            )
            if renovacao.status_code < 400:
                tokens = renovacao.json()
                if isinstance(tokens, dict) and tokens.get("access_token") and tokens.get("refresh_token"):
                    sessao["access_token"] = str(tokens["access_token"])
                    sessao["refresh_token"] = str(tokens["refresh_token"])
                    cabecalhos["Authorization"] = f"Bearer {sessao['access_token']}"
                    resposta = requests.request(
                        metodo, url, headers=cabecalhos, json=payload, params=params, timeout=(3, 12)
                    )
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError):
            pass
    if resposta.status_code >= 400:
        raise ErroContaKnowix(_mensagem_erro(resposta))
    if resposta.status_code == 204 or not getattr(resposta, "content", b""):
        return None
    try:
        return resposta.json()
    except (ValueError, json.JSONDecodeError) as erro:
        raise ErroContaKnowix("O serviço de contas retornou uma resposta inválida.") from erro


def _validar_email_senha(email: str, senha: str):
    email = str(email or "").strip().casefold()
    senha = str(senha or "")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ErroContaKnowix("Informe um endereço de e-mail válido.")
    if len(senha) < 12 or len(senha) > 128:
        raise ErroContaKnowix("Use uma senha com pelo menos 12 caracteres (máximo 128).")
    return email, senha


def cadastrar(config: dict, email: str, senha: str) -> dict:
    email, senha = _validar_email_senha(email, senha)
    resposta = _requisitar(config, "POST", "/auth/v1/signup", payload={"email": email, "password": senha})
    return resposta if isinstance(resposta, dict) else {}


def entrar(config: dict, email: str, senha: str) -> dict:
    email, senha = _validar_email_senha(email, senha)
    resposta = _requisitar(
        config, "POST", "/auth/v1/token?grant_type=password",
        payload={"email": email, "password": senha},
    )
    if not isinstance(resposta, dict) or not resposta.get("access_token") or not resposta.get("refresh_token"):
        raise ErroContaKnowix("O serviço não abriu uma sessão válida. Tente novamente.")
    usuario = resposta.get("user") if isinstance(resposta.get("user"), dict) else {}
    access_token = str(resposta["access_token"])
    usuario_verificado = _requisitar(config, "GET", "/auth/v1/user", {"access_token": access_token})
    if not isinstance(usuario_verificado, dict) or not usuario_verificado.get("id"):
        raise ErroContaKnowix("Não foi possível verificar a conta autenticada.")
    return {
        "access_token": access_token,
        "refresh_token": str(resposta["refresh_token"]),
        "user_id": str(usuario_verificado["id"]),
        "email": str(usuario_verificado.get("email") or usuario.get("email") or "")[:254],
    }


def enviar_recuperacao(config: dict, email: str, redirect_url: str | None = None):
    email = str(email or "").strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ErroContaKnowix("Informe um endereço de e-mail válido.")
    parametros = {"redirect_to": redirect_url} if redirect_url else None
    _requisitar(config, "POST", "/auth/v1/recover", payload={"email": email}, params=parametros)


def alterar_senha(config: dict, token_recuperacao: str, nova_senha: str):
    token_recuperacao = str(token_recuperacao or "")
    nova_senha = str(nova_senha or "")
    if len(token_recuperacao) > 4096 or not token_recuperacao:
        raise ErroContaKnowix("O link de recuperação expirou ou não é válido. Solicite outro.")
    if len(nova_senha) < 12 or len(nova_senha) > 128:
        raise ErroContaKnowix("Use uma senha com pelo menos 12 caracteres (máximo 128).")
    _requisitar(
        config, "PUT", "/auth/v1/user", {"access_token": token_recuperacao},
        payload={"password": nova_senha},
    )


def sair(config: dict, sessao: dict):
    token = str(sessao.get("access_token") or "")
    if token:
        _requisitar(config, "POST", "/auth/v1/logout", sessao)


def carregar_dados(config: dict, sessao: dict):
    linhas = _requisitar(
        config, "GET", "/rest/v1/knowix_user_data", sessao,
        params={"user_id": f"eq.{sessao['user_id']}", "select": "data", "limit": "1"},
    )
    if not isinstance(linhas, list) or not linhas:
        return None
    linha = linhas[0]
    return linha.get("data") if isinstance(linha, dict) and isinstance(linha.get("data"), dict) else None


def salvar_dados(config: dict, sessao: dict, dados: dict):
    corpo = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    if len(corpo.encode("utf-8")) > 700_000:
        raise ErroContaKnowix("Seus dados ultrapassam o limite seguro de sincronização (700 KB).")
    _requisitar(
        config, "POST", "/rest/v1/knowix_user_data", sessao,
        params={"on_conflict": "user_id"},
        payload={"user_id": sessao["user_id"], "data": dados,
                 "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        headers_extra={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


def _juntar_lista(remoto: list, local: list, identidade, ordenacao=None) -> list:
    resultado = []
    indices = {}
    for item in [*remoto, *local]:
        if not isinstance(item, dict):
            continue
        chave = identidade(item)
        if not chave:
            continue
        if chave in indices:
            pos = indices[chave]
            anterior = resultado[pos]
            marco = ordenacao or "saved_at"
            data_item = str(item.get("updated_at") or item.get(marco, ""))
            data_anterior = str(anterior.get("updated_at") or anterior.get(marco, ""))
            if data_item > data_anterior:
                resultado[pos] = item
            continue
        indices[chave] = len(resultado)
        resultado.append(item)
    return resultado


def _unir_textos(remoto, local, atualizado_remoto="", atualizado_local=""):
    remoto = str(remoto or "").strip()
    local = str(local or "").strip()
    if atualizado_remoto or atualizado_local:
        if atualizado_local > atualizado_remoto:
            return local
        if atualizado_remoto > atualizado_local:
            return remoto
    if not remoto:
        return local
    if not local or local == remoto or local in remoto:
        return remoto
    if remoto in local:
        return local
    return f"{remoto}\n\n--- Anotação deste dispositivo ---\n\n{local}"


def mesclar_dados_conta(remoto: dict, local: dict) -> dict:
    """Combina alterações offline sem apagar registros nem anotações divergentes."""
    remoto = remoto if isinstance(remoto, dict) else {}
    local = local if isinstance(local, dict) else {}
    historico = _juntar_lista(
        remoto.get("history", []), local.get("history", []),
        lambda item: str(item.get("query", "")).strip().casefold(), "saved_at",
    )
    favoritos = _juntar_lista(
        remoto.get("favorites", []), local.get("favorites", []),
        lambda item: (item.get("type"), str(item.get("url") or item.get("query", "")).casefold()), "saved_at",
    )
    tombstones_remotos = remoto.get("sync_tombstones", {}) if isinstance(remoto.get("sync_tombstones"), dict) else {}
    tombstones_locais = local.get("sync_tombstones", {}) if isinstance(local.get("sync_tombstones"), dict) else {}

    def normalizar_tombstones(valor):
        if isinstance(valor, list):  # Compatibilidade com sincronizações anteriores.
            return {str(chave): {"deleted": True, "at": ""} for chave in valor if isinstance(chave, str) and chave}
        if not isinstance(valor, dict):
            return {}
        resultado = {}
        for chave, acao in valor.items():
            if not isinstance(chave, str) or not chave:
                continue
            if isinstance(acao, dict) and isinstance(acao.get("deleted"), bool):
                resultado[chave] = {"deleted": acao["deleted"], "at": str(acao.get("at", ""))[:48]}
            else:
                resultado[chave] = {"deleted": True, "at": ""}
        return resultado

    tombstones = {}
    for categoria in ("history", "favorites"):
        combinados = {}
        for origem in (tombstones_remotos, tombstones_locais):
            acoes = normalizar_tombstones(origem.get(categoria, {}))
            for chave, acao in acoes.items():
                anterior = combinados.get(chave)
                if anterior is None or (acao["at"], acao["deleted"]) > (anterior["at"], anterior["deleted"]):
                    combinados[chave] = acao
        tombstones[categoria] = dict(sorted(
            combinados.items(), key=lambda par: par[1]["at"], reverse=True
        )[:1000])

    consultas_excluidas = {chave for chave, acao in tombstones["history"].items() if acao["deleted"]}
    favoritos_excluidos = {chave for chave, acao in tombstones["favorites"].items() if acao["deleted"]}
    historico = [item for item in historico if str(item.get("query", "")).casefold() not in consultas_excluidas]
    favoritos = [
        item for item in favoritos
        if f"{item.get('type')}:{str(item.get('url') or item.get('query', '')).casefold()}" not in favoritos_excluidos
    ]
    projetos_remotos = remoto.get("projects", []) if isinstance(remoto.get("projects"), list) else []
    projetos_locais = local.get("projects", []) if isinstance(local.get("projects"), list) else []
    projetos = _juntar_lista(projetos_remotos, projetos_locais, lambda item: str(item.get("id", "")))
    por_id = {str(p.get("id")): p for p in projetos}
    for projeto_remoto in projetos_remotos:
        if not isinstance(projeto_remoto, dict):
            continue
        id_projeto = str(projeto_remoto.get("id", ""))
        projeto_local = next((p for p in projetos_locais if isinstance(p, dict) and str(p.get("id", "")) == id_projeto), None)
        projeto = por_id.get(id_projeto)
        if not projeto or not projeto_local:
            continue
        projeto["notes"] = _unir_textos(
            projeto_remoto.get("notes"), projeto_local.get("notes"),
            projeto_remoto.get("notes_updated_at", ""), projeto_local.get("notes_updated_at", ""),
        )
        projeto["notes_updated_at"] = max(
            str(projeto_remoto.get("notes_updated_at", "")), str(projeto_local.get("notes_updated_at", ""))
        )
        projeto["updated_at"] = max(str(projeto_remoto.get("updated_at", "")), str(projeto_local.get("updated_at", "")))
        projeto["searches"] = _juntar_lista(
            projeto_remoto.get("searches", []), projeto_local.get("searches", []),
            lambda item: str(item.get("query", "")).casefold(), "saved_at",
        )
        projeto["sources"] = _juntar_lista(
            projeto_remoto.get("sources", []), projeto_local.get("sources", []),
            lambda item: str(item.get("url", "")).casefold(),
        )
    pastas_remotas = remoto.get("folders", []) if isinstance(remoto.get("folders"), list) else []
    pastas_locais = local.get("folders", []) if isinstance(local.get("folders"), list) else []
    pastas = list(dict.fromkeys(str(item) for item in pastas_remotas + pastas_locais if isinstance(item, str)))
    notas_remotas = remoto.get("folder_notes", {}) if isinstance(remoto.get("folder_notes"), dict) else {}
    notas_locais = local.get("folder_notes", {}) if isinstance(local.get("folder_notes"), dict) else {}
    datas_remotas = remoto.get("folder_notes_updated_at", {}) if isinstance(remoto.get("folder_notes_updated_at"), dict) else {}
    datas_locais = local.get("folder_notes_updated_at", {}) if isinstance(local.get("folder_notes_updated_at"), dict) else {}
    notas = {
        nome: _unir_textos(notas_remotas.get(nome), notas_locais.get(nome), datas_remotas.get(nome, ""), datas_locais.get(nome, ""))
        for nome in set(notas_remotas) | set(notas_locais)
    }
    datas_notas = {nome: max(str(datas_remotas.get(nome, "")), str(datas_locais.get(nome, "")))
                   for nome in set(datas_remotas) | set(datas_locais)}
    preferencias = remoto.get("preferences") if isinstance(remoto.get("preferences"), dict) and remoto else local.get("preferences", {})
    return {
        "version": 1,
        "history": sorted(historico, key=lambda item: str(item.get("saved_at", "")), reverse=True)[:20],
        "favorites": sorted(favoritos, key=lambda item: str(item.get("saved_at", "")), reverse=True)[:100],
        "folders": pastas[:30],
        "projects": sorted(projetos, key=lambda item: str(item.get("created_at", "")), reverse=True)[:20],
        "folder_notes": notas,
        "folder_notes_updated_at": datas_notas,
        "sync_tombstones": tombstones,
        "preferences": preferencias,
    }


TEXTOS_CONTA = {
    "Português": {
        "title": "Conta Knowix", "setup": "Para ativar contas, configure `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` nos Secrets do site. Nunca use uma chave `service_role` ou `sb_secret`.",
        "privacy": "Ao entrar, seus históricos, favoritos, pastas, projetos e preferências serão sincronizados com sua conta Knowix no Supabase. A chave pública só permite dados autorizados pelas políticas RLS.",
        "email": "E-mail", "password": "Senha", "confirm": "Confirmar senha", "login": "Entrar", "signup": "Criar conta", "recover": "Enviar link de recuperação", "logout": "Sair da conta", "sync": "Sincronizar agora", "logged": "Conta conectada", "verify": "Cadastro recebido. Confira seu e-mail para confirmar a conta e depois entre.", "created": "Conta criada e conectada.", "signedin": "Sessão iniciada e dados mesclados com segurança.", "signedout": "Você saiu. Os dados deste navegador foram preservados.", "reset_sent": "Se o endereço estiver cadastrado, enviaremos um link de recuperação.", "reset_title": "Defina uma nova senha", "reset_done": "Senha atualizada. Entre novamente com a nova senha.", "sync_ok": "Dados sincronizados.", "sync_fail": "Não foi possível sincronizar agora. Seus dados locais continuam salvos.", "reset_password": "Nova senha", "confirm_new": "Confirmar nova senha", "password_mismatch": "As senhas não coincidem.", "recover_caption": "Enviaremos um link para o endereço informado, sem revelar se ele está cadastrado.",
    },
    "English": {
        "title": "Knowix account", "setup": "To enable accounts, configure `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the site Secrets. Never use a `service_role` or `sb_secret` key.",
        "privacy": "When you sign in, your history, favorites, folders, projects, and preferences are synced to your Knowix account in Supabase. The public key only permits data allowed by RLS policies.",
        "email": "Email", "password": "Password", "confirm": "Confirm password", "login": "Sign in", "signup": "Create account", "recover": "Send recovery link", "logout": "Sign out", "sync": "Sync now", "logged": "Account connected", "verify": "Sign-up received. Check your email to confirm your account, then sign in.", "created": "Account created and connected.", "signedin": "Signed in and data safely merged.", "signedout": "Signed out. This browser's data was preserved.", "reset_sent": "If this address is registered, a recovery link will be sent.", "reset_title": "Set a new password", "reset_done": "Password updated. Sign in again with your new password.", "sync_ok": "Data synced.", "sync_fail": "Could not sync now. Your local data is still saved.", "reset_password": "New password", "confirm_new": "Confirm new password", "password_mismatch": "Passwords do not match.", "recover_caption": "We'll send a link to the address entered without revealing whether it is registered.",
    },
    "Español": {
        "title": "Cuenta Knowix", "setup": "Para activar cuentas, configura `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` en los Secrets del sitio. Nunca uses una clave `service_role` o `sb_secret`.",
        "privacy": "Al iniciar sesión, tu historial, favoritos, carpetas, proyectos y preferencias se sincronizarán con tu cuenta Knowix en Supabase. La clave pública solo permite datos autorizados por políticas RLS.",
        "email": "Correo", "password": "Contraseña", "confirm": "Confirmar contraseña", "login": "Iniciar sesión", "signup": "Crear cuenta", "recover": "Enviar enlace de recuperación", "logout": "Cerrar sesión", "sync": "Sincronizar ahora", "logged": "Cuenta conectada", "verify": "Registro recibido. Revisa tu correo para confirmar la cuenta y luego inicia sesión.", "created": "Cuenta creada y conectada.", "signedin": "Sesión iniciada y datos combinados de forma segura.", "signedout": "Sesión cerrada. Los datos de este navegador se conservaron.", "reset_sent": "Si esta dirección está registrada, enviaremos un enlace de recuperación.", "reset_title": "Establece una nueva contraseña", "reset_done": "Contraseña actualizada. Inicia sesión con la nueva contraseña.", "sync_ok": "Datos sincronizados.", "sync_fail": "No se pudo sincronizar ahora. Tus datos locales siguen guardados.", "reset_password": "Nueva contraseña", "confirm_new": "Confirmar nueva contraseña", "password_mismatch": "Las contraseñas no coinciden.", "recover_caption": "Enviaremos un enlace a la dirección indicada sin revelar si está registrada.",
    },
}
