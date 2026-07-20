from django.urls import path
from . import views
from django_ratelimit.decorators import ratelimit

app_name = 'produtos'

urlpatterns = [
    path('', ratelimit(key='ip', method='GET', rate='10/m')(views.ProdutoListView.as_view()), name='lista'),
    path('novo/', ratelimit(key='ip', method='GET', rate='10/m')(views.ProdutoCreateView.as_view()), name='criar'),
    path('<int:pk>/', ratelimit(key='ip', method='GET', rate='10/m')(views.ProdutoDetailView.as_view()), name='detalhe'),
    path('<int:pk>/editar/', ratelimit(key='ip', method='GET', rate='10/m')(views.ProdutoUpdateView.as_view()), name='editar'),
    path('<int:pk>/excluir/', ratelimit(key='ip', method='GET', rate='10/m')(views.ProdutoDeleteView.as_view()), name='excluir'),

    path('categorias', ratelimit(key='ip', method='GET', rate='10/m')(views.CategoriaProdutoListView.as_view()), name='lista-categorias'),
    path('nova-categoria/', ratelimit(key='ip', method='GET', rate='10/m')(views.CategoriaProdutoCreateView.as_view()), name='novo-categoria'),
    path('categoria/<int:pk>', ratelimit(key='ip', method='GET', rate='10/m')(views.CategoriaProdutoDetailView.as_view()), name='detalhe-categoria'),
    path('categoria/<int:pk>/editar/', ratelimit(key='ip', method='GET', rate='10/m')(views.CategoriaProdutoUpdateView.as_view()), name='editar-categoria'),
    path('categoria/<int:pk>/excluir/', ratelimit(key='ip', method='GET', rate='10/m')(views.CategoriaProdutoDeleteView.as_view()), name='excluir-categoria'),
]