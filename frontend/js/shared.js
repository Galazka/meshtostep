// shared.js — single source of truth for cross-module mutable state.
// Modules that only read `token` import the live binding; writers use setToken().
export let token = localStorage.getItem('mt_token');
export function setToken(v) { token = v; }
