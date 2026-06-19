import type { PlayerSnapshot, TrackV } from "./ws";

async function post(guildId: string, path: string, body?: unknown): Promise<PlayerSnapshot> {
  const r = await fetch(`/api/guilds/${guildId}/${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

export async function getPlayer(guildId: string): Promise<PlayerSnapshot> {
  const r = await fetch(`/api/guilds/${guildId}/player`);
  if (!r.ok) throw new Error(`player ${r.status}`);
  return r.json();
}
export async function search(guildId: string, q: string): Promise<TrackV[]> {
  const r = await fetch(`/api/guilds/${guildId}/search?q=${encodeURIComponent(q)}`);
  if (!r.ok) return [];
  return (await r.json()).results as TrackV[];
}
export const play = (g: string, query: string, mode: "enqueue" | "next" | "skip") => post(g, "play", { query, mode });
export const pause = (g: string) => post(g, "pause");
export const resume = (g: string) => post(g, "resume");
export const skip = (g: string) => post(g, "skip");
export const stop = (g: string) => post(g, "stop");
export const shuffle = (g: string) => post(g, "shuffle");
export const seek = (g: string, position_ms: number) => post(g, "seek", { position_ms });
export const setVolume = (g: string, volume: number) => post(g, "volume", { volume });
export const setLoop = (g: string, mode: string) => post(g, "loop", { mode });
export const setFilters = (g: string, f: { bassboost?: string; effect?: string }) => post(g, "filters", f);
export const queueRemove = (g: string, index: number) => post(g, "queue/remove", { index });
export const queueMove = (g: string, from: number, to: number) => post(g, "queue/move", { from, to });
export const queueJump = (g: string, index: number) => post(g, "queue/jump", { index });
