/** SVG icon per node_type, colored by category via currentColor. */

const CATEGORY_COLOR: Record<string, string> = {
  source:    'text-blue-400',
  filter:    'text-yellow-400',
  inference: 'text-purple-400',
  sink:      'text-green-400',
}

type IconFn = (size: number) => React.ReactElement

const ICONS: Record<string, IconFn> = {
  // ── Sources ─────────────────────────────────────────────────────────────
  camera_source: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <rect x="1" y="4" width="12" height="8.5" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="7" cy="8.5" r="2.2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M4.5 4V3a.5.5 0 01.5-.5h4a.5.5 0 01.5.5v1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
  video_file: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <rect x="1" y="2" width="9" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M10 5.5l3-2v7l-3-2v-3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
    </svg>
  ),
  image_folder: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M1 5h12v7a1 1 0 01-1 1H2a1 1 0 01-1-1V5z" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M1 5V4a1 1 0 011-1h3l1.5 2H1" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M3.5 11L6 8l2 2 1.5-1.5 2 2.5H3.5z" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),

  // ── Filters ──────────────────────────────────────────────────────────────
  trigger: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M8 1.5H4L3 8h3.5l-1 4.5L11 5.5H7.5L8 1.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
    </svg>
  ),
  manual_trigger: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5 7l2 2 4-4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  crop_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M4 1v3H1M10 1v3h3M4 13v-3H1M10 13v-3h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  motion_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M3 5.5C4 3.5 6.5 3 9 4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <path d="M11 8.5C10 10.5 7.5 11 5 9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <path d="M1.5 7h1.5M11 7h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  brightness_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M7 1v1.5M7 11.5V13M1 7h1.5M11.5 7H13M2.6 2.6l1.1 1.1M10.3 10.3l1.1 1.1M2.6 11.4l1.1-1.1M10.3 3.7l1.1-1.1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  resize_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M1 5V1h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M1 1l5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M13 9v4H9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M13 13l-5-5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
  frame_dedup: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <rect x="1" y="3" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5 1h6a2 2 0 012 2v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M9.5 7.5l2 1.5-2 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  time_interval_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7.5" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M7 4.5V7.5l2.5 1.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  time_of_day_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M1.5 9.5a5.5 5.5 0 0111 0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M1 10h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M7 3V1.5M3.8 4.8l-1-1M10.2 4.8l1-1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  yolo_filter: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M1 4V2h2M11 2h2v2M1 10v2h2M11 12h2v-2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <rect x="4" y="4" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M6 7h2M7 6v2" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
    </svg>
  ),

  // ── Inference ────────────────────────────────────────────────────────────
  claude_inference: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M7 1v2.5M7 10.5V13M1 7h2.5M10.5 7H13M2.6 2.6l1.8 1.8M9.6 9.6l1.8 1.8M2.6 11.4l1.8-1.8M9.6 4.4l1.8-1.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <circle cx="7" cy="7" r="2" stroke="currentColor" strokeWidth="1.3"/>
    </svg>
  ),
  ollama_inference: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M3.5 7c0-1.9 1.6-3.5 3.5-3.5S10.5 5.1 10.5 7c0 1-.4 1.8-1 2.4L7 13l-2.5-3.6A3.4 3.4 0 013.5 7z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <circle cx="5.8" cy="6.5" r=".8" fill="currentColor"/>
      <circle cx="8.2" cy="6.5" r=".8" fill="currentColor"/>
    </svg>
  ),
  gemini_inference: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M7 1l6 6-6 6-6-6 6-6z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M7 4.5l2.5 2.5-2.5 2.5-2.5-2.5 2.5-2.5z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round"/>
    </svg>
  ),
  custom_prompt: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M2.5 11.5L9 5l2 2-6.5 6.5H2.5v-2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M9 5l1.5-1.5a1 1 0 011.5 1.5L10.5 6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4.5 9.5h6" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
    </svg>
  ),

  // ── Sinks ─────────────────────────────────────────────────────────────────
  sqlite_sink: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <ellipse cx="7" cy="4" rx="5" ry="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M2 4v6M12 4v6" stroke="currentColor" strokeWidth="1.3"/>
      <ellipse cx="7" cy="10" rx="5" ry="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M2 7c0 1.1 2.2 2 5 2s5-.9 5-2" stroke="currentColor" strokeWidth="1.1"/>
    </svg>
  ),
  pdf_sink: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M3 1h5.5L12 4.5V13a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M8.5 1v4h4" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      <path d="M4.5 7.5h5M4.5 9.5h5M4.5 11.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
    </svg>
  ),
  webhook_sink: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M5.5 9.5a3 3 0 010-5h3M8.5 4.5a3 3 0 010 5h-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
  slack_sink: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M2 1.5h10a1 1 0 011 1V8a1 1 0 01-1 1H8l-3 3.5V9H2a1 1 0 01-1-1V2.5a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M4 5h6M4 7h4" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
    </svg>
  ),
  s3_sink: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <path d="M4.5 11a3.5 3.5 0 110-7h.5A5 5 0 0114 6.5a3.5 3.5 0 01-.5 7H4.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
    </svg>
  ),
  mqtt_sink: s => (
    <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="11.5" r="1" fill="currentColor"/>
      <path d="M4.3 9.3a3.8 3.8 0 015.4 0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M1.8 6.8a7 7 0 0110.4 0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
}

const FALLBACK: IconFn = s => (
  <svg width={s} height={s} viewBox="0 0 14 14" fill="none">
    <rect x="2" y="2" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.3"/>
    <circle cx="7" cy="7" r="1.5" fill="currentColor"/>
  </svg>
)

interface Props {
  nodeType: string
  category: string
  size?: number
}

export function NodeIcon({ nodeType, category, size = 14 }: Props) {
  const colorClass = CATEGORY_COLOR[category] ?? 'text-zinc-400'
  const render = ICONS[nodeType] ?? FALLBACK
  return (
    <span className={`${colorClass} flex-shrink-0`} style={{ lineHeight: 0 }}>
      {render(size)}
    </span>
  )
}
