from django.urls import path
from . import views
from django_ratelimit.decorators import ratelimit

app_name = 'clientes'

urlpatterns = [
    path('cliente/<int:pk>/', ratelimit(key='ip', method='GET', rate='10/m')(views.cliente_detalhe), name='cliente_detalhe'),
    path('', ratelimit(key='ip', method='GET', rate='10/m')(views.ClienteListView.as_view()), name='lista'),
    path('novo/', ratelimit(key='ip', method='GET', rate='10/m')(views.ClienteCreateView.as_view()), name='criar'),
    path('<int:pk>/', ratelimit(key='ip', method='GET', rate='10/m')(views.ClienteDetailView.as_view()), name='detalhe'),
    path('<int:pk>/editar/', ratelimit(key='ip', method='GET', rate='10/m')(views.ClienteUpdateView.as_view()), name='editar'),
    path('<int:pk>/excluir/', ratelimit(key='ip', method='GET', rate='10/m')(views.ClienteDeleteView.as_view()), name='excluir'),
]