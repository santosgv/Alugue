from django.urls import path
from . import views
from .whatsapp_views import (
        WhatsAppConfigView, WhatsAppQRView,
        WhatsAppStatusView, WhatsAppDesconectarView,
        WhatsAppEnviarLocacaoView, WhatsAppTesteView,
    )
from django_ratelimit.decorators import ratelimit

app_name = 'notificacoes'

urlpatterns = [
    path('', ratelimit(key='ip', method='GET', rate='10/m')(views.NotificacaoListView.as_view()), name='lista'),
    path('<int:pk>/lida/', ratelimit(key='ip', method='GET', rate='10/m')(views.MarcarLidaView.as_view()), name='marcar_lida'),
    path('marcar-todas/', ratelimit(key='ip', method='GET', rate='10/m')(views.MarcarTodasLidasView.as_view()), name='marcar_todas'),

    path('whatsapp/',ratelimit(key='ip', method='GET', rate='10/m')                   (WhatsAppConfigView.as_view()),        name='whatsapp_config'),
    path('whatsapp/qr/',ratelimit(key='ip', method='GET', rate='10/m')                (WhatsAppQRView.as_view()),            name='whatsapp_qr'),
    path('whatsapp/status/',ratelimit(key='ip', method='GET', rate='10/m')            (WhatsAppStatusView.as_view()),        name='whatsapp_status'),
    path('whatsapp/desconectar/',ratelimit(key='ip', method='GET', rate='10/m')       (WhatsAppDesconectarView.as_view()),   name='whatsapp_desconectar'),
    path('whatsapp/teste/',ratelimit(key='ip', method='GET', rate='10/m')             (WhatsAppTesteView.as_view()),         name='whatsapp_teste'),
    path('whatsapp/locacao/<int:pk>/',ratelimit(key='ip', method='GET', rate='10/m')  (WhatsAppEnviarLocacaoView.as_view()), name='whatsapp_locacao'),
]