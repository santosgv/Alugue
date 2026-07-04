import json
import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from .whatsapp_models import WhatsAppConfig
from .whatsapp_service import WhatsAppService, WhatsAppConfigError, WhatsAppAPIError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# FORMULÁRIO DE CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────

class WhatsAppConfigView(LoginRequiredMixin, TemplateView):
    template_name = 'notificacoes/whatsapp_config.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = getattr(self.request, 'empresa', None)
        ctx['empresa'] = empresa
        ctx['config']  = WhatsAppConfig.objects.filter(empresa=empresa).first()
        return ctx

    def post(self, request):
        empresa = getattr(request, 'empresa', None)
        if not empresa:
            messages.error(request, 'Empresa não encontrada.')
            return redirect('whatsapp_config')

        acao = request.POST.get('acao')

        if acao == 'salvar':
            return self._salvar(request, empresa)
        if acao == 'desconectar':
            return self._desconectar(request, empresa)

        messages.error(request, 'Ação inválida.')
        return redirect('notificacoes:whatsapp_config')

    @staticmethod
    def _salvar(request, empresa):
        phone_number_id = request.POST.get('phone_number_id', '').strip()
        access_token    = request.POST.get('access_token', '').strip()
        numero          = request.POST.get('numero_whatsapp', '').strip()

        if not phone_number_id or not access_token:
            messages.error(request, 'Phone Number ID e Access Token são obrigatórios.')
            return redirect('notificacoes:whatsapp_config')

        config, criado = WhatsAppConfig.objects.update_or_create(
            empresa=empresa,
            defaults={
                'phone_number_id':       phone_number_id,
                'access_token':          access_token,
                'numero_whatsapp':       numero,
                'ativo':                 True,
                'notif_locacao_criada':  'notif_locacao_criada'  in request.POST,
                'notif_devolucao_amanha':'notif_devolucao_amanha' in request.POST,
                'notif_atraso':          'notif_atraso'          in request.POST,
                'notif_cancelamento':    'notif_cancelamento'    in request.POST,
            },
        )
        acao = 'configurado' if criado else 'atualizado'
        messages.success(request, f'WhatsApp {acao} com sucesso!')
        return redirect('notificacoes:whatsapp_config')

    @staticmethod
    def _desconectar(request, empresa):
        WhatsAppConfig.objects.filter(empresa=empresa).update(ativo=False)
        messages.warning(request, 'WhatsApp desconectado. As notificações automáticas foram pausadas.')
        return redirect('notificacoes:whatsapp_config')


# ─────────────────────────────────────────────────────────────
# ENVIO DE TESTE
# ─────────────────────────────────────────────────────────────

class WhatsAppTesteView(LoginRequiredMixin, View):
    def post(self, request):
        empresa  = getattr(request, 'empresa', None)
        telefone = request.POST.get('telefone', '').strip()

        if not telefone:
            return JsonResponse({'ok': False, 'erro': 'Informe um telefone para o teste.'})

        try:
            svc = WhatsAppService(empresa)
            svc.enviar_texto(
                telefone,
                '✅ Teste de conexão do LocaGest!\n\n'
                'Sua integração com o WhatsApp está funcionando corretamente. '
                'Você receberá notificações automáticas de locações por este número.'
            )
            return JsonResponse({'ok': True, 'mensagem': f'Mensagem enviada para {telefone}!'})

        except WhatsAppConfigError as e:
            return JsonResponse({'ok': False, 'erro': str(e)})
        except WhatsAppAPIError as e:
            return JsonResponse({'ok': False, 'erro': f'Erro da API: {e}'})
        except Exception as e:
            logger.exception("Erro inesperado no teste WhatsApp")
            return JsonResponse({'ok': False, 'erro': f'Erro inesperado: {e}'})


# ─────────────────────────────────────────────────────────────
# WEBHOOK DA META (verificação + recebimento)
# ─────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    def get(self, request):
        """Verificação do webhook pela Meta."""
        mode       = request.GET.get('hub.mode')
        token      = request.GET.get('hub.verify_token')
        challenge  = request.GET.get('hub.challenge')

        if mode == 'subscribe' and WhatsAppService.verificar_webhook(token):
            logger.info("Webhook WhatsApp verificado com sucesso.")
            return HttpResponse(challenge, content_type='text/plain')

        logger.warning(f"Verificação de webhook falhou — token={token!r}")
        return HttpResponse(status=403)

    def post(self, request):
        """Recebe eventos da Meta (mensagens recebidas, status de entrega)."""
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        # Processa em background para não travar o webhook
        try:
            self._processar_payload(payload)
        except Exception:
            logger.exception("Erro ao processar payload do webhook WhatsApp")

        # Sempre retorna 200 para a Meta não reenviar
        return HttpResponse(status=200)

    @staticmethod
    def _processar_payload(payload: dict):
        entry = payload.get('entry', [])
        for e in entry:
            for change in e.get('changes', []):
                value = change.get('value', {})

                # Mensagens recebidas dos clientes
                for msg in value.get('messages', []):
                    remetente = msg.get('from')
                    texto     = msg.get('text', {}).get('body', '')
                    logger.info(f"WhatsApp recebido de {remetente}: {texto!r}")
                    # TODO: resposta automática, chatbot, etc.

                # Status de entrega (sent, delivered, read, failed)
                for status in value.get('statuses', []):
                    msg_id    = status.get('id')
                    estado    = status.get('status')
                    logger.info(f"WhatsApp status: {msg_id} → {estado}")


# ─────────────────────────────────────────────────────────────
# ENVIO MANUAL POR LOCAÇÃO
# ─────────────────────────────────────────────────────────────

class WhatsAppEnviarLocacaoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from locacoes.models import Locacao
        from .models import Notificacao

        empresa = getattr(request, 'empresa', None)
        locacao = get_object_or_404(Locacao, pk=pk)
        tipo    = request.POST.get('tipo', 'confirmacao')

        try:
            svc = WhatsAppService(empresa)

            if tipo == 'confirmacao':
                svc.notificar_locacao_criada(locacao)
                titulo_notif  = f'Confirmação enviada — Locação #{locacao.pk}'

            elif tipo == 'lembrete':
                svc.notificar_devolucao_amanha(locacao)
                titulo_notif  = f'Lembrete enviado — Locação #{locacao.pk}'

            elif tipo == 'atraso':
                from django.utils import timezone
                dias = (timezone.localdate() - locacao.data_fim_prevista).days
                svc.notificar_atraso(locacao, dias)
                titulo_notif  = f'Aviso de atraso enviado — Locação #{locacao.pk}'

            elif tipo == 'cancelamento':
                svc.notificar_locacao_cancelada(locacao)
                titulo_notif  = f'Cancelamento informado — Locação #{locacao.pk}'

            else:
                messages.error(request, 'Tipo de notificação inválido.')
                return redirect('locacoes:detalhe', pk=pk)

            # Registra no histórico de notificações
            Notificacao.objects.create(
                usuario=request.user,
                titulo=titulo_notif,
                mensagem=f'Mensagem WhatsApp enviada para {locacao.cliente.nome} '
                         f'({locacao.cliente.telefone})',
                tipo=Notificacao.TIPO_INFO,
                canal=Notificacao.CANAL_WHATSAPP,
                locacao_ref=locacao,
                enviada=True,
            )

            # Atualiza contador da config
            config = WhatsAppConfig.objects.filter(empresa=empresa).first()
            if config:
                config.registrar_envio()

            messages.success(
                request,
                f'✅ Mensagem WhatsApp enviada para {locacao.cliente.nome}!'
            )

        except WhatsAppConfigError as e:
            messages.error(request, f'WhatsApp não configurado: {e}')
        except WhatsAppAPIError as e:
            messages.error(request, f'Erro ao enviar WhatsApp: {e}')
        except Exception as e:
            logger.exception(f"Erro inesperado ao enviar WhatsApp para locação {pk}")
            messages.error(request, f'Erro inesperado: {e}')

        return redirect('locacoes:detalhe', pk=pk)