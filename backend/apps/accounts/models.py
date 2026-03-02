from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_OPERATOR = 'operator'
    ROLE_CHIEF = 'chief'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_OPERATOR, 'operator'),
        (ROLE_CHIEF, 'chief'),
        (ROLE_ADMIN, 'admin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OPERATOR)
    phone = models.CharField(max_length=30, blank=True, default='')

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f'{self.username} ({self.role})'

    @property
    def is_operator(self):
        return self.role == self.ROLE_OPERATOR

    @property
    def is_chief(self):
        return self.role == self.ROLE_CHIEF

    @property
    def is_chief_or_admin(self):
        return self.role in (self.ROLE_CHIEF, self.ROLE_ADMIN)
