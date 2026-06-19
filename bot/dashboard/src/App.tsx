import { useEffect, useState } from "react";
import { getMe, logout, type Me } from "./api";
import { connectPlayerWs, type PlayerSnapshot } from "./ws";
import { getPlayer } from "./player";
import Layout from "./components/Layout";
import Sidebar, { NAV, type Tab } from "./components/Sidebar";
import PlayerBar from "./components/PlayerBar";
import NowPlaying from "./components/NowPlaying";
import Queue from "./components/Queue";
import Search from "./components/Search";
import Soundboard from "./components/Soundboard";
import Tts from "./components/Tts";
import Stats from "./components/Stats";
import Admin from "./components/Admin";

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [guildId, setGuildId] = useState("");
  const [tab, setTab] = useState<Tab>("player");
  const [snap, setSnap] = useState<PlayerSnapshot>({ active: false });
  const [pos, setPos] = useState(0);

  useEffect(() => { getMe().then(setMe).catch(() => setMe(null)); }, []);
  useEffect(() => { if (me && me.guilds.length && !guildId) setGuildId(me.guilds[0].id); }, [me, guildId]);
  useEffect(() => {
    if (!guildId) return;
    getPlayer(guildId).then(setSnap).catch(() => setSnap({ active: false }));
    return connectPlayerWs(guildId, setSnap);
  }, [guildId]);
  useEffect(() => { setPos(snap.position_ms ?? 0); }, [snap.position_ms, snap.current?.identifier]);
  useEffect(() => {
    if (!snap.active || snap.paused) return;
    const base = { ms: snap.position_ms ?? 0, at: Date.now() };
    const id = setInterval(() => setPos(base.ms + (Date.now() - base.at)), 500);
    return () => clearInterval(id);
  }, [snap.active, snap.paused, snap.position_ms, snap.current?.identifier]);

  if (me === undefined) return <div className="grid h-screen place-items-center text-muted">Загрузка…</div>;
  if (me === null) {
    return (
      <div className="grid h-screen place-items-center bg-bg">
        <div className="flex flex-col items-center gap-6">
          <div className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-4xl font-extrabold text-transparent">Jarvis</div>
          <a href="/auth/discord/login" className="btn-primary px-8 py-3 text-base">Войти через Discord</a>
        </div>
      </div>
    );
  }

  const isAdmin = me.guilds.find((g) => g.id === guildId)?.level === "admin";

  const mobileNav = (
    <div className="flex flex-col gap-2 border-b border-border bg-surface p-3">
      <div className="flex items-center justify-between">
        <span className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-xl font-extrabold text-transparent">Jarvis</span>
        <select value={guildId} onChange={(e) => setGuildId(e.target.value)} className="input max-w-[55%]">
          {me.guilds.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
      </div>
      <nav className="flex gap-1 overflow-x-auto">
        {NAV.filter((n) => !n.admin || isAdmin).map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setTab(id)} className={`pill w-auto shrink-0 ${tab === id ? "pill-active" : ""}`}>
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </nav>
    </div>
  );

  return (
    <Layout
      sidebar={<Sidebar me={me} guildId={guildId} setGuildId={setGuildId} tab={tab} setTab={setTab} isAdmin={isAdmin} onLogout={() => logout().then(() => location.reload())} />}
      mobileNav={mobileNav}
      bar={<PlayerBar guildId={guildId} snap={snap} pos={pos} onSnap={setSnap} />}
    >
      {tab === "player" && (
        <div className="mx-auto max-w-4xl space-y-4">
          <NowPlaying guildId={guildId} snapshot={snap} onSnap={setSnap} />
          <Search guildId={guildId} />
          <Queue guildId={guildId} snapshot={snap} />
        </div>
      )}
      {tab === "sound" && <div className="mx-auto max-w-4xl"><Soundboard guildId={guildId} /></div>}
      {tab === "tts" && <div className="mx-auto max-w-xl"><Tts guildId={guildId} /></div>}
      {tab === "stats" && <div className="mx-auto max-w-4xl"><Stats guildId={guildId} /></div>}
      {tab === "admin" && isAdmin && <div className="mx-auto max-w-4xl"><Admin guildId={guildId} /></div>}
    </Layout>
  );
}
