from django.urls import path
from . import views

app_name = 'relatorios'

urlpatterns = [
    path('',             views.RelatoriosIndexView.as_view(),    name='index'),
    path('atraso/',      views.RelatorioAtrasoView.as_view(),    name='atraso'),
    path('faturamento/', views.RelatorioFaturamentoView.as_view(),name='faturamento'),
    path('produtos/',    views.RelatorioProdutosView.as_view(),  name='produtos'),
    path('ocupacao/',    views.RelatorioOcupacaoView.as_view(),  name='ocupacao'),
    path('clientes/',    views.RelatorioClientesView.as_view(),  name='clientes'),
    path('status/',      views.RelatorioStatusView.as_view(),    name='status'),
]