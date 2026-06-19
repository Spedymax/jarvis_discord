type P = { className?: string };
const S = ({ d, className }: { d: string } & P) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" className={className ?? "h-5 w-5"}>
    <path d={d} />
  </svg>
);
export const IconPlay = (p: P) => <svg viewBox="0 0 24 24" fill="currentColor" className={p.className ?? "h-5 w-5"}><path d="M8 5v14l11-7z" /></svg>;
export const IconPause = (p: P) => <svg viewBox="0 0 24 24" fill="currentColor" className={p.className ?? "h-5 w-5"}><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg>;
export const IconSkip = (p: P) => <svg viewBox="0 0 24 24" fill="currentColor" className={p.className ?? "h-5 w-5"}><path d="M5 5v14l9-7zM16 5h3v14h-3z" /></svg>;
export const IconStop = (p: P) => <svg viewBox="0 0 24 24" fill="currentColor" className={p.className ?? "h-5 w-5"}><rect x="6" y="6" width="12" height="12" rx="2" /></svg>;
export const IconLoop = (p: P) => <S className={p.className} d="M17 2l4 4-4 4M3 11V9a4 4 0 014-4h14M7 22l-4-4 4-4M21 13v2a4 4 0 01-4 4H3" />;
export const IconShuffle = (p: P) => <S className={p.className} d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5" />;
export const IconVolume = (p: P) => <S className={p.className} d="M11 5L6 9H2v6h4l5 4zM19 12a4 4 0 00-2-3.5M16 8a8 8 0 010 8" />;
export const IconSearch = (p: P) => <S className={p.className} d="M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3" />;
export const IconBoard = (p: P) => <S className={p.className} d="M4 4h16v16H4zM4 10h16M10 4v16" />;
export const IconMic = (p: P) => <S className={p.className} d="M12 2a3 3 0 00-3 3v6a3 3 0 006 0V5a3 3 0 00-3-3zM5 11a7 7 0 0014 0M12 18v4" />;
export const IconChart = (p: P) => <S className={p.className} d="M3 3v18h18M8 16v-5M13 16V8M18 16v-9" />;
export const IconGear = (p: P) => <S className={p.className} d="M12 9a3 3 0 100 6 3 3 0 000-6zM19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-2.7.7 1.6 1.6 0 01-3.2 0 1.6 1.6 0 00-2.7-.7l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00-.7-2.7 1.6 1.6 0 010-3.2 1.6 1.6 0 00.7-2.7l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 002.7-.7 1.6 1.6 0 013.2 0 1.6 1.6 0 002.7.7l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00.7 2.7 1.6 1.6 0 010 3.2 1.6 1.6 0 00-1 .9z" />;
export const IconLogout = (p: P) => <S className={p.className} d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />;
export const IconTrash = (p: P) => <S className={p.className} d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />;
export const IconPlus = (p: P) => <S className={p.className} d="M12 5v14M5 12h14" />;
export const IconDrag = (p: P) => <S className={p.className} d="M9 6h.01M9 12h.01M9 18h.01M15 6h.01M15 12h.01M15 18h.01" />;
