"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Globe, FileText, ChevronDown, ChevronRight, AlertTriangle, Mic, Volume2, Loader2, X, Check, Play, Pause } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sendChatStream, ChatResponse, SourceItem, generateTTS } from "@/lib/api";
import { usePersona } from "@/components/PersonaProvider";

type MessageRole = "user" | "assistant" | "system";

interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: SourceItem[];
  isError?: boolean;
  audioUrl?: string;
  isGeneratingAudio?: boolean;
  voiceError?: string;
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function SourceDropdown({ sources }: { sources: SourceItem[] }) {
  const [isOpen, setIsOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-4 border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950/50">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 text-sm font-medium text-zinc-300 hover:bg-zinc-900/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isOpen ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
          Sources used ({sources.length})
        </div>
      </button>
      {isOpen && (
        <div className="p-3 border-t border-zinc-800 space-y-3 bg-zinc-950">
          {sources.map((src, i) => (
            <div key={i} className="text-sm bg-zinc-900 p-3 rounded-md border border-zinc-800/80">
              <div className="flex items-center gap-2 mb-2 font-medium text-emerald-400">
                {src.type === "internet" ? <Globe className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                {src.title}
              </div>
              <p className="text-zinc-400 text-xs leading-relaxed line-clamp-3 italic">"{src.content}"</p>
              {src.url && (
                <a href={src.url} target="_blank" rel="noreferrer" className="text-emerald-500 hover:underline text-xs mt-2 block">
                  {src.url}
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I am **PersonaForge AI**. Ask me anything, and I'll search through your knowledge base or the internet to find the answer."
    }
  ]);
  const { activePersona } = usePersona();
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  
  // Voice Output State
  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(false);

  // STT States
  const [isListening, setIsListening] = useState(false);
  const [transcribedText, setTranscribedText] = useState("");
  const [recordingDuration, setRecordingDuration] = useState(0);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  // Audio Playback State
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playbackGenerationRef = useRef(0);
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      playbackGenerationRef.current++;
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    playbackGenerationRef.current++;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingMessageId(null);
    if (activePersona) {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content: `Hello! I am **PersonaForge AI** (${activePersona.name}). Ask me anything, and I'll search through your knowledge base or the internet to find the answer.`
        }
      ]);
    } else {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content: `Hello! I am **PersonaForge AI**. Ask me anything, and I'll search through your knowledge base or the internet to find the answer.`
        }
      ]);
    }
  }, [activePersona]);

  const startListening = () => {
    const SpeechRecognition = typeof window !== "undefined" ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition : null;
    if (!SpeechRecognition) {
      alert("Voice input is not supported in this browser.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = true; // allow continuous listening until accepted/canceled
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        setIsListening(true);
        setTranscribedText("");
        setRecordingDuration(0);
        timerRef.current = setInterval(() => {
            setRecordingDuration(prev => prev + 1);
        }, 1000);
    };
    
    recognition.onresult = (event: any) => {
      let finalTranscript = "";
      let interimTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }
      
      // Update transcribed text smoothly
      setTranscribedText(prev => {
          // If we have final results, replace the old accumulated text with the new complete sentence
          // In this simple setup, we just join everything for the current session.
          const totalTranscript = Array.from(event.results)
              .map((result: any) => result[0].transcript)
              .join('');
          return totalTranscript;
      });
    };

    recognition.onerror = (event: any) => {
      console.error("Speech Recognition Error:", event.error);
      if (event.error === 'network') {
          alert("Network error occurred during speech recognition. Ensure you have an internet connection and your browser supports Web Speech API services.");
      } else if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          alert("Microphone access was denied. Please allow microphone permissions in your browser.");
      }
      cleanupRecording();
    };

    recognition.onend = () => {
        // We only automatically cleanup if we stopped it, otherwise it might have timed out
        // The user might still want to accept it even if it automatically stopped listening.
        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  const cleanupRecording = () => {
      if (recognitionRef.current) {
          recognitionRef.current.stop();
          recognitionRef.current = null;
      }
      if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
      }
      setIsListening(false);
  };

  const cancelRecording = () => {
      cleanupRecording();
      setTranscribedText("");
      setRecordingDuration(0);
  };

  const acceptRecording = () => {
      cleanupRecording();
      // Append or set the input
      setInput(prev => {
          const space = prev.length > 0 && !prev.endsWith(" ") ? " " : "";
          return prev + space + transcribedText;
      });
      setTranscribedText("");
      setRecordingDuration(0);
  };

  const playTTS = async (msgId: string, textContent: string) => {
    const currentGen = ++playbackGenerationRef.current;

    if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
        audioRef.current = null;
    }
    
    setPlayingMessageId(msgId);
    setMessages(prev => prev.map(m => m.id === msgId ? { ...m, isGeneratingAudio: true, voiceError: undefined } : { ...m, isGeneratingAudio: false }));
    
    try {
        const audioUrl = await generateTTS(textContent, activePersona?.id);
        
        if (playbackGenerationRef.current !== currentGen) {
            return;
        }

        setMessages(prev => prev.map(m => m.id === msgId ? { ...m, isGeneratingAudio: false, audioUrl } : m));
        
        const audio = new Audio(audioUrl);
        audioRef.current = audio;
        audio.onended = () => {
            if (playbackGenerationRef.current === currentGen) {
                setPlayingMessageId(null);
            }
        };
        audio.onpause = () => {
            if (playbackGenerationRef.current === currentGen && audioRef.current === audio) {
                setPlayingMessageId(null);
            }
        };
        audio.play();
    } catch (err: any) {
        if (playbackGenerationRef.current !== currentGen) return;
        console.error(err);
        setMessages(prev => prev.map(m => m.id === msgId ? { 
          ...m, 
          isGeneratingAudio: false, 
          voiceError: "Voice generation failed, but the text response is available." 
        } : m));
        setPlayingMessageId(null);
    }
  };

  const pauseTTS = () => {
      playbackGenerationRef.current++;
      if (audioRef.current) {
          audioRef.current.pause();
          audioRef.current.currentTime = 0;
          audioRef.current = null;
      }
      setPlayingMessageId(null);
      setMessages(prev => prev.map(m => ({ ...m, isGeneratingAudio: false })));
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, isStreaming]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || isStreaming || !activePersona) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: trimmed
    };

    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    setIsStreaming(true);

    const assistantMsgId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      sources: []
    }]);

    let finalContent = "";

    try {
      const history = messages
        .filter(m => m.role === "user" || m.role === "assistant")
        .filter(m => m.id !== "welcome")
        .slice(-10)
        .map(m => ({ role: m.role, content: m.content }));

      await sendChatStream(
        activePersona.id,
        trimmed,
        history,
        (token) => {
          setIsLoading(false);
          finalContent += token;
          setMessages(prev => prev.map(m => 
            m.id === assistantMsgId ? { ...m, content: m.content + token } : m
          ));
        },
        (sources) => {
          setMessages(prev => prev.map(m => 
            m.id === assistantMsgId ? { ...m, sources } : m
          ));
        }
      );
      
      // Auto-play TTS if enabled
      if (voiceOutputEnabled && finalContent.trim().length > 0) {
          await playTTS(assistantMsgId, finalContent.trim());
      }
      
    } catch (err: any) {
      setMessages(prev => prev.map(m => 
        m.id === assistantMsgId ? { 
          ...m, 
          role: "system", 
          content: `Unable to generate a response. Please check whether Ollama is running. (${err.message})`, 
          isError: true 
        } : m
      ));
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    if (confirm("Clear the current conversation?")) {
      setMessages([messages[0]]);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 relative">
      {/* Chat Area - Added pb-48 to ensure last message is scrollable above fixed composer */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 pb-56 space-y-6 min-h-0">
        <div className="max-w-3xl mx-auto flex flex-col gap-6 w-full">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-1 ${
                msg.role === "user" ? "bg-emerald-600" : 
                msg.role === "system" ? "bg-red-900/50" : "bg-zinc-800 border border-zinc-700"
              }`}>
                {msg.role === "user" ? <User className="w-5 h-5 text-white" /> : 
                 msg.role === "system" ? <AlertTriangle className="w-4 h-4 text-red-400" /> :
                 <Bot className="w-5 h-5 text-emerald-400" />}
              </div>
              
              {/* Message Bubble */}
              <div className={`max-w-[85%] ${msg.role === "user" ? "bg-zinc-800" : "bg-transparent"} rounded-2xl px-5 py-3.5 ${msg.role === "user" ? "rounded-tr-sm text-zinc-100" : ""}`}>
                {msg.role === "user" ? (
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                ) : (
                  <div className={`markdown-content ${msg.isError ? "text-red-400" : "text-zinc-300"}`}>
                    {msg.content === "" && isLoading ? (
                      <div className="flex items-center gap-1 text-zinc-400 py-1 h-6">
                        <span className="animate-bounce inline-block" style={{ animationDelay: '0ms' }}>●</span>
                        <span className="animate-bounce inline-block" style={{ animationDelay: '150ms' }}>●</span>
                        <span className="animate-bounce inline-block" style={{ animationDelay: '300ms' }}>●</span>
                      </div>
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    )}
                  </div>
                )}
                
                {msg.sources && msg.sources.length > 0 && (
                  <SourceDropdown sources={msg.sources} />
                )}
                
                {msg.role === "assistant" && !msg.isError && msg.content && !isStreaming && (
                    <div className="mt-3 flex flex-col gap-1.5 border-t border-zinc-800/60 pt-2">
                      <div className="flex items-center gap-2">
                        {msg.isGeneratingAudio ? (
                          <span className="text-xs text-zinc-500 flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" /> Generating audio...
                          </span>
                        ) : playingMessageId === msg.id ? (
                          <button onClick={pauseTTS} className="text-xs flex items-center gap-1 text-emerald-400 hover:text-emerald-300 transition-colors font-medium">
                            <Pause className="w-3.5 h-3.5 fill-current" /> Pause
                          </button>
                        ) : (
                          <button onClick={() => playTTS(msg.id, msg.content)} className="text-xs flex items-center gap-1 text-zinc-500 hover:text-emerald-400 transition-colors">
                            {msg.audioUrl ? <Play className="w-3.5 h-3.5 fill-current" /> : <Volume2 className="w-3.5 h-3.5" />} 
                            {msg.audioUrl ? "Replay" : "Listen"}
                          </button>
                        )}
                      </div>
                      {msg.voiceError && (
                        <span className="text-[11px] text-amber-500/90 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 shrink-0" /> {msg.voiceError}
                        </span>
                      )}
                    </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Fixed Input Area */}
      <div className="absolute bottom-0 left-0 right-0 p-4 sm:p-6 bg-zinc-950/90 border-t border-zinc-900/50 backdrop-blur-md z-10">
        <div className="max-w-3xl mx-auto relative flex flex-col gap-2">
          
          {/* Top Bar above composer: Clear Chat & Voice Toggle */}
          <div className="flex justify-between items-center px-1">
             <button 
                onClick={() => setVoiceOutputEnabled(!voiceOutputEnabled)} 
                className={`text-xs px-3 py-1.5 rounded-full border transition-colors flex items-center gap-2 font-medium ${
                    voiceOutputEnabled 
                    ? 'bg-emerald-900/20 text-emerald-400 border-emerald-800/50' 
                    : 'bg-zinc-900/80 text-zinc-400 border-zinc-800 hover:bg-zinc-800'
                }`}
             >
                {voiceOutputEnabled ? <Volume2 className="w-3 h-3"/> : <Volume2 className="w-3 h-3 opacity-50"/>}
                {voiceOutputEnabled ? 'Voice Responses: ON' : 'Voice Responses: OFF'}
             </button>

             {messages.length > 1 && (
               <button onClick={clearChat} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors bg-zinc-900/80 px-3 py-1.5 rounded-full border border-zinc-800 shadow-sm">
                 Clear conversation
               </button>
             )}
          </div>
          
          {/* Main Composer */}
          {isListening ? (
             <div className="bg-zinc-900 border border-red-900/50 rounded-2xl shadow-xl flex flex-col sm:flex-row items-center justify-between p-4 gap-4 ring-1 ring-red-500/20">
                 <div className="flex items-center gap-3 w-full overflow-hidden">
                     <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse shrink-0" />
                     <span className="text-red-400 font-medium shrink-0 font-mono text-sm">{formatDuration(recordingDuration)}</span>
                     <span className="text-zinc-300 text-sm overflow-hidden whitespace-nowrap text-ellipsis border-l border-zinc-800 pl-3">
                         {transcribedText || "Listening..."}
                     </span>
                 </div>
                 <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto justify-end">
                     <button 
                        onClick={cancelRecording} 
                        className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-xl transition-colors flex items-center gap-2"
                     >
                         <X className="w-4 h-4"/> Cancel
                     </button>
                     <button 
                        onClick={acceptRecording} 
                        disabled={!transcribedText}
                        className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-500 rounded-xl transition-colors disabled:opacity-50 disabled:hover:bg-emerald-600 flex items-center gap-2"
                     >
                         <Check className="w-4 h-4"/> Accept
                     </button>
                 </div>
             </div>
          ) : (
             <div className="bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl flex items-end p-2 focus-within:border-emerald-500/50 focus-within:ring-1 focus-within:ring-emerald-500/50 transition-all">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything..."
                  disabled={isLoading}
                  rows={1}
                  className="w-full max-h-48 min-h-[44px] bg-transparent resize-none border-0 focus:ring-0 text-zinc-100 p-3 disabled:opacity-50 outline-none"
                  style={{ overflow: "hidden" }}
                  onInput={(e) => {
                    const target = e.target as HTMLTextAreaElement;
                    target.style.height = "auto";
                    target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
                  }}
                />
                <button
                  onClick={startListening}
                  className={`m-2 p-2 rounded-xl shrink-0 transition-colors bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200`}
                  title="Voice Input"
                >
                  <Mic className="w-5 h-5" />
                </button>
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading || isStreaming || !activePersona}
                  className="my-2 mr-2 p-2 rounded-xl bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-30 disabled:hover:bg-emerald-600 transition-colors shrink-0"
                >
                  <Send className="w-5 h-5" />
                </button>
             </div>
          )}
        </div>
      </div>
    </div>
  );
}
