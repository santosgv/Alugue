"""
Management command: cria os planos padrão e uma empresa/assinatura trial de exemplo.

Uso:
    python manage.py setup_planos
    python manage.py setup_planos --force   # recria mesmo se já existir
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime

from core.models import SubscriptionPlan, TenantCompany
from core.services import AssinaturaService


PLANOS = [
    {
        'nome':            'Básico',
        'slug':            'basico',
        'descricao':       'Perfeito para quem está começando.',
        'preco_mensal':    '49.90',
        'preco_anual':     '479.00',
        'limite_clientes': 10,
        'limite_produtos': 5,
        'limite_categorias': 5,
        'limite_locacoes': 20,
        'limite_usuarios': 2, 
        'ordem':           1,
        'destaque':        False,
        'recursos': {
            'whatsapp':          False,
            'multiusuario':      False,
            'relatorios':        False,
            'api_acesso':        False,
            'suporte_prioritario': False,
        },
    },
    {
        'nome':            'Pro',
        'slug':            'pro',
        'descricao':       'Para negócios em crescimento. O mais popular.',
        'preco_mensal':    '99.90',
        'preco_anual':     '959.00',
        'limite_clientes': 100,
        'limite_produtos': 50,
        'limite_categorias': 10,
        'limite_locacoes': 100,
        'limite_usuarios': 3, 
        'ordem':           2,
        'destaque':        True,
        'recursos': {
            'whatsapp':          True,
            'multiusuario':      False,
            'relatorios':        True,
            'api_acesso':        False,
            'suporte_prioritario': False,
        },
    },
    {
        'nome':            'Premium',
        'slug':            'premium',
        'descricao':       'Poder total para grandes operações.',
        'preco_mensal':    '199.90',
        'preco_anual':     '1919.00',
        'limite_clientes': 0,
        'limite_produtos': 0,
        'limite_categorias': 0,
        'limite_locacoes': 0,
        'limite_usuarios': 5, 
        'ordem':           3,
        'destaque':        False,
        'recursos': {
            'whatsapp':          True,
            'multiusuario':      True,
            'relatorios':        True,
            'api_acesso':        True,
            'suporte_prioritario': True,
        },
    },
]


class Command(BaseCommand):
    help = 'Cria os planos padrão e empresa de demonstração.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Recria os planos mesmo se já existirem.')

    def handle(self, *args, **options):
        force = options['force']

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Setup de Planos ===\n'))

        # Cria/atualiza planos
        for dados in PLANOS:
            obj, created = SubscriptionPlan.objects.update_or_create(
                slug=dados['slug'],
                defaults=dados,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✔ Plano criado: {obj.nome}'))
            else:
                self.stdout.write(f'  → Plano atualizado: {obj.nome}')

        # Cria empresa demo + trial se não existir
        empresa_qs = TenantCompany.objects.filter(nome='LocaGest')
        if not empresa_qs.exists() or force:
            plano_pro = SubscriptionPlan.objects.get(slug='basico')
            empresa, _ = TenantCompany.objects.update_or_create(
                nome='Empresa Trial',
                defaults={'ativo': True, 'plano': plano_pro},
            )

            # Cria trial de 14 dias
            sub_existente = empresa.assinaturas.filter(
                status__in=['trial', 'ativa']
            ).first()
            if not sub_existente or force:
                AssinaturaService.criar_trial(empresa, plano_pro)
                self.stdout.write(self.style.SUCCESS(
                    f'  ✔ Empresa "{empresa.nome}" criada com trial de 14 dias (plano Básico).'
                ))
            else:
                self.stdout.write(f'  → Empresa "{empresa.nome}" já possui assinatura ativa.')
        else:
            self.stdout.write(f'  → Empresa demo já existe.')

        self.stdout.write(self.style.SUCCESS('\n✔ Setup concluído!\n'))
