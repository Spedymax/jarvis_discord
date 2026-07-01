import { useEffect, useState } from "react";
import type { PlayerSnapshot } from "../ws";
import { getStats, getHistory, type Stats, type RecentPlay } from "../stats";
import { queueClear, leave, setVolume } from "../player";
import { getSounds, playSound } from "../sounds";
import Listeners from "./Listeners";
import RecentList from "./RecentList";
import { IconTrash, IconShuffle, IconVolume } from "../icons";

export default function Overview({ guildId, snapshot, onSnap }: { guildId: string; snapshot: PlayerSnapshot; onSnap: (s: PlayerSnapshot) => void }) {
  const [s, setS] = useState<Stats | null>(null);
  const [history, setHistory] = useState<RecentPlay[] | null>(null);
  useEffect(() => { getStats(guildId).then(setS).catch(() => setS(null)); setHistory(null); }, [guildId]);

  const showAll = () => getHistory(guildId).then(setHistory).catch(() => {});

  const today = new Date().toISOString().slice(0, 10);
  const todayPlays = s?.by_day.find((d) => d.date === today)?.plays ?? 0;
  const topTrack = s?.top_tracks[0];
  const cur = snapshot.active ? snapshot.current : null;

  const randomSound = async () => {
    const list = await getSounds(guildId);
    if (list.length) playSound(guildId, list[Math.floor(Math.random() * list.length)].id);
  };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* now-playing mini */}
      <div className="card flex items-center gap-3 p-4">
        <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-gradient-to-br from-accent to-accent2">
          {cur?.artwork && <img src={cur.artwork} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="min-w-0">
          <div className="text-xs uppercase text-muted">Сейчас играет</div>
          <div className="truncate font-semibold">{cur ? cur.title : "Ничего не играет"}</div>
          <div className="truncate text-sm text-muted">{cur?.author ?? ""}</div>
        </div>
      </div>

      <Listeners guildId={guildId} />

      {/* today */}
      <div className="card p-4">
        <div className="text-sm font-semibold text-muted">Сегодня</div>
        <div className="mt-1 bg-gradient-to-r from-accent to-accent2 bg-clip-text text-3xl font-extrabold text-transparent">{todayPlays}</div>
        <div className="text-xs text-muted">проигрываний</div>
        {topTrack && <div className="mt-2 truncate text-sm">🔥 {topTrack.title} <span className="text-muted">— {topTrack.author ?? "—"}</span></div>}
      </div>

      {/* quick actions */}
      <div className="card p-4">
        <div className="mb-2 text-sm font-semibold text-muted">Быстрые экшены</div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={() => queueClear(guildId).then(onSnap).catch(() => {})}><IconTrash className="h-4 w-4" /> Очистить очередь</button>
          <button className="btn" onClick={() => randomSound()}><IconShuffle className="h-4 w-4" /> Случайный звук</button>
          <button className="btn text-danger" onClick={() => leave(guildId)}>🚪 Выгнать бота</button>
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm text-muted">
          <IconVolume className="h-4 w-4" />
          {[50, 100, 150].map((v) => (
            <button key={v} className="btn px-2 py-1" onClick={() => setVolume(guildId, v).then(onSnap).catch(() => {})}>{v}%</button>
          ))}
        </div>
      </div>

      {/* recent */}
      <div className="card p-4 md:col-span-2">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-semibold text-muted">{history ? "Вся история" : "Недавно играло"}</div>
          {history
            ? <button className="btn px-2 py-1 text-xs" onClick={() => setHistory(null)}>Свернуть</button>
            : <button className="btn px-2 py-1 text-xs" onClick={showAll}>Вся история</button>}
        </div>
        {history
          ? <div className="max-h-96 overflow-y-auto"><RecentList guildId={guildId} rows={history} /></div>
          : <RecentList guildId={guildId} rows={s?.recent ?? []} limit={6} />}
      </div>
    </div>
  );
}
