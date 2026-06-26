"use client";
import { useState, useRef } from "react";
import { Mic, MicOff } from "lucide-react";

export function VoiceChat() {
  const [isRecording, setIsRecording] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  const toggleRecording = () => {
    if (isRecording) {
      setIsRecording(false);
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
    } else {
      setIsRecording(true);
      const wsUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace('http', 'ws');
      try {
        ws.current = new WebSocket(`${wsUrl}/voice/stream`);
        ws.current.onmessage = (event) => {
          console.log("Received voice data", event.data);
          // Play audio back using AudioContext in a full implementation
        };
        // Setup MediaRecorder and send chunks here
      } catch (err) {
        console.error("Failed to connect to voice stream", err);
        setIsRecording(false);
      }
    }
  };

  return (
    <button 
      onClick={toggleRecording}
      className={`p-3 rounded-full flex items-center justify-center transition-colors shadow-lg ${
        isRecording ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse' : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white'
      }`}
      title={isRecording ? "Stop listening" : "Start speaking"}
    >
      {isRecording ? <MicOff size={24} /> : <Mic size={24} />}
    </button>
  );
}
