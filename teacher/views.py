from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny

class TeacherRegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email")

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, status=400)

        user = User.objects.create_user(username=username, password=password, email=email)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"message": "User registered successfully.", "token": token.key}, status=201)


class TeacherLoginView(ObtainAuthToken):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        return Response({"token": token.key, "username": token.user.username})
