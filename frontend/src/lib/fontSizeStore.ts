/**
 * Global font-size store (outside React).
 * AG Grid column defs need column widths before components mount,
 * so we store font-size here and read it synchronously.
 */

export type FontSize = 'small' | 'normal' | 'large';

const KEY = 'app-font-size';
let current: FontSize = (localStorage.getItem(KEY) as FontSize) || 'normal';
const listeners = new Set<(fs: FontSize) => void>();

export function getFontSize(): FontSize { return current; }

/** Multiply base column widths by this factor. */
export function getFontSizeWidthMultiplier(): number {
  if (current === 'small') return 0.85;
  if (current === 'large') return 1.55;
  return 1;
}

export function setFontSizeStore(fs: FontSize) {
  current = fs;
  listeners.forEach(fn => fn(fs));
}

export function subscribeFontSize(fn: (fs: FontSize) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
