import { useRef } from "react";
import type { PlayerSnapshot } from "../ws";
import { queueJump, queueMove, queueRemove } from "../player";

export default function Queue({ guildId, snapshot }: { guildId: string; snapshot: PlayerSnapshot }) {
  const dragFrom = useRef<number | null>(null);
  const queue = snapshot.queue ?? [];
  if (!queue.length) return <div className="mt-4 text-sm text-discord-muted">Очередь пуста.</div>;

  return (
    <ul className="mt-4 space-y-1">
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
          className="flex items-center gap-2 rounded bg-discord-card px-3 py-2 text-sm"
        >
          <span className="w-6 text-discord-muted">{i + 1}</span>
          <span className="min-w-0 flex-1 truncate">{t.title}</span>
          <button className="btn" title="Играть сейчас" onClick={() => queueJump(guildId, i)}>▶️</button>
          <button className="btn" title="Удалить" onClick={() => queueRemove(guildId, i)}>🗑️</button>
        </li>
      ))}
    </ul>
  );
}
