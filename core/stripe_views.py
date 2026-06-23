"""
core/stripe_views.py
======================
Views da integração Stripe:
  - IniciarCheckoutView   → cria a Checkout Session e redireciona o usuário
  - CheckoutSucessoView   → tela de retorno após pagamento confirmado
  - BillingPortalView     → redireciona para o portal de gerenciamento
  - StripeWebhookView     → recebe e processa eventos da Stripe (sem login)
"""
import logging
import stripe
from decouple import config
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import SubscriptionPlan, Assinatura
from .stripe_service import StripeService, WebhookHandler, StripeConfigError

logger = logging.getLogger(__name__)


def _build_absolute_url(request, path: str) -> str:
    return request.build_absolute_uri(path)


class IniciarCheckoutView(LoginRequiredMixin, View):
    """
    Cria a Checkout Session da Stripe e redireciona o usuário para
    a página de pagamento hospedada pela própria Stripe.

    Planos gratuitos não passam por aqui — devem ser ativados
    diretamente via AssinaturaService (ver mudar_plano na view de planos).
    """

    def get(self, request, plano_id, ciclo):
        plano = get_object_or_404(SubscriptionPlan, pk=plano_id, ativo=True)

        if plano.eh_gratuito:
            messages.info(request, 'Este plano é gratuito e não passa pelo checkout de pagamento.')
            return redirect('planos')

        if ciclo not in ('mensal', 'anual'):
            messages.error(request, 'Ciclo de cobrança inválido.')
            return redirect('planos')

        empresa = getattr(request, 'empresa', None)
        if not empresa:
            messages.error(request, 'Nenhuma empresa associada à sua conta.')
            return redirect('planos')

        success_url = _build_absolute_url(request, reverse('stripe_sucesso'))
        cancel_url  = _build_absolute_url(request, reverse('planos'))

        try:
            session = StripeService.criar_checkout_session(
                empresa=empresa,
                plano=plano,
                ciclo=ciclo,
                success_url=success_url,
                cancel_url=cancel_url,
                email=request.user.email,
                usuario_id=request.user.pk,
            )
        except StripeConfigError as exc:
            logger.error(f"Erro de configuração Stripe: {exc}")
            messages.error(request, 'Este plano ainda não está disponível para pagamento. Contate o suporte.')
            return redirect('planos')
        except stripe.error.StripeError as exc:
            logger.exception("Erro ao criar Checkout Session")
            messages.error(request, 'Não foi possível iniciar o pagamento. Tente novamente em alguns instantes.')
            return redirect('planos')

        return redirect(session.url)


class CheckoutSucessoView(LoginRequiredMixin, TemplateView):
    """
    Tela exibida após o usuário concluir o pagamento no Checkout da Stripe.

    O webhook (checkout.session.completed) é a fonte de verdade que
    efetivamente ativa a assinatura — esta tela apenas informa o usuário
    e pode mostrar um estado "processando" caso o webhook ainda não
    tenha chegado (normalmente é instantâneo, mas a tela trata o atraso).
    """
    template_name = 'core/stripe_sucesso.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session_id = self.request.GET.get('session_id')
        ctx['session_id'] = session_id

        # Tenta refletir o estado mais recente para a empresa do usuário
        empresa = getattr(self.request, 'empresa', None)
        if empresa:
            ctx['assinatura'] = (
                Assinatura.objects
                .filter(empresa=empresa)
                .order_by('-criado_em')
                .first()
            )
        return ctx


class BillingPortalView(LoginRequiredMixin, View):
    """
    Redireciona para o Billing Portal da Stripe, onde o cliente pode:
      - Atualizar cartão de crédito
      - Ver histórico de faturas
      - Cancelar a assinatura
      - Trocar de plano (se configurado no dashboard da Stripe)

    Não exige nenhuma tela própria — a Stripe hospeda tudo.
    """

    def get(self, request):
        empresa = getattr(request, 'empresa', None)
        if not empresa or not empresa.stripe_customer_id:
            messages.error(request, 'Você ainda não possui uma assinatura paga ativa.')
            return redirect('planos')

        return_url = _build_absolute_url(request, reverse('planos'))

        try:
            session = StripeService.criar_billing_portal_session(empresa, return_url)
        except StripeConfigError:
            messages.error(request, 'Não foi possível abrir o portal de pagamento.')
            return redirect('planos')
        except stripe.error.StripeError:
            logger.exception("Erro ao criar Billing Portal Session")
            messages.error(request, 'Erro ao conectar com o sistema de pagamento. Tente novamente.')
            return redirect('planos')

        return redirect(session.url)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """
    Endpoint que recebe eventos da Stripe.

    SEM autenticação de usuário — a segurança vem da verificação
    de assinatura HMAC usando STRIPE_WEBHOOK_SECRET, que garante
    que o payload realmente veio da Stripe e não foi alterado.

    Configuração no dashboard da Stripe:
      URL: https://seudominio.com/webhooks/stripe/
      Eventos a escutar:
        - checkout.session.completed
        - customer.subscription.updated
        - customer.subscription.deleted
        - invoice.payment_failed
        - invoice.payment_succeeded
    """

    def post(self, request, *args, **kwargs):
        payload    = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        webhook_secret = config('STRIPE_WEBHOOK_SECRET')

        if not webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET não configurado.")
            return HttpResponse(status=500)

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            logger.warning("Payload de webhook inválido.")
            return HttpResponseBadRequest("Payload inválido")
        except stripe.error.SignatureVerificationError:
            logger.warning("Assinatura de webhook inválida — possível tentativa de fraude.")
            return HttpResponseBadRequest("Assinatura inválida")

        try:
            WebhookHandler.processar(event)
        except Exception:
            # Já logado dentro do WebhookHandler.
            # Retorna 200 mesmo em erro de processamento para a Stripe
            # não ficar reenviando indefinidamente um evento com bug
            # nos NOSSOS dados — o erro já foi registrado em StripeEvent.
            # Se preferir que a Stripe retente, mude para status=500.
            return HttpResponse(status=200)

        return HttpResponse(status=200)
