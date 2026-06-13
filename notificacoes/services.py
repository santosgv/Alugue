"""
Serviço de notificações com arquitetura preparada para múltiplos canais.
"""
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Notificacao


class NotificacaoService:
    """
    Serviço central de notificações.
    Suporta canal interno. Arquitetura preparada para email e WhatsApp.
    """

    @staticmethod
    def criar(usuario: User, titulo: str, mensagem: str,
              tipo: str = Notificacao.TIPO_INFO,
              canal: str = Notificacao.CANAL_INTERNO,
              locacao=None) -> Notificacao:
        return Notificacao.objects.create(
            usuario=usuario,
            titulo=titulo,
            mensagem=mensagem,
            tipo=tipo,
            canal=canal,
            locacao_ref=locacao,
        )

    @staticmethod
    def notificar_todos_staff(titulo: str, mensagem: str,
                               tipo: str = Notificacao.TIPO_INFO, locacao=None):
        """Envia notificação para todos os usuários staff."""
        usuarios = User.objects.filter(is_active=True, is_staff=True)
        notificacoes = [
            Notificacao(
                usuario=u,
                titulo=titulo,
                mensagem=mensagem,
                tipo=tipo,
                locacao_ref=locacao,
            )
            for u in usuarios
        ]
        Notificacao.objects.bulk_create(notificacoes)

    @staticmethod
    def notificar_locacao_vencendo(locacao):
        """Alerta para locação que vence amanhã."""
        titulo = f"⚠️ Locação vence amanhã — {locacao.cliente.nome}"
        mensagem = (
            f"A locação #{locacao.pk} do cliente {locacao.cliente.nome} "
            f"vence amanhã ({locacao.data_fim_prevista.strftime('%d/%m/%Y')}). "
            f"Valor: R$ {locacao.valor_total}."
        )
        NotificacaoService.notificar_todos_staff(
            titulo, mensagem, tipo=Notificacao.TIPO_ALERTA, locacao=locacao
        )

    @staticmethod
    def notificar_locacao_vencida(locacao):
        """Alerta para locação em atraso."""
        titulo = f"🚨 Locação em atraso — {locacao.cliente.nome}"
        mensagem = (
            f"A locação #{locacao.pk} do cliente {locacao.cliente.nome} "
            f"estava prevista para {locacao.data_fim_prevista.strftime('%d/%m/%Y')} "
            f"e ainda não foi devolvida. Valor: R$ {locacao.valor_total}."
        )
        NotificacaoService.notificar_todos_staff(
            titulo, mensagem, tipo=Notificacao.TIPO_URGENTE, locacao=locacao
        )

    @staticmethod
    def notificar_produto_devolvido(locacao):
        """Confirmação de devolução."""
        titulo = f"✅ Produto devolvido — {locacao.cliente.nome}"
        itens = ', '.join(f"{i.quantidade}x {i.produto.nome}" for i in locacao.itens.all())
        mensagem = f"Locação #{locacao.pk} finalizada. Itens devolvidos: {itens}."
        NotificacaoService.notificar_todos_staff(
            titulo, mensagem, tipo=Notificacao.TIPO_SUCESSO, locacao=locacao
        )

    # Ponto de extensão para WhatsApp (futuro)
    @staticmethod
    def enviar_whatsapp(telefone: str, mensagem: str):
        """
        Integração futura com WhatsApp Business API.
        Implementar aqui quando disponível no plano Pro/Premium.
        """
        raise NotImplementedError("Integração WhatsApp disponível no plano Pro.")

    # Ponto de extensão para Email (futuro)
    @staticmethod
    def enviar_email(destinatario: str, assunto: str, mensagem: str):
        """
        Envio de email via Django email backend.
        """
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject=assunto,
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            fail_silently=True,
        )