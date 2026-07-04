from django.urls import path
from . import views
from .whatsapp_views import (
    WhatsAppConfigView,
    WhatsAppTesteView,
    WhatsAppWebhookView,
    WhatsAppEnviarLocacaoView,
)

app_name = 'notificacoes'

urlpatterns = [
    path('', views.NotificacaoListView.as_view(), name='lista'),
    path('<int:pk>/lida/', views.MarcarLidaView.as_view(), name='marcar_lida'),
    path('marcar-todas/', views.MarcarTodasLidasView.as_view(), name='marcar_todas'),

    path('whatsapp/',                  WhatsAppConfigView.as_view(),        name='whatsapp_config'),
    path('whatsapp/teste/',            WhatsAppTesteView.as_view(),          name='whatsapp_teste'),
    path('whatsapp/webhook/',          WhatsAppWebhookView.as_view(),        name='whatsapp_webhook'),
    path('whatsapp/locacao/<int:pk>/', WhatsAppEnviarLocacaoView.as_view(),  name='whatsapp_locacao'),
]