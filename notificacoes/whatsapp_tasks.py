"""
notificacoes/whatsapp_tasks.py
================================
Envios automáticos de WhatsApp disparados por eventos ou agendamento.

Uso via signal (automático ao criar locação):
    Configurado em notificacoes/apps.py → ready()

Uso via comando diário (lembretes e atrasos):
    python manage.py enviar_whatsapp_diario
    Cron: 0 8 * * * cd /app && python manage.py enviar_whatsapp_diario
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_config(empresa):
    """Retorna WhatsAppConfig ativo da empresa ou None."""
    from .whatsapp_models import WhatsAppConfig
    return WhatsAppConfig.objects.filter(empresa=empresa, ativo=True).first()


def _get_empresa(locacao):
    """Resolve a empresa a partir da locação."""
    try:
        return locacao.criado_por.perfil.empresa
    except Exception:
        return None


def _registrar(usuario, titulo, mensagem, locacao=None):
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
            enviada=True,
        )
    except Exception as e:
        logger.warning(f"Não foi possível registrar Notificacao: {e}")


# ─────────────────────────────────────────────────────────────
# SIGNAL — dispara ao criar locação
# ─────────────────────────────────────────────────────────────

def enviar_whatsapp_locacao_criada(locacao):
    """
    Chamado pelo signal em notificacoes/apps.py quando
    uma locação é criada com status ativa ou pendente.
    """
    from .whatsapp_service import notificar_locacao_criada, WhatsAppAPIError, WhatsAppConfigError

    empresa = _get_empresa(locacao)
    if not empresa:
        return

    config = _get_config(empresa)
    if not config or not config.notif_locacao_criada:
        return

    if not config.esta_conectado:
        logger.warning(f"WhatsApp desconectado — locação #{locacao.pk} não notificada.")
        return

    try:
        notificar_locacao_criada(config.instance_name, locacao)
        config.registrar_envio()

        if locacao.criado_por:
            _registrar(
                usuario=locacao.criado_por,
                titulo=f'Confirmação enviada — Locação #{locacao.pk}',
                mensagem=f'WhatsApp enviado para {locacao.cliente.nome}',
                locacao=locacao,
            )
        logger.info(f"WhatsApp confirmação enviado — locação #{locacao.pk}")

    except (WhatsAppConfigError, WhatsAppAPIError) as e:
        logger.error(f"Falha WhatsApp — locação #{locacao.pk}: {e}")


def enviar_whatsapp_locacao_cancelada(locacao):
    """
    Chamado pelo signal em notificacoes/apps.py quando
    uma locação com status Cancelado.
    """
    from .whatsapp_service import notificar_cancelamento, WhatsAppAPIError, WhatsAppConfigError

    empresa = _get_empresa(locacao)
    if not empresa:
        return

    config = _get_config(empresa)
    if not config or not config.notif_cancelamento:
        return

    if not config.esta_conectado:
        logger.warning(f"WhatsApp desconectado — locação #{locacao.pk} não notificada.")
        return

    try:
        notificar_cancelamento(config.instance_name, locacao)
        config.registrar_envio()

        if locacao.criado_por:
            _registrar(
                usuario=locacao.criado_por,
                titulo=f'Cancelamento enviado — Locação #{locacao.pk}',
                mensagem=f'WhatsApp enviado para {locacao.cliente.nome}',
                locacao=locacao,
            )
        logger.info(f"WhatsApp Cancelamento enviado — locação #{locacao.pk}")

    except (WhatsAppConfigError, WhatsAppAPIError) as e:
        logger.error(f"Falha WhatsApp — locação #{locacao.pk}: {e}")

# ─────────────────────────────────────────────────────────────
# LEMBRETES DE DEVOLUÇÃO — rode diariamente
# ─────────────────────────────────────────────────────────────

def enviar_lembretes_devolucao():
    """
    Envia lembretes para locações com devolução prevista para amanhã.
    Retorna (enviados, erros).
    """
    from locacoes.models import Locacao
    from .whatsapp_service import notificar_devolucao_amanha, WhatsAppAPIError, WhatsAppConfigError

    amanha   = timezone.localdate() + timezone.timedelta(days=1)
    locacoes = (
        Locacao.objects
        .filter(status='ativa', data_fim_prevista=amanha)
        .select_related('cliente', 'criado_por__perfil__empresa')
    )

    enviados = erros = 0

    for locacao in locacoes:
        empresa = _get_empresa(locacao)
        if not empresa:
            continue

        config = _get_config(empresa)
        if not config or not config.notif_devolucao_amanha or not config.esta_conectado:
            continue

        try:
            notificar_devolucao_amanha(config.instance_name, locacao)
            config.registrar_envio()
            enviados += 1

            if locacao.criado_por:
                _registrar(
                    usuario=locacao.criado_por,
                    titulo=f'Lembrete enviado — Locação #{locacao.pk}',
                    mensagem=f'Devolução amanhã — {locacao.cliente.nome}',
                    locacao=locacao,
                )
        except (WhatsAppConfigError, WhatsAppAPIError) as e:
            erros += 1
            logger.error(f"Erro lembrete — locação #{locacao.pk}: {e}")

    logger.info(f"Lembretes devolução: {enviados} enviados, {erros} erros.")
    return enviados, erros


# ─────────────────────────────────────────────────────────────
# AVISOS DE ATRASO — rode diariamente
# ─────────────────────────────────────────────────────────────

def enviar_avisos_atraso():
    """
    Envia avisos para locações atrasadas.
    Retorna (enviados, erros).
    """
    from locacoes.models import Locacao
    from .whatsapp_service import notificar_atraso, WhatsAppAPIError, WhatsAppConfigError

    hoje     = timezone.localdate()
    locacoes = (
        Locacao.objects
        .filter(status__in=['ativa', 'atrasada'], data_fim_prevista__lt=hoje)
        .select_related('cliente', 'criado_por__perfil__empresa')
    )

    enviados = erros = 0

    for locacao in locacoes:
        empresa = _get_empresa(locacao)
        if not empresa:
            continue

        config = _get_config(empresa)
        if not config or not config.notif_atraso or not config.esta_conectado:
            continue

        dias = (hoje - locacao.data_fim_prevista).days

        try:
            notificar_atraso(config.instance_name, locacao, dias)
            config.registrar_envio()
            enviados += 1

            if locacao.criado_por:
                _registrar(
                    usuario=locacao.criado_por,
                    titulo=f'Atraso {dias}d — Locação #{locacao.pk}',
                    mensagem=f'{locacao.cliente.nome} com {dias} dia(s) de atraso.',
                    locacao=locacao,
                )
        except (WhatsAppConfigError, WhatsAppAPIError) as e:
            erros += 1
            logger.error(f"Erro atraso — locação #{locacao.pk}: {e}")

    logger.info(f"Avisos atraso: {enviados} enviados, {erros} erros.")
    return enviados, erros