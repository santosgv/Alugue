from django.contrib import messages
from django.shortcuts import redirect

from .services import LimiteService, LimitePlanoExcedido


class VerificarLimiteMixin:
    """
    Mixin base. Subclasses definem `verificar_limite_plano()`.
    O método é chamado no dispatch, antes de qualquer GET ou POST.
    """
    redirect_url_on_limit = 'planos'

    def verificar_limite_plano(self):
        """
        Retorna None se OK.
        Levanta LimitePlanoExcedido ou retorna uma mensagem de erro (str).
        """
        return None

    def dispatch(self, request, *args, **kwargs):
        plano = getattr(request, 'plano_ativo', None)

        if not plano:
            messages.error(
                request,
                "Sua assinatura está inativa. Regularize seu plano para continuar."
            )
            return redirect('/planos')
        
        if plano:
            try:
                self.verificar_limite_plano()
            except LimitePlanoExcedido as e:
                messages.error(request, str(e))
                return redirect(self.redirect_url_on_limit)
        return super().dispatch(request, *args, **kwargs)

class VerificarLimiteClienteMixin(VerificarLimiteMixin):
    """Bloqueia criação de cliente quando o limite do plano é atingido."""

    def verificar_limite_plano(self):
        from clientes.models import Cliente
        plano = getattr(self.request, 'plano_ativo', None)
        if not plano:
            return
        total = Cliente.objects.filter(ativo=True).count()
        LimiteService.verificar_limite_clientes(plano, total)

class VerificarLimiteProdutoMixin(VerificarLimiteMixin):
    """Bloqueia criação de produto quando o limite do plano é atingido."""

    def verificar_limite_plano(self):
        from produtos.models import Produto
        plano = getattr(self.request, 'plano_ativo', None)
        if not plano:
            return
        total = Produto.objects.filter(status='ativo').count()
        LimiteService.verificar_limite_produtos(plano, total)

class VerificarLimiteCategoriaMixin(VerificarLimiteMixin):
    """Bloqueia criação de Categoria quando o limite do plano é atingido."""

    def verificar_limite_plano(self):
        from produtos.models import CategoriaProduto
        plano = getattr(self.request, 'plano_ativo', None)
        if not plano:
            return
        total = CategoriaProduto.objects.count()
        LimiteService.verificar_limite_categorias(plano, total)

class VerificarLimiteLocacaoMixin(VerificarLimiteMixin):
    """Bloqueia criação de locação quando o limite do plano é atingido."""

    def verificar_limite_plano(self):
        from locacoes.models import Locacao
        plano = getattr(self.request, 'plano_ativo', None)
        if not plano or plano.locacoes_ilimitadas:
            return
        total = Locacao.objects.filter(status__in=['ativa', 'pendente']).count()
        LimiteService.verificar_limite_locacoes(plano, total)

class VerificarLimiteUsuarioMixin(VerificarLimiteMixin):
    """
    Bloqueia criação de usuário quando o limite do plano é atingido.
    Conta apenas usuários ativos da empresa (excluindo superusers).
    """
    redirect_url_on_limit = 'accounts:usuarios_empresa'

    def verificar_limite_plano(self):
        from accounts.models import PerfilUsuario
        plano   = getattr(self.request, 'plano_ativo', None)
        empresa = getattr(self.request, 'empresa', None)
        if not plano or plano.usuarios_ilimitados:
            return
        total = PerfilUsuario.objects.filter(
            empresa=empresa, ativo=True
        ).exclude(user__is_superuser=True).count()
        LimiteService.verificar_limite_usuarios(plano, total)