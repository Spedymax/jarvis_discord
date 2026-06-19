import { useEffect, useState } from "react";
import { getVoice, type Voice } from "../overview";
import { summon } from "../player";

export default function Listeners({ guildId }: { guildId: string }) {
  const [v, setV] = useState<Voice>({ channel: null, listeners: [] });
  const [msg, setMsg] = useState("");
  useEffect(() => {
    const tick = () => getVoice(guildId).then(setV).catch(() => {});
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [guildId]);

  const onSummon = async () => {
    const r = await summon(guildId);
    setMsg(r.ok ? "" : (r.status === 409 ? "Зайди в голосовой канал." : "Не вышло."));
  };

  return (
    <div className="card p-4">
      <div className="mb-2 text-sm font-semibold text-muted">Слушают{v.channel ? ` · ${v.channel}` : ""}</div>
      {v.listeners.length === 0 ? (
        <div className="space-y-2">
          <div className="text-sm text-muted">Бот не в голосовом канале.</div>
          <button className="btn-primary" onClick={onSummon}>▶ Играй в моём канале</button>
          {msg && <div className="text-xs text-muted">{msg}</div>}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {v.listeners.map((l, i) => (
            <div key={i} className="flex items-center gap-1.5 rounded-full bg-raised px-2 py-1 text-xs">
              {l.avatar ? <img src={l.avatar} alt="" className="h-5 w-5 rounded-full" /> : <span className="grid h-5 w-5 place-items-center rounded-full bg-accent text-[10px]">{l.name[0]}</span>}
              {l.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
