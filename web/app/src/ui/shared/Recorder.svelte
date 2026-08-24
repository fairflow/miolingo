<script lang="ts">
  // MediaRecorder → one Blob per take (webm/opus on Chrome/Firefox, mp4 on
  // Safari; the oracle ffmpeg-normalizes). Prop-driven so Quick Practice and
  // Story Practice share it; enablement comes ONLY from ready-set props.
  const {
    canRecord,
    canClear,
    busy,
    onBlob,
    onClear,
  }: {
    canRecord: boolean;
    canClear: boolean;
    busy: boolean;
    onBlob: (blob: Blob) => void;
    onClear: () => void;
  } = $props();

  let recording = $state(false);
  let recorder: MediaRecorder | null = null;
  let replayUrl = $state<string | null>(null);
  let micError = $state<string | null>(null);

  function pickMime(): string | undefined {
    for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']) {
      if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return undefined;
  }

  async function start(): Promise<void> {
    micError = null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickMime();
      recorder = new MediaRecorder(stream, mime !== undefined ? { mimeType: mime } : {});
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: recorder?.mimeType ?? 'audio/webm' });
        if (replayUrl !== null) URL.revokeObjectURL(replayUrl);
        replayUrl = URL.createObjectURL(blob);
        onBlob(blob); // recording_made → attempt_made (wired by the caller)
      };
      recorder.start();
      recording = true;
    } catch (e: unknown) {
      micError = `Microphone unavailable: ${String(e)}`;
    }
  }

  function stop(): void {
    recorder?.stop();
    recording = false;
  }

  function clear(): void {
    onClear(); // the clear-then-record re-record idiom
    if (replayUrl !== null) {
      URL.revokeObjectURL(replayUrl);
      replayUrl = null;
    }
  }
</script>

<div class="recorder">
  {#if recording}
    <button class="rec live" onclick={stop}>⏹ Stop</button>
  {:else}
    <button class="rec" onclick={start} disabled={!canRecord || busy}>🎙️ Record</button>
  {/if}
  <button onclick={clear} disabled={!canClear || busy}>↺ Re-record</button>
  {#if replayUrl !== null && canClear}
    <audio src={replayUrl} controls></audio>
  {/if}
  {#if busy}
    <span class="muted">scoring…</span>
  {/if}
  {#if micError !== null}
    <span class="err">{micError}</span>
  {/if}
</div>

<style>
  .recorder {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .rec.live {
    border-color: var(--err);
    color: var(--err);
  }

  audio {
    height: 2rem;
  }

  .err {
    color: var(--err);
    font-size: 0.85rem;
  }
</style>
