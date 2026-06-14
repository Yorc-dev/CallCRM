"""Движок анализа разговоров (вынесен из apps.calls)."""
from django.conf import settings


def get_analyzer():
    """Фабрика: OpenAI-анализатор при наличии ключа, иначе заглушка."""
    if settings.OPENAI_API_KEY:
        from .openai import OpenAIAnalyzer
        return OpenAIAnalyzer()
    from .placeholder import PlaceholderAnalyzer
    return PlaceholderAnalyzer()
