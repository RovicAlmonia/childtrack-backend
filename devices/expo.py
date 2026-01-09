import json
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from django.conf import settings

from .models import Device
from parents.models import ParentMobileAccount, ParentGuardian


EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'


def _send_batch(messages):
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


def _chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]


def send_expo_notifications(tokens, title, body, data=None, priority='high'):
    """Send Expo push notifications to a list of tokens.

    tokens: iterable of expo tokens
    data: optional dict payload
    """
    toks = [t for t in set(filter(None, tokens))]
    if not toks:
        return {'error': 'no tokens'}

    results = []
    for chunk in _chunked(toks, 100):
        messages = []
        for t in chunk:
            msg = {
                'to': t,
                'title': title,
                'body': body,
                'priority': priority,
            }
            if data:
                msg['data'] = data
            messages.append(msg)

        res = _send_batch(messages)
        results.append(res)
        time.sleep(0.2)

    return results


def _tokens_for_parentguardian_qs(parents_qs):
    # Find mobile users for these ParentGuardian records, then extract Device tokens
    user_ids = list(ParentMobileAccount.objects.filter(parent_guardian__in=parents_qs).values_list('user_id', flat=True))
    if not user_ids:
        return []
    return list(Device.objects.filter(user_id__in=user_ids).values_list('token', flat=True))


def notify_parents_of_attendance(attendance):
    """Notify parents related to an Attendance record."""
    try:
        parents_qs = ParentGuardian.objects.none()
        if getattr(attendance, 'student_lrn', None):
            parents_qs = ParentGuardian.objects.filter(student__lrn=attendance.student_lrn)
        if not parents_qs.exists() and getattr(attendance, 'student_name', None):
            name = attendance.student_name
            variants = {name, name.replace(' ', ''), name.replace(',', ''), name.replace(' ', '').replace(',', '')}
            if ',' in name:
                last, rest = name.split(',', 1)
                reordered = rest.strip() + ' ' + last.strip()
                variants.update({reordered, reordered.replace(' ', ''), reordered.replace(',', ''), reordered.replace(' ', '').replace(',', '')})
            q = None
            for v in variants:
                q = Q(student__name__iexact=v) if q is None else q | Q(student__name__iexact=v)
            if q is not None:
                parents_qs = ParentGuardian.objects.filter(q)

        if not parents_qs.exists():
            return {'info': 'no parents found'}

        tokens = _tokens_for_parentguardian_qs(parents_qs)
        title = 'Attendance Update'
        body = f"{attendance.student_name} - {attendance.status}"
        data = {
            'type': 'attendance',
            'student_lrn': getattr(attendance, 'student_lrn', None),
            'attendance_id': getattr(attendance, 'id', None),
            'status': getattr(attendance, 'status', None),
        }

        return send_expo_notifications(tokens, title, body, data=data)
    except Exception as e:
        return {'error': str(e)}


def notify_parents_of_event(event):
    """Notify parents tied to a ParentEvent (section/teacher/student)"""
    try:
        parents_qs = ParentGuardian.objects.none()
        if getattr(event, 'section', None):
            parents_qs = ParentGuardian.objects.filter(student__section__iexact=event.section, teacher=event.teacher)
        elif getattr(event, 'student', None):
            parents_qs = ParentGuardian.objects.filter(student=event.student)
        elif getattr(event, 'teacher', None):
            parents_qs = ParentGuardian.objects.filter(teacher=event.teacher)

        if not parents_qs.exists():
            return {'info': 'no parents found'}

        tokens = _tokens_for_parentguardian_qs(parents_qs)
        title = event.title or 'New Event'
        body = (event.description or '')[:200]
        data = {
            'type': 'event',
            'event_id': getattr(event, 'id', None),
        }
        return send_expo_notifications(tokens, title, body, data=data)
    except Exception as e:
        return {'error': str(e)}


def notify_parents_of_guardian(guardian):
    """Notify parents when a Guardian request is created (pending)."""
    try:
        parents_qs = ParentGuardian.objects.filter(student__lrn=getattr(guardian, 'student__lrn', None))
        # fallback by student_name
        if not parents_qs.exists() and getattr(guardian, 'student_name', None):
            name = guardian.student_name
            variants = {name, name.replace(' ', ''), name.replace(',', ''), name.replace(' ', '').replace(',', '')}
            if ',' in name:
                last, rest = name.split(',', 1)
                reordered = rest.strip() + ' ' + last.strip()
                variants.update({reordered, reordered.replace(' ', ''), reordered.replace(',', ''), reordered.replace(' ', '').replace(',', '')})
            q = None
            for v in variants:
                q = Q(student__name__iexact=v) if q is None else q | Q(student__name__iexact=v)
            if q is not None:
                parents_qs = ParentGuardian.objects.filter(q)

        if not parents_qs.exists():
            return {'info': 'no parents found'}

        tokens = _tokens_for_parentguardian_qs(parents_qs)
        title = 'Guardian Approval Request'
        body = f"{guardian.name} wants to be a guardian for {guardian.student_name}"
        data = {
            'type': 'guardian',
            'guardian_id': getattr(guardian, 'id', None),
        }
        return send_expo_notifications(tokens, title, body, data=data)
    except Exception as e:
        return {'error': str(e)}
