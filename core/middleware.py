"""
Middlewares de tenant/plano e guarda de assinatura.

── PlanoMiddleware ────────────────────────────────────────────
Resolve a empresa do usuário logado e injeta no request:
  request.empresa      → TenantCompany | None
  request.assinatura   → Assinatura | None
  request.plano_ativo  → SubscriptionPlan | None

Preparação para django-tenants:
  Substituir _resolver_empresa() por:
      from django_tenants.utils import get_tenant
      return get_tenant(request)

── AssinaturaGuardMiddleware ──────────────────────────────────
Bloqueia o acesso a todas as rotas operacionais quando a
assinatura está expirada, cancelada, suspensa ou inexistente.

Comportamento:
  - Superuser → sempre passa (administrador da plataforma).
  - Assinatura ativa ou trial com dias restantes → passa.
  - Trial vencido, expirado, cancelado, suspenso → redireciona
    para /planos/ com mensagem explicativa.
  - Rotas da lista ROTAS_LIBERADAS → sempre passam (login,
    logout, planos, assinatura, admin, static, media).
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from .models import TenantCompany
from .services import AssinaturaService


# ─────────────────────────────────────────────────────────────
# Rotas que sempre passam, independente do status da assinatura.
# Use prefixos — qualquer path que COMECE com esses valores é liberado.
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
        try:
            perfil = user.perfil
            if perfil.empresa and perfil.empresa.ativo:
                return perfil.empresa
        except Exception:
            pass
        # Fallback MVP — remover ao adotar django-tenants
        return TenantCompany.objects.filter(ativo=True).select_related('plano').first()


class AssinaturaGuardMiddleware(MiddlewareMixin):
    """
    Deve vir DEPOIS do PlanoMiddleware no settings.MIDDLEWARE,
    pois depende de request.assinatura já estar preenchido.
    """

    def process_request(self, request):
        # Não autenticado → login cuida do redirect
        if not request.user.is_authenticated:
            return

        # Superuser nunca é bloqueado
        if request.user.is_superuser:
            return

        # Rotas sempre liberadas
        path = request.path
        if any(path.startswith(rota) for rota in ROTAS_LIBERADAS):
            return

        # Verifica o status da assinatura
        assinatura = getattr(request, 'assinatura', None)
        bloqueado, motivo = self._avaliar(assinatura)

        if bloqueado:
            # Evita loop: se já está em /planos/ não adiciona msg de novo
            #messages.warning(request, motivo)
            print(motivo)
            return redirect('/planos/')

    # ── lógica de avaliação (separada para facilitar testes) ──

    @staticmethod
    def _avaliar(assinatura) -> tuple[bool, str]:
        """
        Retorna (bloqueado: bool, motivo: str).
        """
        hoje = timezone.localdate()

        # Sem assinatura alguma
        if assinatura is None:
            return True, (
                'Você não possui uma assinatura ativa. '
                'Escolha um plano para começar a usar o sistema.'
            )

        # Status definitivamente bloqueantes
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
                f'Sua assinatura venceu em '
                f'{assinatura.data_fim.strftime("%d/%m/%Y")} e não foi renovada. '
                f'Renove para continuar usando o sistema.'
            )

        # Passa — assinatura válida
        return False, ''