#!/usr/bin/env python
"""
test_webhook_cancelamento.py
==============================
Simula localmente os principais eventos de webhook da Stripe
para validar que o cancelamento (e outros eventos) refletem
corretamente na tabela Assinatura.

Não precisa de Stripe CLI nem de conexão com a internet.
Execute com: python test_webhook_cancelamento.py

Pré-requisito: ter rodado setup_planos + ter pelo menos uma
Assinatura ativa no banco (pode criar via checkout real ou
pelo admin).
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locagest.settings')
django.setup()

import stripe
from django.utils import timezone
from core.models import TenantCompany, SubscriptionPlan, Assinatura, StripeEvent
from core.stripe_service import WebhookHandler

# ─────────────────────────────────────────────────────────────
# HELPERS DE OUTPUT
# ─────────────────────────────────────────────────────────────

def cor(texto, codigo):    return f'\033[{codigo}m{texto}\033[0m'
def ok(msg):               print(f'  {cor("✔", "32")} {msg}')
def erro(msg):             print(f'  {cor("✘", "31")} {msg}')
def info(msg):             print(f'  {cor("→", "36")} {msg}')
def titulo(msg):           print(f'\n{cor("═" * 55, "34")}\n  {cor(msg, "1;34")}\n{cor("═" * 55, "34")}')
def subtitulo(msg):        print(f'\n  {cor(msg, "1;33")}')


def checar(descricao, campo, esperado, assinatura):
    assinatura.refresh_from_db()
    valor = getattr(assinatura, campo)
    # Converte para string para comparação simples
    valor_str    = str(valor)
    esperado_str = str(esperado)
    passou = valor_str == esperado_str
    simbolo = cor('✔', '32') if passou else cor('✘', '31')
    print(f'  {simbolo} {descricao}')
    if not passou:
        print(f'      esperado : {cor(esperado_str, "32")}')
        print(f'      obtido   : {cor(valor_str,    "31")}')
    return passou


class _FakeEvent:
    """Evento mínimo compatível com WebhookHandler (Stripe SDK v15+)."""
    def __init__(self, event_id, event_type, object_dict):
        self.id   = event_id
        self.type = event_type
        # Cria um objeto com acesso por atributo OU por chave
        self.data = type('Data', (), {'object': _AttrDict(object_dict)})()

    def to_dict(self):
        return {'id': self.id, 'type': self.type}


class _AttrDict:
    """Dict que permite acesso por atributo E por chave — igual ao StripeObject."""
    def __init__(self, d: dict):
        self._d = d
        for k, v in d.items():
            setattr(self, k, _AttrDict(v) if isinstance(v, dict) else v)

    def __getitem__(self, key):
        return self._d[key]

    def __contains__(self, key):
        return key in self._d

    def get(self, key, default=None):
        return self._d.get(key, default)


def disparar_evento(tipo, objeto_dict, evento_id):
    """Constrói e processa um evento Stripe fake via WebhookHandler."""
    evento = _FakeEvent(evento_id, tipo, objeto_dict)
    WebhookHandler.processar(evento)


# ─────────────────────────────────────────────────────────────
# SETUP — cria empresa e assinatura de teste
# ─────────────────────────────────────────────────────────────

def setup():
    titulo('Setup — Preparando dados de teste')

    # Limpa eventos anteriores de teste
    StripeEvent.objects.filter(stripe_event_id__startswith='evt_test_').delete()

    # Reutiliza empresa existente ou cria uma nova
    empresa, criada = TenantCompany.objects.get_or_create(
        nome='[TESTE] Empresa Webhook',
        defaults={'email': 'webhook@teste.com', 'stripe_customer_id': 'cus_test_fake'},
    )
    if criada:
        ok(f'Empresa criada: {empresa.nome} (pk={empresa.pk})')
    else:
        ok(f'Empresa reutilizada: {empresa.nome} (pk={empresa.pk})')

    plano = SubscriptionPlan.objects.get(slug='pro')
    plano.stripe_price_id_mensal = 'price_test_pro_mensal'
    plano.stripe_price_id_anual  = 'price_test_pro_anual'
    plano.stripe_product_id      = 'prod_test_pro'
    plano.save()

    plano_premium = SubscriptionPlan.objects.get(slug='premium')
    plano_premium.stripe_price_id_mensal = 'price_test_premium_mensal'
    plano_premium.stripe_product_id      = 'prod_test_premium'
    plano_premium.save()

    # Cria assinatura ativa para os testes
    Assinatura.objects.filter(
        empresa=empresa,
        stripe_subscription_id='sub_test_sim_001',
    ).delete()

    assinatura = Assinatura.objects.create(
        empresa=empresa,
        plano=plano,
        status=Assinatura.STATUS_ATIVA,
        ciclo=Assinatura.CICLO_MENSAL,
        data_inicio=timezone.localdate(),
        data_fim=timezone.localdate().replace(day=28),
        valor_cobrado=plano.preco_mensal,
        stripe_subscription_id='sub_test_sim_001',
        stripe_checkout_session_id='cs_test_sim_001',
    )
    ok(f'Assinatura criada: pk={assinatura.pk} plano={plano.slug} status={assinatura.status}')

    # Monkeypatching — evita chamadas reais à API da Stripe
    class FakeSubAtiva:
        id = 'sub_test_sim_001'
        status = 'active'
        current_period_end = 1761868800  # timestamp futuro

    class FakeSubCancelada:
        id = 'sub_test_sim_001'
        status = 'canceled'
        current_period_end = 1761868800

    stripe.Subscription.retrieve = staticmethod(lambda sid: FakeSubAtiva())

    return empresa, assinatura, plano, plano_premium


# ─────────────────────────────────────────────────────────────
# TESTES
# ─────────────────────────────────────────────────────────────

def testar_payment_failed(assinatura):
    subtitulo('1. invoice.payment_failed — falha de cobrança')
    info('Stripe tenta cobrar, cartão recusado...')

    disparar_evento(
        tipo='invoice.payment_failed',
        objeto_dict={
            'id': 'in_test_001',
            'object': 'invoice',
            'subscription': 'sub_test_sim_001',
        },
        evento_id='evt_test_001',
    )

    checar('status = pendente_pagamento', 'status', Assinatura.STATUS_PENDENTE_PAGAMENTO, assinatura)


def testar_payment_recovered(assinatura):
    subtitulo('2. invoice.payment_succeeded — cliente atualizou o cartão, pagamento recuperado')
    info('Cliente atualiza cartão, Stripe retenta e aprova...')

    disparar_evento(
        tipo='invoice.payment_succeeded',
        objeto_dict={
            'id': 'in_test_002',
            'object': 'invoice',
            'subscription': 'sub_test_sim_001',
        },
        evento_id='evt_test_002',
    )

    checar('status = ativa', 'status', Assinatura.STATUS_ATIVA, assinatura)


def testar_mudanca_plano(assinatura, plano_premium):
    subtitulo('3. customer.subscription.updated — upgrade Pro → Premium')
    info('Cliente fez upgrade pelo Billing Portal...')

    disparar_evento(
        tipo='customer.subscription.updated',
        objeto_dict={
            'id': 'sub_test_sim_001',
            'object': 'subscription',
            'status': 'active',
            'current_period_end': 1761868800,
            'cancel_at_period_end': False,
            'items': {
                'object': 'list',
                'data': [{
                    'id': 'si_001',
                    'object': 'subscription_item',
                    'price': {
                        'id': 'price_test_premium_mensal',
                        'object': 'price',
                    },
                }],
            },
        },
        evento_id='evt_test_003',
    )

    checar('plano = premium', 'plano', plano_premium, assinatura)
    checar('status = ativa',  'status', Assinatura.STATUS_ATIVA, assinatura)


def testar_cancelamento_agendado(assinatura):
    subtitulo('4. customer.subscription.updated — cancelamento agendado para fim do período')
    info('Cliente pediu cancelamento, mas mantém acesso até o fim do ciclo...')

    disparar_evento(
        tipo='customer.subscription.updated',
        objeto_dict={
            'id': 'sub_test_sim_001',
            'object': 'subscription',
            'status': 'active',
            'current_period_end': 1761868800,
            'cancel_at_period_end': True,   # ← chave do comportamento
            'items': {
                'object': 'list',
                'data': [{
                    'id': 'si_001',
                    'object': 'subscription_item',
                    'price': {'id': 'price_test_premium_mensal', 'object': 'price'},
                }],
            },
        },
        evento_id='evt_test_004',
    )

    checar('status ainda = ativa (acesso mantido)', 'status', Assinatura.STATUS_ATIVA, assinatura)
    assinatura.refresh_from_db()
    motivo_ok = 'Cancelamento agendado' in (assinatura.motivo_cancel or '')
    simbolo = cor('✔', '32') if motivo_ok else cor('✘', '31')
    print(f'  {simbolo} motivo_cancel preenchido com aviso de cancelamento agendado')
    if not motivo_ok:
        print(f'      obtido: {assinatura.motivo_cancel!r}')


def testar_cancelamento_definitivo(assinatura):
    subtitulo('5. customer.subscription.deleted — cancelamento definitivo (fim do período chegou)')
    info('Período pago encerrou, Stripe deleta a subscription...')

    disparar_evento(
        tipo='customer.subscription.deleted',
        objeto_dict={
            'id': 'sub_test_sim_001',
            'object': 'subscription',
            'status': 'canceled',
        },
        evento_id='evt_test_005',
    )

    checar('status = cancelada',       'status',       Assinatura.STATUS_CANCELADA, assinatura)
    checar('cancelada_em preenchida',  'cancelada_em', True, assinatura)  # só verifica não-None


def testar_idempotencia():
    subtitulo('6. Idempotência — reprocessar evt_test_005 não duplica nem re-cancela')
    info('Stripe pode enviar o mesmo evento mais de uma vez...')

    # Processa novamente
    disparar_evento(
        tipo='customer.subscription.deleted',
        objeto_dict={
            'id': 'sub_test_sim_001',
            'object': 'subscription',
            'status': 'canceled',
        },
        evento_id='evt_test_005',  # mesmo ID
    )

    total = Assinatura.objects.filter(stripe_subscription_id='sub_test_sim_001').count()
    passou = total == 1
    simbolo = cor('✔', '32') if passou else cor('✘', '31')
    print(f'  {simbolo} Total de assinaturas com sub_id: {total} (esperado: 1)')


def testar_cancelada_em(assinatura):
    """Caso especial: checar se cancelada_em é preenchida (é DateTimeField, não bool)."""
    assinatura.refresh_from_db()
    preenchida = assinatura.cancelada_em is not None
    simbolo = cor('✔', '32') if preenchida else cor('✘', '31')
    print(f'  {simbolo} cancelada_em não é None: {assinatura.cancelada_em}')


def testar_middleware(empresa, assinatura):
    subtitulo('7. AssinaturaGuardMiddleware — valida bloqueio após cancelamento')
    from core.middleware import AssinaturaGuardMiddleware

    assinatura.refresh_from_db()
    bloqueado, motivo = AssinaturaGuardMiddleware._avaliar_acesso(empresa)
    passou = bloqueado is True
    simbolo = cor('✔', '32') if passou else cor('✘', '31')
    print(f'  {simbolo} Acesso bloqueado após cancelar: {bloqueado} (esperado: True)')
    if motivo:
        info(f'Motivo: {motivo}')


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    titulo('Simulação Local de Eventos Stripe — Cancelamento e Ciclo de Vida')

    empresa, assinatura, plano, plano_premium = setup()

    testar_payment_failed(assinatura)
    testar_payment_recovered(assinatura)
    testar_mudanca_plano(assinatura, plano_premium)
    testar_cancelamento_agendado(assinatura)
    testar_cancelamento_definitivo(assinatura)
    testar_cancelada_em(assinatura)
    testar_idempotencia()
    testar_middleware(empresa, assinatura)

    # ── Resumo ────────────────────────────────────────────────
    print(f'\n{cor("═" * 55, "34")}')
    eventos_ok = StripeEvent.objects.filter(
        stripe_event_id__startswith='evt_test_',
        processado=True,
        erro='',
    ).count()
    eventos_total = StripeEvent.objects.filter(
        stripe_event_id__startswith='evt_test_',
    ).count()

    print(f'  Eventos processados: {cor(str(eventos_ok), "32")} / {eventos_total}')
    assinatura.refresh_from_db()
    print(f'  Status final: {cor(assinatura.status, "36")}')
    print(f'  Plano final:  {cor(assinatura.plano.slug, "36")}')
    print(f'{cor("═" * 55, "34")}\n')

    print(f'  {cor("Próximo passo:", "1;33")} para testar com dados REAIS da Stripe:')
    print()
    print('  1. Instale o Stripe CLI:')
    print('     https://docs.stripe.com/stripe-cli#install')
    print()
    print('  2. Conecte sua conta de teste:')
    print('     stripe login')
    print()
    print('  3. Inicie o listener local:')
    print('     stripe listen --forward-to localhost:8000/webhooks/stripe/')
    print()
    print('  4. Copie o whsec_... que o CLI printar para o .env:')
    print('     STRIPE_WEBHOOK_SECRET=whsec_...')
    print()
    print('  5. Num segundo terminal, dispare eventos:')
    print('     stripe trigger customer.subscription.deleted')
    print('     stripe trigger invoice.payment_failed')
    print('     stripe trigger customer.subscription.updated')
    print()
    print('  6. Ou cancele direto no dashboard:')
    print('     https://dashboard.stripe.com/test/subscriptions')
    print()


if __name__ == '__main__':
    main()
