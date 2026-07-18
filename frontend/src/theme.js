// Theme: 'auto' follows the OS (prefers-color-scheme); 'light'/'dark' pin it.
// The effective theme is written to <html data-theme>. An inline script in
// index.html applies it before first paint (no flash); this module keeps it in
// sync at runtime and lets the toggle change it.
const KEY = 'mtrfp_theme'
const mql = window.matchMedia('(prefers-color-scheme: dark)')

export function getPref() {
  return localStorage.getItem(KEY) || 'auto'
}

export function effectiveTheme(pref = getPref()) {
  return pref === 'auto' ? (mql.matches ? 'dark' : 'light') : pref
}

export function applyTheme(pref = getPref()) {
  document.documentElement.setAttribute('data-theme', effectiveTheme(pref))
}

export function setPref(pref) {
  localStorage.setItem(KEY, pref)
  applyTheme(pref)
}

// Re-apply when the OS theme flips, but only while we're in 'auto'.
export function watchSystem(onChange) {
  const handler = () => {
    if (getPref() === 'auto') { applyTheme(); onChange && onChange() }
  }
  mql.addEventListener('change', handler)
  return () => mql.removeEventListener('change', handler)
}
