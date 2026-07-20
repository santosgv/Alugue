from django.urls import path
from . import views
from django_ratelimit.decorators import ratelimit

app_name = 'agenda'

urlpatterns = [
    path('', ratelimit(key='ip', method='GET', rate='10/m')(views.AgendaView.as_view()), name='agenda'),
    path('eventos/', ratelimit(key='ip', method='GET', rate='100/m')(views.eventos_json), name='eventos_json'),
]