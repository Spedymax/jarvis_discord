import { useState } from "react";
import type { TrackV } from "../ws";
import { play, search } from "../player";

export default function Search({ guildId }: { guildId: string }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<TrackV[]>([]);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try {
      setResults(await search(guildId, q));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6">
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="Поиск или ссылка YouTube/Spotify…"
          className="flex-1 rounded bg-discord-card p-2 text-discord-text" />
        <button className="btn" onClick={run} disabled={busy}>{busy ? "…" : "🔍"}</button>
      </div>
      <ul className="mt-2 space-y-1">
        {results.map((t, i) => (
          <li key={`${t.identifier}-${i}`} className="flex items-center gap-2 rounded bg-discord-card px-3 py-2 text-sm">
            <span className="min-w-0 flex-1 truncate">{t.title} <span className="text-discord-muted">— {t.author}</span></span>
            <button className="btn" title="Играть сейчас" onClick={() => play(guildId, t.uri ?? t.title, "skip")}>▶️</button>
            <button className="btn" title="Следующим" onClick={() => play(guildId, t.uri ?? t.title, "next")}>⤵️</button>
            <button className="btn" title="В очередь" onClick={() => play(guildId, t.uri ?? t.title, "enqueue")}>➕</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
