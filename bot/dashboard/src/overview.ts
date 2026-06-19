export interface Voice { channel: string | null; listeners: { name: string; avatar: string | null }[]; }

export async function getVoice(g: string): Promise<Voice> {
  const r = await fetch(`/api/guilds/${g}/voice`);
  if (!r.ok) return { channel: null, listeners: [] };
  return r.json();
}
