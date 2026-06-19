import { useEffect, useState } from "react";
import { errMsg, getVoices, speak, type VoiceV } from "../sounds";
import { IconMic } from "../icons";

export default function Tts({ guildId }: { guildId: string }) {
  const [voices, setVoices] = useState<VoiceV[]>([]);
  const [voice, setVoice] = useState("");
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getVoices(guildId).then((vs) => { setVoices(vs); if (vs.length) setVoice(vs[0].id); });
  }, [guildId]);

  const say = async () => {
    if (!text.trim()) return;
    setMsg((await errMsg(await speak(guildId, text, voice))) || "🗣 Готово");
  };

  return (
    <div className="card space-y-3 p-5">
      <div className="flex items-center gap-2 font-semibold"><IconMic className="h-5 w-5 text-accent2" /> Озвучка текста</div>
      {msg && <div className="rounded-lg bg-raised px-3 py-2 text-sm text-muted">{msg}</div>}
      <div className="relative">
        <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={200} rows={4}
          placeholder="Что сказать…" className="input resize-none" />
        <span className="absolute bottom-2 right-3 text-xs text-muted">{text.length}/200</span>
      </div>
      <div className="flex gap-2">
        <select value={voice} onChange={(e) => setVoice(e.target.value)} className="input">
          {voices.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
        </select>
        <button className="btn-primary shrink-0" onClick={say}>🗣 Сказать</button>
      </div>
    </div>
  );
}
