from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import Device
from .serializers import DeviceSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def register_device(request):
    """Register or update a device push token.

    Expected JSON: { "token": "<expo_or_fcm_token>", "platform": "android|ios|expo", "device_name": "..." }
    If request is authenticated the device will be linked to the user.
    """
    token = request.data.get('token')
    if not token:
        return Response({'detail': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)

    platform = request.data.get('platform')
    device_name = request.data.get('device_name')

    user = request.user if request.user and request.user.is_authenticated else None

    obj, created = Device.objects.update_or_create(
        token=token,
        defaults={
            'platform': platform,
            'device_name': device_name,
            'user': user,
        }
    )

    serializer = DeviceSerializer(obj)
    return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
