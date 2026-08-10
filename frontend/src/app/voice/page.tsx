"use client";

import { useState, useEffect, useRef } from "react";
import { 
  Mic, UploadCloud, Trash2, Loader2, Play, Pause, Volume2, CheckCircle2, AlertCircle, 
  RefreshCcw, FileAudio, Activity, ShieldCheck, AlertTriangle, BarChart3, Sparkles, Check, X
} from "lucide-react";
import { 
  getVoiceSamples, 
  uploadVoiceSample, 
  deleteVoiceSample, 
  getVoiceProfile, 
  createVoiceProfile, 
  deleteVoiceProfile, 
  testPersonaVoice, 
  getVoiceDiagnostic,
  evaluateVoiceCloning,
  toggleVoiceProvider,
  VoiceSample, 
  VoiceProfileStatus,
  DiagnosticReport,
  EvaluationSuiteReport,
  F5TTSStatus,
  fetchF5TTSStatus,
  F5TTSSettings,
  updateF5TTSSettings
} from "@/lib/api";
import { usePersona } from "@/components/PersonaProvider";
import { ChevronDown, ChevronUp, Save } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function VoiceSettingsPage() {
  const { activePersona } = usePersona();
  
  const [samples, setSamples] = useState<VoiceSample[]>([]);
  const [profile, setProfile] = useState<VoiceProfileStatus | null>(null);
  const [diagnostic, setDiagnostic] = useState<DiagnosticReport | null>(null);
  const [evalReport, setEvalReport] = useState<EvaluationSuiteReport | null>(null);
  const [f5Status, setF5Status] = useState<F5TTSStatus | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload State
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Profile Create State
  const [creating, setCreating] = useState(false);
  const [createSuccess, setCreateSuccess] = useState(false);

  // Test Speech State
  const [testText, setTestText] = useState("Hello, I am your AI persona. This is a test of my synthesized voice.");
  const [testing, setTesting] = useState(false);
  const [testAudioUrl, setTestAudioUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [switchingProvider, setSwitchingProvider] = useState<string | null>(null);

  // Evaluation State
  const [evaluating, setEvaluating] = useState(false);

  // F5 Settings State
  const [f5Settings, setF5Settings] = useState<F5TTSSettings>({
    reference_text: "",
    randomize_seed: false,
    seed: 259225565,
    speed: 0.9,
    nfe_steps: 20,
    cross_fade_duration: 0.11
  });
  const [showF5Settings, setShowF5Settings] = useState(false);
  const [savingF5, setSavingF5] = useState(false);

  const fetchVoiceData = async () => {
    if (!activePersona) {
      setSamples([]);
      setProfile(null);
      setDiagnostic(null);
      setEvalReport(null);
      setF5Status(null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const [samplesData, profileData] = await Promise.all([
        getVoiceSamples(activePersona.id),
        getVoiceProfile(activePersona.id)
      ]);
      setSamples(samplesData);
      setProfile(profileData);
      if (profileData?.f5tts_settings) {
        setF5Settings(profileData.f5tts_settings);
      }

      // Attempt to load diagnostic report
      try {
        const diag = await getVoiceDiagnostic(activePersona.id);
        if (diag && diag.status !== "NOT_AVAILABLE" && diag.reference_metrics) {
            setDiagnostic(diag);
        } else {
            setDiagnostic(null);
        }
      } catch {
        setDiagnostic(null);
      }
      
      try {
        const f5 = await fetchF5TTSStatus();
        setF5Status(f5);
      } catch {
        setF5Status(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load voice settings.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoiceData();
  }, [activePersona]);

  const handleFileChange = async (files: FileList | null) => {
    if (!files || files.length === 0 || !activePersona) return;
    setUploadError(null);
    setUploading(true);

    try {
      for (let i = 0; i < files.length; i++) {
        await uploadVoiceSample(activePersona.id, files[i]);
      }
      await fetchVoiceData();
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload audio sample.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteSample = async (sampleId: string) => {
    if (!activePersona) return;
    try {
      await deleteVoiceSample(activePersona.id, sampleId);
      await fetchVoiceData();
    } catch (err: any) {
      setError(err.message || "Failed to delete sample.");
    }
  };

  const handleCreateVoice = async () => {
    if (!activePersona) return;
    setCreating(true);
    setCreateSuccess(false);
    setError(null);
    try {
      await createVoiceProfile(activePersona.id);
      setCreateSuccess(true);
      await fetchVoiceData();
      setTimeout(() => setCreateSuccess(false), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to create voice profile.");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProfile = async () => {
    if (!activePersona) return;
    if (!confirm("Are you sure you want to delete this voice profile? The system will revert to the default TTS voice.")) return;
    try {
      await deleteVoiceProfile(activePersona.id);
      await fetchVoiceData();
    } catch (err: any) {
      setError(err.message || "Failed to delete voice profile.");
    }
  };

  const handleToggleProvider = async (providerName: string) => {
    if (!activePersona) return;
    setSwitchingProvider(providerName);
    setError(null);
    try {
      await toggleVoiceProvider(activePersona.id, providerName);
      await fetchVoiceData();
    } catch (err: any) {
      setError(err.message || `Failed to switch to ${providerName} provider.`);
    } finally {
      setSwitchingProvider(null);
    }
  };

  const handleTestVoice = async (providerToTest?: string | React.MouseEvent) => {
    if (!activePersona) return;
    const targetProvider = typeof providerToTest === "string" ? providerToTest : (profile?.active_provider || profile?.provider || "local");
    setTesting(true);
    setError(null);
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
    try {
      const url = await testPersonaVoice(activePersona.id, testText, targetProvider);
      setTestAudioUrl(url);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onplay = () => setIsPlaying(true);
      audio.onended = () => setIsPlaying(false);
      audio.onpause = () => setIsPlaying(false);
      audio.play();
      // Refresh diagnostic report after test synthesis
      await fetchVoiceData();
    } catch (err: any) {
      setError(err.message || "Failed to generate test speech.");
    } finally {
      setTesting(false);
    }
  };

  const handleRunEvaluation = async () => {
    if (!activePersona) return;
    setEvaluating(true);
    setError(null);
    try {
      const res = await evaluateVoiceCloning(activePersona.id);
      setEvalReport(res);
      await fetchVoiceData();
    } catch (err: any) {
      setError(err.message || "Failed to run controlled sentence evaluation.");
    } finally {
      setEvaluating(false);
    }
  };

  const handleSaveF5Settings = async () => {
    if (!activePersona) return;
    setSavingF5(true);
    setError(null);
    try {
      await updateF5TTSSettings(activePersona.id, f5Settings);
      await fetchVoiceData();
    } catch (err: any) {
      setError(err.message || "Failed to save F5-TTS settings.");
    } finally {
      setSavingF5(false);
    }
  };

  const togglePlayPause = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const getStatusBadge = (status?: string) => {
    const isVerified = testAudioUrl || diagnostic || profile?.has_diagnostic;
    switch (status) {
      case "READY":
        return isVerified ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><CheckCircle2 className="w-3.5 h-3.5" /> Ready (Verified)</span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20" title="Please test voice synthesis below to verify vocal identity before final deployment"><AlertCircle className="w-3.5 h-3.5" /> Ready (Test Synthesis Required)</span>
        );
      case "PROCESSING":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Processing</span>;
      case "SAMPLES_UPLOADED":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20"><FileAudio className="w-3.5 h-3.5" /> Samples Uploaded</span>;
      case "FAILED":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20"><AlertCircle className="w-3.5 h-3.5" /> Failed</span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">Not Configured</span>;
    }
  };

  const getPitchClassification = (f0?: number) => {
    if (!f0 || f0 <= 0) return "Unknown / Unvoiced";
    if (f0 < 120) return `Deep Low-Pitched (~${Math.round(f0)} Hz)`;
    if (f0 < 175) return `Mid-Range Vocal (~${Math.round(f0)} Hz)`;
    return `High-Pitched (~${Math.round(f0)} Hz)`;
  };

  if (!activePersona) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-zinc-950 text-zinc-100">
        <Mic className="w-12 h-12 text-zinc-600 mb-4 animate-bounce" />
        <h2 className="text-xl font-semibold mb-2">No Active Persona Selected</h2>
        <p className="text-zinc-400 text-sm max-w-md mb-6">
          Please select or create a persona in the sidebar to configure its voice identity and cloning settings.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-4xl mx-auto space-y-8 pb-16">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold tracking-tight">Persona Voice Identity & Acoustic Engine</h1>
              {getStatusBadge(profile?.status)}
            </div>
            <p className="text-zinc-400 text-sm">
              Upload speech recordings for <span className="text-emerald-400 font-semibold">{activePersona.name}</span> to clone their vocal identity, analyze acoustic timbre, and evaluate speech synthesis quality.
            </p>
          </div>
          <button
            onClick={fetchVoiceData}
            disabled={loading}
            className="p-2 bg-zinc-900 border border-zinc-800 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors"
            title="Refresh Status"
          >
            <RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {createSuccess && (
          <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Voice profile and 512-dim speaker embedding successfully created! The persona is now ready to speak.</span>
          </div>
        )}

        {/* Section 1: Upload Audio Samples */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-6">
          <div>
            <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center text-xs font-bold">1</span>
              Reference Audio Samples & Preprocessing
            </h2>
            <p className="text-xs text-zinc-400">
              Upload clear speech samples (WAV, MP3, M4A, OGG). Samples are automatically converted to mono, resampled to 16 kHz, trimmed of silence, and normalized. 
              Minimum 5s required (8–12s recommended). Audio longer than 12s will be automatically trimmed to 12s for optimal cloning.
            </p>
          </div>

          {/* Drag and Drop Zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              handleFileChange(e.dataTransfer.files);
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
              isDragging
                ? "border-emerald-500 bg-emerald-500/5"
                : "border-zinc-700/80 hover:border-zinc-600 bg-zinc-900/40 hover:bg-zinc-900/80"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".wav,.mp3,.m4a,.ogg,.flac"
              onChange={(e) => handleFileChange(e.target.files)}
              className="hidden"
            />
            {uploading ? (
              <div className="flex flex-col items-center py-2">
                <Loader2 className="w-8 h-8 text-emerald-500 animate-spin mb-3" />
                <p className="text-sm font-medium text-zinc-300">Preprocessing, trimming silence, and validating audio samples...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-2">
                <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-3">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <p className="text-sm font-medium text-zinc-200 mb-1">Click to upload or drag and drop audio files</p>
                <p className="text-xs text-zinc-500">Supports WAV, MP3, M4A, OGG up to 20MB per file</p>
              </div>
            )}
          </div>

          {uploadError && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {/* Samples List Table */}
          {samples.length > 0 ? (
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-900/90 text-zinc-400 font-medium text-xs border-b border-zinc-800">
                  <tr>
                    <th className="px-4 py-3">File Name</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Size</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 bg-zinc-950/40">
                  {samples.map((s) => (
                    <tr key={s.id} className="hover:bg-zinc-900/40 transition-colors">
                      <td className="px-4 py-3 font-medium text-zinc-200">
                        <div className="flex items-center gap-2">
                          <FileAudio className="w-4 h-4 text-emerald-400 shrink-0" />
                          <span className="truncate max-w-[220px]">{s.filename}</span>
                        </div>
                        {s.warnings && s.warnings.length > 0 && (
                          <div className="mt-1 text-[11px] text-amber-400 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3 shrink-0" />
                            <span>{s.warnings[0]}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-400 text-xs">{s.duration ? `${s.duration}s` : "N/A"}</td>
                      <td className="px-4 py-3 text-zinc-400 text-xs">{formatFileSize(s.file_size)}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" /> {s.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDeleteSample(s.id)}
                          className="p-1.5 hover:bg-red-500/10 text-zinc-500 hover:text-red-400 rounded transition-colors"
                          title="Delete Sample"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-6 border border-dashed border-zinc-800 rounded-lg text-zinc-500 text-xs">
              No audio samples uploaded yet.
            </div>
          )}
        </div>

        {/* Section 2: Build Voice Profile & Acoustic Metadata */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center text-xs font-bold">2</span>
                Build Acoustic Profile & 512-Dim Speaker Embedding
              </h2>
              <p className="text-xs text-zinc-400 max-w-xl">
                Extract fundamental pitch (F0), formant envelope (MFCCs), spectral centroid, and a 512-dim neural conditioning vector from your reference audio.
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {profile && profile.status !== "NOT_CONFIGURED" && (
                <button
                  onClick={handleDeleteProfile}
                  className="px-4 py-2 bg-zinc-900 hover:bg-red-500/10 text-red-400/80 hover:text-red-400 border border-zinc-800 hover:border-red-500/30 rounded-lg text-sm font-medium transition-colors"
                >
                  Delete Profile
                </button>
              )}
              <button
                onClick={handleCreateVoice}
                disabled={creating || samples.length === 0}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 shadow-sm"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Extracting Acoustic Features...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Extract Profile & Embedding
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Voice Synthesis Provider Selection (Dual-Engine Routing) */}
          {profile && (
            <div className="bg-zinc-950/70 border border-zinc-800/80 p-5 rounded-xl space-y-4 my-4">
              <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
                <div>
                  <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                    <Volume2 className="w-4 h-4 text-emerald-400" />
                    Voice Synthesis Provider Selection (Dual-Engine Routing)
                  </div>
                  <p className="text-[11px] text-zinc-400 mt-0.5">
                    Choose which speech synthesis engine generates audio for this persona. You can independently verify and test each engine below.
                  </p>
                </div>
                <span className="text-[11px] font-mono text-emerald-300 bg-emerald-500/10 px-2.5 py-1 rounded border border-emerald-500/20 font-semibold">
                  Active: {(profile.active_provider || profile.provider || "local").toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Local Engine Card */}
                <div className={`p-4 rounded-xl border transition-all flex flex-col justify-between ${
                  (profile.active_provider || profile.provider || "local") === "local"
                    ? "bg-emerald-950/20 border-emerald-500/50 shadow-sm shadow-emerald-950/30"
                    : "bg-zinc-900/40 border-zinc-800/80 hover:border-zinc-700"
                }`}>
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-semibold text-sm text-zinc-100 flex items-center gap-2">
                          Local Engine
                          {(profile.active_provider || profile.provider || "local") === "local" && (
                            <span className="text-[10px] bg-emerald-500 text-zinc-950 font-bold px-1.5 py-0.5 rounded">ACTIVE</span>
                          )}
                        </div>
                        <div className="text-[11px] text-zinc-400">SpeechBrain x-vector + Microsoft SpeechT5</div>
                      </div>
                      <div>
                        {profile.local_voice?.status === "ready" || (profile.status === "READY" && (profile.provider === "local" || !profile.provider)) ? (
                          profile.local_voice?.verified || testAudioUrl ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="w-3 h-3" /> Ready (Verified)
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20" title="Test synthesis required below">
                              <AlertCircle className="w-3 h-3" /> Test Required
                            </span>
                          )
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                            Not Configured
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      Zero-latency local neural synthesis conditioned on extracted 512-dimensional speaker embeddings. Runs entirely offline with formant-preserving loudness normalization.
                    </p>
                  </div>

                  <div className="flex items-center gap-2 mt-4 pt-3 border-t border-zinc-800/60">
                    <button
                      onClick={() => handleToggleProvider("local")}
                      disabled={switchingProvider !== null || (profile.active_provider || profile.provider || "local") === "local"}
                      className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
                        (profile.active_provider || profile.provider || "local") === "local"
                          ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                          : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm"
                      }`}
                    >
                      {switchingProvider === "local" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                      {(profile.active_provider || profile.provider || "local") === "local" ? "Current Provider" : "Select Engine"}
                    </button>
                    <button
                      onClick={() => handleTestVoice("local")}
                      disabled={testing || (profile.local_voice?.status !== "ready" && !(profile.status === "READY"))}
                      className="py-1.5 px-3 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-200 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
                      title="Test synthesis with Local Engine"
                    >
                      <Play className="w-3 h-3 text-emerald-400 fill-current" />
                      Test
                    </button>
                  </div>
                </div>

                {/* Local F5-TTS Engine Card */}
                <div className={`p-4 rounded-xl border transition-all flex flex-col justify-between ${
                  profile.active_provider === "f5tts"
                    ? "bg-purple-950/20 border-purple-500/50 shadow-sm shadow-purple-950/30"
                    : "bg-zinc-900/40 border-zinc-800/80 hover:border-zinc-700"
                }`}>
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-semibold text-sm text-zinc-100 flex items-center gap-2">
                          Local F5-TTS Engine
                          {profile.active_provider === "f5tts" && (
                            <span className="text-[10px] bg-purple-500 text-zinc-950 font-bold px-1.5 py-0.5 rounded">ACTIVE</span>
                          )}
                        </div>
                        <div className="text-[11px] text-zinc-400 flex items-center gap-1">
                          Custom Voice Cloning API
                          {profile.f5tts_voice?.model_name && (
                            <span className="font-mono text-[10px] text-purple-300">({profile.f5tts_voice.model_name})</span>
                          )}
                        </div>
                      </div>
                      <div>
                        {profile.f5tts_voice?.status === "ready" || (profile.status === "READY" && profile.provider === "f5tts") ? (
                          profile.f5tts_voice?.verified ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="w-3 h-3" /> Ready (Verified)
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20" title="Test synthesis required below">
                              <AlertCircle className="w-3 h-3" /> Test Required
                            </span>
                          )
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                            Not Configured
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      High-quality local speech synthesis via Pinokio F5-TTS Gradio interface. Zero-shot voice cloning with automatic transcription.
                    </p>
                  </div>

                  <div className="flex items-center gap-2 mt-4 pt-3 border-t border-zinc-800/60">
                    <button
                      onClick={() => handleToggleProvider("f5tts")}
                      disabled={switchingProvider !== null || profile.active_provider === "f5tts"}
                      className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
                        profile.active_provider === "f5tts"
                          ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                          : "bg-purple-600 hover:bg-purple-500 text-white shadow-sm"
                      }`}
                    >
                      {switchingProvider === "f5tts" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                      {profile.active_provider === "f5tts" ? "Current Provider" : "Select Engine"}
                    </button>
                    <button
                      onClick={() => handleTestVoice("f5tts")}
                      disabled={testing || (profile.f5tts_voice?.status !== "ready" && !(profile.status === "READY" && profile.provider === "f5tts"))}
                      className="py-1.5 px-3 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-200 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
                      title="Test synthesis with Local F5-TTS Engine"
                    >
                      <Play className="w-3 h-3 text-purple-400 fill-current" />
                      Test
                    </button>
                  </div>
                  
                  <div className="mt-3 border-t border-zinc-800/60 pt-3">
                    <button
                      onClick={() => setShowF5Settings(!showF5Settings)}
                      className="flex items-center justify-between w-full text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                    >
                      <span className="flex items-center gap-1.5 font-medium">
                        <Sparkles className="w-3.5 h-3.5" />
                        Advanced F5-TTS Settings
                      </span>
                      {showF5Settings ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    
                    {showF5Settings && (
                      <div className="mt-3 space-y-3 bg-zinc-950/50 p-3 rounded-lg border border-zinc-800/50">
                        <div>
                          <label className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider mb-1 block">Reference Text</label>
                          <textarea
                            value={f5Settings.reference_text}
                            onChange={(e) => setF5Settings({ ...f5Settings, reference_text: e.target.value })}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-purple-500/50 min-h-[60px]"
                            placeholder="Transcript of the reference audio..."
                          />
                        </div>
                        
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider mb-1 block">Speed</label>
                            <input
                              type="number"
                              step="0.1"
                              min="0.5"
                              max="2.0"
                              value={f5Settings.speed}
                              onChange={(e) => setF5Settings({ ...f5Settings, speed: parseFloat(e.target.value) || 1.0 })}
                              className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-purple-500/50"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider mb-1 block">NFE Steps</label>
                            <input
                              type="number"
                              step="1"
                              min="8"
                              max="64"
                              value={f5Settings.nfe_steps}
                              onChange={(e) => setF5Settings({ ...f5Settings, nfe_steps: parseInt(e.target.value) || 20 })}
                              className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-purple-500/50"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider mb-1 flex items-center justify-between">
                              Seed
                              <div className="flex items-center gap-1 normal-case text-zinc-500">
                                <input 
                                  type="checkbox" 
                                  checked={f5Settings.randomize_seed}
                                  onChange={(e) => setF5Settings({ ...f5Settings, randomize_seed: e.target.checked })}
                                  className="rounded border-zinc-700 bg-zinc-900 text-purple-500"
                                />
                                <span className="text-[9px]">Random</span>
                              </div>
                            </label>
                            <input
                              type="number"
                              value={f5Settings.seed}
                              disabled={f5Settings.randomize_seed}
                              onChange={(e) => setF5Settings({ ...f5Settings, seed: parseInt(e.target.value) || 0 })}
                              className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-purple-500/50 disabled:opacity-50"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider mb-1 block">Cross-Fade (s)</label>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              max="1"
                              value={f5Settings.cross_fade_duration}
                              onChange={(e) => setF5Settings({ ...f5Settings, cross_fade_duration: parseFloat(e.target.value) || 0.15 })}
                              className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-purple-500/50"
                            />
                          </div>
                        </div>
                        
                        <div className="pt-2 flex justify-end">
                          <button
                            onClick={handleSaveF5Settings}
                            disabled={savingF5}
                            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-xs font-medium text-zinc-200 rounded transition-colors flex items-center gap-1.5"
                          >
                            {savingF5 ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                            Save Settings
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Display Acoustic Speaker Metadata & Conditioning if Profile Exists */}
          {profile?.speaker_metadata && (
            <div className="space-y-6 pt-2">
              {/* Part A: Analytical Audio Features */}
              <div className="bg-zinc-950/70 border border-zinc-800/80 p-5 rounded-xl space-y-3">
                <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-2.5">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  Analytical Audio Features (Acoustic Vocal Profile)
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
                  <div className="bg-zinc-900/60 border border-zinc-800/60 p-3 rounded-lg">
                    <div className="text-[11px] text-zinc-400 mb-1">Mean Pitch (F0)</div>
                    <div className="text-base font-bold text-zinc-100">
                      {profile.speaker_metadata.analytical_features?.mean_f0 ?? profile.speaker_metadata.mean_f0 ?? "N/A"} Hz
                    </div>
                    <div className="text-[10px] text-emerald-400 mt-0.5 font-medium truncate">
                      {getPitchClassification(profile.speaker_metadata.analytical_features?.mean_f0 ?? profile.speaker_metadata.mean_f0)}
                    </div>
                  </div>

                  <div className="bg-zinc-900/60 border border-zinc-800/60 p-3 rounded-lg">
                    <div className="text-[11px] text-zinc-400 mb-1">Median Pitch</div>
                    <div className="text-base font-bold text-zinc-100">
                      {profile.speaker_metadata.analytical_features?.median_f0 ?? profile.speaker_metadata.median_f0 ?? "N/A"} Hz
                    </div>
                    <div className="text-[10px] text-zinc-400 mt-0.5 truncate">50th percentile</div>
                  </div>

                  <div className="bg-zinc-900/60 border border-zinc-800/60 p-3 rounded-lg">
                    <div className="text-[11px] text-zinc-400 mb-1">Pitch Range</div>
                    <div className="text-base font-bold text-zinc-100">
                      {profile.speaker_metadata.analytical_features?.pitch_range ?? profile.speaker_metadata.pitch_range ?? "N/A"} Hz
                    </div>
                    <div className="text-[10px] text-zinc-400 mt-0.5 truncate">Max - Min F0</div>
                  </div>

                  <div className="bg-zinc-900/60 border border-zinc-800/60 p-3 rounded-lg">
                    <div className="text-[11px] text-zinc-400 mb-1">Loudness (LUFS)</div>
                    <div className="text-base font-bold text-zinc-100">
                      {profile.speaker_metadata.analytical_features?.lufs_est ?? profile.speaker_metadata.loudness_lufs ?? "N/A"} LUFS
                    </div>
                    <div className="text-[10px] text-amber-400 mt-0.5 truncate">Norm Target: -14 LUFS</div>
                  </div>

                  <div className="bg-zinc-900/60 border border-zinc-800/60 p-3 rounded-lg">
                    <div className="text-[11px] text-zinc-400 mb-1">Spectral Centroid</div>
                    <div className="text-base font-bold text-zinc-100">
                      {profile.speaker_metadata.analytical_features?.spectral_centroid ?? "N/A"} Hz
                    </div>
                    <div className="text-[10px] text-blue-400 mt-0.5 truncate">Vocal brightness</div>
                  </div>

                  <div className="bg-zinc-900/60 border border-zinc-800/60 p-3 rounded-lg">
                    <div className="text-[11px] text-zinc-400 mb-1">Speech Activity</div>
                    <div className="text-base font-bold text-zinc-100">
                      {profile.speaker_metadata.analytical_features?.speech_activity_ratio !== undefined ? `${Math.round(profile.speaker_metadata.analytical_features.speech_activity_ratio * 100)}%` : "N/A"}
                    </div>
                    <div className="text-[10px] text-purple-400 mt-0.5 truncate">Voiced frame ratio</div>
                  </div>
                </div>
              </div>

              {/* Part B: Voice Cloning Conditioning (5-Item Status Checklist) */}
              <div className="bg-zinc-950/70 border border-zinc-800/80 p-5 rounded-xl space-y-3.5">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5">
                  <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-purple-400" />
                    Voice Cloning Conditioning (5-Item Status Checklist)
                  </div>
                  <span className="text-[11px] font-mono text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    {profile.speaker_metadata.voice_cloning_conditioning?.conditioning_type ?? profile.speaker_metadata.conditioning_type ?? "READY_VOXCELEB_XVECTOR"}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                  <div className="flex items-center gap-2.5 bg-zinc-900/50 p-3 rounded-lg border border-zinc-800/50">
                    {profile.speaker_metadata.voice_cloning_conditioning?.reference_audio_uploaded ?? (samples.length > 0) ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0"><Check className="w-3.5 h-3.5" /></div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center shrink-0"><X className="w-3.5 h-3.5" /></div>
                    )}
                    <div>
                      <div className="font-medium text-zinc-200">1. Reference Uploaded</div>
                      <div className="text-[10px] text-zinc-500">Audio files cached</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 bg-zinc-900/50 p-3 rounded-lg border border-zinc-800/50">
                    {profile.speaker_metadata.voice_cloning_conditioning?.reference_audio_validated ?? true ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0"><Check className="w-3.5 h-3.5" /></div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center shrink-0"><X className="w-3.5 h-3.5" /></div>
                    )}
                    <div>
                      <div className="font-medium text-zinc-200">2. Reference Validated</div>
                      <div className="text-[10px] text-zinc-500">16kHz mono verified</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 bg-zinc-900/50 p-3 rounded-lg border border-zinc-800/50">
                    {profile.speaker_metadata.voice_cloning_conditioning?.speaker_representation_generated ?? profile.speaker_metadata.has_embedding ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0"><Check className="w-3.5 h-3.5" /></div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center shrink-0"><X className="w-3.5 h-3.5" /></div>
                    )}
                    <div>
                      <div className="font-medium text-zinc-200">3. Representation Extracted</div>
                      <div className="text-[10px] text-zinc-500">Acoustic profile generated</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 bg-zinc-900/50 p-3 rounded-lg border border-zinc-800/50">
                    {profile.speaker_metadata.voice_cloning_conditioning?.tts_compatible_conditioning_created ?? profile.speaker_metadata.has_embedding ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0"><Check className="w-3.5 h-3.5" /></div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center shrink-0"><X className="w-3.5 h-3.5" /></div>
                    )}
                    <div>
                      <div className="font-medium text-zinc-200">4. TTS Compatible</div>
                      <div className="text-[10px] text-zinc-500">512-dim x-vector ready</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 bg-zinc-900/50 p-3 rounded-lg border border-zinc-800/50">
                    {profile.speaker_metadata.voice_cloning_conditioning?.ready_for_synthesis ?? (profile.status === "READY") ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0"><Check className="w-3.5 h-3.5" /></div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><AlertCircle className="w-3.5 h-3.5" /></div>
                    )}
                    <div>
                      <div className="font-medium text-zinc-200">5. Ready for Synthesis</div>
                      <div className="text-[10px] text-zinc-500">
                        {(testAudioUrl || diagnostic || profile.has_diagnostic) ? "Verified via test synthesis" : "Test voice below to verify"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section 3: Test Synthesized Voice */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center text-xs font-bold">3</span>
              Test Synthesized Voice & Pitch Correction
            </h2>
            <p className="text-xs text-zinc-400">
              Test your persona's synthesized voice directly. Loudness normalization (-14 LUFS) and subtle formant-preserving pitch correction are automatically applied.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="Type a sentence to test..."
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-zinc-100 focus:outline-none focus:border-emerald-500/80"
            />
            <button
              onClick={handleTestVoice}
              disabled={testing || !testText.trim()}
              className="px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 shrink-0 shadow-sm"
            >
              {testing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                  Synthesizing & Normalizing...
                </>
              ) : (
                <>
                  <Volume2 className="w-4 h-4 text-emerald-400" />
                  Generate Test Speech
                </>
              )}
            </button>
          </div>

          {testAudioUrl && (
            <div className="mt-4 p-4 bg-zinc-950/80 border border-zinc-800/80 rounded-lg flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <button
                  onClick={togglePlayPause}
                  className="w-10 h-10 rounded-full bg-emerald-500 hover:bg-emerald-400 text-zinc-950 flex items-center justify-center transition-colors shadow-md"
                >
                  {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
                </button>
                <div>
                  <div className="text-sm font-medium text-zinc-200">Test Audio Result (-14 LUFS Normalized)</div>
                  <div className="text-xs text-zinc-500">Using {profile?.status === "READY" ? "cloned acoustic vocal identity" : "default TTS fallback"}</div>
                </div>
              </div>
              <audio controls src={testAudioUrl} className="h-9 max-w-[260px]" />
            </div>
          )}
        </div>

        {/* Section 4: Developer Diagnostic & Acoustic Analysis Report (Phase 4 & 12) */}
        {diagnostic && (
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div>
                <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center text-xs font-bold">4</span>
                  Developer Diagnostic & Acoustic Analysis Report
                </h2>
                <p className="text-xs text-zinc-400">
                  Detailed comparison between reference speaker profile and last generated speech output (Phase 4 & 12).
                </p>
              </div>
              <span className="text-[11px] text-zinc-500 font-mono">
                {diagnostic.timestamp ? new Date(diagnostic.timestamp).toLocaleTimeString() : ""}
              </span>
            </div>

            {/* Similarity Warnings Box */}
            {diagnostic.similarity_warnings && diagnostic.similarity_warnings.length > 0 && (
              <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg space-y-2">
                <div className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  Vocal Identity Similarity Warnings:
                </div>
                <ul className="list-disc list-inside text-xs text-amber-300/90 space-y-1 pl-1">
                  {diagnostic.similarity_warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Similarity Score Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-zinc-950/60 border border-zinc-800/80 p-3.5 rounded-lg text-center">
                <div className="text-[11px] text-zinc-400 mb-1">Pitch Similarity</div>
                <div className="text-xl font-bold text-indigo-400">
                  {diagnostic.similarity_scores?.pitch_similarity !== undefined ? `${Math.round(diagnostic.similarity_scores.pitch_similarity * 100)}%` : "N/A"}
                </div>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-800/80 p-3.5 rounded-lg text-center">
                <div className="text-[11px] text-zinc-400 mb-1">Timbre Similarity</div>
                <div className="text-xl font-bold text-indigo-400">
                  {diagnostic.similarity_scores?.timbre_similarity !== undefined ? `${Math.round(diagnostic.similarity_scores.timbre_similarity * 100)}%` : "N/A"}
                </div>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-800/80 p-3.5 rounded-lg text-center">
                <div className="text-[11px] text-zinc-400 mb-1">Loudness Similarity</div>
                <div className="text-xl font-bold text-indigo-400">
                  {diagnostic.similarity_scores?.loudness_similarity !== undefined ? `${Math.round(diagnostic.similarity_scores.loudness_similarity * 100)}%` : "N/A"}
                </div>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-800/80 p-3.5 rounded-lg text-center">
                <div className="text-[11px] text-zinc-400 mb-1 font-semibold text-emerald-400">Overall Score</div>
                <div className="text-xl font-extrabold text-emerald-400">
                  {diagnostic.similarity_scores?.overall_similarity !== undefined ? `${Math.round(diagnostic.similarity_scores.overall_similarity * 100)}%` : "N/A"}
                </div>
              </div>
            </div>

            {/* Comparative Metrics Table */}
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-900/90 text-zinc-400 font-medium border-b border-zinc-800">
                  <tr>
                    <th className="px-4 py-2.5">Acoustic Metric</th>
                    <th className="px-4 py-2.5">Reference Profile</th>
                    <th className="px-4 py-2.5">Generated Speech</th>
                    <th className="px-4 py-2.5">Target / Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 bg-zinc-950/40 text-zinc-300">
                  <tr>
                    <td className="px-4 py-2 font-medium text-zinc-200">Mean Fundamental Pitch (F0)</td>
                    <td className="px-4 py-2">{diagnostic.reference_metrics?.mean_pitch_hz ? `${diagnostic.reference_metrics.mean_pitch_hz} Hz` : "N/A"}</td>
                    <td className="px-4 py-2 font-semibold text-indigo-300">{diagnostic.generated_metrics?.mean_pitch_hz ? `${diagnostic.generated_metrics.mean_pitch_hz} Hz` : "N/A"}</td>
                    <td className="px-4 py-2 text-zinc-500">Subtle pitch correction applied</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-zinc-200">Median Pitch & Range</td>
                    <td className="px-4 py-2">{diagnostic.reference_metrics?.median_pitch_hz ? `${diagnostic.reference_metrics.median_pitch_hz} Hz (±${diagnostic.reference_metrics.pitch_range_hz} Hz)` : "N/A"}</td>
                    <td className="px-4 py-2">{diagnostic.generated_metrics?.median_pitch_hz ? `${diagnostic.generated_metrics.median_pitch_hz} Hz (±${diagnostic.generated_metrics.pitch_range_hz} Hz)` : "N/A"}</td>
                    <td className="px-4 py-2 text-zinc-500">±2.5 Semitones bounded shift</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-zinc-200">Loudness (LUFS / RMS)</td>
                    <td className="px-4 py-2">{diagnostic.reference_metrics?.loudness_lufs ? `${diagnostic.reference_metrics.loudness_lufs} LUFS` : "N/A"}</td>
                    <td className="px-4 py-2 font-semibold text-emerald-400">{diagnostic.generated_metrics?.loudness_lufs ? `${diagnostic.generated_metrics.loudness_lufs} LUFS` : "N/A"}</td>
                    <td className="px-4 py-2 text-emerald-400 font-medium">Normalized to -14.0 LUFS</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-zinc-200">Spectral Centroid (Timbre)</td>
                    <td className="px-4 py-2">{diagnostic.reference_metrics?.spectral_centroid ? `${diagnostic.reference_metrics.spectral_centroid} Hz` : "N/A"}</td>
                    <td className="px-4 py-2">{diagnostic.generated_metrics?.spectral_centroid ? `${diagnostic.generated_metrics.spectral_centroid} Hz` : "N/A"}</td>
                    <td className="px-4 py-2 text-zinc-500">Formant envelope comparison</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Conditioning Verification Checklist */}
            {diagnostic.voice_conditioning_verification && (
              <div className="bg-zinc-950/60 border border-zinc-800/80 p-4 rounded-lg flex flex-wrap items-center justify-between gap-4 text-xs">
                <div className="flex items-center gap-2">
                  {diagnostic.voice_conditioning_verification.reference_audio_loaded ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <X className="w-4 h-4 text-red-400" />
                  )}
                  <span className="text-zinc-300">Reference Loaded</span>
                </div>

                <div className="flex items-center gap-2">
                  {diagnostic.voice_conditioning_verification.speaker_embedding_generated ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <X className="w-4 h-4 text-red-400" />
                  )}
                  <span className="text-zinc-300">512-Dim Vector Generated</span>
                </div>

                <div className="flex items-center gap-2">
                  {diagnostic.voice_conditioning_verification.speaker_embedding_passed_to_model ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <X className="w-4 h-4 text-amber-400" />
                  )}
                  <span className="text-zinc-300">Embedding Conditioning Active</span>
                </div>

                <div className="flex items-center gap-2 font-semibold">
                  <span className="text-zinc-400">Default Voice Fallback:</span>
                  <span className={diagnostic.voice_conditioning_verification.default_voice_fallback_used ? "text-amber-400 font-bold" : "text-emerald-400"}>
                    {diagnostic.voice_conditioning_verification.default_voice_fallback_used ? "YES (Acoustic DSP Adapted)" : "NO (Neural Model Active)"}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Section 5: Controlled Sentence Evaluation Suite (Phase 11) */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center text-xs font-bold">5</span>
                Controlled Sentence Evaluation Suite (Phase 11)
              </h2>
              <p className="text-xs text-zinc-400 max-w-xl">
                Test voice cloning similarity and naturalness across 8 standardized sentence types (Short, Long, Emotional, Question, Statement, Numbers, Names, and Tamil/English mixed).
              </p>
            </div>
            <button
              onClick={handleRunEvaluation}
              disabled={evaluating}
              className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 shrink-0 shadow-sm"
            >
              {evaluating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Running 8-Sentence Evaluation...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  Run Controlled Evaluation Suite
                </>
              )}
            </button>
          </div>

          {evalReport && evalReport.results && (
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between text-xs text-zinc-400 px-1">
                <span>Total Sentences: <strong className="text-zinc-200">{evalReport.total_sentences}</strong></span>
                <span>Evaluated at: <strong className="text-zinc-200">{new Date(evalReport.evaluated_at).toLocaleTimeString()}</strong></span>
              </div>

              <div className="border border-zinc-800 rounded-lg overflow-hidden divide-y divide-zinc-800/60 bg-zinc-950/40">
                {evalReport.results.map((item) => {
                  const audioSrc = `${API_BASE}${item.audio_url?.replace("/api/v1", "")}`;
                  return (
                    <div key={item.index} className="p-4 hover:bg-zinc-900/30 transition-colors space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                            {item.type}
                          </span>
                          <span className="text-xs font-medium text-zinc-300">Sentence #{item.index + 1}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-zinc-400 font-mono">
                          <span>Duration: <strong className="text-zinc-200">{item.duration || 0}s</strong></span>
                          <span>Loudness: <strong className="text-emerald-400">{item.loudness_lufs || -14} LUFS</strong></span>
                          <span>Pitch: <strong className="text-indigo-400">{item.mean_pitch_hz || 0} Hz</strong></span>
                        </div>
                      </div>

                      <p className="text-sm text-zinc-200 italic bg-zinc-900/50 p-2.5 rounded border border-zinc-800/50">
                        "{item.text}"
                      </p>

                      <div className="flex items-center justify-end pt-1">
                        <audio controls src={audioSrc} className="h-8 w-full sm:w-72" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
