# core/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging

from .models import TenantCompany, Assinatura, SubscriptionPlan

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=User)
def criar_empresa_e_assinatura_free(sender, instance, created, **kwargs):
    """
    Quando um novo usuário é criado (inclusive via Google Login),
    cria automaticamente uma empresa e assinatura free.
    """
    if not created:
        return
    
    logger.info(f"Novo usuário criado: {instance.email} - Criando empresa e assinatura free...")
    
    try:
        # Verificar se o usuário já tem empresa
        if hasattr(instance, 'empresa') and instance.empresa:
            logger.info(f"Usuário {instance.email} já possui empresa, ignorando.")
            return
        
        # Buscar o plano free
        plano_free = SubscriptionPlan.objects.filter(
            slug='free', 
            ativo=True
        ).first()
        
        if not plano_free:
            logger.error("Plano Free não encontrado! Verifique se o plano 'free' existe.")
            return
        
        # Criar a empresa
        empresa = TenantCompany.objects.create(
            nome=f"Empresa de {instance.get_full_name() or instance.email}",
            email=instance.email,
            usuario=instance,
            plano_atual=plano_free,
            stripe_customer_id=None,  # Free não tem stripe
            ativo=True,
        )
        
        # Criar assinatura free
        assinatura = Assinatura.objects.create(
            empresa=empresa,
            plano=plano_free,
            ciclo='mensal',
            status=Assinatura.STATUS_ATIVA,
            data_inicio=timezone.localdate(),
            data_fim=timezone.localdate() + timedelta(days=365 * 100),  # Free "eterno"
            valor_cobrado=0,
        )
        
        logger.info(
            f"✅ Empresa e assinatura free criadas para {instance.email}: "
            f"Empresa ID: {empresa.pk}, Assinatura ID: {assinatura.pk}"
        )
        
    except Exception as e:
        logger.error(f"Erro ao criar empresa/assinatura para {instance.email}: {str(e)}", exc_info=True)


@receiver(post_save, sender=TenantCompany)
def atualizar_usuario_empresa(sender, instance, created, **kwargs):
    """
    Quando uma empresa é criada, atualiza o usuário com a referência à empresa.
    """
    if created and instance.usuario:
        # Garantir que o usuário tem a referência para a empresa
        if not hasattr(instance.usuario, 'empresa') or not instance.usuario.empresa:
            instance.usuario.empresa = instance
            instance.usuario.save(update_fields=['empresa'])
            logger.info(f"Usuário {instance.usuario.email} vinculado à empresa {instance.pk}")