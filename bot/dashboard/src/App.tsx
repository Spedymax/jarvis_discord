import { useEffect, useState } from "react";
import { getHealth, getMe, logout, type Health, type Me } from "./api";

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [guildId, setGuildId] = useState<string>("");
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => { getMe().then(setMe).catch(() => setMe(null)); }, []);
  useEffect(() => {
    if (me && me.guilds.length && !guildId) setGuildId(me.guilds[0].id);
  }, [me, guildId]);
  useEffect(() => {
    if (!guildId) return;
    const tick = () => getHealth(guildId).then(setHealth).catch(() => {});
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [guildId]);

  if (me === undefined) return <div className="p-8 text-discord-muted">Загрузка…</div>;
  if (me === null) {
    return (
      <div className="flex h-screen items-center justify-center">
        <a href="/auth/discord/login" className="rounded-md bg-discord-blurple px-6 py-3 font-semibold text-white">
          Войти через Discord
        </a>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold">Jarvis Dashboard</h1>
        <div className="flex items-center gap-3 text-sm text-discord-muted">
          <span>{me.username}</span>
          <button onClick={() => logout().then(() => location.reload())} className="rounded bg-discord-card px-3 py-1">Выйти</button>
        </div>
      </header>

      <label className="mb-4 block text-sm text-discord-muted">
        Сервер
        <select value={guildId} onChange={(e) => setGuildId(e.target.value)}
          className="mt-1 block w-full rounded bg-discord-card p-2 text-discord-text">
          {me.guilds.map((g) => (
            <option key={g.id} value={g.id}>{g.name} ({g.level})</option>
          ))}
        </select>
      </label>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Uptime" value={health ? `${Math.floor(health.uptime_seconds / 60)} мин` : "—"} />
        <Stat label="Серверов" value={health ? `${health.guild_count}` : "—"} />
        <Stat label="Активных плееров" value={health ? `${health.player_count}` : "—"} />
        <Stat label="Lavalink" value={health ? (health.lavalink_connected ? "🟢" : "🔴") : "—"} />
        <Stat label="Память" value={health ? `${health.memory_mb} MB` : "—"} />
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-discord-card p-4">
      <div className="text-xs uppercase text-discord-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
