import os
import json
import logging
import requests
from typing import List, Tuple
from gradio_client import Client, handle_file
from app.db.models import VoiceProfile
from app.services.providers.base import VoiceProvider

logger = logging.getLogger(__name__)

class F5TTSVoiceProvider(VoiceProvider):
    def __init__(self):
        self.base_url = os.getenv("F5TTS_BASE_URL", "http://127.0.0.1:7860")
        
    def validate_configuration(self) -> Tuple[bool, str]:
        try:
            res = requests.get(self.base_url, timeout=5)
            if res.status_code == 200:
                return (True, "F5-TTS local server is running.")
            return (False, f"F5-TTS server returned status code {res.status_code}.")
        except Exception as e:
            return (False, f"Failed to connect to F5-TTS server at {self.base_url}: {e}")

    def create_profile(self, persona_id: str, sample_paths: List[str], voice_profile: VoiceProfile) -> str:
        if not sample_paths:
            raise ValueError("No audio samples provided for F5-TTS voice profile.")
            
        valid_paths = [p for p in sample_paths if os.path.exists(p)]
        if not valid_paths:
            raise ValueError("Audio sample files could not be found on disk.")
            
        # Select the longest valid sample as reference
        reference_audio_path = max(valid_paths, key=os.path.getsize)
        
        provider_meta = voice_profile.provider_metadata or {}
        provider_meta.update({
            "model_name": "F5-TTS_v1",
            "language": "en",
            "enabled": True,
            "reference_audio_path": reference_audio_path
        })
        voice_profile.provider_metadata = provider_meta
        voice_profile.provider = "f5tts"
        
        return f"f5tts_clone_{persona_id}"

    def generate_speech(self, text: str, voice_profile: VoiceProfile) -> bytes:
        is_valid, err_msg = self.validate_configuration()
        if not is_valid:
            logger.error(err_msg)
            raise ValueError(f"Voice generation failed: {err_msg}")
            
        meta = voice_profile.provider_metadata or {}
        f5_settings = meta.get("f5tts_settings", {})
        
        reference_audio_path = meta.get("reference_audio_path")
        reference_text = f5_settings.get("reference_text", "athula vanthu antha batsman vara ella ballayum six adika dhaan try pannuvaaru.")
        randomize_seed = f5_settings.get("randomize_seed", False)
        seed_input = f5_settings.get("seed", 259225565) if not randomize_seed else 0
        speed_slider = f5_settings.get("speed", 0.9)
        nfe_slider = f5_settings.get("nfe_steps", 20)
        cross_fade_duration_slider = f5_settings.get("cross_fade_duration", 0.11)
        
        if not reference_audio_path or not os.path.exists(reference_audio_path):
            samples_json = voice_profile.reference_audio_files_json or "[]"
            samples = json.loads(samples_json)
            valid_samples = [s for s in samples if os.path.exists(s)]
            if not valid_samples:
                raise ValueError("No valid reference audio samples available for generation.")
            reference_audio_path = max(valid_samples, key=os.path.getsize)
        
        try:
            client = Client(self.base_url)
            logger.info(f"Generating F5-TTS speech for persona {voice_profile.persona_id} (text length: {len(text)})")
            
            res = client.predict(
                ref_audio_input=handle_file(reference_audio_path),
                ref_text_input=reference_text,
                gen_text_input=text,
                remove_silence=False,
                randomize_seed=randomize_seed,
                seed_input=seed_input,
                cross_fade_duration_slider=cross_fade_duration_slider,
                nfe_slider=nfe_slider,
                speed_slider=speed_slider,
                api_name="/basic_tts"
            )
            
            if isinstance(res, tuple) and len(res) > 0:
                audio_file_path = res[0]
            elif isinstance(res, dict) and "synthesized_audio" in res:
                audio_file_path = res["synthesized_audio"]
            else:
                audio_file_path = str(res) 
                
            with open(audio_file_path, "rb") as f:
                audio_bytes = f.read()
                
            try:
                os.remove(audio_file_path)
            except:
                pass
                
            return audio_bytes
            
        except Exception as e:
            logger.error(f"F5-TTS Generation error: {e}")
            raise ValueError(f"Failed to generate speech using F5-TTS: {e}")

    def delete_profile(self, voice_profile: VoiceProfile) -> bool:
        return True
