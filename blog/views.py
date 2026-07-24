# blog/views.py
from django.shortcuts import render, get_object_or_404,redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Post, Category, Comentario
from .forms import ComentarioForm

class PostListView(ListView):
    """Lista todos os posts publicados"""
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 12

    def get_queryset(self):
        queryset = Post.get_published()
        
        # Filtro por categoria
        categoria = self.kwargs.get('categoria')
        if categoria:
            queryset = queryset.filter(categoria__slug=categoria)
        
        # Busca
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(titulo__icontains=q) |
                Q(resumo__icontains=q) |
                Q(conteudo__icontains=q) |
                Q(tags__name__icontains=q)
            ).distinct()
        
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Posts em destaque
        ctx['posts_destaque'] = Post.get_destaques()
        
        # Categorias
        ctx['categorias'] = Category.objects.filter(ativo=True).order_by('ordem')
        
        # Posts populares
        ctx['posts_populares'] = Post.get_populares()
        
        # Arquivo por mês
        ctx['arquivo_meses'] = self._get_arquivo_meses()
        
        return ctx

    def _get_arquivo_meses(self):
        """Retorna meses com posts para arquivo"""
        from django.db.models import Count
        from django.db.models.functions import TruncMonth
        
        return (Post.get_published()
                .annotate(mes=TruncMonth('published_at'))
                .values('mes')
                .annotate(total=Count('id'))
                .order_by('-mes'))


class PostDetailView(DetailView):
    """Exibe um post completo"""
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Post.get_published()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        imagens_galeria = self.object.imagens.all().order_by('ordem')
        ctx['imagens_galeria'] = imagens_galeria

        ctx['tem_galeria'] = imagens_galeria.exists()
        
        # Incrementa visualizações
        self.object.incrementar_views()
        
        # Posts relacionados
        ctx['posts_relacionados'] = Post.get_published().filter(
            categoria=self.object.categoria
        ).exclude(id=self.object.id)[:4]
        
        # Categorias para sidebar
        ctx['categorias'] = Category.objects.filter(ativo=True).order_by('ordem')
        
        # Posts populares
        ctx['posts_populares'] = Post.get_populares()
        
        # Formulário de comentário
        ctx['form_comentario'] = ComentarioForm()
        
        # Comentários aprovados
        ctx['comentarios'] = self.object.comentarios.filter(publicado=True)
        
        return ctx

    def post(self, request, *args, **kwargs):
        """Processa o envio de comentários"""
        self.object = self.get_object()
        form = ComentarioForm(request.POST)
        
        if form.is_valid():
            comentario = form.save(commit=False)
            comentario.post = self.object
            comentario.save()
            
            # Redireciona para o post com âncora
            return redirect(f"{self.object.get_absolute_url()}#comentarios")
        
        # Se o formulário for inválido, mostra a página com erros
        ctx = self.get_context_data()
        ctx['form_comentario'] = form
        return render(request, self.template_name, ctx)


def post_search(request):
    """Página de busca de posts"""
    q = request.GET.get('q', '')
    posts = Post.get_published()
    
    if q:
        posts = posts.filter(
            Q(titulo__icontains=q) |
            Q(resumo__icontains=q) |
            Q(conteudo__icontains=q) |
            Q(tags__name__icontains=q)
        ).distinct()
    
    paginator = Paginator(posts, 12)
    page = request.GET.get('page')
    
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    
    return render(request, 'blog/post_search.html', {
        'posts': posts,
        'q': q,
        'resultados': posts.paginator.count,
    })