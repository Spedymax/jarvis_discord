import { useEffect, useRef, useState } from "react";
import type { PlayerSnapshot } from "../ws";
import { pause, resume, skip, stop, shuffle, seek, setVolume, setLoop } from "../player";

const LOOP_NEXT: Record<string, string> = { off: "track", track: "queue", queue: "off" };
const fmt = (ms: number) => {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export default function NowPlaying({ guildId, snapshot }: { guildId: string; snapshot: PlayerSnapshot }) {
  const [pos, setPos] = useState(0);
  const base = useRef({ ms: 0, at: 0 });

  useEffect(() => {
    base.current = { ms: snapshot.position_ms ?? 0, at: Date.now() };
    setPos(snapshot.position_ms ?? 0);
  }, [snapshot.position_ms, snapshot.current?.identifier]);

  useEffect(() => {
    if (snapshot.paused || !snapshot.active) return;
    const id = setInterval(() => setPos(base.current.ms + (Date.now() - base.current.at)), 500);
    return () => clearInterval(id);
  }, [snapshot.paused, snapshot.active, snapshot.current?.identifier]);

  if (!snapshot.active || !snapshot.current) {
    return <div className="rounded-lg bg-discord-card p-6 text-discord-muted">Бот сейчас не играет.</div>;
  }
  const cur = snapshot.current;
  const len = cur.length_ms || 1;

  return (
    <div className="rounded-lg bg-discord-card p-4">
      <div className="flex gap-4">
        {cur.artwork ? (
          <img src={cur.artwork} alt="" className="h-24 w-24 rounded object-cover" />
        ) : (
          <div className="flex h-24 w-24 items-center justify-center rounded bg-discord-dark text-2xl">🎵</div>
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate text-lg font-semibold">{cur.title}</div>
          <div className="truncate text-sm text-discord-muted">{cur.author}</div>
          <div className="mt-3">
            <input type="range" min={0} max={len} value={Math.min(pos, len)}
              onChange={(e) => seek(guildId, Number(e.target.value))} className="w-full" />
            <div className="flex justify-between text-xs text-discord-muted">
              <span>{fmt(pos)}</span><span>{fmt(len)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button className="btn" onClick={() => (snapshot.paused ? resume(guildId) : pause(guildId))}>
          {snapshot.paused ? "▶️" : "⏸️"}
        </button>
        <button className="btn" onClick={() => skip(guildId)}>⏭️</button>
        <button className="btn" onClick={() => stop(guildId)}>⏹️</button>
        <button className="btn" onClick={() => setLoop(guildId, LOOP_NEXT[snapshot.loop ?? "off"])}>
          🔁 {snapshot.loop}
        </button>
        <button className="btn" onClick={() => shuffle(guildId)}>🔀</button>
        <label className="ml-auto flex items-center gap-2 text-sm text-discord-muted">
          🔊
          <input type="range" min={0} max={150} defaultValue={snapshot.volume ?? 100}
            onMouseUp={(e) => setVolume(guildId, Number((e.target as HTMLInputElement).value))} />
        </label>
      </div>
    </div>
  );
}
