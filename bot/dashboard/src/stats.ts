export interface TrackStat { title: string; author: string | null; plays: number; }
export interface RequesterStat { name: string; plays: number; }
export interface SoundStat { name: string; play_count: number; }
export interface Stats {
  total_plays: number;
  top_tracks: TrackStat[];
  top_requesters: RequesterStat[];
  top_sounds: SoundStat[];
}

export async function getStats(g: string): Promise<Stats> {
  const r = await fetch(`/api/guilds/${g}/stats`);
  if (!r.ok) throw new Error(`stats ${r.status}`);
  return r.json();
}

export async function getLogs(g: string, lines = 200): Promise<string[]> {
  const r = await fetch(`/api/guilds/${g}/logs?lines=${lines}`);
  if (!r.ok) return [];
  return (await r.json()).lines as string[];
}
