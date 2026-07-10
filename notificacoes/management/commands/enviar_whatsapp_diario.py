"""
python manage.py enviar_whatsapp_diario
=========================================
Envia lembretes de devolução e avisos de atraso via WhatsApp.

Configure no cron para rodar diariamente às 8h:
  0 8 * * * cd /app && python manage.py enviar_whatsapp_diario
"""
from django.core.management.base import BaseCommand
from notificacoes.whatsapp_tasks import (
    enviar_lembretes_devolucao,
    enviar_avisos_atraso,
)


class Command(BaseCommand):
    help = 'Envia lembretes de devolução e avisos de atraso via WhatsApp (Evolution API).'

    def handle(self, *args, **options):
        self.stdout.write('\n🔔 Iniciando envios automáticos WhatsApp...\n')

        self.stdout.write('  → Lembretes de devolução (amanhã)...')
        env, err = enviar_lembretes_devolucao()
        self.stdout.write(self.style.SUCCESS(f'     ✔ {env} enviados, {err} erros'))

        self.stdout.write('  → Avisos de atraso...')
        env, err = enviar_avisos_atraso()
        self.stdout.write(self.style.SUCCESS(f'     ✔ {env} enviados, {err} erros'))

        self.stdout.write(self.style.SUCCESS('\n✔ Concluído.\n'))