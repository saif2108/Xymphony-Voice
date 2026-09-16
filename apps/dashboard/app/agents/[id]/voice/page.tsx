"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Volume2, Mic, Sliders } from "lucide-react";

const API_BASE_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

const ELEVENLABS_PRESET_VOICES = [
  { id: "voice_default", name: "Default Voice", gender: "Neutral", style: "Conversational" },
  { id: "21m00Tcm4TlvDq8ikWAM", name: "Rachel", gender: "Female", style: "Calm & Professional" },
  { id: "ErXwobaYiN019PkySvjV", name: "Antoni", gender: "Male", style: "Warm & Engaging" },
  { id: "pNInz6obpgDQGcFmaJgB", name: "Adam", gender: "Male", style: "Deep & Authoritative" },
  { id: "EXAVITQu4vr4xnSDxMaL", name: "Bella", gender: "Female", style: "Dynamic & Friendly" },
  { id: "yoZ06aMxZJJ28mfd3POQ", name: "Sam", gender: "Male", style: "Casual & Approachable" },
];

type AgentVersion = {
  id: string;
  status: string;
  instructions: string;
  personality: string;
  locale: string;
  llm?: {
    provider_key?: string;
    model?: string;
    params?: Record<string, unknown>;
  };
  stt?: {
    provider_key?: string;
    model?: string;
    params?: Record<string, unknown>;
  };
  tts?: {
    provider_key?: string;
    voice_ref?: string;
    params?: Record<string, unknown>;
  };
};

export default function VoicePage() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id ?? "";

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [currentVersion, setCurrentVersion] = useState<AgentVersion | null>(null);

  // Form state
  const [sttProvider, setSttProvider] = useState("assemblyai");
  const [sttModel, setSttModel] = useState("universal-streaming");
  const [ttsProvider, setTtsProvider] = useState("elevenlabs");
  const [ttsVoice, setTtsVoice] = useState("voice_default");
  const [customVoice, setCustomVoice] = useState("");
  const [ttsModelId, setTtsModelId] = useState("eleven_flash_v2");
  const [outputFormat, setOutputFormat] = useState("pcm_16000");

  const loadData = useCallback(async () => {
    if (!agentId) return;

    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions`
      );

      if (!response.ok) {
        throw new Error(`Unable to load voice config (${response.status})`);
      }

      const data: { items?: AgentVersion[] } = await response.json();
      const version =
        data.items?.find((v) => v.status === "draft") ?? data.items?.[0] ?? null;

      if (version) {
        setCurrentVersion(version);
        if (version.stt?.provider_key) setSttProvider(version.stt.provider_key);
        if (version.stt?.model) setSttModel(version.stt.model);
        if (version.tts?.provider_key) setTtsProvider(version.tts.provider_key);
        if (version.tts?.voice_ref) {
          setTtsVoice(version.tts.voice_ref);
          const isPreset = ELEVENLABS_PRESET_VOICES.some(
            (v) => v.id === version.tts?.voice_ref
          );
          if (!isPreset && version.tts.voice_ref !== "voice_default") {
            setCustomVoice(version.tts.voice_ref);
          }
        }
        if (version.tts?.params?.model_id && typeof version.tts.params.model_id === "string") {
          setTtsModelId(version.tts.params.model_id);
        }
        if (version.tts?.params?.output_format && typeof version.tts.params.output_format === "string") {
          setOutputFormat(version.tts.params.output_format);
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Error loading configuration");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!agentId) return;

    setSaving(true);
    setError("");
    setSuccess("");

    const effectiveVoiceRef = customVoice.trim() ? customVoice.trim() : ttsVoice;

    const ttsParams: Record<string, unknown> = {};
    if (ttsModelId.trim()) ttsParams.model_id = ttsModelId.trim();
    if (outputFormat.trim()) ttsParams.output_format = outputFormat.trim();

    try {
      if (currentVersion?.id && currentVersion.status === "draft") {
        // Patch draft version
        const response = await fetch(
          `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions/${currentVersion.id}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              stt: {
                provider_key: sttProvider,
                model: sttModel.trim(),
                params: {},
              },
              tts: {
                provider_key: ttsProvider,
                voice_ref: effectiveVoiceRef,
                params: ttsParams,
              },
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to update voice configuration (${response.status})`);
        }
      } else {
        // Create new draft version
        const response = await fetch(
          `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              instructions: currentVersion?.instructions || "You are a helpful voice assistant.",
              personality: currentVersion?.personality || "Clear and professional.",
              locale: currentVersion?.locale || "en",
              llm: currentVersion?.llm ?? {
                provider_key: "openai",
                model: "gpt-4o-mini",
                params: {},
              },
              stt: {
                provider_key: sttProvider,
                model: sttModel.trim(),
                params: {},
              },
              tts: {
                provider_key: ttsProvider,
                voice_ref: effectiveVoiceRef,
                params: ttsParams,
              },
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to create version (${response.status})`);
        }
      }

      await loadData();
      setSuccess("Voice configuration saved to draft.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save voice configuration");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-10">
      <div className="mb-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
          Agent configuration
        </p>
        <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.03em]">
          Voice & Speech
        </h2>
        <p className="mt-1 text-[13px] text-neutral-500">
          Configure real-time speech recognition and text-to-speech providers for this agent.
        </p>
      </div>

      {loading && (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-12 text-center text-[12px] text-neutral-500">
          Loading voice settings...
        </div>
      )}

      {error && !loading && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[12px] text-red-700">
          {error}
        </div>
      )}

      {!loading && (
        <form onSubmit={handleSave} className="space-y-6">
          {/* TTS Card */}
          <div className="rounded-xl border border-neutral-200 bg-white p-6 sm:p-8">
            <div className="mb-6 flex items-center gap-3 border-b border-neutral-100 pb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50">
                <Volume2 className="h-4 w-4 text-neutral-700" />
              </div>
              <div>
                <h3 className="text-[15px] font-semibold text-neutral-900">
                  Text-to-Speech (TTS)
                </h3>
                <p className="text-[12px] text-neutral-500">
                  Controls how the agent speaks and sounds during live voice calls.
                </p>
              </div>
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  TTS Provider
                </label>
                <select
                  value={ttsProvider}
                  onChange={(e) => setTtsProvider(e.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                >
                  <option value="elevenlabs">ElevenLabs (Streaming)</option>
                </select>
                <p className="mt-1.5 text-[11px] text-neutral-400">
                  High-fidelity neural streaming synthesis.
                </p>
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  Model ID
                </label>
                <select
                  value={ttsModelId}
                  onChange={(e) => setTtsModelId(e.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                >
                  <option value="eleven_flash_v2">eleven_flash_v2 (Ultra-low latency)</option>
                  <option value="eleven_turbo_v2_5">eleven_turbo_v2_5 (Balanced)</option>
                  <option value="eleven_multilingual_v2">eleven_multilingual_v2 (Multi-language)</option>
                </select>
              </div>
            </div>

            {/* Voices Grid */}
            <div className="mt-6">
              <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                Select Voice Preset
              </label>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {ELEVENLABS_PRESET_VOICES.map((preset) => {
                  const isSelected = ttsVoice === preset.id && !customVoice.trim();
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => {
                        setTtsVoice(preset.id);
                        setCustomVoice("");
                      }}
                      className={`flex flex-col items-start rounded-lg border p-3.5 text-left transition-all ${
                        isSelected
                          ? "border-neutral-950 bg-neutral-50 ring-1 ring-neutral-950"
                          : "border-neutral-200 bg-white hover:border-neutral-300 hover:bg-neutral-50/50"
                      }`}
                    >
                      <div className="flex w-full items-center justify-between">
                        <span className="text-[13px] font-medium text-neutral-900">
                          {preset.name}
                        </span>
                        <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[10px] text-neutral-600">
                          {preset.gender}
                        </span>
                      </div>
                      <span className="mt-1 text-[11px] text-neutral-400">
                        {preset.style}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Custom Voice Ref */}
            <div className="mt-5">
              <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                Custom ElevenLabs Voice ID (Optional)
              </label>
              <input
                type="text"
                placeholder="Enter custom ElevenLabs Voice ID..."
                value={customVoice}
                onChange={(e) => setCustomVoice(e.target.value)}
                className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] font-mono outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
              />
              <p className="mt-1.5 text-[11px] text-neutral-400">
                Provide a custom ElevenLabs Voice ID from your ElevenLabs Voice Lab if you wish to override presets.
              </p>
            </div>

            <div className="mt-5 border-t border-neutral-100 pt-4">
              <div className="flex items-center gap-2">
                <Sliders className="h-3.5 w-3.5 text-neutral-400" />
                <span className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider">
                  Audio Output Format:
                </span>
                <span className="text-[11px] font-mono text-neutral-700">
                  {outputFormat} (16kHz 16-bit PCM for LiveKit bridge)
                </span>
              </div>
            </div>
          </div>

          {/* STT Card */}
          <div className="rounded-xl border border-neutral-200 bg-white p-6 sm:p-8">
            <div className="mb-6 flex items-center gap-3 border-b border-neutral-100 pb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50">
                <Mic className="h-4 w-4 text-neutral-700" />
              </div>
              <div>
                <h3 className="text-[15px] font-semibold text-neutral-900">
                  Speech-to-Text (STT)
                </h3>
                <p className="text-[12px] text-neutral-500">
                  Real-time streaming transcription of caller audio.
                </p>
              </div>
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  STT Provider
                </label>
                <select
                  value={sttProvider}
                  onChange={(e) => setSttProvider(e.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                >
                  <option value="assemblyai">AssemblyAI (Streaming)</option>
                </select>
                <p className="mt-1.5 text-[11px] text-neutral-400">
                  Low-latency streaming speech recognition adapter.
                </p>
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  Model
                </label>
                <input
                  type="text"
                  value={sttModel}
                  onChange={(e) => setSttModel(e.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
                <p className="mt-1.5 text-[11px] text-neutral-400">
                  Default model: <code className="font-mono">universal-streaming</code>
                </p>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-4">
            <div className="text-[12px]">
              {success && (
                <span className="inline-flex items-center gap-2 text-emerald-600">
                  <CheckCircle2 className="h-4 w-4" />
                  {success}
                </span>
              )}
            </div>

            <button
              type="submit"
              disabled={saving}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-neutral-950 px-4 text-[12px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save voice settings"
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
