from .models import Notificacao

def notificacoes_nao_lidas(request):
    if request.user.is_authenticated:
        return {
            'notificacoes_nao_lidas': Notificacao.objects.filter(
                usuario=request.user, lida=False
            ).count()
        }
    return {'notificacoes_nao_lidas': 0}
