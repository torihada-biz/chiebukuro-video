"""
Fish Audio S2-Pro TTS エンジン
高品質な日本語音声合成を提供する。
"""

import requests

from utils import settings
from utils.console import print_substep


class FishAudio:
    def __init__(self):
        self.max_chars = 2000
        self.api_key = settings.config["settings"]["tts"]["fish_audio_api_key"]
        self.voice_id = settings.config["settings"]["tts"].get(
            "fish_audio_voice_id", "5161d41404314212af1254556477c17d"
        )
        self.model = settings.config["settings"]["tts"].get(
            "fish_audio_model", "s2-pro"
        )
        self.language = settings.config["settings"]["tts"].get(
            "fish_audio_language", "ja"
        )
        if not self.api_key:
            raise ValueError(
                "Fish Audio APIキーが設定されていません。config.toml の "
                "[settings.tts] fish_audio_api_key を設定してください。"
            )

    def run(self, text: str, filepath: str, random_voice: bool = False):
        """テキストをMP3に変換して保存する"""
        print(
            f"[FishAudio] voice={self.voice_id[:8]}... "
            f"lang={self.language} model={self.model} "
            f"text={text[:60]}..."
        )
        resp = requests.post(
            "https://api.fish.audio/v1/tts",
            json={
                "text": text,
                "model": self.model,
                "reference_id": self.voice_id,
                "language": self.language,
                "format": "mp3",
                "mp3_bitrate": 192,
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
            stream=True,
        )

        if resp.status_code != 200:
            print_substep(
                f"Fish Audio TTS エラー: {resp.status_code} {resp.text[:200]}",
                style="red",
            )
            raise RuntimeError(f"Fish Audio TTS failed: {resp.status_code}")

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
