"""Динамический промптинг: сбор критериев анализа для конкретного звонка."""
from django.db.models import Q

from .models import AnalysisCriterion, CompanyAnalysisSettings


def get_call_scope(call):
    """Возвращает (company_id, department_id, group_id) через профиль оператора."""
    emp = getattr(call.operator, 'employee_profile', None)
    if emp is None:
        return None, None, None
    return emp.company_id, emp.department_id, emp.group_id


def analysis_enabled(company_id) -> bool:
    """Включён ли AI-анализ для компании (мастер-переключатель)."""
    if not company_id:
        return True
    s = CompanyAnalysisSettings.objects.filter(company_id=company_id).first()
    return s.enabled if s else True


def collect_criteria(company_id, department_id, group_id=None):
    """Включённые критерии для звонка.

    Источники: общекомпанейские + по отделу + по группе оператора +
    критерии из списков промптов, назначенных группе оператора.
    """
    if not company_id:
        return []
    scope = Q(department__isnull=True, group__isnull=True, prompt_list__isnull=True)
    if department_id:
        scope |= Q(department_id=department_id)
    if group_id:
        scope |= Q(group_id=group_id)
        # списки промптов, назначенные группе сотрудника
        from apps.staff.models import EmployeeGroup
        grp = EmployeeGroup.objects.filter(id=group_id).prefetch_related('prompt_lists').first()
        if grp:
            list_ids = list(grp.prompt_lists.values_list('id', flat=True))
            if list_ids:
                scope |= Q(prompt_list_id__in=list_ids)
    qs = AnalysisCriterion.objects.filter(
        company_id=company_id, enabled=True
    ).filter(scope).order_by('order', 'id')
    return list(qs)


def build_criteria_prompt(company_id, department_id, group_id=None) -> str:
    """Строит текст с критериями для подмешивания в системный промпт."""
    criteria = collect_criteria(company_id, department_id, group_id)
    if not criteria:
        return ''
    lines = [f'- {c.name}: {c.prompt_text}' for c in criteria]
    return (
        'Дополнительно оцени разговор по следующим критериям '
        '(добавь результат в поле "criteria_scores" как массив '
        'объектов {"name": str, "score": 0..100, "comment": str}):\n'
        + '\n'.join(lines)
    )
