import { useEffect, useRef, useState } from "react";
import { getLogs } from "../stats";

interface Health { uptime_seconds: number; guild_count: number; player_count: number; lavalink_connected: boolean; memory_mb: number; }

export default function Admin({ guildId }: { guildId: string }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const pre = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const tick = () => fetch(`/api/guilds/${guildId}/health`).then((r) => (r.ok ? r.json() : null)).then(setHealth).catch(() => {});
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [guildId]);

  useEffect(() => {
    const tick = () => getLogs(guildId, 200).then((l) => {
      setLogs(l);
      requestAnimationFrame(() => { if (pre.current) pre.current.scrollTop = pre.current.scrollHeight; });
    });
    tick();
    const id = setInterval(tick, 3000);
    return () => clearInterval(id);
  }, [guildId]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Uptime" value={health ? `${Math.floor(health.uptime_seconds / 60)}м` : "—"} />
        <Stat label="Серверов" value={health ? `${health.guild_count}` : "—"} />
        <Stat label="Плееров" value={health ? `${health.player_count}` : "—"} />
        <Stat label="Lavalink" value={health ? (health.lavalink_connected ? "🟢" : "🔴") : "—"} />
        <Stat label="Память" value={health ? `${health.memory_mb}MB` : "—"} />
      </div>
      <pre ref={pre} className="h-96 overflow-auto rounded-2xl border border-border bg-bg p-4 text-xs leading-relaxed text-green/80">
        {logs.join("\n")}
      </pre>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-3">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
