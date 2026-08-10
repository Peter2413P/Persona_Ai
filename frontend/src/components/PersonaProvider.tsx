"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { getPersonas, createPersona, PersonaResponse, deletePersona } from "@/lib/api";

interface PersonaContextType {
  personas: PersonaResponse[];
  activePersona: PersonaResponse | null;
  setActivePersona: (persona: PersonaResponse | null) => void;
  createNewPersona: (name: string) => Promise<void>;
  removePersona: (id: string) => Promise<void>;
  isLoading: boolean;
}

const PersonaContext = createContext<PersonaContextType | undefined>(undefined);

export function PersonaProvider({ children }: { children: React.ReactNode }) {
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [activePersona, setActivePersona] = useState<PersonaResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchPersonas();
  }, []);

  const fetchPersonas = async () => {
    try {
      setIsLoading(true);
      const data = await getPersonas();
      setPersonas(data);
      
      const savedId = localStorage.getItem("activePersonaId");
      if (savedId) {
        const found = data.find((p) => p.id === savedId);
        if (found) {
          setActivePersona(found);
        } else if (data.length > 0) {
          handleSetActive(data[0]);
        }
      } else if (data.length > 0) {
        handleSetActive(data[0]);
      }
    } catch (e) {
      console.error("Failed to fetch personas", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSetActive = (persona: PersonaResponse | null) => {
    setActivePersona(persona);
    if (persona) {
      localStorage.setItem("activePersonaId", persona.id);
    } else {
      localStorage.removeItem("activePersonaId");
    }
  };

  const createNewPersona = async (name: string) => {
    try {
      const newPersona = await createPersona(name);
      setPersonas((prev) => [newPersona, ...prev]);
      handleSetActive(newPersona);
    } catch (e) {
      console.error("Failed to create persona", e);
      throw e;
    }
  };

  const removePersona = async (id: string) => {
    try {
      await deletePersona(id);
      setPersonas((prev) => prev.filter((p) => p.id !== id));
      if (activePersona?.id === id) {
        handleSetActive(null);
      }
    } catch (e) {
      console.error("Failed to delete persona", e);
      throw e;
    }
  };

  return (
    <PersonaContext.Provider value={{
      personas,
      activePersona,
      setActivePersona: handleSetActive,
      createNewPersona,
      removePersona,
      isLoading
    }}>
      {children}
    </PersonaContext.Provider>
  );
}

export function usePersona() {
  const context = useContext(PersonaContext);
  if (context === undefined) {
    throw new Error("usePersona must be used within a PersonaProvider");
  }
  return context;
}
