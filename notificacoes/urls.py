from django.urls import path
from . import views

app_name = 'notificacoes'

urlpatterns = [
    path('', views.NotificacaoListView.as_view(), name='lista'),
    path('<int:pk>/lida/', views.MarcarLidaView.as_view(), name='marcar_lida'),
    path('marcar-todas/', views.MarcarTodasLidasView.as_view(), name='marcar_todas'),
]