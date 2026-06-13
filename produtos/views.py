from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.db.models import Q,ProtectedError
from core.mixins import VerificarLimiteProdutoMixin,VerificarLimiteCategoriaMixin
from locacoes.models import ItemLocacao


from .models import Produto, CategoriaProduto
from .forms import ProdutoForm, CategoriaProdutoForm


class ProdutoListView(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'produtos/lista.html'
    context_object_name = 'produtos'
    paginate_by = 20
    ordering = ['-criado_em']

    def get_queryset(self):
        qs = super().get_queryset().select_related('categoria')
        q = self.request.GET.get('q')
        categoria = self.request.GET.get('categoria')
        status = self.request.GET.get('status')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(codigo_interno__icontains=q))
        if categoria:
            qs = qs.filter(categoria_id=categoria)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categorias'] = CategoriaProduto.objects.all()
        ctx['q'] = self.request.GET.get('q', '')
        ctx['categoria_sel'] = self.request.GET.get('categoria', '')
        ctx['status_sel'] = self.request.GET.get('status', '')
        ctx['status_choices'] = Produto.STATUS_CHOICES
        return ctx


class ProdutoCreateView(VerificarLimiteProdutoMixin,LoginRequiredMixin, CreateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'produtos/form.html'
    success_url = reverse_lazy('produtos:lista')

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        messages.success(self.request, 'Produto cadastrado com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Produto'
        ctx['botao'] = 'Cadastrar'
        return ctx


class ProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'produtos/form.html'
    success_url = reverse_lazy('produtos:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Produto atualizado com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Produto'
        ctx['botao'] = 'Salvar'
        return ctx


class ProdutoDetailView(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = 'produtos/detalhe.html'
    context_object_name = 'produto'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx['historico_locacoes'] = (
            ItemLocacao.objects
            .filter(produto=self.object)
            .select_related(
                'locacao',
                'locacao__cliente'
            )
            .order_by('-locacao__criado_em')[:10]
        )

        return ctx


class ProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = Produto
    template_name = 'produtos/confirmar_exclusao.html'
    success_url = reverse_lazy('produtos:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Produto excluído com sucesso!')
        return super().form_valid(form)
    

class CategoriaProdutoListView(LoginRequiredMixin, ListView):
    model = CategoriaProduto
    template_name = 'categorias/lista.html'
    context_object_name = 'categorias'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(nome__icontains=q) |
                Q(descricao__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class CategoriaProdutoCreateView(VerificarLimiteCategoriaMixin,LoginRequiredMixin, CreateView):
    model = CategoriaProduto
    form_class = CategoriaProdutoForm
    template_name = 'categorias/form.html'
    success_url = reverse_lazy('produtos:lista-categorias')

    def form_valid(self, form):
        messages.success(
            self.request,
            'Categoria cadastrada com sucesso!'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nova Categoria'
        ctx['botao'] = 'Cadastrar'
        return ctx


class CategoriaProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = CategoriaProduto
    form_class = CategoriaProdutoForm
    template_name = 'categorias/form.html'
    success_url = reverse_lazy('produtos:lista-categorias')

    def form_valid(self, form):
        messages.success(
            self.request,
            'Categoria atualizada com sucesso!'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Categoria'
        ctx['botao'] = 'Salvar'
        return ctx


class CategoriaProdutoDetailView(LoginRequiredMixin, DetailView):
    model = CategoriaProduto
    template_name = 'categorias/detalhe.html'
    context_object_name = 'categoria'


class CategoriaProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = CategoriaProduto
    template_name = 'categorias/confirmar_exclusao.html'
    success_url = reverse_lazy('produtos:lista-categorias')

    def delete(self, request, *args, **kwargs):
        try:
            messages.success(request, 'Categoria excluída com sucesso!')
            return super().delete(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                'Não é possível excluir esta categoria pois existem produtos vinculados.'
            )
            return redirect(self.success_url)
        


