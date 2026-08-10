import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from app.db.models import VoiceProfile

class VoiceProvider(ABC):
    """
    Abstract base class for all speech synthesis and voice cloning providers in PersonaForge AI.
    Follows the Strategy Pattern.
    """
    @abstractmethod
    def create_profile(self, persona_id: str, sample_paths: List[str], voice_profile: VoiceProfile) -> str:
        """
        Processes sample audio files and creates a voice profile.
        Returns the voice_id or model reference string.
        """
        pass

    @abstractmethod
    def generate_speech(self, text: str, voice_profile: VoiceProfile) -> bytes:
        """
        Generates speech audio bytes using the cloned voice profile.
        """
        pass

    async def generate_speech_async(self, text: str, voice_profile: VoiceProfile, **kwargs) -> bytes:
        """
        Asynchronously generates speech audio bytes. Defaults to running generate_speech in a thread.
        """
        return await asyncio.to_thread(self.generate_speech, text, voice_profile)

    @abstractmethod
    def delete_profile(self, voice_profile: VoiceProfile) -> bool:
        """
        Deletes the voice profile from the provider if applicable.
        """
        pass

    def validate_configuration(self) -> Tuple[bool, str]:
        """
        Validates provider configuration and credentials.
        Returns (is_valid, message).
        """
        return (True, "Provider configured.")
