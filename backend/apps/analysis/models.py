from django.db import models


class Department(models.Model):
    """Отдел бизнеса внутри компании. К нему привязываются сотрудники и промпты."""
    company = models.ForeignKey(
        'staff.Company', on_delete=models.CASCADE, related_name='departments'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['name']
        unique_together = [('company', 'name')]

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class CompanyAnalysisSettings(models.Model):
    """Настройки анализа разговоров для компании (мастер-переключатель)."""
    company = models.OneToOneField(
        'staff.Company', on_delete=models.CASCADE, related_name='analysis_settings'
    )
    enabled = models.BooleanField(
        default=True, help_text='Глобально включить/выключить AI-анализ разговоров.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Analysis Settings'
        verbose_name_plural = 'Company Analysis Settings'

    def __str__(self):
        return f'Анализ для {self.company.name}: {"вкл" if self.enabled else "выкл"}'


class PromptList(models.Model):
    """Именованный список промптов (критериев) — назначается группам сотрудников."""
    company = models.ForeignKey(
        'staff.Company', on_delete=models.CASCADE, related_name='prompt_lists'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prompt List'
        verbose_name_plural = 'Prompt Lists'
        ordering = ['name']
        unique_together = [('company', 'name')]

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class AnalysisCriterion(models.Model):
    """Критерий анализа: промпт, который подмешивается в системный запрос.

    Если department пуст — критерий применяется ко всем отделам компании.
    Динамический промптинг: для звонка собираются все включённые критерии
    его отдела + общекомпанейские.
    """
    company = models.ForeignKey(
        'staff.Company', on_delete=models.CASCADE, related_name='analysis_criteria'
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE,
        null=True, blank=True, related_name='criteria',
        help_text='Применять к отделу. Пусто = ко всем.'
    )
    group = models.ForeignKey(
        'staff.EmployeeGroup', on_delete=models.CASCADE,
        null=True, blank=True, related_name='criteria',
        help_text='Применять к группе сотрудников. Пусто = ко всем.'
    )
    prompt_list = models.ForeignKey(
        PromptList, on_delete=models.CASCADE,
        null=True, blank=True, related_name='criteria',
        help_text='Список, к которому относится промпт.'
    )
    name = models.CharField(max_length=255, help_text='Название критерия, напр. «Вежливость».')
    prompt_text = models.TextField(help_text='Инструкция для модели по этому критерию.')
    enabled = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Analysis Criterion'
        verbose_name_plural = 'Analysis Criteria'
        ordering = ['order', 'id']

    def __str__(self):
        if self.department:
            scope = f'отдел: {self.department.name}'
        elif self.group:
            scope = f'группа: {self.group.name}'
        else:
            scope = 'все'
        return f'{self.name} [{scope}]'
