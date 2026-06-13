from django.urls import path
from . import views
from .utils import *

app_name = 'locacoes'

urlpatterns = [
    path('', views.LocacaoListView.as_view(), name='lista'),
    path('nova/', views.LocacaoCreateView.as_view(), name='criar'),
    path('<int:pk>/', views.LocacaoDetailView.as_view(), name='detalhe'),
    path('<int:pk>/editar/', views.LocacaoUpdateView.as_view(), name='editar'),
    path('<int:pk>/finalizar/', views.LocacaoFinalizarView.as_view(), name='finalizar'),
    path('<int:pk>/cancelar/', views.LocacaoCancelarView.as_view(), name='cancelar'),
    path('ajax/disponibilidade/', views.verificar_disponibilidade_ajax, name='verificar_disponibilidade'),

    path(
    '<int:pk>/pdf/',
    gerar_pdf_locacao,
    name='pdf'
),
]