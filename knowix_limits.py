"""Rate limits simples por cliente para proteger as chamadas de pesquisa."""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque


def _limite_configurado(nome: str, padrao: int) -> int:
    try:
        return max(1, min(int(os.environ.get(nome, padrao)), 1000))
    except (TypeError, ValueError):
        return padrao


class LimitadorPesquisas:
    """Controla pesquisas por cliente dentro de uma instância/processo do app."""

    def __init__(self, janela_segundos: int = 3600, max_clientes: int = 5000) -> None:
        self.janela_segundos = max(1, janela_segundos)
        self.max_clientes = max(1, max_clientes)
        self.limites = {
            "rapida": _limite_configurado("KNOWIX_SEARCHES_PER_HOUR", 30),
            "profunda": _limite_configurado("KNOWIX_DEEP_SEARCHES_PER_HOUR", 3),
            "imagem": _limite_configurado("KNOWIX_IMAGE_ANALYSES_PER_HOUR", 5),
        }
        self._eventos: OrderedDict[str, dict[str, deque[float]]] = OrderedDict()
        self._lock = threading.Lock()

    def reservar(self, cliente_id: str, modo: str, agora: float | None = None) -> bool:
        categoria = modo if modo in self.limites else "rapida"
        instante = time.monotonic() if agora is None else agora
        with self._lock:
            eventos_cliente = self._eventos.get(cliente_id)
            if eventos_cliente is None:
                eventos_cliente = {categoria_nome: deque() for categoria_nome in self.limites}
                self._eventos[cliente_id] = eventos_cliente
            else:
                self._eventos.move_to_end(cliente_id)

            eventos = eventos_cliente[categoria]
            while eventos and instante - eventos[0] >= self.janela_segundos:
                eventos.popleft()
            if len(eventos) >= self.limites[categoria]:
                return False

            eventos.append(instante)
            while len(self._eventos) > self.max_clientes:
                self._eventos.popitem(last=False)
        return True
