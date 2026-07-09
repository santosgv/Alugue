import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from .whatsapp_models import WhatsAppConfig
from .whatsapp_service import (
    WhatsAppAPIError, WhatsAppConfigError,
    criar_instancia, gerar_qr, status_instancia,
    desconectar_instancia, deletar_instancia,
    instancia_existe, enviar_texto,
    notificar_locacao_criada, notificar_devolucao_amanha,
    notificar_atraso, notificar_cancelamento,
)

logger = logging.getLogger(__name__)


def _instance_name(empresa) -> str:
    """Gera nome único de instância para a empresa."""
    return f'locagest_{empresa.pk}'


# ─────────────────────────────────────────────────────────────
# PÁGINA PRINCIPAL — configuração e painel
# ─────────────────────────────────────────────────────────────

class WhatsAppConfigView(LoginRequiredMixin, TemplateView):
    template_name = 'notificacoes/whatsapp_config.html'

    def get_context_data(self, **kwargs):
        ctx     = super().get_context_data(**kwargs)
        empresa = getattr(self.request, 'empresa', None)
        config  = WhatsAppConfig.objects.filter(empresa=empresa).first()

        ctx['empresa'] = empresa
        ctx['config']  = config

        return ctx

    def post(self, request):
        empresa = getattr(request, 'empresa', None)
        if not empresa:
            messages.error(request, 'Empresa não encontrada.')
            return redirect('notificacoes:whatsapp_config')

        acao = request.POST.get('acao')

        if acao == 'conectar':
            return self._conectar(request, empresa)

        if acao == 'salvar_preferencias':
            return self._salvar_preferencias(request, empresa)

        messages.error(request, 'Ação inválida.')
        return redirect('notificacoes:whatsapp_config')

    @staticmethod
    def _conectar(request, empresa):
        """Cria a instância na Evolution API e inicia o fluxo de QR."""
        instance_name = _instance_name(empresa)

        try:
            # Cria instância se não existir
            if not instancia_existe(instance_name):
                criar_instancia(instance_name)

            # Cria ou atualiza config local
            config, criado = WhatsAppConfig.objects.get_or_create(
                empresa=empresa,
                defaults={'instance_name': instance_name},
            )
            if not criado:
                config.instance_name = instance_name
                config.ativo = True
                config.save(update_fields=['instance_name', 'ativo'])

            messages.success(request, 'Instância criada! Escaneie o QR Code abaixo com seu celular.')
            return redirect('notificacoes:whatsapp_qr')

        except WhatsAppAPIError as e:
            messages.error(request, f'Erro ao conectar: {e}')
            return redirect('notificacoes:whatsapp_config')

    @staticmethod
    def _salvar_preferencias(request, empresa):
        config = WhatsAppConfig.objects.filter(empresa=empresa).first()
        if not config:
            messages.error(request, 'Configure o WhatsApp primeiro.')
            return redirect('notificacoes:whatsapp_config')

        config.notif_locacao_criada   = 'notif_locacao_criada'   in request.POST
        config.notif_devolucao_amanha = 'notif_devolucao_amanha' in request.POST
        config.notif_atraso           = 'notif_atraso'           in request.POST
        config.notif_cancelamento     = 'notif_cancelamento'     in request.POST
        config.save(update_fields=[
            'notif_locacao_criada', 'notif_devolucao_amanha',
            'notif_atraso', 'notif_cancelamento',
        ])
        messages.success(request, 'Preferências salvas.')
        return redirect('notificacoes:whatsapp_config')


# ─────────────────────────────────────────────────────────────
# QR CODE — exibe o QR para escanear
# ─────────────────────────────────────────────────────────────

class WhatsAppQRView(LoginRequiredMixin, View):

    def get(self, request):
        empresa = getattr(request, 'empresa', None)
        config  = WhatsAppConfig.objects.filter(empresa=empresa).first()

        if not config:
            messages.error(request, 'Configure o WhatsApp primeiro.')
            return redirect('notificacoes:whatsapp_config')

        # Se já está conectado, vai para o painel
        if config.esta_conectado:
            messages.success(request, 'WhatsApp já está conectado!')
            return redirect('notificacoes:whatsapp_config')

        qr_data   = None
        qr_base64 = None
        erro      = None

        try:
            data      = gerar_qr(config.instance_name)
            qr_base64 = data.get('base64') or data.get('qrcode', {}).get('base64')
            qr_data   = data.get('code')   or data.get('qrcode', {}).get('code')
        except WhatsAppAPIError as e:
            erro = str(e)

        return render(request, 'notificacoes/whatsapp_qr.html', {
            'config':    config,
            'qr_base64': qr_base64,
            'qr_data':   qr_data,
            'erro':      erro,
        })


# ─────────────────────────────────────────────────────────────
# STATUS — polling AJAX da página de QR
# ─────────────────────────────────────────────────────────────

class WhatsAppStatusView(LoginRequiredMixin, View):
    """Retorna JSON com o estado atual da instância. Usado por polling JS."""

    def get(self, request):
        empresa = getattr(request, 'empresa', None)
        config  = WhatsAppConfig.objects.filter(empresa=empresa).first()

        if not config:
            return JsonResponse({'estado': 'desconectado', 'conectado': False})

        try:
            data  = status_instancia(config.instance_name)
            state = data.get('instance', {}).get('state', 'close')
            phone = data.get('instance', {}).get('profileName', '')

            # Atualiza número vinculado se disponível
            if state == 'open' and phone and phone != config.numero_vinculado:
                config.numero_vinculado = phone
                config.save(update_fields=['numero_vinculado'])

            conectado = state == 'open'
            print(f"WhatsAppStatusView: estado={state}, conectado={conectado}, numero={config.numero_vinculado}, instancia ={config.instance_name}")
            return JsonResponse({
                'estado':    state,
                'conectado': conectado,
                'numero':    config.numero_vinculado,
            })

        except WhatsAppAPIError as e:
            return JsonResponse({'estado': 'erro', 'conectado': False, 'erro': str(e)})


# ─────────────────────────────────────────────────────────────
# DESCONECTAR
# ─────────────────────────────────────────────────────────────

class WhatsAppDesconectarView(LoginRequiredMixin, View):

    def post(self, request):
        empresa = getattr(request, 'empresa', None)
        config  = WhatsAppConfig.objects.filter(empresa=empresa).first()

        if not config:
            messages.error(request, 'Nenhuma configuração encontrada.')
            return redirect('notificacoes:whatsapp_config')

        acao = request.POST.get('acao', 'logout')

        try:
            if acao == 'deletar':
                desconectar_instancia(config.instance_name)
                deletar_instancia(config.instance_name)
                config.delete()
                messages.warning(request, 'WhatsApp desconectado e instância removida.')
            else:
                desconectar_instancia(config.instance_name)
                config.numero_vinculado = ''
                config.save(update_fields=['numero_vinculado'])
                messages.warning(request, 'WhatsApp desconectado. Escaneie o QR para reconectar.')

        except WhatsAppAPIError as e:
            messages.error(request, f'Erro ao desconectar: {e}')

        return redirect('notificacoes:whatsapp_config')


# ─────────────────────────────────────────────────────────────
# ENVIO DE TESTE
# ─────────────────────────────────────────────────────────────

class WhatsAppTesteView(LoginRequiredMixin, View):
    """Envia mensagem de teste. Retorna JSON para AJAX."""

    def post(self, request):
        empresa  = getattr(request, 'empresa', None)
        config   = WhatsAppConfig.objects.filter(empresa=empresa, ativo=True).first()
        telefone = request.POST.get('telefone', '').strip()

        if not config:
            return JsonResponse({'ok': False, 'erro': 'WhatsApp não configurado.'})
        if not telefone:
            return JsonResponse({'ok': False, 'erro': 'Informe um telefone.'})
        if not config.esta_conectado:
            return JsonResponse({'ok': False, 'erro': 'WhatsApp não está conectado. Escaneie o QR code.'})

        try:
            enviar_texto(
                config.instance_name,
                telefone,
                '✅ *Teste AlugeSe!*\n\nSua integração com o WhatsApp está funcionando. '
                'Você receberá notificações automáticas de locações por este número.'
            )
            config.registrar_envio()
            return JsonResponse({'ok': True, 'mensagem': f'Mensagem enviada para {telefone}!'})

        except (WhatsAppConfigError, WhatsAppAPIError) as e:
            return JsonResponse({'ok': False, 'erro': str(e)})


# ─────────────────────────────────────────────────────────────
# ENVIO MANUAL POR LOCAÇÃO
# ─────────────────────────────────────────────────────────────

class WhatsAppEnviarLocacaoView(LoginRequiredMixin, View):
    """Envio manual de notificação para o cliente de uma locação."""

    def post(self, request, pk):
        from locacoes.models import Locacao
        from .models import Notificacao

        empresa = getattr(request, 'empresa', None)
        locacao = get_object_or_404(Locacao, pk=pk)
        config  = WhatsAppConfig.objects.filter(empresa=empresa, ativo=True).first()

        if not config:
            messages.error(request, 'WhatsApp não configurado. Acesse Configurações → WhatsApp.')
            return redirect('locacoes:detalhe', pk=pk)

        if not config.esta_conectado:
            messages.error(request, 'WhatsApp não está conectado. Escaneie o QR code.')
            return redirect('notificacoes:whatsapp_qr')

        tipo = request.POST.get('tipo', 'confirmacao')

        TIPOS = {
            'confirmacao':  (notificar_locacao_criada,  'Confirmação enviada'),
            'lembrete':     (notificar_devolucao_amanha,'Lembrete de devolução enviado'),
            'cancelamento': (notificar_cancelamento,    'Cancelamento informado'),
        }

        if tipo == 'atraso':
            from django.utils import timezone
            dias = (timezone.localdate() - locacao.data_fim_prevista).days
            fn   = lambda inst, loc: notificar_atraso(inst, loc, dias)
            titulo_notif = f'Aviso de atraso ({dias}d) — Locação #{locacao.pk}'
        elif tipo in TIPOS:
            fn, label    = TIPOS[tipo]
            titulo_notif = f'{label} — Locação #{locacao.pk}'
        else:
            messages.error(request, 'Tipo de notificação inválido.')
            return redirect('locacoes:detalhe', pk=pk)

        try:
            fn(config.instance_name, locacao)
            config.registrar_envio()

            Notificacao.objects.create(
                usuario=request.user,
                titulo=titulo_notif,
                mensagem=f'WhatsApp enviado para {locacao.cliente.nome} ({locacao.cliente.telefone})',
                tipo=Notificacao.TIPO_INFO,
                canal=Notificacao.CANAL_WHATSAPP,
                locacao_ref=locacao,
                enviada=True,
            )
            messages.success(request, f'✅ Mensagem enviada para {locacao.cliente.nome}!')

        except WhatsAppConfigError as e:
            messages.error(request, str(e))
        except WhatsAppAPIError as e:
            messages.error(request, f'Erro ao enviar: {e}')

        return redirect('locacoes:detalhe', pk=pk)
