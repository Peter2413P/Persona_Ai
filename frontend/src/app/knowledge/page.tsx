"use client";

import { useState, useEffect, useRef } from "react";
import { UploadCloud, FileText, Trash2, AlertCircle, Loader2, FileType, FileUp, Link as LinkIcon, RefreshCcw, CheckCircle2 } from "lucide-react";
import { getDocuments, uploadDocument, deleteDocument, ingestWebsiteUrl, getKnowledgeStatus, DocumentResponse } from "@/lib/api";
import { usePersona } from "@/components/PersonaProvider";

type TabState = "upload" | "url";

export default function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { activePersona } = usePersona();
  const [activeTab, setActiveTab] = useState<TabState>("upload");
  
  // Upload State
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);



  // URL State
  const [urlInput, setUrlInput] = useState("");
  const [urlStatus, setUrlStatus] = useState<"idle" | "processing" | "success" | "error">("idle");
  const [urlError, setUrlError] = useState<string | null>(null);

  const fetchDocs = async () => {
    if (!activePersona) {
      setDocuments([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const docs = await getDocuments(activePersona.id);
      setDocuments(docs);
    } catch (err: any) {
      setError(err.message || "Failed to load documents.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, [activePersona]);

  useEffect(() => {
    // Only poll if there are items processing
    const hasProcessing = documents.some(d => d.status === "PROCESSING");
    if (!hasProcessing || !activePersona) return;
    
    const interval = setInterval(async () => {
      try {
        const currentDocs = await getDocuments(activePersona.id);
        setDocuments(currentDocs);
      } catch (err) {
        console.error("Polling error", err);
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, [documents, activePersona]);
  // Handle Drag & Drop
  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => { setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  };

  const handleFileSelection = async (file: File) => {
    if (!activePersona) return;
    setSelectedFile(file);
    setUploadStatus("uploading");
    setUploadError(null);
    try {
      await uploadDocument(activePersona.id, file);
      setUploadStatus("success");
      setTimeout(() => { setUploadStatus("idle"); setSelectedFile(null); }, 3000);
      fetchDocs();
    } catch (err: any) {
      setUploadStatus("error");
      setUploadError(err.message || "Upload failed");
    }
  };



  const handleUrlIngest = async () => {
    if (!urlInput.trim() || !activePersona) return;
    setUrlStatus("processing");
    setUrlError(null);
    try {
      await ingestWebsiteUrl({ url: urlInput, persona_id: activePersona.id });
      setUrlInput("");
      setUrlStatus("success");
      setTimeout(() => setUrlStatus("idle"), 3000);
      fetchDocs();
    } catch (err: any) {
      setUrlStatus("error");
      setUrlError(err.message || "URL ingestion failed");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this source?")) return;
    try {
      await deleteDocument(id);
      fetchDocs();
    } catch (err: any) {
      alert(err.message || "Failed to delete source");
    }
  };

  const getSourceIcon = (type: string) => {
    switch(type) {
      case "UPLOAD": return <FileText className="w-5 h-5 text-emerald-500" />;
      case "WIKIPEDIA": return <GlobeIcon className="w-5 h-5 text-purple-500" />;
      case "WEBSITE": return <LinkIcon className="w-5 h-5 text-orange-500" />;
      default: return <FileText className="w-5 h-5 text-zinc-500" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 md:p-10">
      <div className="max-w-4xl w-full mx-auto space-y-8">
        
        {/* Header */}
        <div className="space-y-2 flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-zinc-100">Knowledge Base</h1>
            <p className="text-zinc-400">Ingest knowledge from documents, research, or specific URLs.</p>
          </div>
          <button onClick={fetchDocs} className="flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 px-3 py-1.5 rounded-lg border border-zinc-800 transition-colors">
            <RefreshCcw className="w-4 h-4" /> Refresh
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-zinc-800">
          <button onClick={() => setActiveTab("upload")} className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "upload" ? "border-emerald-500 text-emerald-500" : "border-transparent text-zinc-400 hover:text-zinc-200"}`}>
            <UploadCloud className="w-4 h-4 inline-block mr-2 -mt-0.5" /> Upload Documents
          </button>
          <button onClick={() => setActiveTab("url")} className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "url" ? "border-emerald-500 text-emerald-500" : "border-transparent text-zinc-400 hover:text-zinc-200"}`}>
            <LinkIcon className="w-4 h-4 inline-block mr-2 -mt-0.5" /> Add Website URL
          </button>
        </div>

        {/* Tab Content */}
        <div className="min-h-[250px]">
          {activeTab === "upload" && (
            <div 
              className={`relative rounded-xl border-2 border-dashed p-10 flex flex-col items-center justify-center text-center transition-colors ${isDragging ? "border-emerald-500 bg-emerald-500/10" : "border-zinc-800 bg-zinc-950/50 hover:bg-zinc-900/50"}`}
              onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}
            >
              <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileChange} accept=".pdf,.docx,.txt,.md,.csv,.pptx" />
              
              {uploadStatus === "idle" && (
                <><div className="bg-zinc-900 p-4 rounded-full mb-4"><UploadCloud className="w-8 h-8 text-zinc-400" /></div>
                <p className="text-lg font-medium text-zinc-200">Click or drag a file here</p>
                <p className="text-sm text-zinc-500 mt-2">Supported: PDF, DOCX, PPTX, CSV, TXT, MD</p></>
              )}
              {uploadStatus === "uploading" && (
                <><div className="bg-emerald-900/30 p-4 rounded-full mb-4"><Loader2 className="w-8 h-8 text-emerald-500 animate-spin" /></div>
                <p className="text-lg font-medium text-emerald-400">Uploading & Indexing...</p></>
              )}
              {uploadStatus === "success" && (
                <><div className="bg-emerald-900/30 p-4 rounded-full mb-4"><FileUp className="w-8 h-8 text-emerald-400" /></div>
                <p className="text-lg font-medium text-emerald-400">Indexed successfully!</p></>
              )}
              {uploadStatus === "error" && (
                <><div className="bg-red-900/30 p-4 rounded-full mb-4"><AlertCircle className="w-8 h-8 text-red-500" /></div>
                <p className="text-lg font-medium text-red-400">Upload failed</p>
                <p className="text-sm text-zinc-400 mt-2">{uploadError}</p></>
              )}
            </div>
          )}



          {activeTab === "url" && (
            <div className="bg-zinc-950/50 border border-zinc-800 p-6 rounded-xl space-y-6">
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Enter exact URL</label>
                <input 
                  type="url" 
                  value={urlInput} 
                  onChange={e => setUrlInput(e.target.value)} 
                  placeholder="https://en.wikipedia.org/wiki/Vijay_(actor)" 
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-zinc-100 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                />
              </div>
              <button 
                onClick={handleUrlIngest} 
                disabled={urlStatus === "processing" || !urlInput.trim()}
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 rounded-lg flex justify-center items-center gap-2 transition-colors disabled:opacity-50"
              >
                {urlStatus === "processing" ? <><Loader2 className="w-4 h-4 animate-spin" /> Fetching URL in background...</> : "Add to Knowledge Base"}
              </button>
              
              {urlStatus === "success" && (
                <div className="p-3 bg-emerald-950/30 border border-emerald-900 rounded-lg text-emerald-400 flex items-center gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4" /> URL ingestion started! Check the list below for status.
                </div>
              )}
              {urlStatus === "error" && (
                <div className="p-3 bg-red-950/30 border border-red-900 rounded-lg text-red-400 flex items-center gap-2 text-sm">
                  <AlertCircle className="w-4 h-4" /> {urlError}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Document List */}
        <div className="space-y-4 pt-4 border-t border-zinc-800/50">
          <h2 className="text-xl font-semibold text-zinc-200">Knowledge Sources</h2>
          
          {loading ? (
            <div className="flex items-center justify-center p-10 bg-zinc-950/30 border border-zinc-800 rounded-xl">
              <Loader2 className="w-6 h-6 text-zinc-500 animate-spin mr-2" />
              <span className="text-zinc-500">Loading sources...</span>
            </div>
          ) : error ? (
            <div className="flex items-center p-4 bg-red-950/30 border border-red-900 rounded-xl text-red-400">
              <AlertCircle className="w-5 h-5 mr-3" />
              {error}
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center p-12 bg-zinc-950/30 border border-zinc-800 rounded-xl">
              <FileType className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-500">No knowledge sources ingested yet.</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between p-4 bg-zinc-950 border border-zinc-800 rounded-xl hover:border-zinc-700 transition-colors">
                  <div className="flex items-center gap-4 overflow-hidden w-full">
                    <div className="bg-zinc-900 p-2.5 rounded-lg shrink-0">
                      {getSourceIcon(doc.source_type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-zinc-200 truncate">{doc.name}</p>
                        {doc.status === "PROCESSING" && <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-900/50 text-blue-400 font-medium tracking-wide flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin"/> PROCESSING</span>}
                        {doc.status === "COMPLETED" && <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 font-medium tracking-wide">COMPLETED</span>}
                        {doc.status === "FAILED" && <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-900/50 text-red-400 font-medium tracking-wide">FAILED</span>}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-zinc-500 mt-1">
                        <span>{doc.source_type.replace("_", " ")}</span>
                        <span>•</span>
                        <span>{doc.chunk_count} Chunks</span>
                        <span>•</span>
                        <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                  <button 
                    onClick={() => handleDelete(doc.id)}
                    className="p-2 text-zinc-500 hover:text-red-400 hover:bg-red-950/50 rounded-lg transition-colors shrink-0"
                    title="Delete source"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

function GlobeIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>
      <path d="M2 12h20"/>
    </svg>
  );
}
