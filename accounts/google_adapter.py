"""
accounts/google_adapter.py
===========================
Adapter do allauth que resolve dois problemas do OAuth + django-tenants:

PROBLEMA 1 — redirect_uri errada:
  O allauth constrói a redirect_uri usando request.build_absolute_uri(),
  que retorna o host atual. Se o usuário está em santosgomesv.localhost:8000,
  a redirect_uri fica santosgomesv.localhost:8000/auth/google/login/callback/
  → Google rejeita com erro 400 porque só conhece localhost:8000.

SOLUÇÃO:
  Sobrescreve build_absolute_uri() no request antes do allauth usá-lo,
  forçando sempre o domínio principal na redirect_uri.

PROBLEMA 2 — redirecionamento pós-login:
  Após autenticar, o allauth redireciona para LOGIN_REDIRECT_URL (/).
  Mas o usuário precisa voltar para o subdomínio do seu tenant.

SOLUÇÃO:
  Salva o tenant original na sessão antes do OAuth e redireciona
  para o subdomínio correto após o callback.

Configuração no settings.py:
    SOCIALACCOUNT_ADAPTER = 'accounts.google_adapter.TenantSocialAccountAdapter'
    ACCOUNT_ADAPTER       = 'accounts.google_adapter.TenantAccountAdapter'
    TENANT_BASE_DOMAIN    = 'localhost'   # prod: 'locagest.com.br'
    TENANT_DEV_PORT       = '8000'
"""

import logging
from django.conf import settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger(__name__)

SESSION_KEY_TENANT = '_oauth_origin_host'


def _dominio_principal() -> str:
    """
    Retorna sempre o domínio principal (sem subdomínio).
    Dev:  'localhost:8000'
    Prod: 'locagest.com.br'
    """
    base  = settings('TENANT_BASE_DOMAIN')
    debug = settings('DEBUG')
    port  = settings('TENANT_DEV_PORT')
    print(base,debug,port)
    return f'{base}:{port}' if debug else base


def _e_subdominio(host: str) -> bool:
    """Retorna True se o host atual é um subdomínio de tenant."""
    base  = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    debug = getattr(settings, 'DEBUG', False)
    port  = getattr(settings, 'TENANT_DEV_PORT', '8000')
    print('e dominio',base,debug,port)
    principal = f'{base}:{port}' if debug else base
    return host != principal and (
        host.endswith(f'.{base}:{port}') or host.endswith(f'.{base}')
    )


def _url_tenant(schema_name: str, path: str = '/') -> str:
    """Monta a URL completa do subdomínio do tenant."""
    base  = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    debug = getattr(settings, 'DEBUG', False)
    port  = getattr(settings, 'TENANT_DEV_PORT', '8000')
    proto = 'http' if debug else 'https'
    host  = f'{schema_name}.{base}:{port}' if debug else f'{schema_name}.{base}'
    return f'{proto}://{host}{path}'


def _resolver_url_tenant(user) -> str | None:
    """Resolve a URL do tenant pelo PerfilUsuario do usuário."""
    try:
        from accounts.models import PerfilUsuario
        perfil  = PerfilUsuario.objects.select_related('empresa').get(user=user)
        empresa = perfil.empresa
        if empresa and empresa.schema_name:
            return _url_tenant(empresa.schema_name)
    except Exception as e:
        logger.warning(f"Não foi possível resolver tenant para {user}: {e}")
    return None


class _RequestComDominioPrincipal:
    """
    Wrapper do request que sobrescreve get_host() e build_absolute_uri().

    O allauth chama request.build_absolute_uri(callback_path) para montar
    a redirect_uri que envia ao Google. Este wrapper intercepta essa
    chamada e retorna sempre o domínio principal, independente de onde
    a requisição chegou.

    Não modifica o request original — apenas encapsula para uso pontual.
    """

    def __init__(self, request):
        self._request = request
        self._principal = _dominio_principal()
        debug = getattr(settings, 'DEBUG', False)
        self._schema = 'http' if debug else 'https'

    def get_host(self):
        return self._principal

    def build_absolute_uri(self, path=None):
        if path is None:
            path = self._request.get_full_path()
        # Garante que path começa com /
        if not path.startswith('/'):
            path = f'/{path}'
        return f'{self._schema}://{self._principal}{path}'

    def __getattr__(self, name):
        # Qualquer outro atributo vai para o request original
        return getattr(self._request, name)


class TenantSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter para login social (Google OAuth).

    Sobrescreve o método que o allauth usa para obter o request
    ao construir a redirect_uri, forçando o domínio principal.
    """

    def get_callback_url(self, request, app):
        """
        Chamado pelo allauth para montar a redirect_uri.
        Força sempre o domínio principal.
        """
        # Salva o host original na sessão antes de trocar
        host_atual = request.get_host()
        if _e_subdominio(host_atual):
            request.session[SESSION_KEY_TENANT] = host_atual
            request.session.modified = True
            logger.info(f"OAuth: tenant '{host_atual}' salvo na sessão")

        # Chama o método original mas com o request "mascarado"
        request_principal = _RequestComDominioPrincipal(request)
        return super().get_callback_url(request_principal, app)

    def get_login_redirect_url(self, request):
        """
        Após callback bem-sucedido, redireciona para o subdomínio
        do tenant em vez de ficar no domínio principal.
        """
        # 1. Tenta pelo host salvo na sessão (fluxo de subdomínio)
        tenant_host = request.session.pop(SESSION_KEY_TENANT, None)
        if tenant_host:
            debug  = getattr(settings, 'DEBUG', False)
            schema = 'http' if debug else 'https'
            url    = f'{schema}://{tenant_host}/'
            logger.info(f"Pós-OAuth: redirecionando para tenant salvo: {url}")
            return url

        # 2. Tenta pelo PerfilUsuario (login direto no domínio principal)
        if request.user.is_authenticated:
            url = _resolver_url_tenant(request.user)
            if url:
                logger.info(f"Pós-OAuth: redirecionando para tenant do perfil: {url}")
                return url

        # 3. Fallback: domínio principal
        return getattr(settings, 'LOGIN_REDIRECT_URL', '/')


class TenantAccountAdapter(DefaultAccountAdapter):
    """
    Adapter para login padrão (usuário/senha).
    Redireciona para o subdomínio do tenant após login.
    """

    def get_login_redirect_url(self, request):
        tenant_host = request.session.pop(SESSION_KEY_TENANT, None)
        if tenant_host:
            debug  = getattr(settings, 'DEBUG', False)
            schema = 'http' if debug else 'https'
            return f'{schema}://{tenant_host}/'

        if request.user.is_authenticated:
            url = _resolver_url_tenant(request.user)
            if url:
                return url

        return super().get_login_redirect_url(request)