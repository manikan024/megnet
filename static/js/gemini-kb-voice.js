import { AudioStreamer, AudioPlayer, requestMicrophoneStream } from "./gemini-media.js";

const ResponseType = {
  AUDIO: "AUDIO",
  SETUP_COMPLETE: "SETUP COMPLETE",
  TOOL_CALL: "TOOL_CALL",
  INPUT_TRANSCRIPTION: "INPUT_TRANSCRIPTION",
  OUTPUT_TRANSCRIPTION: "OUTPUT_TRANSCRIPTION",
  INTERRUPTED: "INTERRUPTED",
  TURN_COMPLETE: "TURN COMPLETE",
  ERROR: "ERROR",
};

class SearchKbTool extends FunctionCallDefinition {
  constructor(apiBase, onLog) {
    super(
      "search_local_kb",
      "Search the local AcmeDesk knowledge base for articles matching the user question.",
      { type: "object", properties: { query: { type: "string", description: "Search query" } } },
      ["query"]
    );
    this.apiBase = apiBase;
    this.onLog = onLog;
  }

  async functionToCall(parameters) {
    const query = parameters?.query || "";
    this.onLog?.("[tool] search_local_kb: " + query);
    const res = await fetch(this.apiBase + "/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 3 }),
    });
    if (!res.ok) throw new Error("KB search failed: HTTP " + res.status);
    const data = await res.json();
    return data.context || JSON.stringify(data.results || []);
  }
}

export function createGeminiVoiceController({ apiBase, log, onStatus }) {
  let client = null;
  let audioStreamer = null;
  let audioPlayer = null;
  let mediaStream = null;
  let connected = false;
  let connecting = false;
  let stopping = false;
  let processing = false;

  async function handleToolCall(toolCallData) {
    const functionResponses = [];
    for (const call of toolCallData?.functionCalls || []) {
      try {
        const result = await client.callFunction(call.name, call.args || {});
        functionResponses.push({ id: call.id, name: call.name, response: { result: result ?? "ok" } });
      } catch (err) {
        functionResponses.push({ id: call.id, name: call.name, response: { error: err.message || String(err) } });
      }
    }
    if (functionResponses.length) client.sendToolResponse(functionResponses);
  }

  function wireClient(sess) {
    client = new GeminiLiveAPI(sess.token, sess.model);
    client.setSystemInstructions(
      "You are AcmeDesk voice assistant grounded in a local knowledge base with "
        + (sess.articles_count || 50)
        + " articles. Always call search_local_kb before answering factual questions. "
        + "Answer concisely in spoken English."
    );
    client.setOutputAudioTranscription(true);
    client.setInputAudioTranscription(true);
    client.addFunction(new SearchKbTool(apiBase, log));

    client.onReceiveResponse = async (message) => {
      if (message.type === ResponseType.AUDIO) {
        onStatus?.("speaking");
        await audioPlayer.play(message.data);
      } else if (message.type === ResponseType.SETUP_COMPLETE) {
        connected = true;
        onStatus?.("ready");
      } else if (message.type === ResponseType.INPUT_TRANSCRIPTION && message.data?.text) {
        log("Heard: " + message.data.text);
      } else if (message.type === ResponseType.OUTPUT_TRANSCRIPTION && message.data?.text) {
        log("Assistant: " + message.data.text);
      } else if (message.type === ResponseType.INTERRUPTED) {
        audioPlayer.interrupt();
        processing = false;
        onStatus?.("ready");
      } else if (message.type === ResponseType.TURN_COMPLETE) {
        processing = false;
        onStatus?.("ready");
      } else if (message.type === ResponseType.TOOL_CALL) {
        log("Searching KB…");
        await handleToolCall(message.data);
      } else if (message.type === ResponseType.ERROR) {
        log("API error: " + (message.data || "unknown"));
      }
    };

    client.onError = (msg) => log("Error: " + msg);
    client.onClose = (event) => {
      if (!connected && !connecting) return;
      log("Connection closed: " + (event?.reason || "code " + (event?.code ?? "?")));
      disconnect();
    };
  }

  /** Connect once when Voice tab opens — mic stays idle until user taps. */
  async function connect() {
    if (connected || connecting) return;
    connecting = true;
    onStatus?.("connecting");

    mediaStream = await requestMicrophoneStream();
    const sessRes = await fetch(apiBase + "/api/live/session", { method: "POST" });
    const sess = await sessRes.json();
    if (!sessRes.ok) throw new Error(sess.message || "Session failed");

    audioPlayer = new AudioPlayer();
    await audioPlayer.init();
    wireClient(sess);

    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Connect timeout")), 20000);
      let settled = false;
      const finish = (fn) => { if (!settled) { settled = true; clearTimeout(timeout); fn(); } };

      client.onOpen = async () => {
        try {
          audioStreamer = new AudioStreamer(client);
          await audioStreamer.startWithStream(mediaStream);
        } catch (e) {
          finish(() => reject(e));
        }
      };

      const prev = client.onReceiveResponse;
      client.onReceiveResponse = async (msg) => {
        await prev(msg);
        if (msg.type === ResponseType.SETUP_COMPLETE) {
          connecting = false;
          finish(resolve);
        }
      };
      client.connect();
    });
  }

  /** Tap mic ON → record. Tap mic OFF → stop mic, send to AI. No silence wait. */
  function toggleMic() {
    if (!connected || connecting || processing) return;

    if (audioStreamer?.isRecording()) {
      const sent = audioStreamer.endRecording();
      if (!sent) {
        log("Too short — hold mic longer and speak.");
        onStatus?.("ready");
        return;
      }
      processing = true;
      onStatus?.("processing");
      log("Mic off — waiting for AI…");
      return;
    }

    audioStreamer.beginRecording();
    onStatus?.("recording");
    log("Mic on — speak now, tap mic again when done.");
  }

  function disconnect() {
    if (stopping) return;
    stopping = true;
    connected = false;
    connecting = false;
    processing = false;
    audioStreamer?.stop();
    audioPlayer?.destroy();
    client?.disconnect();
    audioStreamer = audioPlayer = client = null;
    mediaStream?.getTracks().forEach((t) => t.stop());
    mediaStream = null;
    onStatus?.("idle");
    stopping = false;
  }

  return { connect, toggleMic, disconnect, isConnected: () => connected, isRecording: () => audioStreamer?.isRecording() ?? false };
}
