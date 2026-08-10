import os
import json
import pytest
from unittest.mock import patch, MagicMock
from app.db.models import VoiceProfile
from app.services.providers.f5tts_provider import F5TTSVoiceProvider
from app.services.voice_service import get_voice_provider

@pytest.fixture
def f5tts_provider():
    return F5TTSVoiceProvider()

@pytest.fixture
def dummy_profile():
    profile = VoiceProfile(persona_id="test_persona")
    return profile

def test_f5tts_validate_configuration(f5tts_provider):
    with patch("requests.get") as mock_get:
        # Mock success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        is_valid, msg = f5tts_provider.validate_configuration()
        assert is_valid is True
        assert "running" in msg

        # Mock failure
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        is_valid, msg = f5tts_provider.validate_configuration()
        assert is_valid is False
        assert "500" in msg

        # Mock exception
        mock_get.side_effect = Exception("Connection Refused")
        is_valid, msg = f5tts_provider.validate_configuration()
        assert is_valid is False
        assert "Failed to connect" in msg

def test_f5tts_create_profile(f5tts_provider, dummy_profile, tmp_path):
    sample1 = tmp_path / "sample1.wav"
    sample2 = tmp_path / "sample2.wav"
    sample1.write_text("a" * 100) # smaller
    sample2.write_text("b" * 200) # larger, should be chosen
    
    paths = [str(sample1), str(sample2)]
    
    voice_id = f5tts_provider.create_profile(dummy_profile.persona_id, paths, dummy_profile)
    assert voice_id == f"f5tts_clone_{dummy_profile.persona_id}"
    
    assert dummy_profile.provider == "f5tts"
    meta = dummy_profile.provider_metadata
    assert meta["model_name"] == "F5-TTS_v1"
    assert meta["enabled"] is True
    assert meta["reference_audio_path"] == str(sample2)

@patch("app.services.providers.f5tts_provider.Client")
@patch("app.services.providers.f5tts_provider.F5TTSVoiceProvider.validate_configuration")
def test_f5tts_generate_speech(mock_validate, mock_client, f5tts_provider, dummy_profile, tmp_path):
    mock_validate.return_value = (True, "OK")
    
    dummy_wav = tmp_path / "output.wav"
    dummy_wav.write_bytes(b"dummy audio data")
    
    # Mock gradio client
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    mock_instance.predict.return_value = (str(dummy_wav), "spectrogram", "ref text", 0)
    
    # Setup profile
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"ref")
    
    dummy_profile.provider_metadata = {
        "reference_audio_path": str(ref_audio),
        "reference_text": "hello"
    }
    
    res = f5tts_provider.generate_speech("Test text", dummy_profile)
    assert res == b"dummy audio data"
    
    # Check predict was called with correct arguments
    mock_instance.predict.assert_called_once()
    
def test_f5tts_generate_speech_offline(f5tts_provider, dummy_profile):
    with patch.object(f5tts_provider, "validate_configuration", return_value=(False, "Offline Error")):
        with pytest.raises(ValueError, match="Voice generation failed: Offline Error"):
            f5tts_provider.generate_speech("Test text", dummy_profile)

def test_get_voice_provider():
    # Test our factory defaults to F5TTS
    prov = get_voice_provider("f5tts")
    assert isinstance(prov, F5TTSVoiceProvider)
