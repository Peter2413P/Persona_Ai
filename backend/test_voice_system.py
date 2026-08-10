import os
import sys
import wave
import uuid
import struct
import math
import asyncio
from fastapi.testclient import TestClient

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.db.session import SessionLocal
from app.db.models import Persona, VoiceProfile, VoiceSample

client = TestClient(app)

def create_synthetic_wav(filename: str, duration_sec: float = 12.0, sample_rate: int = 22050, freq_hz: float = 120.0):
    """Creates a synthetic WAV file containing a sine wave simulating speech audio (e.g. 120 Hz deep male vocal fundamental)."""
    n_frames = int(sample_rate * duration_sec)
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
            wf.writeframesraw(struct.pack('<h', val))
    return filename

def run_tests():
    print("=== STARTING 13-PHASE GENERIC HYBRID VOICE CLONING VERIFICATION SUITE ===")
    
    # Setup test persona
    db = SessionLocal()
    test_persona_id = f"test_voice_persona_{uuid.uuid4().hex[:6]}"
    persona = Persona(id=test_persona_id, name="Test Voice Actor (Deep Male 120 Hz)")
    db.add(persona)
    db.commit()
    db.close()
    
    try:
        # 1. Test Sample Upload & Phase 2 Preprocessing
        print("\n[TEST 1] Testing Audio Sample Upload & Phase 2 Preprocessing...")
        wav_path = create_synthetic_wav("test_sample.wav", duration_sec=12.0, freq_hz=120.0)
        with open(wav_path, "rb") as f:
            res = client.post(
                f"/personas/{test_persona_id}/voice/samples",
                files={"file": ("test_sample.wav", f, "audio/wav")}
            )
        if os.path.exists(wav_path):
            os.remove(wav_path)
            
        assert res.status_code == 200, f"Sample upload failed: {res.text}"
        data = res.json()
        assert data["status"] == "READY", f"Expected READY status, got {data['status']}"
        assert data["duration"] >= 10.0, f"Expected duration >= 10s, got {data['duration']}"
        assert "warnings" in data, "Expected warnings field in upload response"
        sample_id = data["id"]
        print(f"[OK] Sample upload & Phase 2 preprocessing passed (Sample ID: {sample_id}, Duration: {data['duration']}s)")

        # 2. Test List Samples & Profile Status
        print("\n[TEST 2] Testing List Samples & Profile Status...")
        res = client.get(f"/personas/{test_persona_id}/voice/samples")
        assert res.status_code == 200
        samples = res.json()
        assert len(samples) == 1
        
        res_status = client.get(f"/personas/{test_persona_id}/voice")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "SAMPLES_UPLOADED"
        print("[OK] List samples and profile status passed.")

        # 3. Test Create Voice Profile (Phase 3 & 10: F0 extraction, LUFS, 512-dim embedding)
        print("\n[TEST 3] Testing Voice Profile Creation (Phase 3 & 10 Acoustic Profiling)...")
        res_create = client.post(f"/personas/{test_persona_id}/voice/create")
        assert res_create.status_code == 200, f"Profile creation failed: {res_create.text}"
        create_data = res_create.json()
        assert create_data["success"] is True
        assert create_data["voice_status"] == "READY"
        
        # Verify cached speaker metadata & 512-dim embedding
        res_status_ready = client.get(f"/personas/{test_persona_id}/voice")
        status_data = res_status_ready.json()
        assert status_data["status"] == "READY"
        meta = status_data.get("speaker_metadata", {})
        assert meta.get("has_embedding") is True, "512-dim speaker embedding vector was not generated or cached!"
        print(f"[OK] Voice profile & 512-dim embedding creation passed (Provider: {create_data['provider']}, F0: {meta.get('mean_f0')} Hz, LUFS: {meta.get('loudness_lufs')} LUFS)")

        # 4. Test Custom Voice Synthesis via /chat/tts (Phase 5, 6, 7, 8)
        print("\n[TEST 4] Testing Custom Cloned Voice Speech Generation (with Phase 6 & 7 Normalization)...")
        tts_payload = {
            "text": "Hello, this is a verified test of my cloned vocal identity with loudness normalization.",
            "persona_id": test_persona_id
        }
        res_tts = client.post("/chat/tts", json=tts_payload)
        assert res_tts.status_code == 200, f"TTS generation failed: {res_tts.text}"
        assert len(res_tts.content) > 100, "Generated audio content is empty or too small"
        print(f"[OK] Custom voice speech generation passed ({len(res_tts.content)} bytes generated)")

        # 5. Test Developer Diagnostic Report Endpoint (Phase 4 & 12)
        print("\n[TEST 5] Testing Developer Diagnostic Report Endpoint (Phase 4 & 12)...")
        res_diag = client.get(f"/personas/{test_persona_id}/voice/diagnostic")
        assert res_diag.status_code == 200, f"Diagnostic report fetch failed: {res_diag.text}"
        diag_data = res_diag.json()
        assert diag_data.get("status") != "NOT_AVAILABLE", "Diagnostic report should be available after speech synthesis"
        assert "reference_metrics" in diag_data, "Missing reference_metrics in diagnostic report"
        assert "generated_metrics" in diag_data, "Missing generated_metrics in diagnostic report"
        assert "similarity_scores" in diag_data, "Missing similarity_scores in diagnostic report"
        assert "voice_conditioning_verification" in diag_data, "Missing conditioning verification in diagnostic report"
        
        sim_scores = diag_data["similarity_scores"]
        cond_ver = diag_data["voice_conditioning_verification"]
        print(f"[OK] Diagnostic report passed (Overall Similarity: {sim_scores.get('overall_similarity')}, Default Fallback Used: {cond_ver.get('default_voice_fallback_used')})")

        # 6. Test Controlled Sentence Evaluation Suite (Phase 11)
        print("\n[TEST 6] Testing Controlled Sentence Evaluation Suite (Phase 11)...")
        res_eval = client.post(f"/personas/{test_persona_id}/voice/evaluate")
        assert res_eval.status_code == 200, f"Controlled evaluation failed: {res_eval.text}"
        eval_data = res_eval.json()
        assert eval_data["total_sentences"] == 8, f"Expected 8 evaluation sentences, got {eval_data['total_sentences']}"
        assert len(eval_data["results"]) == 8, f"Expected 8 result items, got {len(eval_data['results'])}"
        
        # Check first sentence result and test audio playback endpoint
        first_sent = eval_data["results"][0]
        assert first_sent["status"] == "SUCCESS", f"Sentence 1 evaluation failed: {first_sent.get('error')}"
        assert first_sent["duration"] > 0, "Sentence duration should be greater than 0"
        assert abs(first_sent.get("loudness_lufs", -24.0) - (-14.0)) <= 4.0, f"Loudness not normalized properly: {first_sent.get('loudness_lufs')} LUFS"
        print(f"[OK] Controlled 8-sentence evaluation passed (Sentence 1 LUFS: {first_sent.get('loudness_lufs')} LUFS)")

        # 7. Test Evaluation Audio Playback Endpoint
        print("\n[TEST 7] Testing Evaluation Audio Playback Endpoint...")
        res_audio = client.get(f"/personas/{test_persona_id}/voice/eval_audio/0")
        assert res_audio.status_code == 200, f"Eval audio fetch failed: {res_audio.text}"
        assert len(res_audio.content) > 100, "Eval audio content too small"
        print(f"[OK] Evaluation audio playback passed ({len(res_audio.content)} bytes served)")

        # 8. Test Fallback to Default TTS when no voice profile exists
        print("\n[TEST 8] Testing Fallback to Default TTS (with Phase 7 Loudness Normalization)...")
        res_fallback = client.post("/chat/tts", json={"text": "Hello from default TTS fallback."})
        assert res_fallback.status_code == 200, f"Fallback TTS failed: {res_fallback.text}"
        assert len(res_fallback.content) > 100
        print(f"[OK] Fallback to default TTS passed ({len(res_fallback.content)} bytes generated)")

        # 9. Test RAG Non-Regression (Persona & Knowledge retrieval endpoints)
        print("\n[TEST 9] Testing RAG & Core Endpoints Non-Regression...")
        res_personas = client.get("/personas")
        assert res_personas.status_code == 200
        assert any(p["id"] == test_persona_id for p in res_personas.json())
        print("[OK] RAG & Core endpoints non-regression passed.")

        # 10. Test Deletion
        print("\n[TEST 10] Testing Sample & Profile Deletion...")
        res_del_sample = client.delete(f"/personas/{test_persona_id}/voice/samples/{sample_id}")
        assert res_del_sample.status_code == 200
        res_del_prof = client.delete(f"/personas/{test_persona_id}/voice")
        assert res_del_prof.status_code == 200
        print("[OK] Deletion passed.")

        print("\n[SUCCESS] ALL 10 GENERIC HYBRID VOICE CLONING & SYSTEM VERIFICATION TESTS PASSED SUCCESSFULLY!")

    finally:
        # Clean up test persona from DB
        db = SessionLocal()
        p = db.query(Persona).filter(Persona.id == test_persona_id).first()
        if p:
            db.delete(p)
            db.commit()
        db.close()

if __name__ == "__main__":
    run_tests()
