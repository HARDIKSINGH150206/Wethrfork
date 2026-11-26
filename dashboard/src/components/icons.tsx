const P = ({ d, size = 20, w = 1.8 }: { d: string; size?: number; w?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={w} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
)
export const IconWind = () => <P d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8a2.5 2.5 0 1 1-2.5 2.5" />
export const IconTemp = () => <P d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0zM12 9v7M17 6h2M17 9h2M17 12h2" />
export const IconRain = () => <P d="M7 14a4 4 0 0 1-.5-7.97A5.5 5.5 0 0 1 17 7a3.5 3.5 0 0 1 0 7zM8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5" />
export const IconPressure = () => <P d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 12l4.5-4.5M7 12h.01M12 7h.01M17 12h.01" />
export const IconMoist = () => <P d="M4 9c2.5-2 5-2 8 0s5.5 2 8 0M4 14c2.5-2 5-2 8 0s5.5 2 8 0M7 19c1.6-1 3.3-1 5 0s3.4 1 5 0" />
export const IconBolt = () => <P d="M13 2 4 14h7l-1 8 9-12h-7z" />
export const IconShield = () => <P d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4" />
export const IconPlay = () => <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.2v15.6c0 .8.9 1.3 1.6.8l12-7.8a1 1 0 0 0 0-1.6l-12-7.8C7.9 2.9 7 3.4 7 4.2z" /></svg>
export const IconPause = () => <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><rect x="5.5" y="4" width="4.5" height="16" rx="1.2" /><rect x="14" y="4" width="4.5" height="16" rx="1.2" /></svg>
export const IconSkipBack = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M5 4h2.5v16H5zM20 5.2v13.6a.8.8 0 0 1-1.2.7L8.6 12.7a.8.8 0 0 1 0-1.4l10.2-6.8a.8.8 0 0 1 1.2.7z" /></svg>
export const IconSplit = () => <P d="M12 3v18M4 7h5v10H4zM15 7h5v10h-5z" />
export const IconRing = () => <P d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" />
export const IconDelta = () => <P d="M12 4 3 20h18zM12 10v5M12 17.5v.01" />
export const IconDraw = () => <P d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4M9 12h6M12 9v6" />
export const IconParticles = () => <P d="M3 8h9M15 8h6M3 12h4M10 12h11M3 16h11M17 16h4" />
export const IconIsobars = () => <P d="M3 7c4-3 8 3 12 0s6-1 6-1M3 12c4-3 8 3 12 0s6-1 6-1M3 17c4-3 8 3 12 0s6-1 6-1" />
export const IconDots = () => <P d="M5 12h.01M12 12h.01M19 12h.01" w={3} />
export const IconSearch = () => <P d="M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.8-4.8" w={2.2} />
export const IconInfo = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path fillRule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm-1.3 8.5h2.6V17h-2.6zM12 6.2a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z" /></svg>
export const IconLocate = () => <P d="M12 2v3M12 19v3M2 12h3M19 12h3M12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM12 10.2a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6z" />
export const IconPlus = () => <P d="M12 5v14M5 12h14" w={2.2} />
export const IconMinus = () => <P d="M5 12h14" w={2.2} />
export const IconChevron = ({ up = true }: { up?: boolean }) => <P d={up ? 'M6 15l6-6 6 6' : 'M6 9l6 6 6-6'} w={2.2} size={16} />
export const IconCheck = () => <P d="M5 12.5l4.5 4.5L19 7.5" w={2.4} size={16} />
export const IconClose = () => <P d="M6 6l12 12M18 6 6 18" w={2.2} size={16} />
export const IconFork = () => <P d="M6 3v5a4 4 0 0 0 4 4h4a4 4 0 0 1 4 4v5M18 3v5a4 4 0 0 1-4 4M6 21v-5" />
export const IconGear = () => <P d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM19.4 13a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V19a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H5a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H11a1.7 1.7 0 0 0 1-1.5V5a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V11a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />

/** Wethrfork mark: one path splitting into two futures, on a round gradient badge. */
export const Mark = ({ size = 34 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
    <defs>
      <radialGradient id="wf-badge" cx="35%" cy="30%" r="75%"><stop offset="0" stopColor="#5fc8ff" /><stop offset=".55" stopColor="#1a7fe6" /><stop offset="1" stopColor="#0b3d8c" /></radialGradient>
    </defs>
    <circle cx="20" cy="20" r="19" fill="url(#wf-badge)" />
    <circle cx="20" cy="20" r="18.4" fill="none" stroke="rgba(255,255,255,.55)" strokeWidth="1.2" />
    <path d="M9 21h8.5c2.4 0 3.6-1 5-3.2L25 13.5h5M17.5 21c2.4 0 3.6 1 5 3.2L25 28.5h5" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="9" cy="21" r="2.4" fill="#fff" />
  </svg>
)
