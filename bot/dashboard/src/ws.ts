export interface TrackV {
  title: string; author: string | null; uri: string | null;
  artwork: string | null; length_ms: number; identifier: string | null; requester: string | null;
}
export interface PlayerSnapshot {
  active: boolean; paused?: boolean; position_ms?: number; volume?: number;
  loop?: string; bassboost?: string; effect?: string;
  current?: TrackV | null; queue?: TrackV[];
}

export function connectPlayerWs(guildId: string, onSnapshot: (s: PlayerSnapshot) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout> | null = null;

  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?guild=${guildId}`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "player") onSnapshot(msg as PlayerSnapshot);
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => {
      if (!closed) retry = setTimeout(open, 2000);
    };
  };
  open();

  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    ws?.close();
  };
}
