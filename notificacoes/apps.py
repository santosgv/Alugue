from django.apps import AppConfig


class NotificacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'notificacoes'
    verbose_name       = 'Notificações'

    def ready(self):
        # Importa os signals para registrá-los
        from locacoes.models import Locacao
        from django.db.models.signals import post_save
        from .whatsapp_tasks import enviar_whatsapp_locacao_criada

        def _on_locacao_save(sender, instance, created, **kwargs):
            """Dispara WhatsApp quando locação é criada como ativa/pendente."""
            if created and instance.status in ('ativa', 'pendente'):
                try:
                    enviar_whatsapp_locacao_criada(instance)
                except Exception:
                    pass  # Nunca trava o fluxo principal

        post_save.connect(_on_locacao_save, sender=Locacao, weak=False)