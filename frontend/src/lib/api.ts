export interface SourceItem {
  type: string;
  title: string;
  content: string;
  url: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: SourceItem[];
}

export interface DocumentResponse {
  id: string;
  name: string;
  source_type: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface UrlRequest {
  url: string;
  persona_id: string;
}

export interface PersonaResponse {
  id: string;
  name: string;
  created_at: string;
}

export interface KnowledgeStatus {
  id: string;
  status: string;
  chunk_count: number;
  error_message: string | null;
}

export interface UploadResponse {
  status: string;
  id: string;
  filename: string;
}

export interface DeleteResponse {
  status: string;
  id: string;
}

export interface HealthResponse {
  status: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchWithTimeout(resource: RequestInfo | URL, options: RequestInit & { timeout?: number } = {}) {
  const { timeout = 30000 } = options;
  
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  const response = await fetch(resource, {
    ...options,
    signal: controller.signal  
  }).finally(() => {
    clearTimeout(id);
  });
  return response;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // Ignored
    }
    throw new ApiError(response.status, errorMessage);
  }
  return response.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${API_URL}/health`, { timeout: 3000 });
    const data = await handleResponse<HealthResponse>(res);
    return data.status === "ok";
  } catch (error) {
    return false;
  }
}

export async function getPersonas(): Promise<PersonaResponse[]> {
  const res = await fetchWithTimeout(`${API_URL}/personas`);
  return handleResponse<PersonaResponse[]>(res);
}

export async function createPersona(name: string): Promise<PersonaResponse> {
  const res = await fetchWithTimeout(`${API_URL}/personas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return handleResponse<PersonaResponse>(res);
}

export async function deletePersona(id: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_URL}/personas/${id}`, {
    method: "DELETE",
  });
  await handleResponse<{status: string}>(res);
}

export async function getDocuments(persona_id: string): Promise<DocumentResponse[]> {
  const res = await fetchWithTimeout(`${API_URL}/documents?persona_id=${persona_id}`);
  return handleResponse<DocumentResponse[]>(res);
}

export async function uploadDocument(persona_id: string, file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetchWithTimeout(`${API_URL}/upload?persona_id=${persona_id}`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<UploadResponse>(res);
}

export async function deleteDocument(id: string): Promise<DeleteResponse> {
  const res = await fetchWithTimeout(`${API_URL}/documents/${id}`, {
    method: "DELETE",
  });
  return handleResponse<DeleteResponse>(res);
}



export async function ingestWebsiteUrl(data: UrlRequest): Promise<UploadResponse> {
  const res = await fetchWithTimeout(`${API_URL}/knowledge/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<UploadResponse>(res);
}

export async function getKnowledgeStatus(id: string): Promise<KnowledgeStatus> {
  const res = await fetchWithTimeout(`${API_URL}/knowledge/${id}/status`);
  return handleResponse<KnowledgeStatus>(res);
}

export async function sendChatStream(
  persona_id: string,
  message: string,
  history: { role: string; content: string }[],
  onToken: (token: string) => void,
  onSources: (sources: SourceItem[]) => void
): Promise<void> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ persona_id, message, history }),
  });

  if (!res.ok) {
    let errorMessage = `HTTP Error ${res.status}`;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // Ignore
    }
    throw new ApiError(res.status, errorMessage);
  }

  if (!res.body) {
    throw new Error("No response body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split("\n\n");
    
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const dataStr = line.substring(6);
        try {
          const data = JSON.parse(dataStr);
          if (data.type === "token") {
            onToken(data.content);
          } else if (data.type === "sources") {
            onSources(data.sources);
          } else if (data.type === "error") {
            throw new Error(data.message);
          } else if (data.type === "done") {
            return;
          }
        } catch (e) {
          // JSON parse error for incomplete chunks, usually handled by a better buffer in production,
          // but our simple generator guarantees newline delimited complete JSON objects.
        }
      }
    }
  }
}

export async function generateTTS(text: string, persona_id?: string): Promise<string> {
  const res = await fetch(`${API_URL}/chat/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text, persona_id }),
  });

  if (!res.ok) {
    throw new Error(`TTS generation failed: ${res.status}`);
  }

  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export interface VoiceSample {
  id: string;
  filename: string;
  duration: number;
  file_size: number;
  status: string;
  warnings?: string[];
  created_at: string;
}

export interface VoiceProfileStatus {
  persona_id: string;
  status: "NOT_CONFIGURED" | "SAMPLES_UPLOADED" | "PROCESSING" | "READY" | "FAILED";
  provider: string;
  active_provider?: string;
  local_voice?: {
    embedding_path?: string | null;
    embedding_model?: string;
    tts_model?: string;
    verified?: boolean;
    status?: string;
  };
  f5tts_settings?: F5TTSSettings;
  f5tts_voice?: {
    model_name: string | null;
    status: string;
    verified: boolean;
  };
  voice_id?: string;
  samples_count: number;
  error_message?: string;
  speaker_metadata?: {
    analytical_features?: {
      sample_rate?: number;
      duration?: number;
      mean_f0?: number;
      median_f0?: number;
      min_f0?: number;
      max_f0?: number;
      pitch_range?: number;
      rms_loudness?: number;
      lufs_est?: number;
      spectral_centroid?: number;
      speech_activity_ratio?: number;
    };
    voice_cloning_conditioning?: {
      reference_audio_uploaded?: boolean;
      reference_audio_validated?: boolean;
      speaker_representation_generated?: boolean;
      tts_compatible_conditioning_created?: boolean;
      conditioning_type?: string;
      ready_for_synthesis?: boolean;
    };
    mean_f0?: number;
    median_f0?: number;
    pitch_range?: number;
    loudness_lufs?: number;
    has_embedding?: boolean;
    conditioning_type?: string;
  };
  has_diagnostic?: boolean;
}

export interface DiagnosticReport {
  timestamp?: string;
  status?: string;
  message?: string;
  reference_metrics?: {
    duration?: number;
    sample_rate?: number;
    mean_pitch_hz?: number;
    median_pitch_hz?: number;
    pitch_range_hz?: number;
    loudness_lufs?: number;
    rms_loudness?: number;
    spectral_centroid?: number;
  };
  generated_metrics?: {
    duration?: number;
    sample_rate?: number;
    mean_pitch_hz?: number;
    median_pitch_hz?: number;
    pitch_range_hz?: number;
    loudness_lufs?: number;
    rms_loudness?: number;
    spectral_centroid?: number;
  };
  similarity_scores?: {
    pitch_similarity?: number;
    timbre_similarity?: number;
    loudness_similarity?: number;
    overall_similarity?: number;
  };
  similarity_warnings?: string[];
  voice_conditioning_verification?: {
    reference_audio_loaded?: boolean;
    speaker_embedding_generated?: boolean;
    speaker_embedding_passed_to_model?: boolean;
    default_voice_fallback_used?: boolean;
  };
}

export interface EvaluationSentence {
  index: number;
  type: string;
  text: string;
  status: string;
  duration?: number;
  rms_loudness?: number;
  loudness_lufs?: number;
  mean_pitch_hz?: number;
  audio_url?: string;
  error?: string;
}

export interface EvaluationSuiteReport {
  persona_id: string;
  evaluated_at: string;
  total_sentences: number;
  results: EvaluationSentence[];
}

export async function getVoiceSamples(persona_id: string): Promise<VoiceSample[]> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/samples`);
  if (!res.ok) throw new Error("Failed to fetch voice samples");
  return res.json();
}

export async function uploadVoiceSample(persona_id: string, file: File): Promise<VoiceSample> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/samples`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteVoiceSample(persona_id: string, sample_id: string): Promise<void> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/samples/${sample_id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete voice sample");
}

export async function getVoiceProfile(persona_id: string): Promise<VoiceProfileStatus> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice`);
  if (!res.ok) throw new Error("Failed to fetch voice profile status");
  return res.json();
}

export async function createVoiceProfile(persona_id: string): Promise<{ success: boolean; voice_status: string }> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/create`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Voice creation failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteVoiceProfile(persona_id: string): Promise<void> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete voice profile");
}

export async function testPersonaVoice(persona_id: string, text: string, provider?: string): Promise<string> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, provider }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Voice test failed: ${res.status}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function toggleVoiceProvider(persona_id: string, provider: string): Promise<VoiceProfileStatus> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/provider`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Provider toggle failed: ${res.status}`);
  }
  return res.json();
}

export async function getVoiceDiagnostic(persona_id: string): Promise<DiagnosticReport> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/diagnostic`);
  if (!res.ok) throw new Error("Failed to fetch diagnostic report");
  return res.json();
}

export async function evaluateVoiceCloning(persona_id: string): Promise<EvaluationSuiteReport> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/evaluate`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Evaluation failed: ${res.status}`);
  }
  return res.json();
}



export interface F5TTSStatus {
  status: string;
  message: string;
  url: string;
  model?: string;
}

export async function fetchF5TTSStatus(): Promise<F5TTSStatus> {
  const res = await fetch(API_URL + '/voice/f5tts/status');
  if (!res.ok) throw new Error('Failed to fetch F5-TTS status');
  return res.json();
}

export interface F5TTSSettings {
  reference_text: string;
  randomize_seed: boolean;
  seed: number;
  speed: number;
  nfe_steps: number;
  cross_fade_duration: number;
}

export async function updateF5TTSSettings(persona_id: string, settings: F5TTSSettings): Promise<void> {
  const res = await fetch(`${API_URL}/personas/${persona_id}/voice/f5tts-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update settings: ${res.status}`);
  }
}
