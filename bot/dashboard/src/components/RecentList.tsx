import type { RecentPlay } from "../stats";
import { play } from "../player";
import { IconPlay, IconPlus } from "../icons";

export default function RecentList({ guildId, rows, limit }: { guildId: string; rows: RecentPlay[]; limit?: number }) {
  const items = limit ? rows.slice(0, limit) : rows;
  if (!items.length) return <div className="text-sm text-muted">Пока пусто.</div>;
  const q = (t: RecentPlay) => t.uri || `${t.title} ${t.author ?? ""}`.trim();
  return (
    <ul className="space-y-0.5">
      {items.map((t, i) => (
        <li key={i} className="group flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-raised">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{t.title}</div>
            <div className="truncate text-xs text-muted">{t.author ?? "—"}{t.requester ? ` · ${t.requester}` : ""}</div>
          </div>
          <button className="icon-btn h-7 w-7 opacity-0 group-hover:opacity-100" title="Играть сейчас" onClick={() => play(guildId, q(t), "skip")}><IconPlay className="h-4 w-4" /></button>
          <button className="icon-btn h-7 w-7 opacity-0 group-hover:opacity-100" title="В очередь" onClick={() => play(guildId, q(t), "enqueue")}><IconPlus className="h-4 w-4" /></button>
        </li>
      ))}
    </ul>
  );
}
