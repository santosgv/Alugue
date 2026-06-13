from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from locacoes.models import Locacao


class AgendaView(LoginRequiredMixin, TemplateView):
    template_name = 'agenda/agenda.html'


def eventos_json(request):
    """Retorna eventos para o FullCalendar."""
    STATUS_CORES = {
        'ativa': '#198754',
        'pendente': '#ffc107',
        'atrasada': '#dc3545',
        'finalizada': '#6c757d',
        'cancelada': '#adb5bd',
    }
    locacoes = Locacao.objects.exclude(
        status__in=['cancelada', 'finalizada']
    ).select_related('cliente').prefetch_related('itens__produto')

    eventos = []
    for loc in locacoes:
        produtos = ', '.join(f"{i.quantidade}x {i.produto.nome}" for i in loc.itens.all())
        eventos.append({
            'id': loc.pk,
            'title': f"{loc.cliente.nome}",
            'start': loc.data_inicio.isoformat(),
            'end': loc.data_fim_prevista.isoformat(),
            'backgroundColor': STATUS_CORES.get(loc.status, '#0d6efd'),
            'borderColor': STATUS_CORES.get(loc.status, '#0d6efd'),
            'extendedProps': {
                'cliente': loc.cliente.nome,
                'produtos': produtos,
                'status': loc.get_status_display(),
                'valor': str(loc.valor_total),
                'url': f'/locacoes/{loc.pk}/',
            }
        })
    return JsonResponse(eventos, safe=False)