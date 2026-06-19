export interface Guild { id: string; name: string; icon: string | null; level: string; }
export interface Me { user_id: string; username: string; avatar: string | null; guilds: Guild[]; }
export interface Health { uptime_seconds: number; guild_count: number; player_count: number; lavalink_connected: boolean; memory_mb: number; }

export async function getMe(): Promise<Me | null> {
  const r = await fetch("/api/me");
  if (r.status === 401) return null;
  if (!r.ok) throw new Error(`me ${r.status}`);
  return r.json();
}

export async function getHealth(guildId: string): Promise<Health> {
  const r = await fetch(`/api/guilds/${guildId}/health`);
  if (!r.ok) throw new Error(`health ${r.status}`);
  return r.json();
}

export async function logout(): Promise<void> {
  await fetch("/api/logout", { method: "POST" });
}
