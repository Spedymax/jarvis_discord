import { useEffect, useRef, useState } from "react";
import type { PlayerSnapshot } from "../ws";
import { pause, resume, skip, stop, shuffle, seek, setLoop } from "../player";
import { IconPlay, IconPause, IconSkip, IconStop, IconLoop, IconShuffle } from "../icons";

const LOOP_NEXT: Record<string, string> = { off: "track", track: "queue", queue: "off" };
const fmt = (ms: number) => { const s = Math.floor(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

export default function NowPlaying({ guildId, snapshot, onSnap }: { guildId: string; snapshot: PlayerSnapshot; onSnap: (s: PlayerSnapshot) => void }) {
  const [pos, setPos] = useState(0);
  const base = useRef({ ms: 0, at: 0 });
  const apply = (p: Promise<PlayerSnapshot>) => { p.then(onSnap).catch(() => {}); };

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
    return (
      <div className="card grid place-items-center p-12 text-center">
        <div className="text-4xl">🎧</div>
        <div className="mt-3 font-semibold">Ничего не играет</div>
        <div className="text-sm text-muted">Найди трек ниже или запусти музыку в Discord.</div>
      </div>
    );
  }

  const cur = snapshot.current;
  const len = cur.length_ms || 1;
  const pct = Math.min(100, (pos / len) * 100);

  return (
    <div className="card relative overflow-hidden p-6">
      {/* ambient blurred artwork */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-accent/30 to-accent2/20" />
      {cur.artwork && (
        <div className="absolute inset-0 -z-10 scale-110 bg-cover bg-center opacity-25 blur-2xl"
          style={{ backgroundImage: `url(${cur.artwork})` }} />
      )}
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <div className="h-40 w-40 shrink-0 overflow-hidden rounded-xl bg-gradient-to-br from-accent to-accent2 shadow-panel">
          {cur.artwork && <img src={cur.artwork} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-wide text-muted">Сейчас играет</div>
          <div className="mt-1 truncate text-2xl font-bold">{cur.title}</div>
          <div className="truncate text-muted">{cur.author ?? "—"}</div>
          {cur.requester && <div className="mt-2 inline-block rounded-full bg-raised px-2 py-0.5 text-xs text-muted">по запросу {cur.requester}</div>}

          <div className="mt-4">
            <div className="relative h-1.5 w-full rounded-full bg-raised">
              <div className="absolute h-1.5 rounded-full bg-gradient-to-r from-accent to-accent2" style={{ width: `${pct}%` }} />
              <input type="range" min={0} max={len} value={Math.min(pos, len)}
                onChange={(e) => apply(seek(guildId, Number(e.target.value)))}
                className="absolute -top-1.5 h-4 w-full cursor-pointer opacity-0" />
            </div>
            <div className="mt-1 flex justify-between text-xs text-muted">
              <span>{fmt(pos)}</span><span>{fmt(len)}</span>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2">
            <button className="icon-btn" onClick={() => apply(setLoop(guildId, LOOP_NEXT[snapshot.loop ?? "off"]))} title={`loop: ${snapshot.loop}`}>
              <IconLoop className={`h-5 w-5 ${snapshot.loop !== "off" ? "text-accent2" : ""}`} />
            </button>
            <button className="flex h-12 w-12 items-center justify-center rounded-full text-white shadow-[0_0_18px_rgba(255,73,217,0.6)]" style={{ background: "var(--accent-grad)" }}
              onClick={() => apply(snapshot.paused ? resume(guildId) : pause(guildId))}>
              {snapshot.paused ? <IconPlay className="h-6 w-6" /> : <IconPause className="h-6 w-6" />}
            </button>
            <button className="icon-btn" onClick={() => apply(skip(guildId))}><IconSkip /></button>
            <button className="icon-btn" onClick={() => apply(shuffle(guildId))} title="shuffle"><IconShuffle /></button>
            <button className="icon-btn text-danger hover:text-danger" onClick={() => apply(stop(guildId))} title="stop"><IconStop /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
