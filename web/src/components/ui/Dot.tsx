// components/ui/Dot.tsx
/**
 * 8px status dot. Optional pulse for live indicators.
 *
 * Add this to globals.css if you want the pulse:
 *
 *   @keyframes bpulse {
 *     0%   { box-shadow: 0 0 0 0 currentColor; opacity: 0.6; }
 *     70%  { box-shadow: 0 0 0 6px transparent; opacity: 0; }
 *     100% { box-shadow: 0 0 0 0 transparent; opacity: 0; }
 *   }
 *   .pulse-dot::after {
 *     content: '';
 *     position: absolute;
 *     inset: 0;
 *     border-radius: inherit;
 *     animation: bpulse 2s infinite;
 *     background: currentColor;
 *   }
 */
export function Dot({
  tone = 'cyan',
  pulse = false,
}: {
  tone?: 'cyan' | 'win' | 'lose' | 'warn' | 'amber' | 'muted' | 'dim'
  pulse?: boolean
}) {
  const tones: Record<string, string> = {
    cyan:  'text-cyan bg-cyan',
    win:   'text-win bg-win',
    lose:  'text-lose bg-lose',
    warn:  'text-warn bg-warn',
    amber: 'text-amber bg-amber',
    muted: 'text-text-muted bg-text-muted',
    dim:   'text-text-dim bg-text-dim',
  }
  return (
    <span
      className={[
        'relative inline-block w-2 h-2 rounded-full shrink-0',
        tones[tone],
        pulse ? 'pulse-dot' : '',
      ].join(' ')}
    />
  )
}
