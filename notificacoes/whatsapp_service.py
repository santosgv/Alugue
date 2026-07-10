import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppConfigError(Exception):
    pass


class WhatsAppAPIError(Exception):
    pass


def _base_url() -> str:
    return getattr(settings, 'EVOLUTION_API_URL', 'http://localhost:8080').rstrip('/')


def _api_key() -> str:
    """Obtém a API Key da Evolution API."""
    api_key = getattr(settings, 'EVOLUTION_API_KEY', '')
    if not api_key:
        raise WhatsAppConfigError(
            "EVOLUTION_API_KEY não configurada no settings.py ou .env"
        )

    return api_key


def _headers() -> dict:
    return {
        'apikey':       _api_key(),
        'Content-Type': 'application/json',
    }


def _req(method: str, path: str, json=None, timeout=10) -> dict:
    """Requisição à Evolution API com tratamento de erro unificado."""
    url = f'{_base_url()}{path}'
    try:
        r = getattr(requests, method)(url, headers=_headers(), json=json, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise WhatsAppAPIError(
            "Evolution API indisponível. "
            "Verifique se o Docker está rodando: docker compose up -d"
        )
    except requests.exceptions.Timeout:
        raise WhatsAppAPIError("Timeout ao conectar com a Evolution API.")

    try:
        data = r.json()
    except Exception:
        data = {'detail': r.text}

    if not r.ok:
        detalhe = data.get('message') or data.get('detail') or str(data)
        raise WhatsAppAPIError(f"Evolution API [{r.status_code}]: {detalhe}")

    return data


# ── Gerenciamento de instância ────────────────────────────────

def criar_instancia(instance_name: str) -> dict:
    """Cria instância na Evolution API. Cada empresa tem a sua."""
    return _req('post', '/instance/create', json={
        'instanceName': instance_name,
        'qrcode':       True,
        'integration':  'WHATSAPP-BAILEYS',
    })


def status_instancia(instance_name: str) -> dict:
    """
    Retorna estado da instância.
    state: 'open' = conectado | 'close' = desconectado | 'connecting' = aguardando QR
    """
    try:
        return _req('get', f'/instance/connectionState/{instance_name}')
    except WhatsAppAPIError:
        return {'instance': {'state': 'close'}}


def gerar_qr(instance_name: str) -> dict:
    """Gera/renova QR code. Retorna dict com 'base64' e 'code'."""
    return _req('get', f'/instance/connect/{instance_name}')


def desconectar_instancia(instance_name: str) -> dict:
    """Desconecta o número mas mantém a instância."""
    return _req('delete', f'/instance/logout/{instance_name}')


def deletar_instancia(instance_name: str) -> dict:
    """Remove completamente a instância."""
    return _req('delete', f'/instance/delete/{instance_name}')


def listar_instancias() -> list:
    try:
        data = _req('get', '/instance/fetchInstances')
        return data if isinstance(data, list) else []
    except WhatsAppAPIError:
        return []


def instancia_existe(instance_name: str) -> bool:
    nomes = [
        i.get('instance', {}).get('instanceName', '')
        for i in listar_instancias()
    ]
    return instance_name in nomes


def obter_ou_criar_instancia(instance_name: str) -> dict:
    """Garante que a instância existe, criando se necessário."""
    if not instancia_existe(instance_name):
        logger.info(f"Criando instância Evolution API: {instance_name}")
        criar_instancia(instance_name)
    return status_instancia(instance_name)


# ── Envio de mensagens ────────────────────────────────────────

def _formatar_telefone(telefone: str) -> str:
    """'(11) 99999-8888' → '5511999998888'"""
    numeros = ''.join(filter(str.isdigit, telefone))
    if not numeros.startswith('55'):
        numeros = f'55{numeros}'
    return numeros


def enviar_texto(instance_name: str, telefone: str, mensagem: str,delay: int = 1000, presence: str = "composing") -> dict:
    """Envia mensagem de texto. Suporta *negrito* e _itálico_ do WhatsApp."""
    numero = _formatar_telefone(telefone)
    payload = {
        "number": numero,
        "textMessage": {
            "text": mensagem
        },
        "options": {
            "delay": delay,
            "presence": presence,
            "linkPreview": True
        }
    }
    logger.info(f"📨 Enviando mensagem para {numero} via {instance_name}")
    logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        data = _req('post', f'/message/sendText/{instance_name}', json=payload)
        logger.info(f"✅ Mensagem enviada com sucesso para {numero}")
        return data
    except WhatsAppAPIError as e:
        logger.error(f"❌ Erro ao enviar mensagem: {str(e)}")
        raise


# ── Mensagens do domínio ──────────────────────────────────────

def _telefone(locacao) -> str:
    tel = getattr(locacao.cliente, 'telefone', '') or ''
    if not tel:
        raise WhatsAppConfigError(
            f"Cliente '{locacao.cliente.nome}' não tem telefone cadastrado."
        )
    return tel


def notificar_locacao_criada(instance_name: str, locacao) -> dict:
    valor_formatado = f"R$ {locacao.valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    itens_lista = []
    for item in locacao.itens.all():
        item_valor_unitario = f"{item.valor_unitario:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        item_valor_total = f"{item.valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        itens_lista.append(f"• {item.produto.nome} ({item.quantidade}x) - {item_valor_unitario} cada, total: {item_valor_total}")
    
    itens_texto = "\n".join(itens_lista) if itens_lista else "   • Nenhum item listado"

    msg = (
        f"✅ *Locação Confirmada!*\n\n"
        f"Olá, {locacao.cliente.nome}!\n"
        f"Sua locação *#{locacao.pk}* foi confirmada.\n\n"
        f"📅 *Período:* {locacao.data_inicio.strftime('%d/%m/%Y')} "
        f"até {locacao.data_fim_prevista.strftime('%d/%m/%Y')}\n"
        f"💰 *Valor total:* {valor_formatado}\n\n"
        f"📦 *Itens Locados:*\n"
        f"{itens_texto}\n\n"
        f"📌 *Próximos passos:* \n"
        f"• Compareça à nossa loja para retirada dos itens\n"
        f"• Traga documento de identificação\n"
        f"• Em caso de dúvidas, entre em contato conosco\n"
        f"Agradecemos pela preferência! 🙏"
    )

    return enviar_texto(instance_name, _telefone(locacao), msg)


def notificar_devolucao_amanha(instance_name: str, locacao) -> dict:
    msg = (
        f"⏰ *Lembrete de Devolução*\n\n"
        f"Olá, {locacao.cliente.nome}!\n"
        f"A data de devolução dos itens que você locou está chegando!\n"
        f"A devolução da locação *#{locacao.pk}* está prevista para "
        f"*amanhã, {locacao.data_fim_prevista.strftime('%d/%m/%Y')}*.\n\n"
        f"⚠️ *IMPORTANTE:*\n"
        f"• Não se esqueça de devolver todos os itens\n"
        f"• Verifique se estão em boas condições\n"
        f"• Entregue na nossa loja no horário comercial\n\n"
        f"🔔 *Precisa prorrogar?*\n"
        f"Entre em contato conosco URGENTE para verificar disponibilidade.\n\n"
        f"Qualquer dúvida, estamos à disposição! 💬"
    )
    return enviar_texto(instance_name, _telefone(locacao), msg)


def notificar_atraso(instance_name: str, locacao, dias: int) -> dict:
    msg = (
        f"⚠️ *Devolução em Atraso*\n\n"
        f"Olá, {locacao.cliente.nome}!\n"
        f"⏰  Sua locação *#{locacao.pk}* está com *{dias} dia(s) de atraso*.\n"
        f"📅 Devolução prevista: {locacao.data_fim_prevista.strftime('%d/%m/%Y')}.\n\n"
        f"⚠️ *O que fazer agora:*\n"
        f"1. Devolva os itens IMEDIATAMENTE em nossa loja\n"
        f"2. Entre em contato para regularizar a situação\n"
        f"3. Esteja ciente de que multas estão sendo aplicadas\n"
    )
    return enviar_texto(instance_name, _telefone(locacao), msg)


def notificar_cancelamento(instance_name: str, locacao) -> dict:
    msg = (
        f"❌ *Locação Cancelada*\n\n"
        f"Olá, {locacao.cliente.nome}!\n"
        f"Sua locação *#{locacao.pk}* foi cancelada.\n\n"
        f"📌 *Motivo do cancelamento:*\n"
        f"• Solicitação do cliente\n"
        f"• Indisponibilidade de itens\n"
        f"• Problemas com pagamento\n"
        f"• Outros motivos operacionais\n"
        f"Lamentamos o ocorrido. Estamos à disposição para ajudar! 💙"

    )
    return enviar_texto(instance_name, _telefone(locacao), msg)
