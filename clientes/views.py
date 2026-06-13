from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.db.models import Q

from .models import Cliente
from .forms import ClienteForm
from core.mixins import VerificarLimiteClienteMixin

from django.http import JsonResponse

def cliente_detalhe(request, pk):
    cliente = Cliente.objects.get(pk=pk)

    return JsonResponse({
        'id': cliente.id,
        'nome': cliente.nome,
        'cpf_cnpj': cliente.cpf_cnpj,
        'telefone': cliente.telefone,
    })


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/lista.html'
    context_object_name = 'clientes'
    paginate_by = 20
    ordering = ['-data_cadastro']

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q) | Q(email__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')

        # Informa o limite para exibir barra de uso na listagem
        plano = getattr(self.request, 'plano_ativo', None)
        if plano:
            total = self.get_queryset().filter(ativo=True).count()
            ctx['limite_clientes'] = plano.limite_clientes
            ctx['total_clientes']  = total
            ctx['clientes_ilimitado'] = plano.clientes_ilimitados
            ctx['pct_clientes'] = (
                0 if plano.clientes_ilimitados
                else min(100, round(total / plano.limite_clientes * 100))
            )
        return ctx


class ClienteCreateView(VerificarLimiteClienteMixin, LoginRequiredMixin, CreateView):
    """
    Verifica limite do plano ANTES de exibir ou processar o formulário.
    Se o limite foi atingido, redireciona para /planos/ com mensagem de erro.
    """
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'
    success_url = reverse_lazy('clientes:lista')

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        messages.success(self.request, f'Cliente "{form.instance.nome}" cadastrado com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Cliente'
        ctx['botao'] = 'Cadastrar Cliente'
        # Passa contexto de limite para o template
        plano = getattr(self.request, 'plano_ativo', None)
        if plano and not plano.clientes_ilimitados:
            from clientes.models import Cliente as ClienteModel
            total = ClienteModel.objects.filter(ativo=True).count()
            ctx['limite_info'] = {
                'atual': total,
                'limite': plano.limite_clientes,
                'restante': plano.limite_clientes - total,
                'pct': min(100, round(total / plano.limite_clientes * 100)),
            }
        return ctx


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'
    success_url = reverse_lazy('clientes:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Cliente'
        ctx['botao'] = 'Salvar Alterações'
        return ctx


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clientes/detalhe.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['locacoes'] = (
            self.object.locacao_set
            .select_related('cliente')
            .prefetch_related('itens__produto')
            .order_by('-criado_em')[:10]
        )
        return ctx


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'clientes/confirmar_exclusao.html'
    success_url = reverse_lazy('clientes:lista')

    def form_valid(self, form):
        nome = self.object.nome
        messages.success(self.request, f'Cliente "{nome}" excluído com sucesso!')
        return super().form_valid(form)
