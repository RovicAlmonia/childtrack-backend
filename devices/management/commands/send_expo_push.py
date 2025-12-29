import json
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from django.core.management.base import BaseCommand
from devices.models import Device


EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'


def send_batch(messages):
    data = json.dumps(messages).encode('utf-8')
    req = Request(EXPO_PUSH_URL, data=data, headers={'Content-Type': 'application/json'})
    try:
        resp = urlopen(req, timeout=10)
        body = resp.read().decode('utf-8')
        return json.loads(body)
    except HTTPError as e:
        return {'error': f'HTTPError {e.code} - {e.reason}'}
    except URLError as e:
        return {'error': f'URLError - {e.reason}'}
    except Exception as e:
        return {'error': str(e)}


class Command(BaseCommand):
    help = 'Send a simple Expo push to registered devices. Use --all to broadcast.'

    def add_arguments(self, parser):
        parser.add_argument('--title', type=str, required=True)
        parser.add_argument('--body', type=str, required=True)
        parser.add_argument('--token', type=str, help='Send to single Expo token')
        parser.add_argument('--all', action='store_true', help='Send to all registered devices')

    def handle(self, *args, **options):
        title = options['title']
        body = options['body']
        token = options.get('token')
        send_all = options.get('all')

        tokens = []
        if send_all:
            tokens = list(Device.objects.values_list('token', flat=True))
        elif token:
            tokens = [token]
        else:
            self.stderr.write('Provide --token or use --all')
            return

        if not tokens:
            self.stdout.write('No tokens to send to')
            return

        # Expo allows batching; we'll send in chunks of 100
        chunk_size = 100
        for i in range(0, len(tokens), chunk_size):
            chunk = tokens[i:i+chunk_size]
            messages = []
            for t in chunk:
                messages.append({
                    'to': t,
                    'title': title,
                    'body': body,
                    'priority': 'high',
                })

            result = send_batch(messages)
            self.stdout.write(f'Batch {i//chunk_size + 1} result: {result}')
            time.sleep(0.2)
