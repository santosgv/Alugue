# blog/urls.py
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Lista de posts
    path('', views.PostListView.as_view(), name='post_list'),
    
    # Categoria
    path('categoria/<slug:categoria>/', views.PostListView.as_view(), name='categoria_detail'),
    
    # Busca
    path('busca/', views.post_search, name='post_search'),
    
    # Detalhe do post
    path('<slug:slug>/', views.PostDetailView.as_view(), name='post_detail'),
]