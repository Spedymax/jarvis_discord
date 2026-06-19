import { useEffect, useState } from "react";
import { getMe, logout, type Me } from "./api";
import { connectPlayerWs, type PlayerSnapshot } from "./ws";
import { getPlayer } from "./player";
import NowPlaying from "./components/NowPlaying";
import Queue from "./components/Queue";
import Search from "./components/Search";

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [guildId, setGuildId] = useState<string>("");

  useEffect(() => { getMe().then(setMe).catch(() => setMe(null)); }, []);
  useEffect(() => {
    if (me && me.guilds.length && !guildId) setGuildId(me.guilds[0].id);
  }, [me, guildId]);

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

      <PlayerPanel guildId={guildId} />
    </div>
  );
}

function PlayerPanel({ guildId }: { guildId: string }) {
  const [snap, setSnap] = useState<PlayerSnapshot>({ active: false });
  useEffect(() => {
    if (!guildId) return;
    getPlayer(guildId).then(setSnap).catch(() => setSnap({ active: false }));
    const disconnect = connectPlayerWs(guildId, setSnap);
    return disconnect;
  }, [guildId]);
  if (!guildId) return null;
  return (
    <div className="mt-4">
      <NowPlaying guildId={guildId} snapshot={snap} />
      <Search guildId={guildId} />
      <Queue guildId={guildId} snapshot={snap} />
    </div>
  );
}
