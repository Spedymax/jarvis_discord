import type { Me } from "../api";
import { IconHome, IconPlay, IconBoard, IconMic, IconChart, IconGear, IconLogout } from "../icons";

export type Tab = "overview" | "player" | "sound" | "tts" | "stats" | "admin";

export const NAV: { id: Tab; label: string; Icon: (p: { className?: string }) => JSX.Element; admin?: boolean }[] = [
  { id: "overview", label: "Главная", Icon: IconHome },
  { id: "player", label: "Плеер", Icon: IconPlay },
  { id: "sound", label: "Саундборд", Icon: IconBoard },
  { id: "tts", label: "TTS", Icon: IconMic },
  { id: "stats", label: "Статистика", Icon: IconChart },
  { id: "admin", label: "Админ", Icon: IconGear, admin: true },
];

export default function Sidebar({ me, guildId, setGuildId, tab, setTab, isAdmin, onLogout }: {
  me: Me; guildId: string; setGuildId: (g: string) => void;
  tab: Tab; setTab: (t: Tab) => void; isAdmin: boolean; onLogout: () => void;
}) {
  return (
    <aside className="flex h-full flex-col gap-4 border-r border-border bg-surface p-4">
      <div className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-2xl font-extrabold text-transparent">Jarvis</div>
      <select value={guildId} onChange={(e) => setGuildId(e.target.value)} className="input">
        {me.guilds.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
      </select>
      <nav className="flex flex-1 flex-col gap-1">
        {NAV.filter((n) => !n.admin || isAdmin).map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setTab(id)} className={`pill ${tab === id ? "pill-active" : ""}`}>
            <Icon className="h-5 w-5" /> {label}
          </button>
        ))}
      </nav>
      <div className="flex items-center justify-between border-t border-border pt-3">
        <span className="truncate text-sm text-muted">{me.username}</span>
        <button className="icon-btn" title="Выйти" onClick={onLogout}><IconLogout /></button>
      </div>
    </aside>
  );
}
