"""
core/signals.py
================
Provisiona empresa + assinatura free automaticamente quando
um novo usuário é criado — seja via cadastro normal ou Google Login.

Fluxo corrigido para django-tenants + Google OAuth:
  1. Usuário criado (post_save, created=True)
  2. Cria TenantCompany com schema isolado
  3. Cria Domain apontando para o DOMÍNIO PÚBLICO com path prefix
     (não subdomínio — evita conflito com Google OAuth callback)
  4. Vincula User → TenantCompany via PerfilUsuario (role=admin)
  5. Cria Assinatura free

Por que não usar subdomínio no Domain:
  O Google OAuth só aceita redirect_uri cadastradas explicitamente.
  Se o django-tenants resolver o callback num subdomínio dinâmico
  (ex: usuario.localhost:8000) o Google rejeita com erro 400.
  A solução é manter login/OAuth sempre no domínio público e
  resolver o tenant pelo usuário logado (via PerfilUsuario),
  não pelo subdomínio — que é o que o PlanoMiddleware já faz.
"""

import re
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

from .models import TenantCompany, Domain, Assinatura, SubscriptionPlan

logger = logging.getLogger(__name__)
User   = get_user_model()


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _gerar_schema_name(email: str) -> str:
    """
    Converte email em schema_name válido para PostgreSQL.
    Apenas letras minúsculas, números e underscore. Máximo 50 chars.

    'joao.silva@gmail.com'       -> 'joao_silva'
    'maria+teste@empresa.com.br' -> 'maria_teste'
    """
    nome = email.split("@")[0].lower()
    nome = re.sub(r"[^\w]", "_", nome)
    nome = re.sub(r"_+", "_", nome).strip("_")
    return nome[:50]


def _schema_name_unico(base: str) -> str:
    """
    Garante unicidade adicionando sufixo numérico se necessário.
    'joao_gmail_com' → 'joao_gmail_com_2' se o primeiro já existe.
    """
    nome = base
    contador = 2
    while TenantCompany.objects.filter(schema_name=nome).exists():
        sufixo = f'_{contador}'
        nome   = base[:50 - len(sufixo)] + sufixo
        contador += 1
    return nome


# ─────────────────────────────────────────────────────────────
# SIGNAL PRINCIPAL
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=User)
def provisionar_tenant_free(sender, instance, created, **kwargs):
    """
    Cria empresa e assinatura free para todo novo usuário.
    Ignora superusers e staff.
    """
    if not created:
        return

    if instance.is_superuser or instance.is_staff:
        logger.info(f"Staff/superuser criado ({instance.email}) — provisionamento ignorado.")
        return

    logger.info(f"Novo usuário: {instance.email} — provisionando tenant free...")

    try:
        from accounts.models import PerfilUsuario

        # Evita duplicar se por algum motivo o signal disparar duas vezes
        if PerfilUsuario.objects.filter(user=instance, empresa__isnull=False).exists():
            logger.info(f"{instance.email} já tem empresa — ignorando.")
            return

        # ── Plano free ──────────────────────────────────────────
        plano_free = SubscriptionPlan.objects.filter(slug='free', ativo=True).first()
        if not plano_free:
            logger.error(
                f"Plano 'free' não encontrado para {instance.email}. "
                f"Execute: python manage.py setup_planos"
            )
            return

        # ── Schema name único ───────────────────────────────────
        schema_name = _schema_name_unico(_gerar_schema_name(instance.email))

        nome_display = (
            instance.get_full_name().strip()
            or instance.email.split('@')[0]
        )

        # ── Empresa (TenantCompany) ─────────────────────────────
        # IMPORTANTE: NÃO passe plano_atual — é @property sem setter.
        # Use o FK `plano` diretamente.
        empresa = TenantCompany.objects.create(
            schema_name=schema_name,
            nome=f"Empresa de {nome_display}",
            email=instance.email,
            plano=plano_free,       # FK direto — não plano_atual
            ativo=True,
        )
        logger.info(f"Empresa criada: pk={empresa.pk} schema={schema_name}")

        # ── Domain ─────────────────────────────────────────────
        # Usamos o DOMÍNIO PÚBLICO (não subdomínio dinâmico).
        #
        # Por quê?
        # ─ Google OAuth redireciona para o domínio cadastrado no Console.
        # ─ Se criássemos 'usuario.locagest.com.br', o Google rejeitaria
        #   com erro 400 porque esse subdomínio não está cadastrado.
        # ─ O tenant é resolvido pelo PlanoMiddleware via PerfilUsuario,
        #   não pelo subdomínio — então isso funciona perfeitamente.
        #
        # Em produção real com subdomínios: adicione o subdomínio DEPOIS
        # do cadastro, como um segundo domain (is_primary=False), e use
        # wildcard *.locagest.com.br no Google Console.
        dominio_publico = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')

        Domain.objects.create(
            domain=f"{schema_name}.{dominio_publico}",
            tenant=empresa,
            is_primary=False,
        )

        # ── Perfil do usuário ───────────────────────────────────
        perfil, _ = PerfilUsuario.objects.get_or_create(user=instance)
        perfil.empresa = empresa
        perfil.role    = PerfilUsuario.ROLE_ADMIN  # primeiro usuário = admin
        perfil.ativo   = True
        perfil.save(update_fields=['empresa', 'role', 'ativo'])

        # ── Assinatura free ─────────────────────────────────────
        # data_fim=None: plano free não tem vencimento automático.
        # Para desativar um free, mude o status via admin.
        assinatura = Assinatura.objects.create(
            empresa=empresa,
            plano=plano_free,
            ciclo=Assinatura.CICLO_MENSAL,
            status=Assinatura.STATUS_ATIVA,
            data_inicio=timezone.localdate(),
            data_fim=None,
            valor_cobrado=0,
            criado_por=instance,
        )

        logger.info(
            f"✅ Provisionamento concluído: {instance.email} | "
            f"empresa={empresa.pk} | schema={schema_name} | "
            f"assinatura={assinatura.pk} | plano=free"
        )

    except Exception as exc:
        # Não relança — erro aqui não deve impedir o usuário de ser criado.
        # Admin pode provisionar manualmente se necessário.
        logger.error(
            f"❌ Erro ao provisionar {instance.email}: {exc}",
            exc_info=True,
        )