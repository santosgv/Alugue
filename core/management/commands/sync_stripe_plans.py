# management/commands/sync_stripe_plans.py

from django.core.management.base import BaseCommand, CommandError
from core.models import SubscriptionPlan
from core.stripe_service import StripeService
import stripe
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sincroniza os planos pagos do banco com Products/Prices na Stripe.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--plano', type=str, default=None,
            help='Slug de um plano específico (default: todos os planos pagos)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a recriação de todos os produtos e preços'
        )
        parser.add_argument(
            '--check',
            action='store_true',
            help='Apenas verifica os preços existentes sem sincronizar'
        )

    def handle(self, *args, **options):
        # Se for apenas verificação
        if options.get('check'):
            self._check_prices()
            return
        
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
                if options.get('force'):
                    self.stdout.write("    Forçando recriação...")
                    plano_atualizado = StripeService.sincronizar_plano_forcado(plano)
                else:
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
    
    def _check_prices(self):
        """Verifica os preços existentes"""
        self.stdout.write("\n🔍 Verificando preços no Stripe...\n")
        
        planos = SubscriptionPlan.objects.filter(ativo=True)
        
        for plano in planos:
            self.stdout.write(f"\n📋 {plano.nome}:")
            
            # Verificar preço mensal
            if plano.stripe_price_id_mensal:
                try:
                    price = stripe.Price.retrieve(plano.stripe_price_id_mensal)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ Mensal: {price.id} - "
                            f"R$ {price.unit_amount/100:.2f}/{price.recurring.interval}"
                        )
                    )
                except stripe.error.InvalidRequestError:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Mensal: {plano.stripe_price_id_mensal} não encontrado")
                    )
            
            # Verificar preço anual
            if plano.stripe_price_id_anual:
                try:
                    price = stripe.Price.retrieve(plano.stripe_price_id_anual)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ Anual: {price.id} - "
                            f"R$ {price.unit_amount/100:.2f}/{price.recurring.interval}"
                        )
                    )
                except stripe.error.InvalidRequestError:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Anual: {plano.stripe_price_id_anual} não encontrado")
                    )