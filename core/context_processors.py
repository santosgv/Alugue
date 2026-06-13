"""
Injeta dados de plano/assinatura em todos os templates.
"""
from .models import SubscriptionPlan
from accounts.models import PerfilUsuario

def plano_context(request):
    ctx = {
        'plano_ativo':  getattr(request, 'plano_ativo',  None),
        'assinatura':   getattr(request, 'assinatura',   None),
        'empresa':      getattr(request, 'empresa',      None),
    }

    # Alertas de assinatura
    assinatura = ctx['assinatura']
    ctx['assinatura_alerta'] = None

    if assinatura:
        # Na página de planos o bloqueio já é mostrado inline — não duplica o banner
        from django.urls import resolve, Resolver404
        try:
            url_name = resolve(request.path).url_name
            if url_name == 'planos':
                return ctx
        except Exception:
            pass

        dias = assinatura.dias_restantes
        if assinatura.status == 'trial' and dias is not None and dias <= 5:
            ctx['assinatura_alerta'] = {
                'tipo': 'warning',
                'mensagem': (
                    f"Seu trial expira em {dias} dia(s). "
                    f"Escolha um plano para continuar."
                ),
                'link': '/planos/',
                'link_texto': 'Ver planos',
            }
        elif assinatura.status == 'trial' and dias is not None:
            ctx['assinatura_alerta'] = {
                'tipo': 'info',
                'mensagem': f"Trial ativo — {dias} dia(s) restante(s).",
                'link': '/planos/',
                'link_texto': 'Ver planos',
            }
        elif assinatura.vencida or assinatura.status == 'expirada':
            ctx['assinatura_alerta'] = {
                'tipo': 'danger',
                'mensagem': 'Sua assinatura expirou. Renove para continuar usando o sistema.',
                'link': '/planos/',
                'link_texto': 'Renovar agora',
            }
        elif dias is not None and dias <= 7:
            ctx['assinatura_alerta'] = {
                'tipo': 'warning',
                'mensagem': f"Sua assinatura vence em {dias} dia(s).",
                'link': '/assinatura/',
                'link_texto': 'Renovar',
            }

    return ctx


def user_perfil_context(request):
    """
    Disponibiliza o perfil do usuário e suas permissões em todos os templates
    """
    context = {
        'user_perfil': None,
        'user_role': None,
        'user_is_admin': False,
        'user_is_operador': False,
        'user_is_readonly': False,
    }
    
    if request.user.is_authenticated:
        try:
            perfil = request.user.perfil
            context.update({
                'user_perfil': perfil,
                'user_role': perfil.role,
                'user_is_admin': perfil.role == PerfilUsuario.ROLE_ADMIN,
                'user_is_operador': perfil.role == PerfilUsuario.ROLE_OPERADOR,
                'user_is_readonly': perfil.role == PerfilUsuario.ROLE_READONLY,
            })
        except PerfilUsuario.DoesNotExist:
            pass
    
    return context
