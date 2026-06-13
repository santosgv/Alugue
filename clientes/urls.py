from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('cliente/<int:pk>/',views.cliente_detalhe,name='cliente_detalhe'),
    path('', views.ClienteListView.as_view(), name='lista'),
    path('novo/', views.ClienteCreateView.as_view(), name='criar'),
    path('<int:pk>/', views.ClienteDetailView.as_view(), name='detalhe'),
    path('<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='editar'),
    path('<int:pk>/excluir/', views.ClienteDeleteView.as_view(), name='excluir'),
]