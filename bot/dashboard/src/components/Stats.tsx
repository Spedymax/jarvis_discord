import { useEffect, useState } from "react";
import { getStats, type Stats } from "../stats";

function Bars({ title, rows }: { title: string; rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="mb-4">
      <div className="mb-2 text-sm font-semibold text-discord-muted">{title}</div>
      {rows.length === 0 ? (
        <div className="text-xs text-discord-muted">—</div>
      ) : (
        rows.map((r, i) => (
          <div key={i} className="mb-1">
            <div className="flex justify-between text-xs">
              <span className="min-w-0 truncate pr-2">{r.label}</span>
              <span className="text-discord-muted">{r.value}</span>
            </div>
            <div className="h-2 rounded bg-discord-dark">
              <div className="h-2 rounded bg-discord-blurple" style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default function Stats({ guildId }: { guildId: string }) {
  const [s, setS] = useState<Stats | null>(null);
  useEffect(() => { getStats(guildId).then(setS).catch(() => setS(null)); }, [guildId]);
  if (!s) return <div className="mt-4 text-discord-muted">Загрузка…</div>;
  if (s.total_plays === 0 && s.top_sounds.length === 0) {
    return <div className="mt-4 rounded-lg bg-discord-card p-6 text-discord-muted">Пока нет данных — статистика копится с момента запуска.</div>;
  }
  return (
    <div className="mt-4 rounded-lg bg-discord-card p-4">
      <div className="mb-4 text-lg font-bold">🎵 {s.total_plays} проигрываний всего</div>
      <Bars title="Топ треков" rows={s.top_tracks.map((t) => ({ label: `${t.title} — ${t.author ?? "—"}`, value: t.plays }))} />
      <Bars title="Топ реквестеров" rows={s.top_requesters.map((r) => ({ label: r.name, value: r.plays }))} />
      <Bars title="Топ звуков" rows={s.top_sounds.map((x) => ({ label: x.name, value: x.play_count }))} />
    </div>
  );
}
