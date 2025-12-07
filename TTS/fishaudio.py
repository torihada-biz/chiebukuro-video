import random

from fishaudio import FishAudio as FishAudioClient
from fishaudio.utils import save

from utils import settings


class FishAudio:
    def __init__(self):
        self.max_chars = 5000
        self.client = None
        self.voices = [
            "8ef4a238714b45718ce04243307c57a7",  # E-girl
            "802e3bc2b27e49c2995d23ef70e6ac89",  # Energetic Male
            "933563129e564b19a115bedd57b7406a",  # Sarah
            "bf322df2096a46f18c579d0baa36f41d",  # Adrian
            "b347db033a6549378b48d00acb0d06cd",  # Selene
            "536d3a5e000945adb7038665781a4aca",  # Ethan
        ]

    def run(self, text, filepath, random_voice: bool = False):
        if self.client is None:
            self.initialize()

        if random_voice:
            voice_id = self.randomvoice()
        else:
            voice_id = str(settings.config["settings"]["tts"]["fishaudio_voice"])

        audio = self.client.tts.convert(text=text, reference_id=voice_id)
        save(audio, filepath)

    def initialize(self):
        api_key = settings.config["settings"]["tts"].get("fishaudio_api_key")
        if not api_key:
            raise ValueError(
                "You didn't set a Fish Audio API key! Please set the config variable fishaudio_api_key to a valid API key."
            )

        self.client = FishAudioClient(api_key=api_key)

    def randomvoice(self):
        return random.choice(self.voices)
