# management/commands/check_stripe_prices.py

from django.core.management.base import BaseCommand
from core.models import SubscriptionPlan
import stripe
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Verifica os preços no Stripe e compara com o banco'

    def handle(self, *args, **options):
        self.stdout.write("Verificando preços no Stripe...\n")
        
        planos = SubscriptionPlan.objects.filter(ativo=True)
        
        for plano in planos:
            self.stdout.write(f"\n📋 Plano: {plano.nome}")
            self.stdout.write(f"   ID no banco: {plano.pk}")
            
            # Verificar produto
            if plano.stripe_product_id:
                try:
                    product = stripe.Product.retrieve(plano.stripe_product_id)
                    self.stdout.write(
                        self.style.SUCCESS(f"   ✅ Produto: {product.id} - {product.name}")
                    )
                except stripe.error.InvalidRequestError:
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Produto {plano.stripe_product_id} não encontrado")
                    )
                    self.stdout.write("      Sugestão: Rode sync_stripe_plans --force")
            
            # Verificar preço mensal
            if plano.stripe_price_id_mensal:
                try:
                    price = stripe.Price.retrieve(plano.stripe_price_id_mensal)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Preço mensal: {price.id} - "
                            f"R$ {price.unit_amount/100:.2f} - {price.recurring.interval}"
                        )
                    )
                except stripe.error.InvalidRequestError:
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Preço mensal {plano.stripe_price_id_mensal} não encontrado")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING("   ⚠️  Nenhum preço mensal cadastrado")
                )
            
            # Verificar preço anual
            if plano.stripe_price_id_anual:
                try:
                    price = stripe.Price.retrieve(plano.stripe_price_id_anual)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Preço anual: {price.id} - "
                            f"R$ {price.unit_amount/100:.2f} - {price.recurring.interval}"
                        )
                    )
                except stripe.error.InvalidRequestError:
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Preço anual {plano.stripe_price_id_anual} não encontrado")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING("   ⚠️  Nenhum preço anual cadastrado")
                )