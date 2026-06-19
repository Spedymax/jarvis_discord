export interface SoundV { id: number; name: string; length_ms: number; volume: number; play_count: number; }
export interface VoiceV { id: string; label: string; }

async function jpost(g: string, path: string, body?: unknown): Promise<Response> {
  return fetch(`/api/guilds/${g}/${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function getSounds(g: string): Promise<SoundV[]> {
  const r = await fetch(`/api/guilds/${g}/sounds`);
  if (!r.ok) return [];
  return (await r.json()).sounds as SoundV[];
}
export const playSound = (g: string, id: number) => jpost(g, `sounds/${id}/play`);
export const stopSound = (g: string) => jpost(g, "sounds/stop");
export const renameSound = (g: string, id: number, name: string) => jpost(g, `sounds/${id}/rename`, { name });
export const setSoundVolume = (g: string, id: number, volume: number) => jpost(g, `sounds/${id}/volume`, { volume });
export const deleteSound = (g: string, id: number) => jpost(g, `sounds/${id}/delete`);
export async function addSoundUrl(g: string, name: string, url: string): Promise<Response> {
  return jpost(g, "sounds/add", { name, url });
}
export async function addSoundFile(g: string, name: string, file: File): Promise<Response> {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("file", file);
  return fetch(`/api/guilds/${g}/sounds/add`, { method: "POST", body: fd });
}
export async function getVoices(g: string): Promise<VoiceV[]> {
  const r = await fetch(`/api/guilds/${g}/tts/voices`);
  if (!r.ok) return [];
  return (await r.json()).voices as VoiceV[];
}
export const speak = (g: string, text: string, voice: string) => jpost(g, "tts", { text, voice });

export async function errMsg(r: Response): Promise<string> {
  if (r.ok) return "";
  try {
    const b = await r.json();
    if (b.error === "not_in_voice") return "Зайди в голосовой канал.";
    if (b.error === "bot_busy") return "Бот занят в другом канале.";
    return b.message || b.error || `Ошибка ${r.status}`;
  } catch {
    return `Ошибка ${r.status}`;
  }
}
