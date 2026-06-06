from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


def _employee_profile_data(user, context=None):
    """Лениво строит профиль сотрудника, если он привязан к пользователю.

    Ленивый импорт staff.serializers внутри функции, чтобы избежать
    циклической зависимости accounts -> staff на этапе загрузки модулей.
    """
    employee = getattr(user, 'employee_profile', None)
    if employee is None:
        return None
    from apps.staff.serializers import EmployeeProfileSerializer
    return EmployeeProfileSerializer(employee, context=context or {}).data


class EmployeeProfileMixin(serializers.Serializer):
    """Добавляет вложенное поле employee_profile к любому представлению пользователя."""
    employee_profile = serializers.SerializerMethodField()
    is_employee = serializers.SerializerMethodField()

    def get_employee_profile(self, obj):
        return _employee_profile_data(obj, self.context)

    def get_is_employee(self, obj):
        return getattr(obj, 'employee_profile', None) is not None


class UserSerializer(EmployeeProfileMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone',
            'password', 'employee_profile', 'is_employee',
        )
        read_only_fields = ('id',)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserPublicSerializer(EmployeeProfileMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'role',
                  'employee_profile', 'is_employee')


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = user.role
        # Лёгкие claim'ы о сотруднике (без раздувания токена)
        employee = getattr(user, 'employee_profile', None)
        token["is_employee"] = employee is not None
        if employee is not None:
            token["employee_id"] = employee.id
            token["company_id"] = employee.company_id
        return token
