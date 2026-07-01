"use client";

import { useState, useRef, useCallback } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";

type Status = "idle" | "connecting" | "ready" | "recording" | "processing" | "error";

interface Props {
  onTranscript: (text: string) => void;
}

const API_URL = () =>
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace(/^https:/, "wss:")
    .replace(/^http:/, "ws:");

export function VoiceChat({ onTranscript }: Props) {
  const [status, setStatus] = useState<Status>("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const transcriptRef = useRef("");

  const stopAll = useCallback(() => {
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
  }, []);

  const stopRecording = useCallback(() => {
    setStatus("processing");
    stopAll();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end_turn" }));
    }
  }, [stopAll]);

  const startRecording = useCallback(async () => {
    setStatus("connecting");
    transcriptRef.current = "";

    const wsUrl = `${API_URL()}/voice/stream`;
    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onclose = () => {
      stopAll();
      setStatus("idle");
    };

    socket.onerror = () => {
      stopAll();
      setStatus("error");
      setTimeout(() => setStatus("idle"), 2000);
    };

    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string);
        if (msg.type === "status" && msg.message === "ready") {
          setStatus("recording");
        } else if (msg.type === "transcript") {
          transcriptRef.current += msg.text;
          if (msg.final) {
            const text = transcriptRef.current.trim();
            if (text) onTranscript(text);
            transcriptRef.current = "";
          }
        } else if (msg.type === "turn_complete") {
          const text = transcriptRef.current.trim();
          if (text) {
            onTranscript(text);
            transcriptRef.current = "";
          }
          socket.close();
          setStatus("idle");
        } else if (msg.type === "error") {
          console.error("[voice]", msg.message);
          setStatus("error");
          setTimeout(() => setStatus("idle"), 2000);
        }
      } catch {
        // ignore parse errors
      }
    };

    // Wait for WebSocket open before starting mic
    await new Promise<void>((resolve, reject) => {
      socket.addEventListener("open", () => resolve(), { once: true });
      socket.addEventListener("error", () => reject(new Error("ws error")), { once: true });
    });

    // Start mic capture
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      console.error("[voice] mic access denied", err);
      socket.close();
      setStatus("error");
      setTimeout(() => setStatus("idle"), 2000);
      return;
    }
    streamRef.current = stream;

    const ctx = new AudioContext({ sampleRate: 16000 });
    audioCtxRef.current = ctx;

    await ctx.audioWorklet.addModule("/audio-processor.js");
    const source = ctx.createMediaStreamSource(stream);
    const worklet = new AudioWorkletNode(ctx, "keralty-audio-processor");
    workletNodeRef.current = worklet;

    worklet.port.onmessage = (e) => {
      if (socket.readyState !== WebSocket.OPEN) return;
      const pcmBuffer: ArrayBuffer = e.data;
      const bytes = new Uint8Array(pcmBuffer);
      let binary = "";
      for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
      const b64 = btoa(binary);
      socket.send(JSON.stringify({ type: "audio_chunk", data: b64 }));
    };

    source.connect(worklet);
    // worklet output is silence — no need to connect to destination
  }, [onTranscript, stopAll]);

  const toggle = useCallback(() => {
    if (status === "recording") {
      stopRecording();
    } else if (status === "idle") {
      startRecording().catch((err) => {
        console.error("[voice]", err);
        setStatus("error");
        setTimeout(() => setStatus("idle"), 2000);
      });
    }
  }, [status, startRecording, stopRecording]);

  const isActive = status === "recording";
  const isBusy = status === "connecting" || status === "processing";

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={isBusy}
      title={isActive ? "Detener grabación" : "Hablar con el asistente"}
      className={`p-2 rounded-full transition-all flex items-center justify-center ${
        isActive
          ? "bg-red-500 hover:bg-red-600 text-white animate-pulse"
          : isBusy
          ? "bg-gray-300 text-gray-500 cursor-not-allowed"
          : status === "error"
          ? "bg-orange-400 text-white"
          : "text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary-light)]"
      }`}
    >
      {isBusy ? (
        <Loader2 size={18} className="animate-spin" />
      ) : isActive ? (
        <MicOff size={18} />
      ) : (
        <Mic size={18} />
      )}
    </button>
  );
}
