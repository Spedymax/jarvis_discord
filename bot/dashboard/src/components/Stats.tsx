import { useEffect, useState } from "react";
import { getStats, type Stats } from "../stats";
import RecentList from "./RecentList";

const MEDALS = ["🥇", "🥈", "🥉"];

function Bars({ title, rows }: { title: string; rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="card p-4">
      <div className="mb-3 text-sm font-semibold text-muted">{title}</div>
      {rows.length === 0 ? (
        <div className="text-xs text-muted">—</div>
      ) : (
        rows.map((r, i) => (
          <div key={i} className="mb-2">
            <div className="flex justify-between text-xs">
              <span className="min-w-0 truncate pr-2">{i < 3 ? `${MEDALS[i]} ` : `${i + 1}. `}{r.label}</span>
              <span className="text-muted">{r.value}</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-raised">
              <div className="h-2 rounded-full bg-gradient-to-r from-accent to-accent2" style={{ width: `${(r.value / max) * 100}%` }} />
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
  if (!s) return <div className="text-muted">Загрузка…</div>;
  if (s.total_plays === 0 && s.top_sounds.length === 0) {
    return <div className="card p-8 text-center text-muted">Пока нет данных — статистика копится с момента запуска.</div>;
  }
  return (
    <div className="space-y-4">
      <div className="card flex items-center gap-4 p-5">
        <div className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-5xl font-extrabold text-transparent">{s.total_plays}</div>
        <div className="text-sm text-muted">проигрываний<br />всего</div>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Bars title="Топ треков" rows={s.top_tracks.map((t) => ({ label: `${t.title} — ${t.author ?? "—"}`, value: t.plays }))} />
        <Bars title="Топ реквестеров" rows={s.top_requesters.map((r) => ({ label: r.name, value: r.plays }))} />
        <Bars title="Топ звуков" rows={s.top_sounds.map((x) => ({ label: x.name, value: x.play_count }))} />
      </div>

      {s.by_day.length > 0 && (
        <div className="card p-4">
          <div className="mb-3 text-sm font-semibold text-muted">Проигрывания по дням</div>
          <div className="flex h-32 items-end gap-1">
            {(() => {
              const max = Math.max(1, ...s.by_day.map((d) => d.plays));
              return s.by_day.map((d, i) => (
                <div key={i} className="flex flex-1 flex-col items-center gap-1" title={`${d.date}: ${d.plays}`}>
                  <div className="w-full rounded-t bg-gradient-to-t from-accent to-accent2" style={{ height: `${(d.plays / max) * 100}%` }} />
                  <span className="text-[9px] text-muted">{d.date.slice(5)}</span>
                </div>
              ));
            })()}
          </div>
        </div>
      )}

      <div className="card p-4">
        <div className="mb-2 text-sm font-semibold text-muted">История</div>
        <RecentList guildId={guildId} rows={s.recent} />
      </div>
    </div>
  );
}
