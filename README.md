# PersonaForge AI

PersonaForge AI is an intelligent chatbot platform that combines Retrieval-Augmented Generation (RAG), local Large Language Models (LLMs), and internet search to provide highly accurate answers.

## Prerequisites

1. **Python 3.12+**
2. **Node.js 18+**
3. **Ollama**: Download and install from [ollama.com](https://ollama.com/).
4. **LLM Model**: Pull the required model before running the backend:
   ```bash
   ollama run llama3.1:8b
   ```

## Running the Application

### 1. Backend (FastAPI)

Navigate to the `backend` directory, activate the virtual environment, and run the server.

**Windows:**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host localhost --port 8000 --reload
```

**Mac/Linux:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host localhost --port 8000 --reload
```

The backend API will be available at [http://localhost:8000](http://localhost:8000). You can view the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend (Next.js)

Navigate to the `frontend` directory and start the development server.

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000).

# 🎙️ F5-TTS Voice Setup with Pinokio

## Overview

PersonaForge uses F5-TTS for zero-shot voice cloning.

The workflow is:

```
User Voice Sample
        ↓
PersonaForge
        ↓
F5-TTS running through Pinokio
        ↓
Reference Voice + Reference Text + TTS Settings
        ↓
Generated Speech
        ↓
PersonaForge Chat UI
```

F5-TTS does not need to be integrated directly into the PersonaForge Python environment. Pinokio can run F5-TTS in its own environment, while PersonaForge communicates with the running F5-TTS service.

## 1. Prerequisites

- Windows 10/11
- NVIDIA GPU is recommended for practical generation speed (CPU generation may be significantly slower)
- Sufficient RAM/VRAM
- Pinokio installed
- Git if required by the Pinokio installation
- PersonaForge backend and frontend already installed

*Note: F5-TTS currently works best with supported languages such as English and Chinese, depending on the selected checkpoint/version.*

## 2. Install Pinokio

1. Download and install Pinokio from its official website.
2. Launch Pinokio.
3. Allow it to create/manage its application environments.
4. Open the Pinokio application interface.

> Always download Pinokio from its official website.

## 3. Install F5-TTS through Pinokio

1. Open Pinokio.
2. Search for the **F5-TTS** application.
3. Install the F5-TTS application.
4. Allow Pinokio to create its isolated environment.
5. Wait for model and dependency installation to finish.
6. Start the F5-TTS application.

Pinokio may create a directory similar to `C:\pinokio\api\e2-f5-tts.git\`. The exact directory may differ depending on the Pinokio installation.

## 4. Start F5-TTS

After installation:
1. Open the F5-TTS application inside Pinokio.
2. Start the local server/UI.
3. Wait until the F5-TTS interface becomes available.
4. Keep Pinokio/F5-TTS running while PersonaForge uses voice generation.

The local F5-TTS UI may look similar to the **F5-TTS Demo Space** with options such as:
- F5-TTS
- E2-TTS
- Custom
- Reference Audio
- Reference Text
- Speed
- NFE Steps
- Cross Fade Duration
- Seed

## 5. Verify F5-TTS Manually First

Before connecting PersonaForge, test F5-TTS manually in the Pinokio UI.

Use the following test settings:
- **Reference Audio**: 8–12 second clean voice sample
- **Reference Text**: `athula vanthu antha batsman vara ella ballayum six adika dhaan try pannuvaaru.`
- **Randomize Seed**: OFF
- **Seed**: 259225565
- **Speed**: 0.9
- **NFE Steps**: 20
- **Cross Fade Duration**: 0.11

Generate a short sentence and confirm that the generated audio resembles the reference speaker.

> If the voice does not work correctly inside F5-TTS itself, PersonaForge integration will not fix the underlying model/output problem. First verify the F5-TTS installation independently.

## 6. Reference Audio Requirements

**Recommended:** 8–12 seconds  
**Maximum:** 12 seconds  

The application automatically:
1. Preserves the original upload.
2. Converts the working copy to WAV.
3. Converts it to mono.
4. Resamples it appropriately.
5. Removes unnecessary silence.
6. Trims it to a maximum of 12 seconds.
7. Sends the processed reference to F5-TTS.

Clean speech is strongly recommended:
- One speaker
- Minimal background noise
- No music
- No overlapping speakers
- Clear pronunciation
- Stable microphone volume

## 7. Reference Text

The reference text should match what is actually spoken in the reference audio.

**Example:**
If the audio says:
> "athula vanthu antha batsman vara ella ballayum six adika dhaan try pannuvaaru."

Then the Reference Text must be:
> athula vanthu antha batsman vara ella ballayum six adika dhaan try pannuvaaru.

Incorrect reference text can reduce voice similarity and speech quality.

## 8. F5-TTS Settings Used by PersonaForge

| Setting | Default |
|---|---|
| Reference Audio | 8–12 seconds |
| Maximum Audio | 12 seconds |
| Randomize Seed | OFF |
| Seed | 259225565 |
| Speed | 0.9 |
| NFE Steps | 20 |
| Cross Fade Duration | 0.11 |

* **Seed**: Controls randomness. Keeping it fixed ensures consistent voices.
* **Speed**: Controls the pacing of the generated audio.
* **NFE Steps**: Number of function evaluations; higher values can improve quality but take longer to generate.
* **Cross Fade Duration**: Blends generated audio chunks seamlessly.

## 9. Connecting PersonaForge to F5-TTS

PersonaForge does NOT need to launch Pinokio itself. Instead, they communicate over HTTP:

```
Pinokio
  ↓
F5-TTS local service
  ↓
Local HTTP/API endpoint
  ↓
PersonaForge Backend
  ↓
Chat Response
  ↓
F5-TTS
  ↓
Audio
```

The PersonaForge backend internally transforms your generation requests into the specific payload format required by the currently installed F5-TTS server. It dynamically adjusts settings to include:
```json
{
    "text": "The generated chatbot response",
    "reference_audio": "...",
    "reference_text": "...",
    "seed": 259225565,
    "randomize_seed": false,
    "speed": 0.9,
    "nfe_steps": 20,
    "cross_fade_duration": 0.11
}
```

## 10. Configure the F5-TTS Server URL

PersonaForge needs to know where the Pinokio F5-TTS service is running. You must set this in your `backend/.env` file:

```env
F5_TTS_BASE_URL=http://127.0.0.1:<PORT>
```

> The exact port is installation-dependent. Check the Pinokio console/application output for the local address. Ensure you replace `<PORT>` with the actual port shown by Pinokio.

## 11. Persona Voice Generation Flow

1. User creates a Persona.
2. User uploads reference voice.
3. PersonaForge validates the audio.
4. PersonaForge stores the original audio.
5. PersonaForge creates the processed ≤12-second reference.
6. User configures F5-TTS settings.
7. PersonaForge stores the settings.
8. User asks a question.
9. RAG/LLM generates the text response.
10. PersonaForge cleans the response for TTS.
11. Backend sends the text + reference voice + F5-TTS parameters.
12. Pinokio's F5-TTS service generates audio.
13. Backend returns the generated audio.
14. Frontend displays the text response.
15. If voice output is enabled, only the current response is played.

## 12. Running Both Applications

Both services must be running simultaneously:

**Terminal / Process 1:**
PersonaForge Backend

**Terminal / Process 2:**
PersonaForge Frontend

**Application:**
Pinokio → F5-TTS

**Conceptual Architecture:**
```
┌──────────────────────┐
│ PersonaForge Frontend│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ PersonaForge Backend │
└──────────┬───────────┘
           │ HTTP
           ▼
┌──────────────────────┐
│ F5-TTS / Pinokio     │
│ Local Service        │
└──────────────────────┘
```

## 13. Important: Separate Python Environments

Pinokio's F5-TTS environment and PersonaForge's backend Python environment should remain separate. Do NOT install all F5-TTS dependencies into the PersonaForge virtual environment unless there is a specific reason. This prevents dependency conflicts involving PyTorch, CUDA, Transformers, NumPy, Audio libraries, and Python versions.

## 14. GPU / RAM Considerations

**Warning**: F5-TTS can consume significant GPU VRAM and system RAM. Running all of these simultaneously may cause high resource usage:
- Ollama
- PersonaForge Backend
- PersonaForge Frontend
- F5-TTS
- Other AI models

If RAM/VRAM usage becomes excessive:
1. Close unused applications.
2. Reduce the number of simultaneously loaded AI models.
3. Run F5-TTS on another computer/server.
4. Configure PersonaForge to access F5-TTS over the local network.
5. Keep only the backend/frontend/required services on the main development machine.

## 15. Remote F5-TTS Option

F5-TTS does not necessarily need to run on the same computer.

**Example:**
* **Computer A**: PersonaForge (Frontend, Backend, RAG, Ollama)
* **Computer B**: Pinokio (F5-TTS, GPU)

**Network Configuration:**
```
Computer A
   │
   │ HTTP
   ▼
Computer B (F5-TTS)
```

The backend on Computer A can use:
```env
F5_TTS_BASE_URL=http://<F5-TTS-PC-IP>:<PORT>
```

The F5-TTS service must be configured to accept connections from the network, and firewall/network settings must allow the connection. Do not expose the service directly to the public internet without proper authentication and security controls.

## 16. Troubleshooting

| Problem | Possible Cause | Solution |
|---|---|---|
| F5-TTS does not start | Missing dependency/model | Check Pinokio console |
| PersonaForge cannot connect | Wrong URL/port | Check Pinokio's displayed local address |
| Connection refused | F5-TTS not running | Start F5-TTS in Pinokio |
| Voice sounds incorrect | Poor reference audio | Use clean 8–12 second sample |
| Voice similarity is poor | Incorrect reference text | Make transcript match audio |
| Generation is slow | CPU or limited GPU | Use NVIDIA GPU |
| RAM reaches 99% | Multiple AI services | Move F5-TTS to another machine |
| CUDA error | Driver/PyTorch mismatch | Check the F5-TTS environment |
| Audio is empty | Invalid generation response | Inspect F5-TTS logs/API response |

## 17. Verification Checklist

### Pinokio
- [ ] Pinokio installed
- [ ] F5-TTS installed
- [ ] F5-TTS starts successfully
- [ ] F5-TTS UI accessible
- [ ] Reference audio works
- [ ] Reference text works
- [ ] Voice generation works

### PersonaForge
- [ ] F5_TTS_BASE_URL configured
- [ ] Backend can reach F5-TTS
- [ ] Voice profile created
- [ ] Reference audio stored
- [ ] Reference text stored
- [ ] F5-TTS settings stored
- [ ] Chat response generated
- [ ] TTS request generated
- [ ] Audio returned successfully
- [ ] Frontend plays only the current response

## 18. Security Notes

- Never commit `.env` files containing secrets.
- Do not expose a local F5-TTS service publicly without authentication.
- If using another computer on the LAN, restrict access to trusted devices.
- Keep raw reference recordings private.
- Do not upload or clone voices without appropriate permission/authorization.

## 19. Final Quick Start

1. Install Pinokio.
2. Install F5-TTS through Pinokio.
3. Launch F5-TTS.
4. Verify F5-TTS manually with an 8–12 second reference.
5. Copy the F5-TTS local server address/port.
6. Configure:
   ```env
   F5_TTS_BASE_URL=http://127.0.0.1:<PORT>
   ```
7. Start PersonaForge backend.
8. Start PersonaForge frontend.
9. Create a persona.
10. Upload the reference voice.
11. Set the reference transcript.
12. Keep the default F5-TTS settings or customize them.
13. Test the persona voice.
14. Ask a question.
15. Enable voice response.
16. PersonaForge sends the response to F5-TTS.
17. F5-TTS returns the generated speech.
18. PersonaForge plays the current response.
