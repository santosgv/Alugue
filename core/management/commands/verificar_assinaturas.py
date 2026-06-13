"""
Management command: verifica e atualiza status de assinaturas expiradas.

Uso (cron diário):
    python manage.py verificar_assinaturas
"""
from django.core.management.base import BaseCommand
from core.services import AssinaturaService, UsoService
from core.models import TenantCompany


class Command(BaseCommand):
    help = 'Marca assinaturas expiradas e registra snapshot de uso.'

    def handle(self, *args, **options):
        count = AssinaturaService.verificar_expiradas()
        self.stdout.write(self.style.WARNING(f'{count} assinatura(s) marcada(s) como expirada(s).'))

        for empresa in TenantCompany.objects.filter(ativo=True):
            UsoService.registrar_snapshot(empresa)

        self.stdout.write(self.style.SUCCESS('Snapshots de uso registrados.'))
