"""
notificacoes/whatsapp_tasks.py
================================
Envios automáticos de WhatsApp disparados por eventos do sistema.

Duas formas de usar:

1. SIGNALS (imediato) — dispara junto com o evento:
   Conecte os signals em notificacoes/apps.py → ready()

2. COMANDO DIÁRIO (agendado) — rode via cron ou Celery:
   python manage.py enviar_whatsapp_diario
   Cron exemplo (todo dia às 8h):
     0 8 * * * cd /app && python manage.py enviar_whatsapp_diario

Sem Celery é necessário o comando diário para lembretes e atrasos.
Com Celery, chame as funções abaixo como tasks.
"""

import logging
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _get_service(empresa):
    """
    Retorna WhatsAppService para a empresa ou None se não configurado.
    Silencia erros de configuração — não deve travar o fluxo principal.
    """
    from .whatsapp_service import WhatsAppService, WhatsAppConfigError
    try:
        return WhatsAppService(empresa)
    except WhatsAppConfigError:
        return None


def _registrar_notificacao(usuario, titulo, mensagem, locacao=None, enviada=True):
    """Cria registro de Notificacao no banco."""
    from .models import Notificacao
    try:
        Notificacao.objects.create(
            usuario=usuario,
            titulo=titulo,
            mensagem=mensagem,
            tipo=Notificacao.TIPO_INFO,
            canal=Notificacao.CANAL_WHATSAPP,
            locacao_ref=locacao,
            enviada=enviada,
        )
    except Exception as e:
        logger.warning(f"Não foi possível registrar Notificacao: {e}")


# ─────────────────────────────────────────────────────────────
# SIGNAL — locação criada/confirmada
# ─────────────────────────────────────────────────────────────

def enviar_whatsapp_locacao_criada(locacao):
    """
    Chamado quando uma locação é criada com status 'ativa' ou 'pendente'.
    Conecte este signal em notificacoes/apps.py.
    """
    from .whatsapp_models import WhatsAppConfig
    from .whatsapp_service import WhatsAppAPIError

    empresa = getattr(locacao, 'empresa', None)
    if not empresa:
        # Tenta resolver pelo usuário criador
        if locacao.criado_por:
            try:
                empresa = locacao.criado_por.perfil.empresa
            except Exception:
                return

    if not empresa:
        return

    config = WhatsAppConfig.objects.filter(empresa=empresa, ativo=True).first()
    if not config or not config.notif_locacao_criada:
        return

    svc = _get_service(empresa)
    if not svc:
        return

    try:
        svc.notificar_locacao_criada(locacao)
        config.registrar_envio()

        usuario = locacao.criado_por
        if usuario:
            _registrar_notificacao(
                usuario=usuario,
                titulo=f'Confirmação enviada — Locação #{locacao.pk}',
                mensagem=f'WhatsApp enviado para {locacao.cliente.nome}',
                locacao=locacao,
            )
        logger.info(f"WhatsApp de confirmação enviado — locação #{locacao.pk}")

    except WhatsAppAPIError as e:
        logger.error(f"Falha ao enviar WhatsApp de confirmação — locação #{locacao.pk}: {e}")


# ─────────────────────────────────────────────────────────────
# ENVIOS DIÁRIOS (rode via manage.py enviar_whatsapp_diario)
# ─────────────────────────────────────────────────────────────

def enviar_lembretes_devolucao():
    """
    Envia lembretes para locações com devolução prevista para amanhã.
    Execute diariamente (ex: cron às 8h).
    """
    from locacoes.models import Locacao
    from .whatsapp_models import WhatsAppConfig
    from .whatsapp_service import WhatsAppAPIError

    amanha = timezone.localdate() + timezone.timedelta(days=1)

    locacoes = Locacao.objects.filter(
        status__in=['ativa'],
        data_fim_prevista=amanha,
    ).select_related('cliente', 'criado_por__perfil__empresa')

    enviados = 0
    erros    = 0

    for locacao in locacoes:
        try:
            empresa = locacao.criado_por.perfil.empresa
        except Exception:
            continue

        config = WhatsAppConfig.objects.filter(empresa=empresa, ativo=True).first()
        if not config or not config.notif_devolucao_amanha:
            continue

        svc = _get_service(empresa)
        if not svc:
            continue

        try:
            svc.notificar_devolucao_amanha(locacao)
            config.registrar_envio()
            enviados += 1

            if locacao.criado_por:
                _registrar_notificacao(
                    usuario=locacao.criado_por,
                    titulo=f'Lembrete de devolução — Locação #{locacao.pk}',
                    mensagem=f'Devolução amanhã ({amanha.strftime("%d/%m/%Y")}) — '
                             f'{locacao.cliente.nome}',
                    locacao=locacao,
                )
        except WhatsAppAPIError as e:
            erros += 1
            logger.error(f"Erro no lembrete — locação #{locacao.pk}: {e}")

    logger.info(f"Lembretes de devolução: {enviados} enviados, {erros} erros.")
    return enviados, erros


def enviar_avisos_atraso():
    """
    Envia avisos para locações atrasadas (passou da data de devolução).
    Execute diariamente (ex: cron às 8h).
    """
    from locacoes.models import Locacao
    from .whatsapp_models import WhatsAppConfig
    from .whatsapp_service import WhatsAppAPIError

    hoje = timezone.localdate()

    locacoes = Locacao.objects.filter(
        status__in=['ativa', 'atrasada'],
        data_fim_prevista__lt=hoje,
    ).select_related('cliente', 'criado_por__perfil__empresa')

    enviados = 0
    erros    = 0

    for locacao in locacoes:
        try:
            empresa = locacao.criado_por.perfil.empresa
        except Exception:
            continue

        config = WhatsAppConfig.objects.filter(empresa=empresa, ativo=True).first()
        if not config or not config.notif_atraso:
            continue

        svc = _get_service(empresa)
        if not svc:
            continue

        dias_atraso = (hoje - locacao.data_fim_prevista).days

        try:
            svc.notificar_atraso(locacao, dias_atraso)
            config.registrar_envio()
            enviados += 1

            if locacao.criado_por:
                _registrar_notificacao(
                    usuario=locacao.criado_por,
                    titulo=f'Atraso {dias_atraso}d — Locação #{locacao.pk}',
                    mensagem=f'{locacao.cliente.nome} está com {dias_atraso} dia(s) de atraso.',
                    locacao=locacao,
                )
        except WhatsAppAPIError as e:
            erros += 1
            logger.error(f"Erro no aviso de atraso — locação #{locacao.pk}: {e}")

    logger.info(f"Avisos de atraso: {enviados} enviados, {erros} erros.")
    return enviados, erros