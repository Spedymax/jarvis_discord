import { useState } from "react";
import type { TrackV } from "../ws";
import { play, search } from "../player";
import { IconSearch, IconPlay, IconPlus } from "../icons";

export default function Search({ guildId }: { guildId: string }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<TrackV[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try { setResults(await search(guildId, q)); } finally { setBusy(false); }
  };

  const doPlay = async (t: TrackV, mode: "skip" | "next" | "enqueue") => {
    try { await play(guildId, t.uri ?? t.title, mode); setMsg(""); }
    catch { setMsg("Зайди в голосовой канал, чтобы играть."); }
  };

  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 rounded-lg bg-raised px-3">
        <IconSearch className="h-4 w-4 text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="Поиск или ссылка YouTube/Spotify…"
          className="flex-1 bg-transparent py-2 text-sm text-text outline-none placeholder:text-muted" />
        <button className="btn-primary px-3 py-1.5" onClick={run} disabled={busy}>{busy ? "…" : "Найти"}</button>
      </div>
      {msg && <div className="mt-2 text-xs text-muted">{msg}</div>}
      {results.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {results.map((t, i) => (
            <li key={`${t.identifier}-${i}`} className="group flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-raised">
              <div className="h-9 w-9 shrink-0 overflow-hidden rounded bg-gradient-to-br from-accent to-accent2">
                {t.artwork && <img src={t.artwork} alt="" className="h-full w-full object-cover" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{t.title}</div>
                <div className="truncate text-xs text-muted">{t.author ?? "—"}</div>
              </div>
              <button className="icon-btn h-8 w-8" title="Играть сейчас" onClick={() => doPlay(t, "skip")}><IconPlay className="h-4 w-4" /></button>
              <button className="btn px-2 py-1 text-xs" title="Следующим" onClick={() => doPlay(t, "next")}>след</button>
              <button className="icon-btn h-8 w-8" title="В очередь" onClick={() => doPlay(t, "enqueue")}><IconPlus className="h-4 w-4" /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
