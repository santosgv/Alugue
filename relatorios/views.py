from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .services import (
    RelatorioAtrasoService,
    RelatorioFaturamentoService,
    RelatorioProdutosService,
    RelatorioOcupacaoService,
    RelatorioClientesService,
    RelatorioStatusService,
)


class RelatoriosIndexView(LoginRequiredMixin, TemplateView):
    """Página inicial dos relatórios — lista todos disponíveis."""
    template_name = 'relatorios/index.html'


class RelatorioAtrasoView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/atraso.html'

    def get_context_data(self, **kwargs):
        ctx     = super().get_context_data(**kwargs)
        ordenar = self.request.GET.get('ordenar', 'dias_atraso')
        ctx.update(RelatorioAtrasoService.dados(ordenar=ordenar))
        ctx['ordenar'] = ordenar
        return ctx


class RelatorioFaturamentoView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/faturamento.html'

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        meses = int(self.request.GET.get('meses', 12))
        meses = max(1, min(meses, 24))          # limita 1–24
        ctx.update(RelatorioFaturamentoService.dados(meses=meses))
        return ctx


class RelatorioProdutosView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/produtos.html'

    def get_context_data(self, **kwargs):
        ctx    = super().get_context_data(**kwargs)
        limite = int(self.request.GET.get('limite', 20))
        ctx.update(RelatorioProdutosService.dados(limite=limite))
        return ctx


class RelatorioOcupacaoView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/ocupacao.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(RelatorioOcupacaoService.dados())
        return ctx


class RelatorioClientesView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/clientes.html'

    def get_context_data(self, **kwargs):
        ctx    = super().get_context_data(**kwargs)
        limite = int(self.request.GET.get('limite', 20))
        ctx.update(RelatorioClientesService.dados(limite=limite))
        return ctx


class RelatorioStatusView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/status.html'

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        dias = int(self.request.GET.get('dias', 30))
        dias = max(7, min(dias, 365))
        ctx.update(RelatorioStatusService.dados(dias=dias))
        return ctx