from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
import json

from clientes.models import Cliente

from .models import Locacao, ItemLocacao
from .forms import LocacaoForm, ItemLocacaoFormSet
from .services import LocacaoService, DisponibilidadeService, DisponibilidadeError
from core.mixins import VerificarLimiteLocacaoMixin
from notificacoes.services import NotificacaoService
from produtos.models import Produto


def _produtos_json():
    """
    Retorna string JSON válida para uso em templates.
    DjangoJSONEncoder converte Decimal -> float corretamente.
    """
    qs = list(
        Produto.objects.filter(status='ativo')
        .values('id', 'nome', 'valor_diario', 'quantidade_disponivel')
        .order_by('nome')
    )

    return json.dumps(qs, cls=DjangoJSONEncoder)


class LocacaoListView(LoginRequiredMixin, ListView):
    model = Locacao
    template_name = 'locacoes/lista.html'
    context_object_name = 'locacoes'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('cliente').prefetch_related('itens__produto')
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        if q:
            qs = qs.filter(Q(cliente__nome__icontains=q) | Q(pk__icontains=q))
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Locacao.STATUS_CHOICES
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status_sel'] = self.request.GET.get('status', '')
        return ctx


class LocacaoCreateView(VerificarLimiteLocacaoMixin, LoginRequiredMixin, CreateView):
    model = Locacao
    form_class = LocacaoForm
    template_name = 'locacoes/form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = ItemLocacaoFormSet(self.request.POST)
        else:
            ctx['formset'] = ItemLocacaoFormSet()
        ctx['titulo'] = 'Nova Locação'
        ctx['produtos_json'] = _produtos_json()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if not formset.is_valid():
            return self.form_invalid(form)

        itens_data = []
        for f in formset:
            if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                itens_data.append({
                    'produto_id': f.cleaned_data['produto'].id,
                    'quantidade': f.cleaned_data['quantidade'],
                    'valor_unitario': f.cleaned_data['valor_unitario'],
                })

        if not itens_data:
            messages.error(self.request, 'Adicione ao menos um item à locação.')
            return self.form_invalid(form)
        


        try:
            locacao = LocacaoService.criar_locacao(
                cliente=form.cleaned_data['cliente'],
                data_inicio=form.cleaned_data['data_inicio'],
                data_fim=form.cleaned_data['data_fim_prevista'],
                itens_data=itens_data,
                usuario=self.request.user,
                observacoes=form.cleaned_data.get('observacoes', ''),
            )
            messages.success(self.request, f'Locação #{locacao.pk} criada com sucesso!')
            return redirect('locacoes:detalhe', pk=locacao.pk)
        except DisponibilidadeError as e:
            messages.error(self.request, f'Conflito de disponibilidade:\n{e}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class LocacaoUpdateView(LoginRequiredMixin, UpdateView):
    model = Locacao
    form_class = LocacaoForm
    template_name = 'locacoes/form.html'
    ordering = ['-criado_em']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = ItemLocacaoFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = ItemLocacaoFormSet(instance=self.object)
        ctx['titulo'] = f'Editar Locação #{self.object.pk}'
        ctx['produtos_json'] = _produtos_json()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if not formset.is_valid():
            return self.form_invalid(form)

        itens_data = []
        for f in formset:
            if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                itens_data.append({
                    'produto_id': f.cleaned_data['produto'].id,
                    'quantidade': f.cleaned_data['quantidade'],
                    'valor_unitario': f.cleaned_data['valor_unitario'],
                })

        if not itens_data:
            messages.error(self.request, 'Adicione ao menos um item à locação.')
            return self.form_invalid(form)

        try:
            LocacaoService.atualizar_locacao(
                locacao=self.object,
                data_inicio=form.cleaned_data['data_inicio'],
                data_fim=form.cleaned_data['data_fim_prevista'],
                itens_data=itens_data,
                observacoes=form.cleaned_data.get('observacoes', ''),
            )
            messages.success(self.request, 'Locação atualizada com sucesso!')
            return redirect('locacoes:detalhe', pk=self.object.pk)
        except DisponibilidadeError as e:
            messages.error(self.request, f'Conflito de disponibilidade:\n{e}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class LocacaoDetailView(LoginRequiredMixin, DetailView):
    model = Locacao
    template_name = 'locacoes/detalhe.html'
    context_object_name = 'locacao'

    def get_queryset(self):
        return super().get_queryset().select_related('cliente', 'criado_por').prefetch_related('itens__produto')


class LocacaoFinalizarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        locacao = get_object_or_404(Locacao, pk=pk)
        try:
            LocacaoService.finalizar_locacao(locacao)
            NotificacaoService.notificar_produto_devolvido(locacao)
            messages.success(request, f'Locação #{pk} finalizada e produtos devolvidos ao estoque.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('locacoes:detalhe', pk=pk)


class LocacaoCancelarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        locacao = get_object_or_404(Locacao, pk=pk)
        try:
            LocacaoService.cancelar_locacao(locacao)
            messages.success(request, f'Locação #{pk} cancelada.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('locacoes:detalhe', pk=pk)


def verificar_disponibilidade_ajax(request):
    """Endpoint AJAX para verificar disponibilidade em tempo real."""
    from datetime import date
    produto_id = request.GET.get('produto_id')
    quantidade = int(request.GET.get('quantidade', 1))
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    locacao_id = request.GET.get('locacao_id')

    if not all([produto_id, data_inicio, data_fim]):
        return JsonResponse({'error': 'Parâmetros insuficientes'}, status=400)

    try:
        produto = Produto.objects.get(pk=produto_id)
        d_inicio = date.fromisoformat(data_inicio)
        d_fim = date.fromisoformat(data_fim)
        resultado = LocacaoService.verificar_disponibilidade(
            produto, quantidade, d_inicio, d_fim,
            excluir_locacao_id=int(locacao_id) if locacao_id else None
        )
        return JsonResponse(resultado)
    except Produto.DoesNotExist:
        return JsonResponse({'error': 'Produto não encontrado'}, status=404)
