export function announce(message: string) {
  const el = document.getElementById('a11y-announcer');
  if (!el) return;
  el.textContent = '';
  setTimeout(() => { el.textContent = message; }, 50);
}
