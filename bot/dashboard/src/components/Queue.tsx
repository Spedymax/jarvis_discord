import { useRef } from "react";
import type { PlayerSnapshot } from "../ws";
import { queueJump, queueMove, queueRemove } from "../player";
import { IconDrag, IconPlay, IconTrash } from "../icons";

const fmt = (ms: number) => { const s = Math.floor(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

export default function Queue({ guildId, snapshot }: { guildId: string; snapshot: PlayerSnapshot }) {
  const dragFrom = useRef<number | null>(null);
  const queue = snapshot.queue ?? [];

  return (
    <div className="card p-2">
      <div className="px-3 py-2 text-sm font-semibold text-muted">Очередь · {queue.length}</div>
      {queue.length === 0 ? (
        <div className="px-3 pb-3 text-sm text-muted">Очередь пуста.</div>
      ) : (
        <ul className="space-y-0.5">
          {queue.map((t, i) => (
            <li
              key={`${t.identifier}-${i}`}
              draggable
              onDragStart={() => (dragFrom.current = i)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => {
                if (dragFrom.current !== null && dragFrom.current !== i) queueMove(guildId, dragFrom.current, i);
                dragFrom.current = null;
              }}
              className="group flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-raised"
            >
              <span className="cursor-grab text-muted opacity-0 transition-opacity group-hover:opacity-100"><IconDrag className="h-4 w-4" /></span>
              <span className="w-5 text-right text-xs text-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{t.title}</div>
                <div className="truncate text-xs text-muted">{t.author ?? "—"}</div>
              </div>
              <span className="text-xs text-muted">{fmt(t.length_ms)}</span>
              <button className="icon-btn h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100" title="Играть сейчас" onClick={() => queueJump(guildId, i)}><IconPlay className="h-4 w-4" /></button>
              <button className="icon-btn h-8 w-8 text-muted opacity-0 transition-opacity hover:text-danger group-hover:opacity-100" title="Удалить" onClick={() => queueRemove(guildId, i)}><IconTrash className="h-4 w-4" /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
