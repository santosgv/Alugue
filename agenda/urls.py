from django.urls import path
from . import views

app_name = 'agenda'

urlpatterns = [
    path('', views.AgendaView.as_view(), name='agenda'),
    path('eventos/', views.eventos_json, name='eventos_json'),
]