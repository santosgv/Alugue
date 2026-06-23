
import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from decouple import config
from django.utils import timezone

from .models import SubscriptionPlan, TenantCompany, Assinatura, StripeEvent

logger = logging.getLogger(__name__)

stripe.api_key = config('STRIPE_SECRET_KEY')


class StripeConfigError(Exception):
    """Levantado quando a Stripe não está configurada corretamente."""
    pass


# ─────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────

def _ts_para_date(ts):
    """
    Converte timestamp Unix (int) → date.
    Retorna None se o valor for nulo ou inválido.
    """
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=dt_timezone.utc).date()
    except (TypeError, ValueError, OSError) as e:
        logger.warning(f"Não foi possível converter timestamp {ts!r}: {e}")
        return None


def _metadata_para_dict(metadata) -> dict:
    """
    Converte o StripeObject metadata → dict Python puro.
    Funciona tanto com o StripeObject real quanto com dicts de testes.
    """
    if not metadata:
        return {}
    if hasattr(metadata, 'to_dict'):          # StripeObject real
        return metadata.to_dict()
    return dict(metadata)                      # dict de testes


def _obter_atributo(obj, chave):
    """
    Lê um atributo de um StripeObject de forma segura —
    tenta como atributo primeiro, depois como chave de dict.
    """
    try:
        return getattr(obj, chave)
    except AttributeError:
        pass
    try:
        return obj[chave]
    except (KeyError, TypeError):
        pass
    return None


# Mapeamento status Stripe → status interno (compartilhado entre classes)
STRIPE_STATUS_MAP = {
    'active':             Assinatura.STATUS_ATIVA,
    'trialing':           Assinatura.STATUS_TRIAL,
    'past_due':           Assinatura.STATUS_PENDENTE_PAGAMENTO,
    'unpaid':             Assinatura.STATUS_PENDENTE_PAGAMENTO,
    'canceled':           Assinatura.STATUS_CANCELADA,
    'incomplete':         Assinatura.STATUS_PENDENTE_PAGAMENTO,
    'incomplete_expired': Assinatura.STATUS_CANCELADA,
    'paused':             Assinatura.STATUS_SUSPENSA,
}


def _ativar_ou_atualizar_assinatura(
    empresa: TenantCompany,
    plano: SubscriptionPlan,
    stripe_subscription_id: str,
    stripe_status: str,
    ciclo: str,
    data_fim,
    checkout_session_id: str = '',
) -> Assinatura:
    """
    Cria ou atualiza a Assinatura local com base nos dados vindos da Stripe.

    Usado em checkout.session.completed e invoice.payment_succeeded
    (na renovação o subscription_id já existe — só atualiza).

    Cancela qualquer outra assinatura ativa da mesma empresa para
    garantir que exista apenas uma por vez.
    """
    status_interno = STRIPE_STATUS_MAP.get(stripe_status, Assinatura.STATUS_ATIVA)
    valor = plano.preco_anual if ciclo == 'anual' else plano.preco_mensal

    # Cancela assinaturas ativas anteriores desta empresa
    # (que não sejam a que estamos criando/atualizando agora)
    Assinatura.objects.filter(
        empresa=empresa,
        status__in=[Assinatura.STATUS_ATIVA, Assinatura.STATUS_TRIAL],
    ).exclude(
        stripe_subscription_id=stripe_subscription_id,
    ).update(status=Assinatura.STATUS_CANCELADA)

    assinatura, criada = Assinatura.objects.update_or_create(
        stripe_subscription_id=stripe_subscription_id,
        defaults={
            'empresa':                   empresa,
            'plano':                     plano,
            'ciclo':                     ciclo,
            'status':                    status_interno,
            'data_inicio':               timezone.localdate(),
            'data_fim':                  data_fim,
            'valor_cobrado':             valor,
            'stripe_checkout_session_id': checkout_session_id,
        },
    )

    acao = 'Assinatura criada' if criada else 'Assinatura atualizada'
    logger.info(
        f"{acao}: pk={assinatura.pk} empresa={empresa.pk} "
        f"plano={plano.slug} ciclo={ciclo} status={status_interno} data_fim={data_fim}"
    )
    return assinatura


# ─────────────────────────────────────────────────────────────
# STRIPE SERVICE
# ─────────────────────────────────────────────────────────────

class StripeService:

    @staticmethod
    def obter_ou_criar_customer(empresa: TenantCompany, email: str = '') -> str:
        """
        Retorna o stripe_customer_id da empresa, criando na Stripe se necessário.
        Idempotente — chamadas repetidas não criam customers duplicados.
        """
        if empresa.stripe_customer_id:
            return empresa.stripe_customer_id

        customer = stripe.Customer.create(
            name=empresa.nome,
            email=email or empresa.email,
            metadata={'tenant_company_id': str(empresa.pk)},
        )
        empresa.stripe_customer_id = customer.id
        empresa.save(update_fields=['stripe_customer_id'])
        return customer.id

    @staticmethod
    def criar_checkout_session(
        empresa: TenantCompany,
        plano: SubscriptionPlan,
        ciclo: str,
        success_url: str,
        cancel_url: str,
        email: str = '',
        usuario_id: int | None = None,
    ) -> stripe.checkout.Session:
        """
        Cria uma Checkout Session para assinatura recorrente.
        Planos gratuitos não devem chegar aqui (verificar plano.eh_gratuito antes).
        """
        price_id = plano.stripe_price_id(ciclo)
        if not price_id:
            raise StripeConfigError(
                f"Plano '{plano.nome}' não tem stripe_price_id_{ciclo} configurado. "
                f"Rode 'python manage.py sync_stripe_plans'."
            )

        customer_id = StripeService.obter_ou_criar_customer(empresa, email=email)

        return stripe.checkout.Session.create(
            customer=customer_id,
            mode='subscription',
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            billing_address_collection='auto',
            metadata={
                'tenant_company_id':     str(empresa.pk),
                'subscription_plan_id':  str(plano.pk),
                'ciclo':                 ciclo,
                'usuario_id':            str(usuario_id) if usuario_id else '',
            },
            subscription_data={
                'metadata': {
                    'tenant_company_id':    str(empresa.pk),
                    'subscription_plan_id': str(plano.pk),
                    'ciclo':                ciclo,
                },
            },
        )

    @staticmethod
    def criar_billing_portal_session(
        empresa: TenantCompany,
        return_url: str,
    ) -> stripe.billing_portal.Session:
        """
        Abre o portal de gerenciamento da Stripe (cartão, faturas, cancelamento).
        """
        if not empresa.stripe_customer_id:
            raise StripeConfigError(
                "Empresa não possui stripe_customer_id. "
                "É necessário ter passado pelo menos uma vez pelo checkout."
            )
        return stripe.billing_portal.Session.create(
            customer=empresa.stripe_customer_id,
            return_url=return_url,
        )

    @staticmethod
    def cancelar_assinatura(
        assinatura: Assinatura,
        no_fim_do_periodo: bool = True,
    ) -> None:
        """
        Cancela a assinatura na Stripe.
        no_fim_do_periodo=True → mantém acesso até o fim do ciclo (recomendado).
        """
        if not assinatura.stripe_subscription_id:
            return
        if no_fim_do_periodo:
            stripe.Subscription.modify(
                assinatura.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        else:
            stripe.Subscription.delete(assinatura.stripe_subscription_id)

    @staticmethod
    def sincronizar_plano(plano: SubscriptionPlan) -> SubscriptionPlan:
        """
        Cria/garante Product e Prices na Stripe para o plano local.
        Idempotente. Planos gratuitos são ignorados.
        """
        if plano.eh_gratuito:
            return plano

        if not plano.stripe_product_id:
            product = stripe.Product.create(
                name=f"LocaGest — {plano.nome}",
                description=plano.descricao or f"Plano {plano.nome}",
                metadata={'subscription_plan_id': str(plano.pk), 'slug': plano.slug},
            )
            plano.stripe_product_id = product.id
        else:
            product = stripe.Product.retrieve(plano.stripe_product_id)

        if not plano.stripe_price_id_mensal and plano.preco_mensal > 0:
            p = stripe.Price.create(
                product=product.id,
                currency='brl',
                unit_amount=int(plano.preco_mensal * 100),
                recurring={'interval': 'month'},
                metadata={'subscription_plan_id': str(plano.pk), 'ciclo': 'mensal'},
            )
            plano.stripe_price_id_mensal = p.id

        if not plano.stripe_price_id_anual and plano.preco_anual > 0:
            p = stripe.Price.create(
                product=product.id,
                currency='brl',
                unit_amount=int(plano.preco_anual * 100),
                recurring={'interval': 'year'},
                metadata={'subscription_plan_id': str(plano.pk), 'ciclo': 'anual'},
            )
            plano.stripe_price_id_anual = p.id

        plano.save(update_fields=[
            'stripe_product_id', 'stripe_price_id_mensal', 'stripe_price_id_anual',
        ])
        return plano


# ─────────────────────────────────────────────────────────────
# WEBHOOK HANDLER
# ─────────────────────────────────────────────────────────────

class WebhookHandler:
    """
    Processa eventos do webhook da Stripe.
    Cada tipo de evento tem um método _handle_<tipo_com_underscores>.
    """

    @classmethod
    def processar(cls, event: stripe.Event) -> None:
        """
        Ponto de entrada único.
        Garante idempotência via StripeEvent e despacha para o handler certo.
        """
        registro, criado = StripeEvent.objects.get_or_create(
            stripe_event_id=event.id,
            defaults={'tipo': event.type, 'payload': event.to_dict()},
        )
        if not criado and registro.processado:
            logger.info(f"Evento {event.id} já processado — ignorando.")
            return

        handler_name = f"_handle_{event.type.replace('.', '_')}"
        handler = getattr(cls, handler_name, None)

        try:
            if handler:
                handler(event)
            else:
                logger.info(f"Evento sem handler específico: {event.type}")
            registro.processado = True
            registro.save(update_fields=['processado'])
        except Exception as exc:
            registro.erro = str(exc)
            registro.save(update_fields=['erro'])
            logger.exception(f"Erro ao processar evento {event.id} ({event.type}): {exc}")
            raise

    # ── checkout.session.completed ───────────────────────────
    # Pagamento aprovado no checkout → ativa a assinatura local.

    @classmethod
    def _handle_checkout_session_completed(cls, event: stripe.Event) -> None:
        session = event.data.object

        if _obter_atributo(session, 'mode') != 'subscription':
            return

        metadata = _metadata_para_dict(_obter_atributo(session, 'metadata'))
        empresa_id = metadata.get('tenant_company_id')
        plano_id   = metadata.get('subscription_plan_id')
        ciclo      = metadata.get('ciclo', 'mensal')

        if not empresa_id or not plano_id:
            logger.warning(f"checkout.session.completed sem metadata: session={_obter_atributo(session,'id')}")
            return

        empresa = TenantCompany.objects.filter(pk=empresa_id).first()
        plano   = SubscriptionPlan.objects.filter(pk=plano_id).first()

        if not empresa:
            logger.warning(f"Empresa não encontrada: pk={empresa_id}")
            return
        if not plano:
            logger.warning(f"Plano não encontrado: pk={plano_id}")
            return

        stripe_subscription_id = _obter_atributo(session, 'subscription')
        if not stripe_subscription_id:
            logger.warning(f"Session sem subscription_id: {_obter_atributo(session,'id')}")
            return

        # Busca detalhes da subscription para pegar current_period_end real
        sub_stripe  = stripe.Subscription.retrieve(stripe_subscription_id)
        stripe_status = _obter_atributo(sub_stripe, 'status') or 'active'
        period_end    = _obter_atributo(sub_stripe, 'current_period_end')
        data_fim      = _ts_para_date(period_end)

        _ativar_ou_atualizar_assinatura(
            empresa=empresa,
            plano=plano,
            stripe_subscription_id=stripe_subscription_id,
            stripe_status=stripe_status,
            ciclo=ciclo,
            data_fim=data_fim,
            checkout_session_id=_obter_atributo(session, 'id') or '',
        )

    # ── customer.subscription.updated ────────────────────────
    # Renovação automática, mudança de plano, past_due, etc.

    @classmethod
    def _handle_customer_subscription_updated(cls, event: stripe.Event) -> None:
        sub_stripe = event.data.object
        sub_id     = _obter_atributo(sub_stripe, 'id')

        assinatura = Assinatura.objects.filter(stripe_subscription_id=sub_id).first()
        if not assinatura:
            logger.warning(f"subscription.updated: assinatura local não encontrada para {sub_id}")
            return

        # ── Atualiza status ──────────────────────────────────
        stripe_status  = _obter_atributo(sub_stripe, 'status') or ''
        status_interno = STRIPE_STATUS_MAP.get(stripe_status, assinatura.status)

        # ── Atualiza data de fim (current_period_end) ────────
        period_end = _obter_atributo(sub_stripe, 'current_period_end')
        data_fim   = _ts_para_date(period_end)

        # ── Detecta mudança de plano (upgrade/downgrade via portal) ──
        # Stripe envia os items da subscription com o price novo.
        novo_plano = assinatura.plano
        try:
            items = _obter_atributo(sub_stripe, 'items')
            if items:
                data_items = _obter_atributo(items, 'data') or []
                if data_items:
                    price = _obter_atributo(data_items[0], 'price')
                    price_id = _obter_atributo(price, 'id') if price else None
                    if price_id:
                        plano_pelo_price = (
                            SubscriptionPlan.objects.filter(
                                stripe_price_id_mensal=price_id
                            ).first()
                            or SubscriptionPlan.objects.filter(
                                stripe_price_id_anual=price_id
                            ).first()
                        )
                        if plano_pelo_price and plano_pelo_price != assinatura.plano:
                            logger.info(
                                f"Mudança de plano detectada: "
                                f"{assinatura.plano.slug} → {plano_pelo_price.slug}"
                            )
                            novo_plano = plano_pelo_price
                            # Atualiza ciclo baseado em qual price_id foi identificado
                            if price_id == plano_pelo_price.stripe_price_id_anual:
                                assinatura.ciclo = Assinatura.CICLO_ANUAL
                            else:
                                assinatura.ciclo = Assinatura.CICLO_MENSAL
        except Exception as e:
            logger.warning(f"Não foi possível verificar mudança de plano: {e}")

        # ── Persiste todas as mudanças ───────────────────────
        assinatura.status   = status_interno
        assinatura.plano    = novo_plano
        if data_fim:
            assinatura.data_fim = data_fim

        # Se cancelamento agendado — registra mas mantém ativa até deletar
        if _obter_atributo(sub_stripe, 'cancel_at_period_end') and status_interno == Assinatura.STATUS_ATIVA:
            assinatura.motivo_cancel = (
                'Cancelamento agendado para o fim do período atual. '
                'O acesso permanece ativo até a data de renovação.'
            )

        assinatura.save(update_fields=['status', 'plano', 'ciclo', 'data_fim', 'motivo_cancel'])
        logger.info(
            f"Assinatura {assinatura.pk} atualizada: "
            f"status={status_interno} plano={novo_plano.slug} data_fim={data_fim}"
        )

    # ── customer.subscription.deleted ────────────────────────
    # Subscription encerrada definitivamente (cancelada ou expirada).

    @classmethod
    def _handle_customer_subscription_deleted(cls, event: stripe.Event) -> None:
        sub_stripe = event.data.object
        sub_id     = _obter_atributo(sub_stripe, 'id')

        assinatura = Assinatura.objects.filter(stripe_subscription_id=sub_id).first()
        if not assinatura:
            return

        assinatura.status       = Assinatura.STATUS_CANCELADA
        assinatura.cancelada_em = timezone.now()
        assinatura.save(update_fields=['status', 'cancelada_em'])
        logger.info(f"Assinatura {assinatura.pk} cancelada definitivamente via Stripe.")

    # ── invoice.payment_failed ───────────────────────────────
    # Cobrança falhou → bloqueia acesso via AssinaturaGuardMiddleware.

    @classmethod
    def _handle_invoice_payment_failed(cls, event: stripe.Event) -> None:
        invoice = event.data.object
        sub_id  = _obter_atributo(invoice, 'subscription')
        if not sub_id:
            return

        assinatura = Assinatura.objects.filter(stripe_subscription_id=sub_id).first()
        if not assinatura:
            return

        assinatura.status = Assinatura.STATUS_PENDENTE_PAGAMENTO
        assinatura.save(update_fields=['status'])
        logger.warning(f"Pagamento falhou — assinatura {assinatura.pk} marcada como pendente.")

    # ── invoice.payment_succeeded ─────────────────────────────
    # Cobrança aprovada (renovação automática ou recuperação após falha).

    @classmethod
    def _handle_invoice_payment_succeeded(cls, event: stripe.Event) -> None:
        invoice = event.data.object
        sub_id  = _obter_atributo(invoice, 'subscription')
        if not sub_id:
            return

        assinatura = Assinatura.objects.filter(stripe_subscription_id=sub_id).first()
        if not assinatura:
            # Pode chegar aqui antes do checkout.session.completed em corridas de eventos.
            # Neste caso o checkout.session.completed vai criar a assinatura.
            logger.info(f"invoice.payment_succeeded: assinatura ainda não existe para {sub_id}")
            return

        # Recupera se estava com pagamento pendente
        if assinatura.status == Assinatura.STATUS_PENDENTE_PAGAMENTO:
            assinatura.status = Assinatura.STATUS_ATIVA
            assinatura.save(update_fields=['status'])
            logger.info(f"Assinatura {assinatura.pk} reativada após pagamento bem-sucedido.")

        # Renova data_fim para o novo período
        try:
            sub_stripe = stripe.Subscription.retrieve(sub_id)
            period_end = _obter_atributo(sub_stripe, 'current_period_end')
            data_fim   = _ts_para_date(period_end)
            if data_fim and data_fim != assinatura.data_fim:
                assinatura.data_fim = data_fim
                assinatura.save(update_fields=['data_fim'])
                logger.info(f"Assinatura {assinatura.pk} renovada até {data_fim}.")
        except stripe.error.StripeError as e:
            logger.error(f"Não foi possível atualizar data_fim após renovação: {e}")
