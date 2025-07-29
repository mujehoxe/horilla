from django.core.management.base import BaseCommand
from django.utils import timezone

class Command(BaseCommand):
    help = 'Sync Hikvision employees with Horilla'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting sync process...')
        # Your logic to sync employees will go here

        self.stdout.write('Sync complete at {}'.format(timezone.now()))
