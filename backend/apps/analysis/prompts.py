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
    """Включённые критерии: общие (без отдела/группы) + по отделу + по группе оператора."""
    if not company_id:
        return []
    scope = Q(department__isnull=True, group__isnull=True)  # общекомпанейские
    if department_id:
        scope |= Q(department_id=department_id)
    if group_id:
        scope |= Q(group_id=group_id)
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
