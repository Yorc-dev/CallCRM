"""Транскрибация + диаризация внутри CallCRM (faster-whisper + sherpa-onnx).

Кроссплатформенно: CPU по умолчанию (Win/Mac/Linux), CUDA — опционально через
USE_CUDA=1. На macOS CTranslate2 не поддерживает GPU → всегда CPU.
ML-зависимости импортируются ЛЕНИВО, чтобы Django стартовал без них и пайплайн
мягко деградировал, если модели ещё не скачаны.
"""
import os
import wave

MODELS_DIR = os.environ.get(
    "MODELS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "models"),
)
MODELS_DIR = os.path.abspath(MODELS_DIR)

# Размер модели Whisper: tiny|base|small|medium|large-v3
# По умолчанию medium (как в исходнике). Меняется через env WHISPER_MODEL.
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")
WHISPER_DIR = os.path.join(MODELS_DIR, f"whisper-{WHISPER_MODEL}")
SEG_MODEL = os.path.join(MODELS_DIR, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
EMB_MODEL = os.path.join(MODELS_DIR, "embedding", "embedding_model.onnx")

LANGUAGE = os.environ.get("ASR_LANGUAGE", "ru")

# --- Параметры скорости/точности (настраиваются через env) ---
# Квантизация: int8 (быстро) < int8_float32 (точнее) < float32 (макс. точность, медленно)
BEAM_SIZE = int(os.environ.get("ASR_BEAM_SIZE", "5"))
# Температуры: один 0.0 = быстрее (без повторного декодирования); список = надёжнее
TEMPERATURE = [float(x) for x in os.environ.get("ASR_TEMPERATURE", "0.0").split(",") if x.strip()]
DIARIZE_ENABLED = os.environ.get("DIARIZE_ENABLED", "1") == "1"
# Порог кластеризации спикеров: ниже = чувствительнее к разным голосам (больше спикеров).
# 0.8 слепляет всех в одного; 0.4-0.5 разделяет двух собеседников.
DIARIZE_THRESHOLD = float(os.environ.get("DIARIZE_THRESHOLD", "0.42"))
# Жёстко задать число спикеров (напр. 2 для звонка). 0/пусто = авто.
DIARIZE_NUM_SPEAKERS = int(os.environ.get("DIARIZE_NUM_SPEAKERS", "0"))
# Контекстный промпт. По умолчанию ПУСТО: маленькие модели «протекают» промптом
# в результат. Включайте осознанно только для medium/large.
INITIAL_PROMPT = os.environ.get("ASR_INITIAL_PROMPT", "")
# Подсказки-термины (через запятую): названия, бренды, имена — повышают распознавание
HOTWORDS = os.environ.get("ASR_HOTWORDS", "").strip()
VAD_MIN_SILENCE_MS = int(os.environ.get("ASR_VAD_MIN_SILENCE_MS", "500"))


def _device():
    """CPU по умолчанию; CUDA только если явно включено. compute_type — из env."""
    if os.environ.get("USE_CUDA", "0") == "1":
        return "cuda", os.environ.get("ASR_COMPUTE_TYPE", "float16")
    # int8_float32 заметно точнее чистого int8 при умеренной потере скорости
    return "cpu", os.environ.get("ASR_COMPUTE_TYPE", "int8_float32")


def models_available() -> bool:
    return (
        os.path.isdir(WHISPER_DIR)
        and os.path.exists(SEG_MODEL)
        and os.path.exists(EMB_MODEL)
    )


# Кэш загруженных моделей (на процесс воркера)
_asr = None
_diar = None


def _load_models():
    global _asr, _diar
    import faster_whisper

    device, compute_type = _device()
    if _asr is None:
        _asr = faster_whisper.WhisperModel(
            WHISPER_DIR, device=device, compute_type=compute_type,
            cpu_threads=os.cpu_count() or 4,  # все ядра → компенсируем точную квантизацию
        )
    if DIARIZE_ENABLED and _diar is None:
        import sherpa_onnx
        provider = "cuda" if device == "cuda" else "cpu"
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=SEG_MODEL),
                num_threads=1, provider=provider,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=EMB_MODEL, num_threads=1, provider=provider,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=(DIARIZE_NUM_SPEAKERS if DIARIZE_NUM_SPEAKERS > 0 else -1),
                threshold=DIARIZE_THRESHOLD,
            ),
            min_duration_on=0.2, min_duration_off=0.3,
        )
        if not config.validate():
            raise ValueError("Invalid sherpa-onnx diarization config")
        _diar = sherpa_onnx.OfflineSpeakerDiarization(config)
    return _asr, _diar


def _read_wav_mono16k(path: str):
    """Читает WAV → float32 numpy (моно, 16k предполагается). Лёгкая зависимость numpy."""
    import numpy as np
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


# Денойз перед ASR ВЫКЛЮЧЕН по умолчанию: Whisper устойчив к шуму, а агрессивный
# денойз срезает форманты речи → ухудшает распознавание. Включать только для
# реально шумной среды (DENOISE_ASR=1).
DENOISE_ASR = os.environ.get("DENOISE_ASR", "0") == "1"
DENOISE_STRENGTH = float(os.environ.get("DENOISE_STRENGTH", "0.5"))  # 0..1, мягче = чище голос


def _denoise_for_asr(samples):
    """Лёгкое шумоподавление перед Whisper. Не влияет на сохранённое аудио."""
    if not DENOISE_ASR:
        return samples
    try:
        import noisereduce as nr
        return nr.reduce_noise(y=samples, sr=SAMPLE_RATE_HZ, stationary=False,
                               prop_decrease=DENOISE_STRENGTH)
    except Exception as e:
        print(f"[denoise-asr] пропущено: {e}")
        return samples


SAMPLE_RATE_HZ = 16000


def _speaker_at(diar_segments, start, end):
    """Спикер с максимальным перекрытием интервала [start, end]."""
    best, best_ov = "SPEAKER_UNKNOWN", 0.0
    for d in diar_segments:
        ov = min(end, d["end"]) - max(start, d["start"])
        if ov > best_ov:
            best_ov, best = ov, d["speaker"]
    return best


def _assign_speakers(segments, diar_segments):
    """Назначить спикера по словам (точнее), с откатом на уровень сегмента."""
    if not diar_segments:
        for s in segments:
            s["speaker"] = "SPEAKER_UNKNOWN"
        return segments
    from collections import Counter
    for s in segments:
        words = s.get("words") or []
        if words:
            votes = [_speaker_at(diar_segments, w["start"], w["end"]) for w in words]
            s["speaker"] = Counter(votes).most_common(1)[0][0]
        else:
            s["speaker"] = _speaker_at(diar_segments, s["start"], s["end"])
    return segments


def transcribe_wav(path: str) -> dict:
    """Главная функция: WAV → {available, text, segments:[{start,end,text,speaker}]}."""
    if not models_available():
        return {
            "available": False,
            "text": "",
            "segments": [],
            "note": f"ASR-модели не найдены в {MODELS_DIR}. Запустите download_models.",
        }

    asr, diar = _load_models()
    samples = _read_wav_mono16k(path)
    asr_samples = _denoise_for_asr(samples)  # денойз только для ASR

    want_words = DIARIZE_ENABLED  # пословные тайминги нужны только для диаризации
    segments_gen, _info = asr.transcribe(
        asr_samples,
        language=LANGUAGE,
        beam_size=BEAM_SIZE,
        word_timestamps=want_words,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": VAD_MIN_SILENCE_MS},
        condition_on_previous_text=True,
        temperature=TEMPERATURE,               # один 0.0 = быстрее
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
        initial_prompt=INITIAL_PROMPT or None,
        hotwords=HOTWORDS or None,
    )
    segments = []
    for s in segments_gen:
        segments.append({
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text.strip(),
            "words": [{"start": float(w.start), "end": float(w.end)} for w in (s.words or [])] if want_words else [],
        })

    diar_segments = []
    if DIARIZE_ENABLED:
        diar_result = diar.process(samples).sort_by_start_time()
        diar_segments = [
            {"start": d.start, "end": d.end, "speaker": f"SPEAKER_{d.speaker:02d}"}
            for d in diar_result
        ]

    segments = _assign_speakers(segments, diar_segments)
    for s in segments:
        s.pop("words", None)  # не тащим в итоговый JSON
    text = "\n".join(f'{s["speaker"]}: {s["text"]}' for s in segments)
    return {"available": True, "text": text, "segments": segments}
