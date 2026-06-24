# core/management/commands/fix_plan.py

from django.core.management.base import BaseCommand, CommandError
from core.models import SubscriptionPlan
from core.stripe_service import StripeService

class Command(BaseCommand):
    help = 'Corrige um plano específico no Stripe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            type=str,
            required=True,
            help='Slug do plano para corrigir (ex: pro, premium)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Corrigir todos os planos pagos'
        )

    def handle(self, *args, **options):
        if options.get('all'):
            self._fix_all_plans()
        else:
            slug = options['slug']
            self._fix_plan(slug)
    
    def _fix_plan(self, slug):
        try:
            plano = SubscriptionPlan.objects.get(slug=slug)
            self.stdout.write(f"🔧 Corrigindo plano: {plano.nome}")
            
            # Mostrar IDs atuais
            self.stdout.write(f"   ID atual product: {plano.stripe_product_id}")
            self.stdout.write(f"   ID atual price_mensal: {plano.stripe_price_id_mensal}")
            self.stdout.write(f"   ID atual price_anual: {plano.stripe_price_id_anual}")
            
            # Limpar IDs
            plano.stripe_product_id = None
            plano.stripe_price_id_mensal = None
            plano.stripe_price_id_anual = None
            plano.save()
            
            self.stdout.write("   IDs limpos, recriando...")
            
            # Sincronizar novamente
            plano_atualizado = StripeService.sincronizar_plano(plano)
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Plano corrigido:"))
            self.stdout.write(f"   product_id: {plano_atualizado.stripe_product_id}")
            self.stdout.write(f"   price_mensal: {plano_atualizado.stripe_price_id_mensal}")
            self.stdout.write(f"   price_anual: {plano_atualizado.stripe_price_id_anual}")
            
        except SubscriptionPlan.DoesNotExist:
            raise CommandError(f"Plano com slug '{slug}' não encontrado")
        except Exception as e:
            raise CommandError(f"Erro ao corrigir plano: {str(e)}")
    
    def _fix_all_plans(self):
        planos = SubscriptionPlan.objects.filter(ativo=True, eh_gratuito=False)
        
        if not planos:
            self.stdout.write(self.style.WARNING("Nenhum plano pago encontrado."))
            return
        
        self.stdout.write(f"🔧 Corrigindo {planos.count()} planos...\n")
        
        for plano in planos:
            self.stdout.write(f"\n{'='*50}")
            self._fix_plan(plano.slug)
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Todos os planos corrigidos!"))