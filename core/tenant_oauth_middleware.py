"""
core/tenant_oauth_middleware.py
================================
Middleware auxiliar que salva o tenant de origem na sessão
quando o usuário inicia o login OAuth a partir de um subdomínio.

Trabalha em conjunto com o google_adapter.py:
  - Este middleware: salva o tenant na sessão
  - google_adapter.py: lê o tenant e redireciona de volta após login

Por que ainda é necessário se o adapter já salva na sessão?
  O adapter só é chamado quando o allauth processa a requisição.
  Este middleware garante que o tenant seja salvo no momento EXATO
  em que o usuário clica em "Login com Google", antes de qualquer
  redirect. Isso cobre edge cases onde o adapter não é chamado
  (ex: requisições diretas à URL do Google).

Configuração no settings.py — DEPOIS do SessionMiddleware:
    MIDDLEWARE = [
        ...
        'django.contrib.sessions.middleware.SessionMiddleware',
        'core.tenant_oauth_middleware.TenantOAuthMiddleware',  # ← aqui
        ...
    ]
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

SESSION_KEY_TENANT = '_oauth_origin_host'  # mesma chave do adapter

PREFIXOS_OAUTH = (
    '/auth/google/',
    '/auth/social/',
    '/accounts/social/',
)


def _e_subdominio(host: str) -> bool:
    base  = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    debug = getattr(settings, 'DEBUG', False)
    port  = getattr(settings, 'TENANT_DEV_PORT', '8000')
    principal = f'{base}:{port}' if debug else base
    return host != principal and (
        host.endswith(f'.{base}:{port}') or host.endswith(f'.{base}')
    )


class TenantOAuthMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        path = request.path

        # Se é subdomínio de tenant iniciando OAuth → salva na sessão
        if (
            _e_subdominio(host)
            and any(path.startswith(p) for p in PREFIXOS_OAUTH)
            and SESSION_KEY_TENANT not in request.session
        ):
            request.session[SESSION_KEY_TENANT] = host
            request.session.modified = True
            logger.info(f"OAuth iniciado em tenant '{host}' — salvo na sessão")

        return self.get_response(request)