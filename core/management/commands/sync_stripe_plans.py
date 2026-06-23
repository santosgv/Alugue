"""
python manage.py sync_stripe_plans
=====================================
Cria na Stripe os Products e Prices correspondentes a cada
SubscriptionPlan pago do banco (planos gratuitos são ignorados).

Idempotente: se o plano já tem stripe_product_id, não recria —
apenas completa price_id_mensal/anual que estiverem faltando.

Pré-requisito: STRIPE_SECRET_KEY configurada no settings/.env.

Uso:
    python manage.py sync_stripe_plans
    python manage.py sync_stripe_plans --plano pro     # só um plano específico
"""
from django.core.management.base import BaseCommand, CommandError
from core.models import SubscriptionPlan
from core.stripe_service import StripeService

import stripe


class Command(BaseCommand):
    help = 'Sincroniza os planos pagos do banco com Products/Prices na Stripe.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--plano', type=str, default=None,
            help='Slug de um plano específico (default: todos os planos pagos)',
        )

    def handle(self, *args, **options):
        qs = SubscriptionPlan.objects.filter(ativo=True)
        if options['plano']:
            qs = qs.filter(slug=options['plano'])
            if not qs.exists():
                raise CommandError(f"Plano com slug '{options['plano']}' não encontrado.")

        planos_pagos = [p for p in qs if not p.eh_gratuito]
        planos_gratis = [p for p in qs if p.eh_gratuito]

        for plano in planos_gratis:
            self.stdout.write(f"  ⏭  Ignorado (gratuito): {plano.nome}")

        if not planos_pagos:
            self.stdout.write(self.style.WARNING('Nenhum plano pago para sincronizar.'))
            return

        for plano in planos_pagos:
            self.stdout.write(f"\n  → Sincronizando: {plano.nome}")
            try:
                plano_atualizado = StripeService.sincronizar_plano(plano)
            except stripe.error.AuthenticationError:
                raise CommandError(
                    "Chave da Stripe inválida. Verifique STRIPE_SECRET_KEY no settings."
                )
            except stripe.error.StripeError as exc:
                self.stdout.write(self.style.ERROR(f"    ✘ Erro na Stripe: {exc}"))
                continue

            self.stdout.write(self.style.SUCCESS(f"    ✔ product_id      = {plano_atualizado.stripe_product_id}"))
            self.stdout.write(self.style.SUCCESS(f"    ✔ price_id_mensal = {plano_atualizado.stripe_price_id_mensal}"))
            self.stdout.write(self.style.SUCCESS(f"    ✔ price_id_anual  = {plano_atualizado.stripe_price_id_anual}"))

        self.stdout.write(self.style.SUCCESS(f"\n✔ Sincronização concluída."))