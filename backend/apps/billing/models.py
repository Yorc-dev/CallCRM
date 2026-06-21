from django.db import models


class Plan(models.Model):
    """Тарифный пакет. Настраивается админом, назначается компаниям."""
    BILLING_PER_USER = 'per_user'
    BILLING_FIXED = 'fixed'
    BILLING_CHOICES = [
        (BILLING_PER_USER, 'За сотрудника × ставка'),
        (BILLING_FIXED, 'Фиксированная ставка'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    max_users = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Максимум пользователей. Пусто = без ограничения.'
    )
    billing_type = models.CharField(
        max_length=10, choices=BILLING_CHOICES, default=BILLING_FIXED,
        help_text='Тип тарификации.'
    )
    rate = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Ставка за одного сотрудника (для типа «за сотрудника»).'
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Фиксированная цена за период (для типа «фикс»).'
    )
    features = models.JSONField(
        default=dict, blank=True,
        help_text='Набор фич, напр. {"analytics": true, "dynamic_prompts": true}'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'
        ordering = ['price', 'name']

    def __str__(self):
        limit = self.max_users if self.max_users is not None else '∞'
        return f'{self.name} (≤{limit} польз.)'

    def has_feature(self, key: str) -> bool:
        return bool(self.features.get(key, False))

    def cost_for(self, user_count: int):
        """Стоимость подписки для компании с заданным числом сотрудников."""
        if self.billing_type == self.BILLING_PER_USER:
            return self.rate * user_count
        return self.price
