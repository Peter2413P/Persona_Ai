# PersonaForge AI - Frontend

This is the Next.js frontend for PersonaForge AI.

For full project details and instructions on running both the backend and frontend, please refer to the **root [README.md](../README.md)**.

## Quick Start

### Frontend (Next.js)
```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies if you haven't already
npm install

# Run the development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) with your browser to see the application.

### Backend (FastAPI)
*Note: Make sure Ollama is running and the `llama3.1:8b` model is pulled.*

```powershell
# Navigate to the backend directory
cd backend

# Activate the virtual environment
.\venv\Scripts\activate

# Run the API server
uvicorn app.main:app --host localhost --port 8000 --reload
```
The backend API runs on [http://localhost:8000](http://localhost:8000).
