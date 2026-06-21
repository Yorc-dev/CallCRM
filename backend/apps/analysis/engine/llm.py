"""Бесплатный локальный анализ транскрипта через Ollama (без OpenAI).

Берёт текст разговора и возвращает краткое содержание + список инцидентов.
Работает оффлайн. Если Ollama недоступна — мягко возвращает пустой результат.
"""
import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
LLM_ENABLED = os.environ.get("LLM_ENABLED", "1") == "1"
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT_SEC", "180"))

SYSTEM = (
    "Ты — аналитик разговоров колл-центра. На вход дан транскрипт, где каждая "
    "строка имеет тайминг в секундах: '[start-end] SPEAKER_xx: текст'. "
    "Верни СТРОГО JSON по схеме:\n"
    "{\n"
    '  "summary": "1-2 предложения в ТРЕТЬЕМ лице о сути разговора, '
    'без обращений и воды",\n'
    '  "topics": ["короткая тема", ...],\n'
    '  "incidents": [\n'
    '    {"description": "кратко: угроза/оскорбление/конфликт/нарушение", '
    '"severity": "low|medium|high", '
    '"start_sec": число_секунд_начала, "end_sec": число_секунд_конца}\n'
    "  ]\n"
    "}\n"
    "Правила: пиши кратко и по делу, на русском, в третьем лице. "
    "Угрозы и оскорбления — всегда incident с severity high. "
    "start_sec/end_sec бери из таймингов строк, где случился инцидент. "
    "Если инцидентов нет — пустой массив. Выведи ТОЛЬКО JSON."
)


def llm_available() -> bool:
    if not LLM_ENABLED:
        return False
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _segments_to_timed_text(segments) -> str:
    """Сегменты → строки с таймингами для LLM: '[0.0-2.8] SPEAKER_00: текст'."""
    lines = []
    for s in segments or []:
        st = float(s.get("start", 0)); en = float(s.get("end", 0))
        sp = s.get("speaker", "SPEAKER_00"); tx = (s.get("text") or "").strip()
        if tx:
            lines.append(f"[{st:.1f}-{en:.1f}] {sp}: {tx}")
    return "\n".join(lines)


def analyze_transcript(text: str, segments=None) -> dict:
    """Транскрипт → {available, summary, topics, incidents}.

    segments — список {start,end,speaker,text}; если задан, инциденты получают время.
    """
    if not LLM_ENABLED:
        return {"available": False, "summary": "", "topics": [], "incidents": []}
    timed = _segments_to_timed_text(segments) if segments else ""
    prompt_text = timed or text
    if not prompt_text.strip():
        return {"available": False, "summary": "", "topics": [], "incidents": []}

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM}\n\nТРАНСКРИПТ:\n{prompt_text}\n\nJSON:",
        "stream": False,
        "format": "json",
        # keep_alive — держим модель в памяти между вызовами (быстрее повторный анализ)
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "30m"),
        "options": {
            "temperature": 0.2,
            "num_predict": int(os.environ.get("OLLAMA_NUM_PREDICT", "512")),
            "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "4096")),
        },
    }
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=LLM_TIMEOUT)
        r.raise_for_status()
        raw = r.json().get("response", "{}")
        data = json.loads(raw)
    except Exception as e:
        return {"available": False, "error": str(e),
                "summary": "", "topics": [], "incidents": []}

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    incidents = []
    for it in data.get("incidents", []) or []:
        if isinstance(it, dict) and it.get("description"):
            incidents.append({
                "description": str(it.get("description", "")).strip(),
                "severity": str(it.get("severity", "")).strip().lower() or "medium",
                "start_sec": _num(it.get("start_sec", 0)),
                "end_sec": _num(it.get("end_sec", 0)),
            })
    return {
        "available": True,
        "summary": str(data.get("summary", "")).strip(),
        "topics": [str(t).strip() for t in (data.get("topics") or []) if str(t).strip()],
        "incidents": incidents,
    }
