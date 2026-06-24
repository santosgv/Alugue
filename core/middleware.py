"""
Middlewares de tenant/plano e guarda de assinatura.

── PlanoMiddleware ────────────────────────────────────────────
Resolve a empresa do usuário logado e injeta no request:
  request.empresa      → TenantCompany | None
  request.assinatura   → Assinatura | None
  request.plano_ativo  → SubscriptionPlan | None

Modo MVP (sem django-tenants):
  Resolve pelo perfil.empresa do usuário ou pelo primeiro tenant ativo.

Modo django-tenants (PostgreSQL):
  O TenantMainMiddleware já resolveu o tenant pelo subdomínio e colocou
  em connection.tenant. O PlanoMiddleware apenas lê de lá — sem fazer
  nenhuma query extra de resolução.

  Para ativar: settings._USE_TENANTS = True (automático quando
  django_tenants está instalado).

── AssinaturaGuardMiddleware ──────────────────────────────────
Bloqueia o acesso a todas as rotas operacionais quando a
assinatura está expirada, cancelada, suspensa ou inexistente.
Também bloqueia rotas de recursos não disponíveis no plano ativo.

Comportamento:
  - Superuser → sempre passa (administrador da plataforma).
  - Assinatura ativa ou trial com dias restantes → passa.
  - Trial vencido, expirado, cancelado, suspenso → redireciona
    para /planos/ com mensagem explicativa.
  - Rotas da lista ROTAS_LIBERADAS → sempre passam (login,
    logout, planos, assinatura, admin, static, media).
  - Rotas de recursos sem permissão no plano → redireciona
    para /planos/ com mensagem de upgrade.
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
import logging
from .models import TenantCompany
from .services import AssinaturaService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Rotas sempre liberadas pelo guard de assinatura
# ─────────────────────────────────────────────────────────────
ROTAS_LIBERADAS = (
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/senha/',
    '/accounts/perfil/',
    '/planos/',
    '/assinatura/',
    '/admin/',
    '/plataforma/',
    '/static/',
    '/media/',
    '/webhooks/stripe/',
)


# ─────────────────────────────────────────────────────────────
# Mapeamento de rotas → recurso exigido no plano.
# Chave: prefixo da URL.
# Valor: chave do campo JSON `recursos` em SubscriptionPlan.
#
# Para adicionar um novo recurso no futuro, basta incluir uma
# entrada aqui. Não é necessário mexer em nenhum outro lugar.
# ─────────────────────────────────────────────────────────────
RECURSOS_POR_ROTA = {
    '/relatorios/': 'relatorios',
    # '/api/':       'api_acesso',      # descomente quando lançar
    # '/whatsapp/':  'whatsapp',        # descomente quando lançar
}

NOMES_RECURSO = {
    'relatorios':          'Relatórios Avançados',
    'api_acesso':          'Acesso à API',
    'whatsapp':            'Alertas WhatsApp',
    'suporte_prioritario': 'Suporte Prioritário',
}


class PlanoMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request.empresa     = None
        request.assinatura  = None
        request.plano_ativo = None

        if not request.user.is_authenticated:
            return

        if request.user.is_superuser:
            return

        # ── Modo django-tenants ────────────────────────────────
        # O TenantMainMiddleware já resolveu o tenant pelo subdomínio
        # e colocou em connection.tenant. Apenas lemos daqui.
        try:
            from django.db import connection
            if hasattr(connection, 'tenant') and connection.tenant is not None:
                empresa = connection.tenant
                request.empresa     = empresa
                request.assinatura  = AssinaturaService.assinatura_ativa(empresa)
                request.plano_ativo = (
                    request.assinatura.plano
                    if request.assinatura
                    else empresa.plano
                )
                return
        except Exception:
            pass

        # ── Modo MVP (sem django-tenants) ──────────────────────
        empresa = self._resolver_empresa(request.user)
        if not empresa:
            return

        request.empresa     = empresa
        request.assinatura  = AssinaturaService.assinatura_ativa(empresa)
        request.plano_ativo = (
            request.assinatura.plano
            if request.assinatura
            else empresa.plano
        )

    @staticmethod
    def _resolver_empresa(user) -> TenantCompany | None:
        """
        MVP: resolve empresa pelo perfil do usuário.
        Fallback: primeira empresa ativa (compatibilidade).

        Com django-tenants este método não é chamado —
        a resolução já aconteceu pelo subdomínio no TenantMainMiddleware.
        """
        try:
            perfil = user.perfil
            if perfil.empresa and perfil.empresa.ativo:
                return perfil.empresa
        except Exception:
            pass
        # Fallback MVP — remover quando todos tiverem empresa no perfil
        return TenantCompany.objects.filter(ativo=True).select_related('plano').first()


# ─────────────────────────────────────────────────────────────
# ASSINATURA GUARD MIDDLEWARE
# ─────────────────────────────────────────────────────────────

class AssinaturaGuardMiddleware(MiddlewareMixin):
    """
    Bloqueia acesso quando assinatura está inativa.
    Deve vir APÓS PlanoMiddleware (depende de request.assinatura).
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return

        if request.user.is_superuser:
            return

        path = request.path
        if any(path.startswith(rota) for rota in ROTAS_LIBERADAS):
            return

        # ── 1. Verifica assinatura ─────────────────────────────
        assinatura = getattr(request, 'assinatura', None)
        bloqueado, motivo = self._avaliar(assinatura)

        if bloqueado:
            messages.warning(request, motivo)
            return redirect('/planos/')

        # ── 2. Verifica recurso do plano ───────────────────────
        # Só chega aqui se a assinatura está válida.
        # Bloqueia rotas de recursos não disponíveis no plano ativo.
        recurso_bloqueado, msg_recurso = self._avaliar_recurso(request)
        if recurso_bloqueado:
            messages.warning(request, msg_recurso)
            return redirect('/planos/')

    # ── Avaliação de assinatura ────────────────────────────────

    @staticmethod
    def _avaliar(assinatura) -> tuple[bool, str]:
        """
        Avalia se a assinatura bloqueia o acesso.
        Retorna (bloqueado: bool, motivo: str).
        Isolado para facilitar testes unitários.
        """
        hoje = timezone.localdate()

        if assinatura is None:
            return True, (
                'Você não possui uma assinatura ativa. '
                'Escolha um plano para começar a usar o sistema.'
            )

        if assinatura.status == 'cancelada':
            return True, (
                'Sua assinatura foi cancelada. '
                'Escolha um novo plano para reativar o acesso.'
            )

        if assinatura.status == 'suspensa':
            return True, (
                'Sua assinatura está suspensa. '
                'Entre em contato com o suporte ou renove seu plano.'
            )

        if assinatura.status == 'expirada':
            return True, (
                'Sua assinatura expirou. '
                'Renove agora para continuar usando o sistema.'
            )

        if assinatura.status == 'pendente_pagamento':
            return True, (
                'Há um problema com seu pagamento. '
                'Acesse o portal de pagamento para atualizar seu cartão '
                'e reativar o acesso.'
            )

        # ── Status liberados (ativa / trial) ────────────────────
        if assinatura.status in STATUS_LIBERADOS:

            # Sem data_fim: Stripe gerencia — libera
            if not assinatura.data_fim:
                return False, ''

            # Dentro do período válido → libera
            if hoje <= assinatura.data_fim:
                return False, ''

            # Passou da data_fim mas dentro do grace period
            dias_apos_vencimento = (hoje - assinatura.data_fim).days
            if dias_apos_vencimento <= GRACE_PERIOD_DIAS:
                logger.warning(
                    f"Assinatura {assinatura.pk} com data_fim={assinatura.data_fim} "
                    f"({dias_apos_vencimento}d atrás) — dentro do grace period, liberando."
                )
                return False, ''

            return True, (
                f'Sua assinatura venceu em {assinatura.data_fim.strftime("%d/%m/%Y")} '
                f'e a renovação ainda não foi confirmada. '
                f'Se você acabou de renovar, aguarde alguns minutos e tente novamente. '
                f'Se o problema persistir, acesse o portal de pagamento.'
            )

        # Status desconhecido → bloqueia por segurança
        return True, 'Status de assinatura não reconhecido. Entre em contato com o suporte.'

    # ── Avaliação de recurso por rota ──────────────────────────

    @staticmethod
    def _avaliar_recurso(request) -> tuple[bool, str]:
        """
        Verifica se o plano ativo tem o recurso exigido pela rota acessada.
        Retorna (bloqueado: bool, mensagem: str).
        """
        path  = request.path
        plano = getattr(request, 'plano_ativo', None)

        # Sem plano resolvido → deixa passar (PlanoMiddleware não encontrou)
        if plano is None:
            return False, ''

        for prefixo, chave_recurso in RECURSOS_POR_ROTA.items():
            if not path.startswith(prefixo):
                continue

            if not plano.tem_recurso(chave_recurso):
                nome = NOMES_RECURSO.get(chave_recurso, chave_recurso)
                logger.info(
                    f"Recurso '{chave_recurso}' bloqueado — "
                    f"plano={plano.slug} path={path}"
                )
                return True, (
                    f'O recurso "{nome}" não está disponível no plano {plano.nome}. '
                    f'Faça upgrade para acessar.'
                )

        return False, ''
