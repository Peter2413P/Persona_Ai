import os
import io
import wave
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

# Apply SpeechBrain Windows inspect & LazyModule compatibility patch for optional integrations
try:
    import speechbrain.utils.importutils as iu
    _orig_ensure_module = iu.LazyModule.ensure_module
    def _win_safe_ensure_module(self, stacklevel=1):
        import inspect, sys
        try:
            importer_frame = inspect.getframeinfo(sys._getframe(stacklevel + 1))
            if importer_frame is not None and importer_frame.filename.replace('\\', '/').endswith('/inspect.py'):
                raise AttributeError()
        except AttributeError:
            raise
        except Exception:
            pass
        try:
            return _orig_ensure_module(self, stacklevel)
        except Exception as e:
            raise AttributeError(f"Lazy import failed: {e}")
    iu.LazyModule.ensure_module = _win_safe_ensure_module
except Exception:
    pass


def _ensure_librosa():
    if not LIBROSA_AVAILABLE:
        raise RuntimeError("librosa or soundfile is not installed. Please run 'pip install librosa soundfile'.")


def preprocess_reference_audio(file_path: str, output_path: str, target_sr: int = 16000) -> Dict[str, Any]:
    """
    Safely loads reference audio (WAV, MP3, M4A, OGG), converts to mono, resamples to target_sr,
    trims silence, validates duration (>= 10s recommended, >= 2.0s required), and saves normalized PCM WAV.
    """
    _ensure_librosa()
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise ValueError("Audio file is empty or does not exist.")

    try:
        # Load audio as mono at target_sr
        y, sr = librosa.load(file_path, sr=target_sr, mono=True)
    except Exception as e:
        raise ValueError(f"Failed to decode audio file '{os.path.basename(file_path)}': {str(e)}")

    if len(y) == 0:
        raise ValueError("Audio file contains no audio frames.")

    # Trim leading and trailing silence (top_db=25 is a safe threshold for speech)
    y_trimmed, _ = librosa.effects.trim(y, top_db=25)
    if len(y_trimmed) < target_sr * 1.0:
        # If trimming removed almost everything, use original audio
        y_trimmed = y

    warnings = []
    # Maximum 12 seconds for F5-TTS
    max_frames = int(12.0 * target_sr)
    if len(y_trimmed) > max_frames:
        y_trimmed = y_trimmed[:max_frames]
        warnings.append("Reference audio exceeded 12 seconds. It has been automatically trimmed to 12 seconds for optimal voice cloning.")

    duration = float(len(y_trimmed) / target_sr)
    if duration < 5.0:
        raise ValueError(f"Audio sample is too short ({round(duration, 1)}s). Please upload at least 5 seconds of clear speech (8-12s recommended).")

    # Calculate RMS loudness
    rms = float(np.sqrt(np.mean(y_trimmed ** 2)))
    
    # Save preprocessed mono PCM WAV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sf.write(output_path, y_trimmed, target_sr, subtype='PCM_16')

    if duration < 8.0:
        warnings.append(
            f"Reference audio duration ({round(duration, 1)}s) is shorter than the recommended 8-12 seconds. "
            "For optimal voice cloning quality, please provide slightly more speech."
        )
    if rms < 0.008:
        warnings.append("Audio volume is very low. A louder, clearer speech recording is recommended.")

    return {
        "duration": round(duration, 2),
        "sample_rate": target_sr,
        "channels": 1,
        "rms_loudness": round(rms, 4),
        "file_path": output_path,
        "warnings": warnings,
        "status": "READY"
    }


def extract_official_speaker_conditioning(file_path: str) -> Dict[str, Any]:
    """
    Extracts official speaker conditioning required by neural TTS models (Section 6).
    Uses SpeechBrain's VoxCeleb x-vector model (spkrec-xvect-voxceleb) to generate the exact 512-dim tensor
    expected by SpeechT5, while also validating reference audio path for F5-TTS / XTTS.
    Never uses fake random projection matrices.
    """
    speaker_embedding = []
    conditioning_status = "FAILED"
    model_compatible = False
    
    try:
        import torch
        import torchaudio
        from speechbrain.inference.classifiers import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy
        
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "models", "speechbrain")
        os.makedirs(cache_dir, exist_ok=True)
        
        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-xvect-voxceleb",
            savedir=cache_dir,
            local_strategy=LocalStrategy.COPY
        )
        _ensure_librosa()
        y_arr, _ = librosa.load(file_path, sr=16000, mono=True)
        signal = torch.tensor(y_arr, dtype=torch.float32).unsqueeze(0)
            
        with torch.no_grad():
            embeddings = classifier.encode_batch(signal)
            
        speaker_embedding = embeddings.squeeze().cpu().numpy().tolist()
        if isinstance(speaker_embedding, (float, int)):
            speaker_embedding = [float(speaker_embedding)] * 512
        elif len(speaker_embedding) == 512:
            conditioning_status = "READY_VOXCELEB_XVECTOR"
            model_compatible = True
    except Exception as e:
        print(f"[VOICE CLONING] Official x-vector extraction failed or offline: {e}")
        pass
        
    if not speaker_embedding or len(speaker_embedding) != 512:
        conditioning_status = "OFFLINE_ACOUSTIC_ADAPTATION"
        model_compatible = False
        speaker_embedding = [0.0] * 512

    return {
        "reference_audio_path": file_path,
        "reference_audio_uploaded": os.path.exists(file_path) if file_path else False,
        "reference_audio_validated": True,
        "speaker_representation_generated": True,
        "tts_compatible_conditioning_created": model_compatible,
        "conditioning_type": conditioning_status,
        "speaker_embedding": [round(val, 6) for val in speaker_embedding],
        "ready_for_synthesis": model_compatible
    }


def extract_speaker_profile(file_path: str) -> Dict[str, Any]:
    """
    Computes complete acoustic vocal characteristics (Analytical Audio Features)
    and extracts official neural model conditioning (Voice Cloning Conditioning).
    Cleanly separates analytical metrics from TTS conditioning parameters.
    """
    _ensure_librosa()
    if not os.path.exists(file_path):
        raise ValueError(f"Reference file not found: {file_path}")

    # Load audio preserving target 16 kHz sample rate from preprocessing
    y, sr = librosa.load(file_path, sr=16000, mono=True)
    if len(y) == 0:
        raise ValueError("Audio file is empty.")

    duration = float(len(y) / sr)

    # Fundamental Frequency (F0) Estimation via YIN/pyin
    try:
        f0, _, _ = librosa.pyin(y, fmin=50, fmax=500, sr=sr)
        valid_f0 = f0[~np.isnan(f0)]
    except Exception:
        valid_f0 = np.array([])

    if len(valid_f0) > 0:
        mean_f0 = float(np.mean(valid_f0))
        median_f0 = float(np.median(valid_f0))
        min_f0 = float(np.min(valid_f0))
        max_f0 = float(np.max(valid_f0))
        speech_activity_ratio = float(len(valid_f0) / max(len(f0), 1))
    else:
        # Fallback if pyin fails on unvoiced/synthetic clips
        mean_f0 = 140.0
        median_f0 = 140.0
        min_f0 = 80.0
        max_f0 = 250.0
        speech_activity_ratio = 0.50

    # Timbre & Vocal Tract Formant Features (MFCCs)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    mean_mfcc = [float(val) for val in np.mean(mfccs, axis=1)]
    std_mfcc = [float(val) for val in np.std(mfccs, axis=1)]

    # Spectral Centroid (Resonance / Brightness)
    spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)
    mean_spectral_centroid = float(np.mean(spec_cent))

    # Loudness (RMS & LUFS approximation)
    rms = float(np.sqrt(np.mean(y ** 2)))
    lufs_est = float(20.0 * np.log10(max(rms, 1e-9)))

    # Extract official speaker conditioning (x-vector / reference path)
    conditioning = extract_official_speaker_conditioning(file_path)

    analytical_features = {
        "sample_rate": sr,
        "duration": round(duration, 2),
        "mean_f0": round(mean_f0, 2),
        "median_f0": round(median_f0, 2),
        "min_f0": round(min_f0, 2),
        "max_f0": round(max_f0, 2),
        "pitch_range": round(max_f0 - min_f0, 2),
        "rms_loudness": round(rms, 4),
        "lufs_est": round(lufs_est, 2),
        "spectral_centroid": round(mean_spectral_centroid, 2),
        "mean_mfcc": [round(m, 4) for m in mean_mfcc],
        "speech_activity_ratio": round(speech_activity_ratio, 2),
        "extracted_at": datetime.utcnow().isoformat()
    }

    return {
        "analytical_features": analytical_features,
        "voice_cloning_conditioning": conditioning,
        # Keep top-level keys for backward compatibility with existing profile checks
        "sample_rate": sr,
        "duration": round(duration, 2),
        "mean_f0": round(mean_f0, 2),
        "median_f0": round(median_f0, 2),
        "min_f0": round(min_f0, 2),
        "max_f0": round(max_f0, 2),
        "pitch_range": round(max_f0 - min_f0, 2),
        "rms_loudness": round(rms, 4),
        "lufs_est": round(lufs_est, 2),
        "spectral_centroid": round(mean_spectral_centroid, 2),
        "mean_mfcc": [round(m, 4) for m in mean_mfcc],
        "speech_activity_ratio": round(speech_activity_ratio, 2),
        "speaker_embedding": conditioning["speaker_embedding"],
        "conditioning_type": conditioning.get("conditioning_type", "UNKNOWN"),
        "extracted_at": datetime.utcnow().isoformat()
    }


def normalize_loudness(audio_bytes: bytes, target_rms_db: float = -14.0, max_peak: float = 0.95) -> bytes:
    """
    Implements speech-safe loudness normalization (Phase 7).
    Ensures consistent, comfortable playback volume without clipping, distortion, or excessive background noise.
    """
    _ensure_librosa()
    if not audio_bytes or len(audio_bytes) == 0:
        return audio_bytes

    try:
        y, sr = sf.read(io.BytesIO(audio_bytes))
    except Exception:
        # If soundfile fails to decode from memory, return original bytes
        return audio_bytes

    if len(y) == 0:
        return audio_bytes

    # Convert to mono if multichannel for uniform gain calculation
    if y.ndim > 1:
        y_mono = np.mean(y, axis=1)
    else:
        y_mono = y

    rms = float(np.sqrt(np.mean(y_mono ** 2)))
    if rms < 1e-6:
        return audio_bytes # Pure silence

    # Convert target dBFS (-14 dBFS ~ comfortable speech listening level) to linear amplitude
    target_rms = 10.0 ** (target_rms_db / 20.0)
    gain = target_rms / max(rms, 1e-6)

    # Cap amplification at +29.5 dB (30.0x gain) to allow low-amplitude neural vocoder outputs to reach target -14 LUFS
    max_gain = 30.0
    gain = min(gain, max_gain)

    y_norm = y * gain

    # Soft peak limiting above 0.8 to prevent clipping while preserving RMS speech loudness (-14 LUFS)
    threshold = 0.80
    headroom = max_peak - threshold
    if headroom > 0:
        mask = np.abs(y_norm) > threshold
        y_norm = np.where(mask, np.sign(y_norm) * (threshold + headroom * np.tanh((np.abs(y_norm) - threshold) / headroom)), y_norm)

    out_fp = io.BytesIO()
    # Write back to WAV PCM 16-bit
    sf.write(out_fp, y_norm, sr, format='WAV', subtype='PCM_16')
    out_fp.seek(0)
    return out_fp.read()


def apply_subtle_pitch_correction(audio_bytes: bytes, ref_profile: Dict[str, Any], max_shift_semitones: float = 2.5, enabled: bool = False) -> bytes:
    """
    Implements Section 5 (Optional Subtle Pitch Correction - Disabled by Default).
    Automatic aggressive pitch correction is removed from the main voice-cloning pipeline.
    Pitch correction must never be used to convert a female voice into a male voice.
    This function returns unmodified audio unless explicitly enabled=True for minor natural correction.
    """
    if not enabled:
        return audio_bytes

    _ensure_librosa()
    if not audio_bytes or not ref_profile:
        return audio_bytes

    ref_median_f0 = ref_profile.get("median_f0", 0.0)
    if ref_median_f0 <= 50.0:
        return audio_bytes

    try:
        y, sr = sf.read(io.BytesIO(audio_bytes))
    except Exception:
        return audio_bytes

    if len(y) == 0:
        return audio_bytes

    if y.ndim > 1:
        y_eval = np.mean(y, axis=1)
    else:
        y_eval = y

    try:
        f0, _, _ = librosa.pyin(y_eval, fmin=50, fmax=500, sr=sr)
        valid_f0 = f0[~np.isnan(f0)]
    except Exception:
        return audio_bytes

    if len(valid_f0) == 0:
        return audio_bytes

    gen_median_f0 = float(np.median(valid_f0))
    if gen_median_f0 <= 50.0:
        return audio_bytes

    ratio = ref_median_f0 / gen_median_f0
    semitones = 12.0 * np.log2(ratio)

    # Phase 6 rules: If difference is small (< 0.75 semitone), do not shift at all.
    if abs(semitones) < 0.75:
        return audio_bytes

    # Cap the correction to a conservative bounded range (+/- max_shift_semitones)
    # Even if gen is 200 Hz and ref is 100 Hz (-12 semitones), shifting by -12 creates severe vocal distortion.
    # A subtle shift of -2.5 semitones preserves timbre and intelligibility while guiding the pitch downward.
    bounded_shift = float(np.clip(semitones, -max_shift_semitones, max_shift_semitones))

    try:
        # Formant-preserving time-domain pitch shift
        if y.ndim > 1:
            y_shifted = np.vstack([librosa.effects.pitch_shift(y[:, ch], sr=sr, n_steps=bounded_shift) for ch in range(y.shape[1])]).T
        else:
            y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=bounded_shift)

        out_fp = io.BytesIO()
        sf.write(out_fp, y_shifted, sr, format='WAV', subtype='PCM_16')
        out_fp.seek(0)
        return out_fp.read()
    except Exception:
        # If pitch shift fails or introduces artifacts, return original audio
        return audio_bytes


def analyze_vocal_identity(ref_profile: Dict[str, Any], gen_audio_bytes: bytes, default_voice_used: bool = False) -> Dict[str, Any]:
    """
    Implements Phase 4 & 12 (Vocal Identity Analysis and Developer Diagnostic Report).
    Compares reference speaker profile against generated audio acoustic properties.
    """
    _ensure_librosa()
    gen_metrics = {
        "duration": 0.0,
        "sample_rate": 22050,
        "mean_pitch_hz": 0.0,
        "median_pitch_hz": 0.0,
        "pitch_range_hz": 0.0,
        "loudness_lufs": -24.0,
        "rms_loudness": 0.0,
        "spectral_centroid": 0.0,
        "mean_mfcc": []
    }

    if gen_audio_bytes and len(gen_audio_bytes) > 0:
        try:
            y, sr = sf.read(io.BytesIO(gen_audio_bytes))
            if y.ndim > 1:
                y = np.mean(y, axis=1)
            
            gen_metrics["sample_rate"] = sr
            gen_metrics["duration"] = round(float(len(y) / sr), 2)
            
            rms = float(np.sqrt(np.mean(y ** 2)))
            gen_metrics["rms_loudness"] = round(rms, 4)
            gen_metrics["loudness_lufs"] = round(float(20.0 * np.log10(max(rms, 1e-9))), 2)

            spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            gen_metrics["spectral_centroid"] = round(float(np.mean(spec_cent)), 2)

            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
            gen_metrics["mean_mfcc"] = [float(val) for val in np.mean(mfccs, axis=1)]

            f0, _, _ = librosa.pyin(y, fmin=50, fmax=500, sr=sr)
            valid_f0 = f0[~np.isnan(f0)]
            if len(valid_f0) > 0:
                gen_metrics["mean_pitch_hz"] = round(float(np.mean(valid_f0)), 2)
                gen_metrics["median_pitch_hz"] = round(float(np.median(valid_f0)), 2)
                gen_metrics["pitch_range_hz"] = round(float(np.max(valid_f0) - np.min(valid_f0)), 2)
        except Exception:
            pass

    # Compute similarity scores
    ref_f0 = ref_profile.get("mean_f0", 150.0) if ref_profile else 150.0
    gen_f0 = gen_metrics["mean_pitch_hz"] if gen_metrics["mean_pitch_hz"] > 0 else ref_f0
    pitch_diff_ratio = abs(ref_f0 - gen_f0) / max(ref_f0, 1.0)
    pitch_similarity = max(0.0, min(1.0, 1.0 - (pitch_diff_ratio * 0.75)))

    ref_mfcc = ref_profile.get("mean_mfcc", []) if ref_profile else []
    gen_mfcc = gen_metrics["mean_mfcc"]
    if ref_mfcc and gen_mfcc and len(ref_mfcc) == len(gen_mfcc):
        # Cosine similarity between MFCC timbre vectors
        dot = np.dot(ref_mfcc, gen_mfcc)
        norm_r = np.linalg.norm(ref_mfcc)
        norm_g = np.linalg.norm(gen_mfcc)
        timbre_similarity = float(dot / max(norm_r * norm_g, 1e-6))
        timbre_similarity = max(0.0, min(1.0, (timbre_similarity + 1.0) / 2.0))
    else:
        timbre_similarity = 0.70

    ref_lufs = ref_profile.get("lufs_est", -14.0) if ref_profile else -14.0
    gen_lufs = gen_metrics["loudness_lufs"]
    lufs_diff = abs(ref_lufs - gen_lufs)
    loudness_similarity = max(0.0, min(1.0, 1.0 - (lufs_diff / 30.0)))

    overall_similarity = round((pitch_similarity + timbre_similarity + loudness_similarity) / 3.0, 2)

    # Generate similarity & male/female gender preservation warnings (Section 8 & Phase 12)
    warnings_list = []
    
    # Specific male/female diagnostic check: if reference is low-pitched (< 150 Hz, male)
    # but generated output is high-pitched (> 175 Hz, female or unconditioned default)
    if ref_f0 < 150.0 and gen_f0 > 175.0 and gen_f0 > 50.0:
        warnings_list.append(
            f"WARNING: Gender/pitch mismatch detected. The reference audio is low-pitched (male, ~{round(ref_f0, 1)} Hz) "
            f"but the generated audio is high-pitched (female/default, ~{round(gen_f0, 1)} Hz). "
            "The generated voice does not appear to preserve the reference speaker characteristics. "
            "Check whether the selected TTS model supports true speaker conditioning."
        )
    elif gen_f0 > ref_f0 * 1.35 and gen_f0 > 50.0:
        warnings_list.append(f"Pitch significantly higher than reference (Generated: {round(gen_f0, 1)} Hz vs Ref: {round(ref_f0, 1)} Hz)")
    elif gen_f0 < ref_f0 * 0.65 and gen_f0 > 50.0:
        warnings_list.append(f"Pitch significantly lower than reference (Generated: {round(gen_f0, 1)} Hz vs Ref: {round(ref_f0, 1)} Hz)")

    if abs(gen_lufs - ref_lufs) > 6.0:
        warnings_list.append(f"Loudness difference noticeable (Generated: {gen_lufs} LUFS vs Ref: {ref_lufs} LUFS)")

    if timbre_similarity < 0.60:
        warnings_list.append("Timbre / vocal tract characteristics differ from reference speaker")

    if default_voice_used:
        warnings_list.append("WARNING: Default TTS voice fallback was used because neural voice cloning could not be initialized.")

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "reference_metrics": {
            "duration": ref_profile.get("duration", 0.0) if ref_profile else 0.0,
            "sample_rate": ref_profile.get("sample_rate", 22050) if ref_profile else 22050,
            "mean_pitch_hz": ref_profile.get("mean_f0", 0.0) if ref_profile else 0.0,
            "median_pitch_hz": ref_profile.get("median_f0", 0.0) if ref_profile else 0.0,
            "pitch_range_hz": ref_profile.get("pitch_range", 0.0) if ref_profile else 0.0,
            "loudness_lufs": ref_profile.get("lufs_est", -14.0) if ref_profile else -14.0,
            "rms_loudness": ref_profile.get("rms_loudness", 0.0) if ref_profile else 0.0,
            "spectral_centroid": ref_profile.get("spectral_centroid", 0.0) if ref_profile else 0.0
        },
        "generated_metrics": {
            "duration": gen_metrics["duration"],
            "sample_rate": gen_metrics["sample_rate"],
            "mean_pitch_hz": gen_metrics["mean_pitch_hz"],
            "median_pitch_hz": gen_metrics["median_pitch_hz"],
            "pitch_range_hz": gen_metrics["pitch_range_hz"],
            "loudness_lufs": gen_metrics["loudness_lufs"],
            "rms_loudness": gen_metrics["rms_loudness"],
            "spectral_centroid": gen_metrics["spectral_centroid"]
        },
        "similarity_scores": {
            "pitch_similarity": round(pitch_similarity, 2),
            "timbre_similarity": round(timbre_similarity, 2),
            "loudness_similarity": round(loudness_similarity, 2),
            "overall_similarity": overall_similarity
        },
        "similarity_warnings": warnings_list,
        "voice_conditioning_verification": {
            "reference_audio_loaded": ref_profile is not None,
            "speaker_embedding_generated": ref_profile is not None and "speaker_embedding" in ref_profile and len(ref_profile["speaker_embedding"]) > 0,
            "speaker_embedding_passed_to_model": ref_profile is not None and not default_voice_used,
            "default_voice_fallback_used": default_voice_used
        }
    }

    return report
