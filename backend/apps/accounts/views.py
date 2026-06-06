from django.conf import settings
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import UserSerializer, MyTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = UserSerializer
    # Open in DEBUG, admin only in production
    permission_classes = [permissions.AllowAny] if settings.DEBUG else [permissions.IsAdminUser]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Подтягиваем профиль сотрудника одним запросом, чтобы избежать N+1
        User = self.request.user.__class__
        return (
            User.objects
            .select_related('employee_profile__company', 'employee_profile__group')
            .get(pk=self.request.user.pk)
        )



class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer