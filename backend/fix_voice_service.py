import re

with open("app/services/voice_service.py", "r") as f:
    content = f.read()

# 1. Imports
content = content.replace("from app.services.providers.uberduck_provider import UberduckVoiceProvider", "from app.services.providers.f5tts_provider import F5TTSVoiceProvider")

# 2. get_voice_provider
content = content.replace(
"""def get_voice_provider(provider_name: Optional[str] = None) -> VoiceProvider:
    if not provider_name:
        provider_name = os.getenv("VOICE_PROVIDER", "local").lower()
    
    provider_name = provider_name.lower()
    if provider_name == "uberduck":
        return UberduckVoiceProvider()""",
"""def get_voice_provider(provider_name: Optional[str] = None) -> VoiceProvider:
    if not provider_name:
        provider_name = os.getenv("VOICE_PROVIDER", "f5tts").lower()
    
    provider_name = provider_name.lower()
    if provider_name == "f5tts":
        return F5TTSVoiceProvider()"""
)

# 3. Default fallback "local" -> "f5tts" in environment fetches
content = content.replace('os.getenv("VOICE_PROVIDER", "local")', 'os.getenv("VOICE_PROVIDER", "f5tts")')

# 4. In create_profile (around line 494)
uberduck_meta_block = """elif active_prov == "uberduck":
                uberduck_meta = {
                    "voice_id": voice_id,
                    "model": "uberduck-tts-v1",
                    "voice_type": "custom_cloned",
                    "source": "uploaded_reference_audio",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "status": "ready"
                }
                meta_dict["uberduck"] = uberduck_meta
                meta_dict["uberduck_voice"] = uberduck_meta"""
                
content = content.replace(uberduck_meta_block, "")

# 5. In get_voice_profile (default fallback for return dict)
content = content.replace('''"provider": "local",
                "active_provider": "local",''', '''"provider": "f5tts",
                "active_provider": "f5tts",''')

uberduck_voice_block1 = """"uberduck_voice": {
                    "voice_id": None,
                    "status": "not_configured",
                    "verified": False
                }"""
                
f5tts_voice_block1 = """"f5tts_voice": {
                    "model_name": "F5-TTS_v1",
                    "status": "not_configured",
                    "verified": False
                }"""

content = content.replace(uberduck_voice_block1, f5tts_voice_block1)

uberduck_voice_block2 = """uberduck_voice = meta.get("uberduck_voice", {
            "voice_id": profile.voice_id if profile.provider == "uberduck" else None,
            "status": "ready" if (profile.provider == "uberduck" and profile.status == "READY") else "not_configured",
            "verified": profile.provider == "uberduck" and profile.status == "READY"
        })"""
        
f5tts_voice_block2 = """f5tts_voice = meta.get("f5tts_voice", {
            "model_name": meta.get("model_name", "F5-TTS_v1") if profile.provider == "f5tts" else None,
            "status": "ready" if (profile.provider == "f5tts" and profile.status == "READY") else "not_configured",
            "verified": profile.provider == "f5tts" and profile.status == "READY"
        })"""
        
content = content.replace(uberduck_voice_block2, f5tts_voice_block2)

content = content.replace('"uberduck_voice": uberduck_voice', '"f5tts_voice": f5tts_voice')

with open("app/services/voice_service.py", "w") as f:
    f.write(content)

print("Done replacing.")
