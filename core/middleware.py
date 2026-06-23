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
Bloqueia todas as rotas operacionais quando a assinatura está
expirada, cancelada, suspensa ou inexistente.
Redireciona para /planos/ com mensagem explicativa.
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

        assinatura = getattr(request, 'assinatura', None)
        bloqueado, motivo = self._avaliar(assinatura)

        if bloqueado:
            print(f'ACESSO BLOQUEADO: {request.user} → {path} | Motivo: {motivo}')
            #messages.warning(request, motivo)
            return redirect('/planos/')

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

        # Trial ou ativa — verifica se a data_fim já passou
        if assinatura.data_fim and hoje > assinatura.data_fim:
            if assinatura.status == 'trial':
                return True, (
                    f'Seu período de trial encerrou em '
                    f'{assinatura.data_fim.strftime("%d/%m/%Y")}. '
                    f'Escolha um plano para continuar.'
                )
            return True, (
                f'Sua assinatura venceu em {assinatura.data_fim.strftime("%d/%m/%Y")} '
                f'e a renovação ainda não foi confirmada. '
                f'Se você acabou de renovar, aguarde alguns minutos e tente novamente. '
                f'Se o problema persistir, acesse o portal de pagamento.'
            )

        # Passa — assinatura válida
        return False, ''