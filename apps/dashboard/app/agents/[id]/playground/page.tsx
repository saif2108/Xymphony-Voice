"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Mic,
  MicOff,
  PhoneOff,
  Radio,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
  Loader2,
  AlertCircle,
} from "lucide-react";

const API_BASE_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

interface MessageItem {
  id: string;
  sender: "user" | "agent" | "system";
  text: string;
  timestamp: string;
}

interface AgentVersion {
  id: string;
  version_n: number;
  status: string;
  personality: string;
  instructions: string;
}

export default function PlaygroundPage() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id ?? "";

  const [activeVersion, setActiveVersion] = useState<AgentVersion | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [callDuration, setCallDuration] = useState(0);
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [error, setError] = useState("");

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const visualizerRef = useRef<NodeJS.Timeout | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const loadVersions = useCallback(async () => {
    if (!agentId) return;

    try {
      const res = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions`
      );
      if (!res.ok) return;
      const data = await res.json();
      const items: AgentVersion[] = data.items ?? [];
      const published = items.find((v) => v.status === "published");
      const draft = items.find((v) => v.status === "draft");
      setActiveVersion(published ?? draft ?? items[0] ?? null);
    } catch {
      // ignore
    }
  }, [agentId]);

  useEffect(() => {
    void loadVersions();
  }, [loadVersions]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isConnected) {
      timerRef.current = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);

      visualizerRef.current = setInterval(() => {
        setAudioLevel(Math.random() * 0.8 + 0.2);
      }, 150);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      if (visualizerRef.current) clearInterval(visualizerRef.current);
      setCallDuration(0);
      setAudioLevel(0);
      setIsAgentSpeaking(false);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (visualizerRef.current) clearInterval(visualizerRef.current);
    };
  }, [isConnected]);

  function formatTime(seconds: number) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  async function handleConnect() {
    if (isConnected) {
      handleDisconnect();
      return;
    }

    setIsConnecting(true);
    setError("");

    try {
      // 1. Create real backend session
      const sessionPayload: Record<string, unknown> = {
        agent_id: agentId,
        channel: "playground",
      };
      if (activeVersion?.id) {
        sessionPayload.agent_version_id = activeVersion.id;
      }

      const res = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/sessions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sessionPayload),
        }
      );

      if (!res.ok) {
        throw new Error(`Failed to create session (${res.status})`);
      }

      const session = await res.json();
      setSessionId(session.id);
      setIsConnected(true);

      // Add system greeting
      setMessages([
        {
          id: "sys-init",
          sender: "system",
          text: `Session connected (${session.id.slice(0, 8)}...). Agent ready.`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
        {
          id: "agent-greet",
          sender: "agent",
          text: activeVersion?.personality
            ? `Hello! I'm online and ready to assist you.`
            : "Hello! How can I help you today?",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Connection failed");
    } finally {
      setIsConnecting(false);
    }
  }

  function handleDisconnect() {
    setIsConnected(false);
    setMessages((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}`,
        sender: "system",
        text: "Session ended.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  }

  function handleSendMessage(e: React.FormEvent) {
    e.preventDefault();
    const text = inputText.trim();
    if (!text || !isConnected) return;

    const userMsg: MessageItem = {
      id: `usr-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsAgentSpeaking(true);

    // Simulate real-time agent turn response
    setTimeout(() => {
      const agentMsg: MessageItem = {
        id: `agt-${Date.now()}`,
        sender: "agent",
        text: `Understood: "${text}". I have processed your input following the instructions configured for this agent.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, agentMsg]);
      setIsAgentSpeaking(false);
    }, 1200);
  }

  return (
    <div className="flex h-[calc(100vh-120px)] flex-col bg-white">
      {/* Session Header Status */}
      <div className="flex h-14 items-center justify-between border-b border-neutral-200 bg-white px-8">
        <div className="flex items-center gap-3">
          <span className="flex h-2.5 w-2.5 relative">
            {isConnected ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
              </>
            ) : (
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-neutral-300" />
            )}
          </span>

          <span className="text-[13px] font-medium text-neutral-900">
            {isConnected ? "Active Call Session" : "Session Idle"}
          </span>

          {isConnected && (
            <span className="rounded bg-neutral-100 px-2 py-0.5 font-mono text-[11px] text-neutral-600">
              {formatTime(callDuration)}
            </span>
          )}

          {activeVersion && (
            <span className="text-[11px] text-neutral-400">
              · Testing v{activeVersion.version_n || 1} ({activeVersion.status})
            </span>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-1.5 text-[12px] text-red-600">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        <div className="flex items-center gap-3">
          {sessionId && (
            <span className="font-mono text-[10px] text-neutral-400">
              ID: {sessionId.slice(0, 12)}...
            </span>
          )}
        </div>
      </div>

      {/* Main Playground Content */}
      <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[1fr_360px]">
        {/* Left: Chat & Voice Interaction Stream */}
        <div className="flex flex-col border-r border-neutral-200 bg-neutral-50/40">
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-400 shadow-sm">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h3 className="mt-4 text-[15px] font-semibold text-neutral-800">
                  Ready to test agent
                </h3>
                <p className="mt-1 max-w-[340px] text-[12px] text-neutral-500 leading-relaxed">
                  Click connect below to launch a live test session. You can speak or send simulated speech inputs to test instructions and voice turns.
                </p>
              </div>
            ) : (
              messages.map((m) => {
                if (m.sender === "system") {
                  return (
                    <div key={m.id} className="text-center">
                      <span className="rounded-full bg-neutral-200/60 px-3 py-1 text-[10px] font-medium text-neutral-600">
                        {m.text}
                      </span>
                    </div>
                  );
                }

                const isUser = m.sender === "user";

                return (
                  <div
                    key={m.id}
                    className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                  >
                    <div className="flex items-center gap-1.5 mb-1 px-1">
                      <span className="text-[11px] font-medium text-neutral-500 capitalize">
                        {m.sender}
                      </span>
                      <span className="text-[10px] text-neutral-400">
                        {m.timestamp}
                      </span>
                    </div>
                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
                        isUser
                          ? "bg-neutral-950 text-white rounded-br-sm"
                          : "border border-neutral-200 bg-white text-neutral-900 rounded-bl-sm shadow-sm"
                      }`}
                    >
                      {m.text}
                    </div>
                  </div>
                );
              })
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Bottom input bar */}
          <div className="border-t border-neutral-200 bg-white p-4">
            <form onSubmit={handleSendMessage} className="flex items-center gap-3">
              <input
                type="text"
                disabled={!isConnected}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={
                  isConnected
                    ? "Type speech transcript or prompt test..."
                    : "Connect session to start testing..."
                }
                className="h-10 flex-1 rounded-lg border border-neutral-300 bg-white px-3.5 text-[13px] outline-none transition-colors focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100 disabled:bg-neutral-50 disabled:text-neutral-400"
              />

              <button
                type="submit"
                disabled={!isConnected || !inputText.trim()}
                className="flex h-10 w-10 items-center justify-center rounded-lg bg-neutral-950 text-white transition-colors hover:bg-neutral-800 disabled:bg-neutral-200 disabled:text-neutral-400"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right: Audio Controls & Visualizer Panel */}
        <div className="flex flex-col justify-between bg-white p-6">
          <div className="space-y-6">
            <div>
              <h4 className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
                Voice Media Channel
              </h4>
              <p className="mt-1 text-[13px] text-neutral-600">
                LiveKit media transport & VAD turn detection.
              </p>
            </div>

            {/* Audio Waveform Bars */}
            <div className="rounded-xl border border-neutral-200 bg-neutral-50/50 p-6 text-center">
              <p className="mb-4 text-[11px] font-medium text-neutral-500">
                {isConnected
                  ? isAgentSpeaking
                    ? "Agent Speaking..."
                    : "Listening for caller voice..."
                  : "Audio channel disconnected"}
              </p>

              <div className="flex h-14 items-center justify-center gap-1.5">
                {[0.4, 0.7, 1.0, 0.6, 0.8, 0.3, 0.9, 0.5, 0.7, 0.3].map((heightScale, idx) => {
                  const currentHeight = isConnected
                    ? Math.max(6, Math.min(48, audioLevel * heightScale * 48))
                    : 4;

                  return (
                    <div
                      key={idx}
                      style={{ height: `${currentHeight}px` }}
                      className={`w-1.5 rounded-full transition-all duration-150 ${
                        isConnected
                          ? isAgentSpeaking
                            ? "bg-neutral-950"
                            : "bg-emerald-500"
                          : "bg-neutral-200"
                      }`}
                    />
                  );
                })}
              </div>
            </div>

            {/* Live Session Controls */}
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-neutral-200 p-3">
                <span className="text-[12px] font-medium text-neutral-700">
                  Microphone
                </span>
                <button
                  type="button"
                  onClick={() => setIsMuted(!isMuted)}
                  disabled={!isConnected}
                  className={`flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[11px] font-medium transition-colors ${
                    isMuted
                      ? "bg-red-50 text-red-600 border border-red-200"
                      : "bg-neutral-100 text-neutral-700 hover:bg-neutral-200"
                  } disabled:opacity-50`}
                >
                  {isMuted ? (
                    <>
                      <MicOff className="h-3.5 w-3.5" /> Muted
                    </>
                  ) : (
                    <>
                      <Mic className="h-3.5 w-3.5" /> Active
                    </>
                  )}
                </button>
              </div>

              <div className="flex items-center justify-between rounded-lg border border-neutral-200 p-3">
                <span className="text-[12px] font-medium text-neutral-700">
                  Turn Detection (VAD)
                </span>
                <span className="flex items-center gap-1 text-[11px] text-neutral-500">
                  <Radio className="h-3.5 w-3.5 text-emerald-500" /> Auto
                </span>
              </div>
            </div>
          </div>

          {/* Connect / Disconnect Action Button */}
          <div className="pt-6 border-t border-neutral-100">
            <button
              onClick={handleConnect}
              disabled={isConnecting}
              className={`flex h-11 w-full items-center justify-center gap-2 rounded-xl text-[13px] font-medium text-white transition-colors ${
                isConnected
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-neutral-950 hover:bg-neutral-800"
              } disabled:bg-neutral-400`}
            >
              {isConnecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Connecting session...
                </>
              ) : isConnected ? (
                <>
                  <PhoneOff className="h-4 w-4" />
                  Disconnect Session
                </>
              ) : (
                <>
                  <Mic className="h-4 w-4" />
                  Connect Live Session
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
