"""
core/signals.py
================
Cria empresa + trial de 14 dias automaticamente quando
um novo usuário é registrado (cadastro manual ou Google Login).
"""
import logging
from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import TenantCompany, Assinatura, SubscriptionPlan

logger = logging.getLogger(__name__)
User   = get_user_model()


@receiver(post_save, sender=User)
def criar_empresa_e_trial(sender, instance, created, **kwargs):
    """
    Disparado quando um novo User é salvo.
    Cria TenantCompany + Assinatura trial (14 dias) automaticamente.
    """
    if not created:
        return

    if instance.is_superuser or instance.is_staff:
        logger.info(f"Staff/superuser criado ({instance.email}) — trial não aplicável.")
        return

    logger.info(f"Novo usuário: {instance.email} — provisionando trial...")

    try:
        from accounts.models import PerfilUsuario

        # Evita duplicar se o signal disparar mais de uma vez
        if PerfilUsuario.objects.filter(user=instance, empresa__isnull=False).exists():
            logger.info(f"{instance.email} já tem empresa — ignorando.")
            return

        # ── Busca o plano básico/pro para o trial ──────────────
        # O trial usa o plano mais completo disponível para o usuário
        # experimentar todas as funcionalidades.
        # Ajuste o slug conforme seu setup_planos.
        plano_trial = (
            SubscriptionPlan.objects.filter(slug='trial',    ativo=True).first()
           # or SubscriptionPlan.objects.filter(slug='pro', ativo=True).first()
           # or SubscriptionPlan.objects.filter(ativo=True).order_by('-preco_mensal').first()
        )

        if not plano_trial:
            logger.error(f"Nenhum plano ativo encontrado para {instance.email}.")
            return

        # ── Empresa ────────────────────────────────────────────
        # IMPORTANTE: não use plano_atual= (é @property sem setter)
        # nem usuario= (campo não existe no TenantCompany).
        # Use apenas campos reais do model.
        nome_display = (
            instance.get_full_name().strip()
            or instance.email.split('@')[0]
        )

        empresa = TenantCompany.objects.create(
            nome=f"Empresa de {nome_display}",
            email=instance.email,
            plano=plano_trial,       # FK direto — não plano_atual
            ativo=True,
        )
        logger.info(f"Empresa criada: pk={empresa.pk} nome={empresa.nome}")

        # ── Perfil: vincula User → Empresa ─────────────────────
        perfil, _ = PerfilUsuario.objects.get_or_create(user=instance)
        perfil.empresa = empresa
        perfil.role    = PerfilUsuario.ROLE_ADMIN
        perfil.ativo   = True
        perfil.save(update_fields=['empresa', 'role', 'ativo'])

        # ── Trial de 14 dias ───────────────────────────────────
        hoje    = timezone.localdate()
        data_fim = hoje + timedelta(days=14)

        assinatura = Assinatura.objects.create(
            empresa=empresa,
            plano=plano_trial,
            ciclo=Assinatura.CICLO_MENSAL,
            status=Assinatura.STATUS_TRIAL,
            data_inicio=hoje,
            data_fim=data_fim,
            valor_cobrado=0,
            criado_por=instance,
        )

        logger.info(
            f"✅ Trial criado para {instance.email}: "
            f"empresa={empresa.pk} | plano={plano_trial.slug} | "
            f"vence={data_fim} | assinatura={assinatura.pk}"
        )

    except Exception as exc:
        # Não relança — erro aqui não deve impedir o usuário de ser salvo
        logger.error(
            f"❌ Erro ao provisionar trial para {instance.email}: {exc}",
            exc_info=True,
        )