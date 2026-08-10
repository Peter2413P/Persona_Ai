import re

with open("src/app/voice/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Add F5TTS imports
content = content.replace(
    "EvaluationSuiteReport\n} from \"@/lib/api\";",
    "EvaluationSuiteReport,\n  F5TTSStatus,\n  fetchF5TTSStatus\n} from \"@/lib/api\";"
)

# Add F5Status state
content = content.replace(
    "const [evalReport, setEvalReport] = useState<EvaluationSuiteReport | null>(null);",
    "const [evalReport, setEvalReport] = useState<EvaluationSuiteReport | null>(null);\n  const [f5Status, setF5Status] = useState<F5TTSStatus | null>(null);"
)

# Update fetchVoiceData
content = content.replace(
    "setEvalReport(null);\n      setLoading(false);",
    "setEvalReport(null);\n      setF5Status(null);\n      setLoading(false);"
)

fetch_inject = """      // Attempt to load diagnostic report
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
      }"""

content = content.replace("""      // Attempt to load diagnostic report
      try {
        const diag = await getVoiceDiagnostic(activePersona.id);
        if (diag && diag.status !== "NOT_AVAILABLE" && diag.reference_metrics) {
          setDiagnostic(diag);
        } else {
          setDiagnostic(null);
        }
      } catch {
        setDiagnostic(null);
      }""", fetch_inject)

# Replace Uberduck strings
content = content.replace("uberduck_voice", "f5tts_voice")
content = content.replace('"uberduck"', '"f5tts"')
content = content.replace('provider === "uberduck"', 'provider === "f5tts"')
content = content.replace('provider: "uberduck"', 'provider: "f5tts"')
content = content.replace('Uberduck Engine', 'Local F5-TTS Engine')
content = content.replace("Cloud-based studio-grade speech synthesis via Uberduck custom voice cloning. Automatically routes reference samples and generates expressive natural speech.", 
"High-quality local speech synthesis via Pinokio F5-TTS Gradio interface. Zero-shot voice cloning with automatic transcription.")
content = content.replace("Test synthesis with Uberduck Engine", "Test synthesis with F5-TTS Engine")

# Change the voice ID display for F5-TTS to model_name
content = content.replace(
    """{profile.f5tts_voice?.voice_id && (
                            <span className="font-mono text-[10px] text-purple-300">({profile.f5tts_voice.voice_id.slice(0, 10)}...)</span>
                          )}""",
    """{profile.f5tts_voice?.model_name && (
                            <span className="font-mono text-[10px] text-purple-300">({profile.f5tts_voice.model_name})</span>
                          )}"""
)

# Add Server Status badge
status_badge_inject = """<div className="flex items-center space-x-2">
                        {f5Status?.status === 'online' ? (
                            <span className="flex items-center text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-400 mr-1.5 animate-pulse"></span>
                                Online
                            </span>
                        ) : (
                            <span className="flex items-center text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded">
                                <span className="w-1.5 h-1.5 rounded-full bg-red-400 mr-1.5"></span>
                                Offline
                            </span>
                        )}
                      </div>"""

content = content.replace(
    '<h3 className="font-semibold text-gray-100 flex items-center">Local F5-TTS Engine</h3>',
    f'<div className="flex items-center justify-between"><h3 className="font-semibold text-gray-100 flex items-center">Local F5-TTS Engine</h3>\n{status_badge_inject}\n</div>'
)

with open("src/app/voice/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)

print("Done replacing in page.tsx")
