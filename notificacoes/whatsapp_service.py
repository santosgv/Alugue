"""
notificacoes/whatsapp_service.py
=================================
Integração com WhatsApp Business API (Meta Cloud API).

Documentação: https://developers.facebook.com/docs/whatsapp/cloud-api

Configuração necessária no settings.py / .env:
    WHATSAPP_API_VERSION   = 'v20.0'
    WHATSAPP_VERIFY_TOKEN  = 'token_secreto_para_webhook'   # você define
    # Os demais campos ficam por empresa em WhatsAppConfig

Instalação:
    pip install requests

Fluxo de configuração por empresa:
    1. Empresa acessa /whatsapp/configurar/
    2. Informa Phone Number ID e Access Token da Meta
    3. Sistema salva em WhatsAppConfig
    4. Empresa testa o envio com número próprio
    5. Pronto — notificações automáticas de locação passam a funcionar
"""

import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

WHATSAPP_API_BASE = 'https://graph.facebook.com'


class WhatsAppConfigError(Exception):
    """Levantado quando a configuração da empresa está incompleta."""
    pass


class WhatsAppAPIError(Exception):
    """Levantado quando a API da Meta retorna erro."""
    pass


class WhatsAppService:
    """
    Serviço de envio de mensagens WhatsApp via Meta Cloud API.
    Instanciado por empresa — cada empresa tem seus próprios
    Phone Number ID e Access Token.
    """

    def __init__(self, empresa):
        """
        empresa: TenantCompany
        Busca a configuração WhatsApp desta empresa.
        Levanta WhatsAppConfigError se não configurado.
        """
        from notificacoes.whatsapp_models import WhatsAppConfig

        try:
            config = WhatsAppConfig.objects.get(empresa=empresa, ativo=True)
        except WhatsAppConfig.DoesNotExist:
            raise WhatsAppConfigError(
                f"WhatsApp não configurado para a empresa {empresa.nome}. "
                f"Acesse /whatsapp/configurar/ para conectar."
            )

        self.config         = config
        self.phone_number_id = config.phone_number_id
        self.access_token    = config.access_token
        self.api_version     = getattr(settings, 'WHATSAPP_API_VERSION', 'v20.0')
        self.base_url        = f'{WHATSAPP_API_BASE}/{self.api_version}/{self.phone_number_id}/messages'

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type':  'application/json',
        }

    def _post(self, payload: dict) -> dict:
        """Faz o POST na API e trata erros."""
        try:
            response = requests.post(
                self.base_url,
                headers=self._headers(),
                json=payload,
                timeout=10,
            )
            data = response.json()
        except requests.exceptions.Timeout:
            raise WhatsAppAPIError("Timeout ao conectar com a API do WhatsApp.")
        except requests.exceptions.RequestException as e:
            raise WhatsAppAPIError(f"Erro de conexão: {e}")

        if not response.ok:
            erro = data.get('error', {})
            raise WhatsAppAPIError(
                f"Erro da API WhatsApp [{response.status_code}]: "
                f"{erro.get('message', data)}"
            )

        return data

    # ── Métodos públicos de envio ─────────────────────────────

    def enviar_texto(self, telefone: str, mensagem: str) -> dict:
        """
        Envia mensagem de texto simples.
        telefone: formato internacional sem + (ex: '5511999998888')
        """
        telefone = self._formatar_telefone(telefone)
        payload = {
            'messaging_product': 'whatsapp',
            'to':                telefone,
            'type':              'text',
            'text':              {'body': mensagem},
        }
        result = self._post(payload)
        logger.info(f"WhatsApp texto enviado para {telefone}: {result}")
        return result

    def enviar_template(
        self,
        telefone: str,
        template_name: str,
        language_code: str = 'pt_BR',
        components: list | None = None,
    ) -> dict:
        """
        Envia mensagem usando template aprovado pela Meta.
        Necessário para primeiro contato com o cliente.
        templates são aprovados no Meta Business Manager.
        """
        telefone = self._formatar_telefone(telefone)
        payload = {
            'messaging_product': 'whatsapp',
            'to':                telefone,
            'type':              'template',
            'template': {
                'name':     template_name,
                'language': {'code': language_code},
            },
        }
        if components:
            payload['template']['components'] = components

        result = self._post(payload)
        logger.info(f"WhatsApp template '{template_name}' enviado para {telefone}")
        return result

    # ── Mensagens específicas do domínio de locação ──────────

    def notificar_locacao_criada(self, locacao) -> dict:
        """
        Notifica o cliente sobre nova locação confirmada.
        Usa template 'locacao_confirmada' (deve ser aprovado na Meta).
        """
        telefone = locacao.cliente.telefone
        if not telefone:
            raise WhatsAppConfigError(
                f"Cliente {locacao.cliente.nome} não tem telefone cadastrado."
            )

        # Se quiser usar mensagem de texto livre (janela de 24h aberta):
        mensagem = (
            f"✅ *Locação Confirmada!*\n\n"
            f"Olá, {locacao.cliente.nome}!\n"
            f"Sua locação #{locacao.pk} foi confirmada.\n\n"
            f"📅 *Período:* {locacao.data_inicio.strftime('%d/%m/%Y')} "
            f"até {locacao.data_fim_prevista.strftime('%d/%m/%Y')}\n"
            f"💰 *Valor total:* R$ {locacao.valor_total}\n\n"
            f"Em caso de dúvidas, entre em contato conosco."
        )
        return self.enviar_texto(telefone, mensagem)

    def notificar_devolucao_amanha(self, locacao) -> dict:
        """Lembrete de devolução no dia seguinte."""
        telefone = locacao.cliente.telefone
        if not telefone:
            raise WhatsAppConfigError(
                f"Cliente {locacao.cliente.nome} não tem telefone cadastrado."
            )

        mensagem = (
            f"⏰ *Lembrete de Devolução*\n\n"
            f"Olá, {locacao.cliente.nome}!\n"
            f"A devolução da sua locação #{locacao.pk} está prevista "
            f"para *amanhã, {locacao.data_fim_prevista.strftime('%d/%m/%Y')}*.\n\n"
            f"Por favor, prepare os itens para a retirada.\n"
            f"Obrigado! 🙏"
        )
        return self.enviar_texto(telefone, mensagem)

    def notificar_atraso(self, locacao, dias_atraso: int) -> dict:
        """Notifica cliente sobre locação em atraso."""
        telefone = locacao.cliente.telefone
        if not telefone:
            raise WhatsAppConfigError(
                f"Cliente {locacao.cliente.nome} não tem telefone cadastrado."
            )

        mensagem = (
            f"⚠️ *Devolução em Atraso*\n\n"
            f"Olá, {locacao.cliente.nome}!\n"
            f"Sua locação #{locacao.pk} está com *{dias_atraso} dia(s) de atraso*.\n"
            f"A devolução estava prevista para "
            f"{locacao.data_fim_prevista.strftime('%d/%m/%Y')}.\n\n"
            f"Por favor, entre em contato para regularizar a situação.\n"
            f"Obrigado."
        )
        return self.enviar_texto(telefone, mensagem)

    def notificar_locacao_cancelada(self, locacao) -> dict:
        """Notifica cliente sobre cancelamento."""
        telefone = locacao.cliente.telefone
        if not telefone:
            raise WhatsAppConfigError(
                f"Cliente {locacao.cliente.nome} não tem telefone cadastrado."
            )

        mensagem = (
            f"❌ *Locação Cancelada*\n\n"
            f"Olá, {locacao.cliente.nome}!\n"
            f"Sua locação #{locacao.pk} foi cancelada.\n\n"
            f"Se tiver dúvidas, entre em contato conosco."
        )
        return self.enviar_texto(telefone, mensagem)

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _formatar_telefone(telefone: str) -> str:
        """
        Remove caracteres não numéricos e garante o formato
        internacional sem +.
        '(11) 99999-8888' → '5511999998888'
        '11999998888'     → '5511999998888'
        """
        apenas_numeros = ''.join(filter(str.isdigit, telefone))

        # Adiciona DDI Brasil se não tiver
        if len(apenas_numeros) == 11:
            return f'55{apenas_numeros}'
        if len(apenas_numeros) == 10:
            return f'55{apenas_numeros}'

        return apenas_numeros

    @staticmethod
    def verificar_webhook(token_recebido: str) -> bool:
        """
        Verifica o token de validação do webhook da Meta.
        Usado no endpoint GET /whatsapp/webhook/
        """
        token_esperado = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', '')
        return token_recebido == token_esperado