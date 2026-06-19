import { useEffect, useState } from "react";
import { deleteSound, errMsg, getSounds, playSound, renameSound, setSoundVolume, addSoundUrl, addSoundFile, type SoundV } from "../sounds";

export default function Soundboard({ guildId }: { guildId: string }) {
  const [sounds, setSounds] = useState<SoundV[]>([]);
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState("");
  const reload = () => getSounds(guildId).then(setSounds);
  useEffect(() => { reload(); }, [guildId]);

  const onPlay = async (id: number) => setMsg(await errMsg(await playSound(guildId, id)));
  const onVolume = async (s: SoundV) => {
    const v = prompt(`Громкость для «${s.name}» (20–300):`, String(s.volume));
    if (!v) return;
    await setSoundVolume(guildId, s.id, Number(v)); reload();
  };
  const onRename = async (s: SoundV) => {
    const n = prompt("Новое имя:", s.name);
    if (!n) return;
    setMsg(await errMsg(await renameSound(guildId, s.id, n))); reload();
  };
  const onDelete = async (s: SoundV) => {
    if (!confirm(`Удалить «${s.name}»?`)) return;
    await deleteSound(guildId, s.id); reload();
  };

  const filtered = sounds.filter((s) => s.name.includes(q.toLowerCase()));

  return (
    <div className="mt-4">
      {msg && <div className="mb-2 rounded bg-discord-dark px-3 py-2 text-sm text-discord-muted">{msg}</div>}
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Фильтр…"
        className="mb-3 w-full rounded bg-discord-card p-2 text-discord-text" />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {filtered.map((s) => (
          <div key={s.id} className="rounded-lg bg-discord-card p-2">
            <button className="w-full truncate rounded bg-discord-dark px-2 py-3 font-semibold hover:bg-discord-blurple"
              onClick={() => onPlay(s.id)}>{s.name}</button>
            <div className="mt-1 flex justify-between text-xs text-discord-muted">
              <span>{Math.round(s.length_ms / 1000)}s · {s.play_count}▶</span>
              <span className="flex gap-1">
                <button title="Громкость" onClick={() => onVolume(s)}>🎚</button>
                <button title="Переименовать" onClick={() => onRename(s)}>✏️</button>
                <button title="Удалить" onClick={() => onDelete(s)}>🗑</button>
              </span>
            </div>
          </div>
        ))}
      </div>
      <UploadArea guildId={guildId} onDone={reload} setMsg={setMsg} />
    </div>
  );
}

function UploadArea({ guildId, onDone, setMsg }: { guildId: string; onDone: () => void; setMsg: (s: string) => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const onFile = async (f: File | undefined) => {
    if (!f || !name.trim()) { setMsg("Сначала впиши имя."); return; }
    setMsg(await errMsg(await addSoundFile(guildId, name, f))); setName(""); onDone();
  };
  const onUrl = async () => {
    if (!name.trim() || !url.trim()) return;
    setMsg(await errMsg(await addSoundUrl(guildId, name, url))); setName(""); setUrl(""); onDone();
  };
  return (
    <div className="mt-6 rounded-lg bg-discord-card p-3">
      <div className="mb-2 text-sm text-discord-muted">Добавить звук</div>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Имя"
        className="mb-2 w-full rounded bg-discord-dark p-2 text-sm" />
      <div className="flex flex-wrap gap-2">
        <label className="btn cursor-pointer">
          📁 Файл
          <input type="file" accept="audio/*" className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])} />
        </label>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="или URL"
          className="flex-1 rounded bg-discord-dark p-2 text-sm" />
        <button className="btn" onClick={onUrl}>➕ URL</button>
      </div>
    </div>
  );
}
