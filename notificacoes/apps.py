from django.apps import AppConfig


class NotificacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'notificacoes'
    verbose_name       = 'Notificações'

    def ready(self):
        from locacoes.models import Locacao
        from django.db.models.signals import post_save,pre_save
        from django.dispatch import receiver
        from django.db import transaction
        from .whatsapp_tasks import (enviar_whatsapp_locacao_criada,
                                     enviar_whatsapp_locacao_cancelada)
        
        # 🔥 IMPORTANTE: Usamos pre_save para capturar o estado anterior
        @receiver(pre_save, sender=Locacao)
        def capturar_status_anterior(sender, instance, **kwargs):
            """
            Captura o status anterior da locação ANTES de ser salvo.
            Isso permite detectar mudanças de status.
            """
            if instance.pk:
                try:
                    # Busca o estado atual no banco
                    anterior = sender.objects.get(pk=instance.pk)
                    # Armazena o status anterior na instância para uso posterior
                    instance._status_anterior = anterior.status
                except sender.DoesNotExist:
                    instance._status_anterior = None
            else:
                instance._status_anterior = None

        @receiver(post_save, sender=Locacao)
        def on_locacao_save(sender, instance, created, **kwargs):
            """
            Dispara notificações quando uma locação é criada ou atualizada.
            Detecta mudanças de status para enviar notificações apropriadas.
            """
            try:
                # 🔥 OBTÉM O STATUS ANTERIOR (capturado no pre_save)
                status_anterior = getattr(instance, '_status_anterior', None)
                status_atual = instance.status
                
                # 📝 LOCAÇÃO CRIADA (nova locação)
                if created:
                    if status_atual in ('ativa', 'pendente', 'confirmada'):
                        transaction.on_commit(lambda: enviar_whatsapp_locacao_criada(instance))
                    return
                
                # 🔄 LOCAÇÃO ATUALIZADA (mudança de status)
                if status_anterior is not None and status_anterior != status_atual:
                    
                    # ❌ LOCAÇÃO CANCELADA
                    if status_atual == 'cancelada':
                        transaction.on_commit(lambda: enviar_whatsapp_locacao_cancelada(instance))
                    
                    # ✅ LOCAÇÃO CONFIRMADA (de pendente para ativa)
                    elif status_atual == 'ativa' and status_anterior == 'pendente':
                        transaction.on_commit(lambda: enviar_whatsapp_locacao_criada(instance))
                    
                    
                    # ⏰ LOCAÇÃO PARA DEVOLUÇÃO AMANHÃ
                    # (pode ser verificado em uma task separada ou aqui)
                    # Se o status mudou para algo que indica devolução próxima
                    
            except Exception as e:
                # Nunca trava o fluxo principal
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ Erro no signal de notificação: {str(e)}")



        