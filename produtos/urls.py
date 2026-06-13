from django.urls import path
from . import views

app_name = 'produtos'

urlpatterns = [
    path('', views.ProdutoListView.as_view(), name='lista'),
    path('novo/', views.ProdutoCreateView.as_view(), name='criar'),
    path('<int:pk>/', views.ProdutoDetailView.as_view(), name='detalhe'),
    path('<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='editar'),
    path('<int:pk>/excluir/', views.ProdutoDeleteView.as_view(), name='excluir'),

    path('categorias', views.CategoriaProdutoListView.as_view(), name='lista-categorias'),
    path('nova-categoria/', views.CategoriaProdutoCreateView.as_view(), name='novo-categoria'),
    path('categoria/<int:pk>', views.CategoriaProdutoDetailView.as_view(), name='detalhe-categoria'),
    path('categoria/<int:pk>/editar/', views.CategoriaProdutoUpdateView.as_view(), name='editar-categoria'),
    path('categoria/<int:pk>/excluir/', views.CategoriaProdutoDeleteView.as_view(), name='excluir-categoria'),
]