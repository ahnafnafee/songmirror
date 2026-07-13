import { ACCOUNT_STATE_STYLES } from '@/lib/constants'
import { cn } from '@/lib/cn'
import type { AccountState } from '@/types'

/** h-[26px] rounded-full · glyph + word + tint, per the design spec. Pills
 * never truncate — they wrap whole rather than clip. */
export function StatusPill({ state, className }: { state: AccountState; className?: string }) {
  const style = ACCOUNT_STATE_STYLES[state]
  return (
    <span
      className={cn(
        'inline-flex h-[26px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-[12.5px] font-semibold',
        style.badge,
        className,
      )}
    >
      <span className="font-mono font-semibold" aria-hidden="true">
        {style.glyph}
      </span>
      {style.label}
    </span>
  )
}
