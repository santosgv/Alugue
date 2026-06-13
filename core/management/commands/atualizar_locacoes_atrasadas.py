from django.core.management.base import BaseCommand
from django.utils import timezone

from locacoes.models import Locacao


class Command(BaseCommand):
    help = 'Atualiza locações vencidas para status atrasada'

    def handle(self, *args, **options):

        hoje = timezone.localdate()

        atualizadas = Locacao.objects.filter(
            status=Locacao.STATUS_ATIVA,
            data_fim_prevista__lt=hoje
        ).update(
            status=Locacao.STATUS_ATRASADA
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'{atualizadas} locações atualizadas para atrasada.'
            )
        )