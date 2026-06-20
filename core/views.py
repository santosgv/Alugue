from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponse
from django.views.generic import TemplateView, FormView, View
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import cache_page
from accounts.models import PerfilUsuario
from clientes.models import Cliente
from locagest import settings
from produtos.models import Produto,CategoriaProduto
from locacoes.models import Locacao
from locacoes.services import DisponibilidadeService
import os
from .models import SubscriptionPlan, Assinatura
from .services import AssinaturaService, LimiteService
from .forms import MudarPlanoForm, CancelarAssinaturaForm, TenantCompanyForm
from django.contrib import sitemaps

# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx['total_clientes']      = Cliente.objects.filter(ativo=True).count()
        ctx['total_produtos']      = Produto.objects.filter(status='ativo').count()
        ctx['total_categorias']    = CategoriaProduto.objects.count()
        ctx['locacoes_ativas']     = Locacao.objects.filter(status__in=['ativa', 'pendente']).count()
        ctx['locacoes_atrasadas']  = Locacao.objects.filter(status='atrasada').count()
        ctx['proximas_devolucoes'] = DisponibilidadeService.produtos_proximos_devolucao(dias=7)
        ctx['locacoes_em_atraso']  = DisponibilidadeService.locacoes_atrasadas()[:5]
        ctx['produtos_disponiveis'] = Produto.objects.filter(status='ativo', quantidade_disponivel__gt=0).count()
        ctx['produtos_esgotados']   = Produto.objects.filter(status='ativo', quantidade_disponivel=0).count()


        # Total de usuários ativos da empresa (excluindo superusers)
        empresa = getattr(self.request, 'empresa', None)
        ctx['total_usuarios'] = (
            PerfilUsuario.objects
            .filter(empresa=empresa, ativo=True)
            .exclude(user__is_superuser=True)
            .count()
        ) if empresa else 0

        # Uso do plano
        plano = getattr(self.request, 'plano_ativo', None)
        if plano:
            ctx['uso_plano'] = LimiteService.uso_atual(
                plano,
                total_clientes=ctx['total_clientes'],
                total_produtos=ctx['total_produtos'],
                total_categorias=ctx['total_categorias'],
                total_locacoes=ctx['locacoes_ativas'],
                total_usuarios=ctx['total_usuarios'],
            )
        return ctx


# ─────────────────────────────────────────────────────────────
# PÁGINA PÚBLICA DE PLANOS
# ─────────────────────────────────────────────────────────────

class PlanosView(TemplateView):
    template_name = 'core/planos.html'
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .recursos_config import get_recursos_para_plano

        planos_qs = SubscriptionPlan.objects.filter(ativo=True).order_by('ordem', 'preco_mensal')

        # Para cada plano, calcula o estado de cada recurso (ativo/indisponivel/em_desenvolvimento)
        planos_com_recursos = [
            {
                'plano':    plano,
                'recursos': get_recursos_para_plano(plano),
            }
            for plano in planos_qs
        ]

        ctx['planos_com_recursos'] = planos_com_recursos
        ctx['planos']              = planos_qs          # mantido para compatibilidade
        ctx['ciclo_sel']           = self.request.GET.get('ciclo', 'mensal')
        ctx['plano_atual']         = getattr(self.request, 'plano_ativo', None)

        # Detecta se o usuário chegou aqui bloqueado pelo guard
        assinatura = getattr(self.request, 'assinatura', None)
        ctx['acesso_bloqueado'] = False
        ctx['motivo_bloqueio']  = ''
        if self.request.user.is_authenticated and not self.request.user.is_superuser:
            from .middleware import AssinaturaGuardMiddleware
            bloqueado, motivo = AssinaturaGuardMiddleware._avaliar(assinatura)
            ctx['acesso_bloqueado'] = bloqueado
            ctx['motivo_bloqueio']  = motivo
        return ctx

# ─────────────────────────────────────────────────────────────
# PAINEL DA ASSINATURA
# ─────────────────────────────────────────────────────────────


class AssinaturaPainelView(LoginRequiredMixin, TemplateView):
    template_name = 'core/assinatura_painel.html'
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = getattr(self.request, 'empresa', None)
        if empresa:
            ctx['historico'] = empresa.assinaturas.select_related('plano').order_by('-criado_em')[:10]
        ctx['planos'] = SubscriptionPlan.objects.filter(ativo=True).order_by('ordem')
        ctx['form_cancelar'] = CancelarAssinaturaForm()
 
        plano = getattr(self.request, 'plano_ativo', None)
        if plano:
            ctx['uso_plano'] = LimiteService.uso_atual(
                plano,
                total_clientes=Cliente.objects.filter(ativo=True).count(),
                total_produtos=Produto.objects.filter(status='ativo').count(),
                total_categorias= CategoriaProduto.objects.count(),
                total_usuarios= PerfilUsuario.objects.filter(empresa=empresa,ativo=True).count(),
                total_locacoes=Locacao.objects.filter(status__in=['ativa', 'pendente']).count(),
            )
        return ctx
 

# ─────────────────────────────────────────────────────────────
# MUDAR PLANO
# ─────────────────────────────────────────────────────────────

class MudarPlanoView(LoginRequiredMixin, View):

    def post(self, request):
        form = MudarPlanoForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Dados inválidos. Tente novamente.')
            return redirect('planos')

        empresa = getattr(request, 'empresa', None)
        if not empresa:
            messages.error(request, 'Nenhuma empresa configurada.')
            return redirect('planos')

        novo_plano = form.cleaned_data['plano']
        ciclo      = form.cleaned_data['ciclo']

        try:
            nova_sub = AssinaturaService.mudar_plano(
                empresa=empresa,
                novo_plano=novo_plano,
                ciclo=ciclo,
                usuario=request.user,
            )
            messages.success(
                request,
                f'Plano alterado para {novo_plano.nome} com sucesso! '
                f'Vigência: {nova_sub.data_inicio:%d/%m/%Y} a {nova_sub.data_fim:%d/%m/%Y}.'
            )
        except Exception as e:
            messages.error(request, f'Erro ao mudar plano: {e}')

        return redirect('assinatura_painel')


# ─────────────────────────────────────────────────────────────
# CANCELAR ASSINATURA
# ─────────────────────────────────────────────────────────────

class CancelarAssinaturaView(LoginRequiredMixin, FormView):
    form_class    = CancelarAssinaturaForm
    template_name = 'core/cancelar_assinatura.html'
    success_url   = reverse_lazy('assinatura_painel')

    def form_valid(self, form):
        assinatura = getattr(self.request, 'assinatura', None)
        if not assinatura:
            messages.error(self.request, 'Nenhuma assinatura ativa encontrada.')
            return redirect('assinatura_painel')

        try:
            AssinaturaService.cancelar(
                assinatura,
                motivo=form.cleaned_data.get('motivo', ''),
                usuario=self.request.user,
            )
            messages.warning(
                self.request,
                'Assinatura cancelada. Você pode continuar usando o sistema até o fim do período pago.'
            )
        except Exception as e:
            messages.error(self.request, str(e))

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['assinatura'] = getattr(self.request, 'assinatura', None)
        return ctx


# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÕES DA EMPRESA
# ─────────────────────────────────────────────────────────────

class EmpresaConfigView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/empresa_config.html'

    def test_func(self):
        return self.request.user.is_staff

    def get(self, request):
        from django.shortcuts import render
        empresa = getattr(request, 'empresa', None)
        form = TenantCompanyForm(instance=empresa)
        return render(request, self.template_name, {'form': form, 'empresa': empresa})

    def post(self, request):
        from django.shortcuts import render
        empresa = getattr(request, 'empresa', None)
        form = TenantCompanyForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações salvas com sucesso!')
            return redirect('empresa_config')
        return render(request, self.template_name, {'form': form, 'empresa': empresa})


class PaginaVendasView(TemplateView):
    template_name = 'core/pagina_vendas.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .recursos_config import get_recursos_para_plano

        planos_qs = SubscriptionPlan.objects.filter(ativo=True).order_by('ordem', 'preco_mensal')

        # Para cada plano, calcula o estado de cada recurso (ativo/indisponivel/em_desenvolvimento)
        planos_com_recursos = [
            {
                'plano':    plano,
                'recursos': get_recursos_para_plano(plano),
            }
            for plano in planos_qs
        ]

        ctx['planos_com_recursos'] = planos_com_recursos
        ctx['planos']              = planos_qs          # mantido para compatibilidade
        ctx['ciclo_sel']           = self.request.GET.get('ciclo', 'mensal')
        ctx['plano_atual']         = getattr(self.request, 'plano_ativo', None)

        # Detecta se o usuário chegou aqui bloqueado pelo guard
        assinatura = getattr(self.request, 'assinatura', None)
        ctx['acesso_bloqueado'] = False
        ctx['motivo_bloqueio']  = ''
        if self.request.user.is_authenticated and not self.request.user.is_superuser:
            from .middleware import AssinaturaGuardMiddleware
            bloqueado, motivo = AssinaturaGuardMiddleware._avaliar(assinatura)
            ctx['acesso_bloqueado'] = bloqueado
            ctx['motivo_bloqueio']  = motivo
        return ctx

@cache_page(60 * 15)
def robots(request):
    if not settings.DEBUG:
        path = os.path.join(settings.STATIC_ROOT,'robots.txt')
        with open(path,'r') as arq:
            return HttpResponse(arq, content_type='text/plain')
    else:
        path = os.path.join(settings.BASE_DIR,'templates/robots.txt')
        with open(path,'r') as arq:
            return HttpResponse(arq, content_type='text/plain')
        

class Sitemap(sitemaps.Sitemap):
    priority = 0.8
    changefreq = "annual"

    def items(self):
        return [
            "pagina_vendas",
            "robots_txt",
            "accounts:login",
        ]

    def location(self, item):
        return reverse(item)