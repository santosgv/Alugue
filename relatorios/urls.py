from django.urls import path
from . import views
from django_ratelimit.decorators import ratelimit

app_name = 'relatorios'

urlpatterns = [
    path('',             ratelimit(key='ip', method='GET', rate='10/m')(views.RelatoriosIndexView.as_view()),    name='index'),
    path('atraso/',      ratelimit(key='ip', method='GET', rate='10/m')(views.RelatorioAtrasoView.as_view()),    name='atraso'),
    path('faturamento/', ratelimit(key='ip', method='GET', rate='10/m')(views.RelatorioFaturamentoView.as_view()),name='faturamento'),
    path('produtos/',    ratelimit(key='ip', method='GET', rate='10/m')(views.RelatorioProdutosView.as_view()),  name='produtos'),
    path('ocupacao/',    ratelimit(key='ip', method='GET', rate='10/m')(views.RelatorioOcupacaoView.as_view()),  name='ocupacao'),
    path('clientes/',    ratelimit(key='ip', method='GET', rate='10/m')(views.RelatorioClientesView.as_view()),  name='clientes'),
    path('status/',      ratelimit(key='ip', method='GET', rate='10/m')(views.RelatorioStatusView.as_view()),    name='status'),
]