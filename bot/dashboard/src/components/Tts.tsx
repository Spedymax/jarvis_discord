import { useEffect, useState } from "react";
import { errMsg, getVoices, speak, type VoiceV } from "../sounds";

export default function Tts({ guildId }: { guildId: string }) {
  const [voices, setVoices] = useState<VoiceV[]>([]);
  const [voice, setVoice] = useState("");
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getVoices(guildId).then((vs) => {
      setVoices(vs);
      if (vs.length) setVoice(vs[0].id);
    });
  }, [guildId]);

  const say = async () => {
    if (!text.trim()) return;
    setMsg((await errMsg(await speak(guildId, text, voice))) || "🗣 Готово");
  };

  return (
    <div className="mt-4 rounded-lg bg-discord-card p-4">
      {msg && <div className="mb-2 text-sm text-discord-muted">{msg}</div>}
      <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={200}
        placeholder="Что сказать (до 200 символов)…" rows={3}
        className="w-full rounded bg-discord-dark p-2 text-discord-text" />
      <div className="mt-2 flex gap-2">
        <select value={voice} onChange={(e) => setVoice(e.target.value)}
          className="flex-1 rounded bg-discord-dark p-2 text-sm">
          {voices.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
        </select>
        <button className="btn" onClick={say}>🗣 Сказать</button>
      </div>
    </div>
  );
}
