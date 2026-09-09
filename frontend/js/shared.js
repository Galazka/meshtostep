// shared.js — shared mutable state across modules
export let token = localStorage.getItem('mt_token');

// Expose to window for cross-module access and dynamic HTML
window._appToken = token;
Object.defineProperty(window, '_appTokenRW', {
  get() { return token; },
  set(v) { token = v; window._appToken = v; },
});

export function setToken(v) { token = v; window._appToken = v; window._appTokenRW = v; }
export function getToken() { return token; }
