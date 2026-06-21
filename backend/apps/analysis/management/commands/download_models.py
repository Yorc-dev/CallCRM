"""Скачивание ONNX/CTranslate2 моделей для локальной транскрибации.

Запуск: python manage.py download_models
Полностью оффлайн после скачивания, без токенов HuggingFace.
"""
import os
import tarfile
import urllib.request

from django.core.management.base import BaseCommand

from apps.analysis.engine.transcribe import MODELS_DIR, WHISPER_MODEL

SEG_TAR_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
)
EMB_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/wespeaker_en_voxceleb_CAM++.onnx"
)


class Command(BaseCommand):
    help = 'Скачать модели Whisper (CT2) и Sherpa-ONNX (диаризация)'

    def handle(self, *args, **options):
        os.makedirs(MODELS_DIR, exist_ok=True)
        from huggingface_hub import snapshot_download

        self.stdout.write(f'Каталог моделей: {MODELS_DIR}')

        # 1. Whisper (CTranslate2), размер из WHISPER_MODEL — с HuggingFace
        whisper_dir = os.path.join(MODELS_DIR, f'whisper-{WHISPER_MODEL}')
        if not os.path.exists(os.path.join(whisper_dir, 'model.bin')):
            self.stdout.write(f'Скачиваю Whisper "{WHISPER_MODEL}" (CTranslate2)...')
            snapshot_download(repo_id=f'Systran/faster-whisper-{WHISPER_MODEL}',
                              local_dir=whisper_dir)
        else:
            self.stdout.write(f'Whisper "{WHISPER_MODEL}" уже скачан.')

        # 2. Сегментация спикеров (sherpa-onnx, GitHub release tar.bz2)
        seg_dir = os.path.join(MODELS_DIR, 'sherpa-onnx-pyannote-segmentation-3-0')
        seg_model = os.path.join(seg_dir, 'model.onnx')
        if not os.path.exists(seg_model):
            self.stdout.write('Скачиваю модель сегментации...')
            os.makedirs(seg_dir, exist_ok=True)
            tar_path = os.path.join(MODELS_DIR, 'segmentation.tar.bz2')
            urllib.request.urlretrieve(SEG_TAR_URL, tar_path)
            with tarfile.open(tar_path, 'r:bz2') as tar:
                for m in tar.getmembers():
                    if m.name.endswith('model.onnx'):
                        m.name = 'model.onnx'
                        tar.extract(m, seg_dir)
                        break
            os.remove(tar_path)
        else:
            self.stdout.write('Модель сегментации уже скачана.')

        # 3. Эмбеддинги спикеров (wespeaker CAM++, GitHub release)
        emb_dir = os.path.join(MODELS_DIR, 'embedding')
        emb_model = os.path.join(emb_dir, 'embedding_model.onnx')
        if not os.path.exists(emb_model):
            self.stdout.write('Скачиваю модель эмбеддингов...')
            os.makedirs(emb_dir, exist_ok=True)
            urllib.request.urlretrieve(EMB_URL, emb_model)
        else:
            self.stdout.write('Модель эмбеддингов уже скачана.')

        self.stdout.write(self.style.SUCCESS('Модели готовы.'))
