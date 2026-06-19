import { useEffect, useState } from "react";
import { deleteSound, errMsg, getSounds, playSound, renameSound, setSoundVolume, addSoundUrl, addSoundFile, type SoundV } from "../sounds";
import { IconSearch, IconVolume, IconTrash, IconPlus } from "../icons";

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
    <div className="space-y-4">
      {msg && <div className="rounded-lg bg-raised px-3 py-2 text-sm text-muted">{msg}</div>}
      <div className="flex items-center gap-2 rounded-lg bg-raised px-3">
        <IconSearch className="h-4 w-4 text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Фильтр звуков…"
          className="flex-1 bg-transparent py-2 text-sm outline-none placeholder:text-muted" />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {filtered.map((s) => (
          <div key={s.id} className="card group overflow-hidden p-0">
            <button onClick={() => onPlay(s.id)}
              className="flex h-20 w-full items-center justify-center bg-gradient-to-br from-accent/20 to-accent2/10 text-center text-sm font-semibold transition-colors hover:from-accent hover:to-accent2 hover:text-white">
              <span className="truncate px-2">{s.name}</span>
            </button>
            <div className="flex items-center justify-between px-2 py-1.5 text-xs text-muted">
              <span>{Math.round(s.length_ms / 1000)}s · {s.play_count}▶</span>
              <span className="flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <button className="icon-btn h-7 w-7" title="Громкость" onClick={() => onVolume(s)}><IconVolume className="h-4 w-4" /></button>
                <button className="icon-btn h-7 w-7" title="Переименовать" onClick={() => onRename(s)}>✏️</button>
                <button className="icon-btn h-7 w-7 hover:text-danger" title="Удалить" onClick={() => onDelete(s)}><IconTrash className="h-4 w-4" /></button>
              </span>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <div className="col-span-full text-sm text-muted">Звуков нет.</div>}
      </div>

      <UploadArea guildId={guildId} onDone={reload} setMsg={setMsg} />
    </div>
  );
}

function UploadArea({ guildId, onDone, setMsg }: { guildId: string; onDone: () => void; setMsg: (s: string) => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [over, setOver] = useState(false);

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    if (!name.trim()) { setMsg("Сначала впиши имя."); return; }
    setMsg(await errMsg(await addSoundFile(guildId, name, f))); setName(""); onDone();
  };
  const onUrl = async () => {
    if (!name.trim() || !url.trim()) return;
    setMsg(await errMsg(await addSoundUrl(guildId, name, url))); setName(""); setUrl(""); onDone();
  };

  return (
    <div className="card space-y-3 p-4">
      <div className="text-sm font-semibold text-muted">Добавить звук</div>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Имя" className="input" />
      <label
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]); }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-6 text-center text-sm transition-colors ${over ? "border-accent bg-accent/10 text-text" : "border-border text-muted"}`}>
        <IconPlus className="h-5 w-5" />
        Перетащи файл или нажми, чтобы выбрать
        <input type="file" accept="audio/*" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
      </label>
      <div className="flex gap-2">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="…или вставь URL" className="input" />
        <button className="btn-primary shrink-0" onClick={onUrl}>Добавить</button>
      </div>
    </div>
  );
}
