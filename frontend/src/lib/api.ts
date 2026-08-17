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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Fetch helper with timeout support.
 *
 * The custom `timeout` property is removed before passing
 * the remaining options to fetch().
 */
async function fetchWithTimeout(
  resource: RequestInfo | URL,
  options: RequestInit & { timeout?: number } = {}
): Promise<Response> {
  const { timeout = 30000, ...fetchOptions } = options;

  const controller = new AbortController();

  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeout);

  try {
    return await fetch(resource, {
      ...fetchOptions,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeout / 1000} seconds`);
    }

    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Handle normal JSON API responses.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}`;

    try {
      const errorData = await response.json();

      if (typeof errorData?.detail === "string") {
        errorMessage = errorData.detail;
      } else if (typeof errorData?.message === "string") {
        errorMessage = errorData.message;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

/**
 * Health check
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${API_URL}/health`, {
      timeout: 3000,
    });

    const data = await handleResponse<HealthResponse>(res);

    return data.status === "ok";
  } catch {
    return false;
  }
}

/**
 * Personas
 */
export async function getPersonas(): Promise<PersonaResponse[]> {
  const res = await fetchWithTimeout(`${API_URL}/personas`);
  return handleResponse<PersonaResponse[]>(res);
}

export async function createPersona(
  name: string
): Promise<PersonaResponse> {
  const res = await fetchWithTimeout(`${API_URL}/personas`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });

  return handleResponse<PersonaResponse>(res);
}

export async function deletePersona(id: string): Promise<void> {
  try {
    const res = await fetchWithTimeout(
      `${API_URL}/personas/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
        timeout: 10000,
      }
    );

    /*
     * If the persona is already gone, treat the deletion
     * as successful. This prevents stale frontend state
     * from producing "Persona not found" errors.
     */
    if (res.status === 404) {
      return;
    }

    await handleResponse<{ status: string }>(res);
  } catch (error) {
    /*
     * A timeout should still be reported to the caller.
     * Only 404 is intentionally ignored above.
     */
    throw error;
  }
}

/**
 * Documents
 */
export async function getDocuments(
  persona_id: string
): Promise<DocumentResponse[]> {
  const res = await fetchWithTimeout(
    `${API_URL}/documents?persona_id=${encodeURIComponent(persona_id)}`
  );

  return handleResponse<DocumentResponse[]>(res);
}

export async function uploadDocument(
  persona_id: string,
  file: File
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetchWithTimeout(
    `${API_URL}/upload?persona_id=${encodeURIComponent(persona_id)}`,
    {
      method: "POST",
      body: formData,
      timeout: 120000,
    }
  );

  return handleResponse<UploadResponse>(res);
}

export async function deleteDocument(
  id: string
): Promise<DeleteResponse> {
  const res = await fetchWithTimeout(
    `${API_URL}/documents/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
      timeout: 30000,
    }
  );

  return handleResponse<DeleteResponse>(res);
}

/**
 * Knowledge / website ingestion
 */
export async function ingestWebsiteUrl(
  data: UrlRequest
): Promise<UploadResponse> {
  const res = await fetchWithTimeout(`${API_URL}/knowledge/url`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
    timeout: 120000,
  });

  return handleResponse<UploadResponse>(res);
}

export async function getKnowledgeStatus(
  id: string
): Promise<KnowledgeStatus> {
  const res = await fetchWithTimeout(
    `${API_URL}/knowledge/${encodeURIComponent(id)}/status`
  );

  return handleResponse<KnowledgeStatus>(res);
}

/**
 * Streaming chat
 */
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
    body: JSON.stringify({
      persona_id,
      message,
      history,
    }),
  });

  if (!res.ok) {
    let errorMessage = `HTTP Error ${res.status}`;

    try {
      const errorData = await res.json();

      if (typeof errorData?.detail === "string") {
        errorMessage = errorData.detail;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new ApiError(res.status, errorMessage);
  }

  if (!res.body) {
    throw new Error("No response body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, {
      stream: true,
    });

    const lines = buffer.split("\n\n");

    /*
     * Keep the final incomplete chunk in the buffer.
     */
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) {
        continue;
      }

      const dataStr = line.substring(6).trim();

      if (!dataStr) {
        continue;
      }

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
      } catch (error) {
        /*
         * Ignore malformed/incomplete JSON chunks.
         * The server normally sends complete JSON messages.
         */
        if (
          error instanceof Error &&
          error.message !== "Unexpected end of JSON input"
        ) {
          throw error;
        }
      }
    }
  }
}

/**
 * Generic TTS
 */
export async function generateTTS(
  text: string,
  persona_id?: string
): Promise<string> {
  const res = await fetch(`${API_URL}/chat/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      persona_id,
    }),
  });

  if (!res.ok) {
    let errorMessage = `TTS generation failed: ${res.status}`;

    try {
      const errorData = await res.json();

      if (typeof errorData?.detail === "string") {
        errorMessage = errorData.detail;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new Error(errorMessage);
  }

  const blob = await res.blob();

  return URL.createObjectURL(blob);
}

/**
 * Voice samples
 */
export interface VoiceSample {
  id: string;
  filename: string;
  duration: number;
  file_size: number;
  status: string;
  warnings?: string[];
  created_at: string;
}

export async function getVoiceSamples(
  persona_id: string
): Promise<VoiceSample[]> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/samples`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch voice samples");
  }

  return res.json();
}

export async function uploadVoiceSample(
  persona_id: string,
  file: File
): Promise<VoiceSample> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/samples`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));

    throw new Error(
      err.detail || `Upload failed: ${res.status}`
    );
  }

  return res.json();
}

export async function deleteVoiceSample(
  persona_id: string,
  sample_id: string
): Promise<void> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(
      persona_id
    )}/voice/samples/${encodeURIComponent(sample_id)}`,
    {
      method: "DELETE",
    }
  );

  if (!res.ok) {
    throw new Error("Failed to delete voice sample");
  }
}

/**
 * Voice profile
 */
export interface VoiceProfileStatus {
  persona_id: string;

  status:
    | "NOT_CONFIGURED"
    | "SAMPLES_UPLOADED"
    | "PROCESSING"
    | "READY"
    | "FAILED";

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

export async function getVoiceProfile(
  persona_id: string
): Promise<VoiceProfileStatus> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch voice profile status");
  }

  return res.json();
}

export async function createVoiceProfile(
  persona_id: string
): Promise<{
  success: boolean;
  voice_status: string;
}> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/create`,
    {
      method: "POST",
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));

    throw new Error(
      err.detail || `Voice creation failed: ${res.status}`
    );
  }

  return res.json();
}

export async function deleteVoiceProfile(
  persona_id: string
): Promise<void> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice`,
    {
      method: "DELETE",
    }
  );

  if (!res.ok) {
    throw new Error("Failed to delete voice profile");
  }
}

/**
 * Voice testing
 */
export async function testPersonaVoice(
  persona_id: string,
  text: string,
  provider?: string
): Promise<string> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/test`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        provider,
      }),
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));

    throw new Error(
      err.detail || `Voice test failed: ${res.status}`
    );
  }

  const blob = await res.blob();

  return URL.createObjectURL(blob);
}

/**
 * Voice provider
 */
export async function toggleVoiceProvider(
  persona_id: string,
  provider: string
): Promise<VoiceProfileStatus> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/provider`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        provider,
      }),
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));

    throw new Error(
      err.detail || `Provider toggle failed: ${res.status}`
    );
  }

  return res.json();
}

/**
 * Voice diagnostics
 */
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

export async function getVoiceDiagnostic(
  persona_id: string
): Promise<DiagnosticReport> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/diagnostic`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch diagnostic report");
  }

  return res.json();
}

/**
 * Voice evaluation
 */
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

export async function evaluateVoiceCloning(
  persona_id: string
): Promise<EvaluationSuiteReport> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(persona_id)}/voice/evaluate`,
    {
      method: "POST",
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));

    throw new Error(
      err.detail || `Evaluation failed: ${res.status}`
    );
  }

  return res.json();
}

/**
 * F5-TTS status
 */
export interface F5TTSStatus {
  status: string;
  message: string;
  url: string;
  model?: string;
}

export async function fetchF5TTSStatus(): Promise<F5TTSStatus> {
  const res = await fetch(`${API_URL}/voice/f5tts/status`);

  if (!res.ok) {
    throw new Error("Failed to fetch F5-TTS status");
  }

  return res.json();
}

/**
 * F5-TTS settings
 */
export interface F5TTSSettings {
  reference_text: string;
  randomize_seed: boolean;
  seed: number;
  speed: number;
  nfe_steps: number;
  cross_fade_duration: number;
}

export async function updateF5TTSSettings(
  persona_id: string,
  settings: F5TTSSettings
): Promise<void> {
  const res = await fetch(
    `${API_URL}/personas/${encodeURIComponent(
      persona_id
    )}/voice/f5tts-settings`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(settings),
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));

    throw new Error(
      err.detail || `Failed to update settings: ${res.status}`
    );
  }
}