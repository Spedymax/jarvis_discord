import type { PlayerSnapshot } from "../ws";
import { pause, resume, skip, seek, setVolume, setLoop, shuffle } from "../player";
import { IconPlay, IconPause, IconSkip, IconLoop, IconShuffle, IconVolume } from "../icons";

const fmt = (ms: number) => { const s = Math.floor(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const LOOP_NEXT: Record<string, string> = { off: "track", track: "queue", queue: "off" };

export default function PlayerBar({ guildId, snap, pos, onSnap }: { guildId: string; snap: PlayerSnapshot; pos: number; onSnap: (s: PlayerSnapshot) => void }) {
  const cur = snap.active ? snap.current : null;
  const len = cur?.length_ms || 1;
  const apply = (p: Promise<PlayerSnapshot>) => { p.then(onSnap).catch(() => {}); };
  return (
    <div className="flex h-20 items-center gap-4 border-t border-border bg-surface px-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="h-12 w-12 shrink-0 overflow-hidden rounded bg-gradient-to-br from-accent to-accent2">
          {cur?.artwork && <img src={cur.artwork} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{cur ? cur.title : "Ничего не играет"}</div>
          <div className="truncate text-xs text-muted">{cur?.author ?? ""}</div>
        </div>
      </div>
      <div className="flex flex-[2] flex-col items-center gap-1">
        <div className="flex items-center gap-2">
          <button className="icon-btn" onClick={() => apply(setLoop(guildId, LOOP_NEXT[snap.loop ?? "off"]))} title={`loop: ${snap.loop}`}>
            <IconLoop className={`h-4 w-4 ${snap.loop && snap.loop !== "off" ? "text-accent2" : ""}`} />
          </button>
          <button className="flex h-10 w-10 items-center justify-center rounded-full text-white shadow-[0_0_16px_rgba(255,73,217,0.55)] disabled:opacity-50"
            style={{ background: "var(--accent-grad)" }}
            onClick={() => apply(snap.paused ? resume(guildId) : pause(guildId))} disabled={!cur}>
            {snap.paused ? <IconPlay /> : <IconPause />}
          </button>
          <button className="icon-btn" onClick={() => apply(skip(guildId))} disabled={!cur}><IconSkip className="h-4 w-4" /></button>
          <button className="icon-btn" onClick={() => apply(shuffle(guildId))} title="shuffle"><IconShuffle className="h-4 w-4" /></button>
        </div>
        <div className="flex w-full max-w-md items-center gap-2 text-[11px] text-muted">
          <span>{fmt(pos)}</span>
          <input type="range" min={0} max={len} value={Math.min(pos, len)} disabled={!cur}
            onChange={(e) => apply(seek(guildId, Number(e.target.value)))} className="flex-1 accent-accent2" />
          <span>{fmt(len)}</span>
        </div>
      </div>
      <div className="hidden flex-1 items-center justify-end gap-2 sm:flex">
        <IconVolume className="h-4 w-4 text-muted" />
        <input type="range" min={0} max={150} defaultValue={snap.volume ?? 100}
          onMouseUp={(e) => apply(setVolume(guildId, Number((e.target as HTMLInputElement).value)))} className="w-24 accent-accent2" />
      </div>
    </div>
  );
}
