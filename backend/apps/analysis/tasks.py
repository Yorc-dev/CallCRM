from celery import shared_task
from django.apps import apps


@shared_task(bind=True)
def transcribe_recording(self, record_id):
    """Транскрибация записи (внутри CallCRM): WAV -> текст с диаризацией.

    Результат сохраняется в TranscriptionRecord.text. ML-импорт ленивый.
    """
    TranscriptionRecord = apps.get_model('staff', 'TranscriptionRecord')
    rec = TranscriptionRecord.objects.select_related('employee').get(pk=record_id)

    from apps.analysis.engine.transcribe import transcribe_wav

    audio_path = rec.audio.path
    result = transcribe_wav(audio_path)

    if result.get('available'):
        rec.text = result['text'] or '(речь не распознана)'
        rec.transcript_segments = result.get('segments', [])
    else:
        rec.text = result.get('note', 'Транскрибация недоступна (модели не установлены).')
    rec.save(update_fields=['text', 'transcript_segments', 'updated_at'])

    # Цепочка: бесплатный локальный анализ (краткое содержание + инциденты)
    if result.get('available') and result.get('text'):
        analyze_recording.delay(record_id)

    return {
        'record_id': record_id,
        'available': result.get('available', False),
        'segments': len(result.get('segments', [])),
    }


@shared_task(bind=True)
def analyze_recording(self, record_id):
    """Локальный LLM-анализ транскрипта: краткое содержание + инциденты.

    Создаёт/обновляет Analysis (summary) и Incident по записи. Бесплатно (Ollama).
    """
    TranscriptionRecord = apps.get_model('staff', 'TranscriptionRecord')
    Analysis = apps.get_model('staff', 'Analysis')
    Incident = apps.get_model('staff', 'Incident')

    rec = TranscriptionRecord.objects.get(pk=record_id)
    # Анализируем и сегменты, и сплошной оригинал (по нему — весь разговор с таймингами).
    if not rec.text or rec.text.startswith('(') or not (rec.transcript_segments or []):
        return {'record_id': record_id, 'skipped': True}

    from apps.analysis.engine.llm import analyze_transcript
    res = analyze_transcript(rec.text, segments=rec.transcript_segments)
    if not res.get('available'):
        return {'record_id': record_id, 'available': False, 'error': res.get('error')}

    summary = res.get('summary', '')
    topics = res.get('topics', [])
    description = summary
    if topics:
        description += '\n\nТемы: ' + ', '.join(topics)

    analysis, _ = Analysis.objects.update_or_create(
        record=rec, defaults={'description': description},
    )

    # Длительность записи (для зажима таймингов от модели)
    dur_sec = 0.0
    for s in (rec.transcript_segments or []):
        dur_sec = max(dur_sec, float(s.get('end', 0)))

    # Пересоздаём инциденты этого анализа
    Incident.objects.filter(analysis=analysis).delete()
    created = 0
    for inc in res.get('incidents', []):
        ss = max(0.0, min(float(inc.get('start_sec', 0) or 0), dur_sec or 1e9))
        es = max(ss, min(float(inc.get('end_sec', 0) or 0), dur_sec or 1e9))
        Incident.objects.create(
            record=rec, analysis=analysis,
            start_minutes=round(ss / 60.0, 2), end_minutes=round(es / 60.0, 2),
            description=inc['description'], severity=inc.get('severity', 'medium'),
        )
        created += 1

    return {'record_id': record_id, 'available': True,
            'summary_len': len(summary), 'incidents': created}
