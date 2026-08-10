"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, Database, Server, Cpu, Layers, Mic } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { useEffect, useState } from "react";
import { checkHealth } from "@/lib/api";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

import { usePersona } from "@/components/PersonaProvider";
import { Plus, Trash2, CheckCircle2 } from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const { personas, activePersona, setActivePersona, createNewPersona, removePersona, isLoading } = usePersona();
  const [isCreating, setIsCreating] = useState(false);
  const [newPersonaName, setNewPersonaName] = useState("");

  useEffect(() => {
    let mounted = true;
    const checkStatus = async () => {
      const isOnline = await checkHealth();
      if (mounted) setIsBackendOnline(isOnline);
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000); // Check every 30s
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { name: "Chat", href: "/", icon: MessageSquare },
    { name: "Knowledge Base", href: "/knowledge", icon: Database },
    { name: "Voice Settings", href: "/voice", icon: Mic },
  ];

  const handleCreate = async () => {
    if (!newPersonaName.trim()) return;
    await createNewPersona(newPersonaName);
    setNewPersonaName("");
    setIsCreating(false);
  };

  return (
    <div className="flex flex-col w-64 bg-zinc-950 border-r border-zinc-800 text-zinc-100 h-screen overflow-y-auto">
      <div className="p-6 flex items-center gap-3 border-b border-zinc-800/50">
        <div className="bg-emerald-600 p-2 rounded-lg">
          <Layers className="w-5 h-5 text-white" />
        </div>
        <h1 className="font-semibold text-lg tracking-tight">PersonaForge</h1>
      </div>
      
      <div className="p-4 border-b border-zinc-800/50">
        <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Active Persona</div>
        
        {isLoading ? (
           <div className="text-sm text-zinc-500 animate-pulse">Loading...</div>
        ) : (
          <div className="space-y-2">
            <select
              className="w-full bg-zinc-900 border border-zinc-800 rounded-md p-2 text-sm text-zinc-200 focus:ring-1 focus:ring-emerald-500 outline-none"
              value={activePersona?.id || ""}
              onChange={(e) => {
                const found = personas.find(p => p.id === e.target.value);
                setActivePersona(found || null);
              }}
            >
              <option value="" disabled>Select a Persona</option>
              {personas.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            
            {!isCreating ? (
              <button 
                onClick={() => setIsCreating(true)}
                className="w-full flex items-center justify-center gap-2 py-1.5 text-xs text-zinc-400 hover:text-emerald-400 border border-dashed border-zinc-700 hover:border-emerald-500 rounded transition-colors"
              >
                <Plus className="w-3.5 h-3.5" /> New Persona
              </button>
            ) : (
              <div className="flex gap-2 items-center mt-2">
                <input 
                  type="text" 
                  autoFocus
                  placeholder="Name..." 
                  className="flex-1 bg-zinc-900 border border-zinc-700 text-xs p-1.5 rounded"
                  value={newPersonaName}
                  onChange={e => setNewPersonaName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleCreate()}
                />
                <button onClick={handleCreate} className="p-1.5 bg-emerald-600/20 text-emerald-500 rounded hover:bg-emerald-600/40">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            
            {activePersona && (
              <div className="flex justify-end pt-1">
                <button 
                  onClick={() => confirm(`Delete persona ${activePersona.name}?`) && removePersona(activePersona.id)}
                  className="text-xs flex items-center gap-1 text-red-500/70 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="w-3 h-3" /> Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <nav className="flex-1 px-4 py-6 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors text-sm font-medium",
                isActive 
                  ? "bg-zinc-800/80 text-white" 
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50"
              )}
            >
              <item.icon className={cn("w-4 h-4", isActive ? "text-emerald-400" : "text-zinc-500")} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-zinc-800/50 space-y-3">
        <div className="flex items-center justify-between px-2 text-xs">
          <div className="flex items-center gap-2 text-zinc-400">
            <Server className="w-3.5 h-3.5" />
            <span>Backend</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div 
              className={cn(
                "w-2 h-2 rounded-full",
                isBackendOnline === true ? "bg-emerald-500" : 
                isBackendOnline === false ? "bg-red-500" : "bg-zinc-600 animate-pulse"
              )} 
            />
            <span className="text-zinc-300 font-medium">
              {isBackendOnline === true ? "Online" : isBackendOnline === false ? "Offline" : "Checking..."}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between px-2 text-xs">
          <div className="flex items-center gap-2 text-zinc-400">
            <Cpu className="w-3.5 h-3.5" />
            <span>Ollama</span>
          </div>
          <div className="flex items-center gap-1.5">
            {/* If backend is online, we assume Ollama is reachable for now. A deeper health check could be implemented on backend. */}
            <div 
              className={cn(
                "w-2 h-2 rounded-full",
                isBackendOnline === true ? "bg-emerald-500" : 
                isBackendOnline === false ? "bg-red-500" : "bg-zinc-600 animate-pulse"
              )} 
            />
            <span className="text-zinc-300 font-medium">
              {isBackendOnline === true ? "Ready" : isBackendOnline === false ? "Offline" : "Checking..."}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
