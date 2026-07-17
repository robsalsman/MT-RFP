import { useEffect, useState } from 'react'

// Single source of truth for the desktop/mobile break. Kept in sync with the
// CSS @media (max-width: 720px) rules in styles.css.
export const MOBILE_BREAKPOINT = 720

export function useIsMobile(breakpoint = MOBILE_BREAKPOINT) {
  const query = `(max-width: ${breakpoint}px)`
  const [match, setMatch] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const update = () => setMatch(mql.matches)
    update()
    // matchMedia 'change' is canonical; 'resize' is a belt-and-braces
    // fallback for environments that don't dispatch it (some emulators).
    mql.addEventListener('change', update)
    window.addEventListener('resize', update)
    return () => {
      mql.removeEventListener('change', update)
      window.removeEventListener('resize', update)
    }
  }, [query])
  return match
}
