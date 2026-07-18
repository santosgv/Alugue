from django.urls import path
from . import views
from .utils import *
from django_ratelimit.decorators import ratelimit

app_name = 'locacoes'

urlpatterns = [
    path('', ratelimit(key='ip', method='GET', rate='10/m')(views.LocacaoListView.as_view()), name='lista'),
    path('nova/', ratelimit(key='ip', method='GET', rate='10/m')(views.LocacaoCreateView.as_view()), name='criar'),
    path('<int:pk>/', ratelimit(key='ip', method='GET', rate='10/m')(views.LocacaoDetailView.as_view()), name='detalhe'),
    path('<int:pk>/editar/', ratelimit(key='ip', method='GET', rate='10/m')(views.LocacaoUpdateView.as_view()), name='editar'),
    path('<int:pk>/finalizar/', ratelimit(key='ip', method='GET', rate='10/m')(views.LocacaoFinalizarView.as_view()), name='finalizar'),
    path('<int:pk>/cancelar/', ratelimit(key='ip', method='GET', rate='10/m')(views.LocacaoCancelarView.as_view()), name='cancelar'),
    path('ajax/disponibilidade/', ratelimit(key='ip', method='GET', rate='100/m')(views.verificar_disponibilidade_ajax), name='verificar_disponibilidade'),

    path(
    '<int:pk>/pdf/',
    gerar_pdf_locacao,
    name='pdf'
),
]