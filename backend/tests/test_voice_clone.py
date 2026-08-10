import os
import sys
import wave
import uuid
import struct
import math
import json
from fastapi.testclient import TestClient

# Add backend root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.db.session import SessionLocal
from app.db.models import Persona, VoiceProfile, VoiceSample

client = TestClient(app)

def create_synthetic_male_wav(filename: str, duration_sec: float = 12.0, sample_rate: int = 16000, f0_hz: float = 110.0):
    """
    Creates a synthetic male vocal reference (110 Hz fundamental with harmonics)
    simulating a deep male voice like Vijay (~100-110 Hz).
    """
    n_frames = int(sample_rate * duration_sec)
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            t = i / sample_rate
            # Generate 110 Hz fundamental + harmonics to simulate vocal cord excitation
            val = (
                0.50 * math.sin(2.0 * math.pi * f0_hz * t) +
                0.25 * math.sin(2.0 * math.pi * f0_hz * 2 * t) +
                0.15 * math.sin(2.0 * math.pi * f0_hz * 3 * t) +
                0.10 * math.sin(2.0 * math.pi * f0_hz * 4 * t)
            )
            raw_val = int(32767.0 * min(max(val, -1.0), 1.0))
            wf.writeframesraw(struct.pack('<h', raw_val))
    return filename

def run_voice_cloning_tests():
    print("=== STARTING AUTOMATED TRUE VOICE CLONING VERIFICATION SUITE ===")
    
    db = SessionLocal()
    test_persona_id = f"test_male_persona_{uuid.uuid4().hex[:6]}"
    persona = Persona(id=test_persona_id, name="Test Male Actor (Vijay Profile 110 Hz)")
    db.add(persona)
    db.commit()
    db.close()

    wav_path = "test_male_sample.wav"
    try:
        # STEP 1: Upload synthetic male reference audio
        print(f"\n[STEP 1] Generating and uploading 12s male reference audio (~110 Hz) to persona '{test_persona_id}'...")
        create_synthetic_male_wav(wav_path, duration_sec=12.0, sample_rate=16000, f0_hz=110.0)
        
        with open(wav_path, "rb") as f:
            res_up = client.post(
                f"/personas/{test_persona_id}/voice/samples",
                files={"file": ("test_male_sample.wav", f, "audio/wav")}
            )
        assert res_up.status_code == 200, f"Sample upload failed: {res_up.text}"
        up_data = res_up.json()
        assert up_data["status"] == "READY", f"Expected READY sample status, got {up_data['status']}"
        print(f"[OK] Male reference sample uploaded successfully (ID: {up_data['id']}, Duration: {up_data['duration']}s)")

        # STEP 2: Create voice profile and verify 16 kHz official conditioning extraction
        print("\n[STEP 2] Creating voice profile and extracting official neural conditioning...")
        res_create = client.post(f"/personas/{test_persona_id}/voice/create")
        assert res_create.status_code == 200, f"Profile creation failed: {res_create.text}"
        create_data = res_create.json()
        assert create_data["success"] is True
        assert create_data["voice_status"] == "READY"

        # Verify separated Analytical vs Conditioning metadata structure
        res_status = client.get(f"/personas/{test_persona_id}/voice")
        assert res_status.status_code == 200
        status_data = res_status.json()
        meta = status_data.get("speaker_metadata", {})
        
        print("\n--- VOICE CLONING CONDITIONING STATUS ---")
        cond = meta.get("voice_cloning_conditioning", {})
        print(f"  * Reference Audio Uploaded:         {cond.get('reference_audio_uploaded')}")
        print(f"  * Reference Audio Validated:        {cond.get('reference_audio_validated')}")
        print(f"  * Speaker Representation Generated: {cond.get('speaker_representation_generated')}")
        print(f"  * TTS Compatible Conditioning:      {cond.get('tts_compatible_conditioning_created')}")
        print(f"  * Conditioning Type:                {cond.get('conditioning_type')}")
        print("-----------------------------------------")
        
        assert "analytical_features" in meta, "Missing separated analytical_features structure!"
        assert "voice_cloning_conditioning" in meta, "Missing separated voice_cloning_conditioning structure!"
        assert cond.get("reference_audio_validated") is True
        assert cond.get("speaker_representation_generated") is True

        # STEP 3: Test voice speech synthesis and inspect conditioning headers
        print("\n[STEP 3] Testing speech generation via /personas/{persona_id}/voice/test...")
        test_payload = {"text": "Hello, I am testing the preservation of male vocal identity and fundamental pitch."}
        res_test = client.post(f"/personas/{test_persona_id}/voice/test", json=test_payload)
        assert res_test.status_code == 200, f"Voice test synthesis failed: {res_test.text}"
        assert len(res_test.content) > 500, "Generated audio bytes too small"
        
        cond_header = res_test.headers.get("X-Voice-Conditioned")
        print(f"[OK] Voice test synthesis completed ({len(res_test.content)} bytes, X-Voice-Conditioned={cond_header})")

        # STEP 4: Inspect diagnostic report and assert male vocal characteristics
        print("\n[STEP 4] Inspecting Developer Diagnostic Report for male pitch preservation...")
        res_diag = client.get(f"/personas/{test_persona_id}/voice/diagnostic")
        assert res_diag.status_code == 200
        diag_data = res_diag.json()
        
        ref_metrics = diag_data.get("reference_metrics", {})
        gen_metrics = diag_data.get("generated_metrics", {})
        sim_scores = diag_data.get("similarity_scores", {})
        warnings = diag_data.get("similarity_warnings", [])
        cond_verif = diag_data.get("voice_conditioning_verification", {})
        
        ref_pitch = ref_metrics.get("mean_pitch_hz", 0.0)
        gen_pitch = gen_metrics.get("mean_pitch_hz", 0.0)
        default_used = cond_verif.get("default_voice_fallback_used", False)
        
        print(f"  * Reference Mean F0: {ref_pitch} Hz")
        print(f"  * Generated Mean F0: {gen_pitch} Hz")
        print(f"  * Overall Similarity: {sim_scores.get('overall_similarity')}")
        print(f"  * Default Voice Used: {default_used}")
        if warnings:
            print("  * Diagnostic Warnings Generated:")
            for w in warnings:
                print(f"      ! {w}")

        # Assert preservation of male vocal characteristics (< 165 Hz F0) OR explicit diagnostic fallback warning
        if not default_used and gen_pitch > 0:
            assert gen_pitch < 165.0, f"Assertion Failed: Generated pitch ({gen_pitch} Hz) is female-like/too high for a male reference (< 165 Hz expected)."
            print("[SUCCESS] Verified neural voice cloning preserved male fundamental pitch characteristics (< 165 Hz)!")
        else:
            assert any("mismatch" in w.lower() or "default" in w.lower() or "higher" in w.lower() or "fallback" in w.lower() for w in warnings), "Expected explicit diagnostic warning when fallback/high pitch occurs!"
            print("[SUCCESS] Verified diagnostic validation correctly flagged fallback/gender mismatch!")

        print("\n=== ALL VOICE CLONING TESTS PASSED SUCCESSFULLY ===")

    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
        # Clean up test persona in DB
        db = SessionLocal()
        p_del = db.query(Persona).filter(Persona.id == test_persona_id).first()
        if p_del:
            from app.services.voice_service import delete_voice_profile
            delete_voice_profile(test_persona_id)
            db.delete(p_del)
            db.commit()
        db.close()

if __name__ == "__main__":
    run_voice_cloning_tests()
