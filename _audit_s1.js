/* headless admin audit: dump print-tab state + screenshots */
import { execSync } from 'child_process';
import fs from 'fs';

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";

/* step 1: fetch login token via node fetch (node 18+) */
const login = async () => {
  try {
    const email = "admin@meshtostep.pl";
    const pass = process.env.MT_PASS;
    const r = await fetch("https://3dfile.link/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password: pass })
    });
    const d = await r.json();
    if (!d.token) { console.log("LOGIN_FAIL", r.status, JSON.stringify(d).slice(0,200)); process.exit(1); }
    return d.token;
  } catch (e) { console.log("LOGIN_ERR", e.message); process.exit(1); }
};

const run = async () => {
  const token = await login();
  console.log("TOKEN_OK len", token.length);
  fs.writeFileSync("mt_token_dump.txt", token);

  /* step 2: drive headless chrome with remote debugging to inject token and capture state */
  const prof = "C:/Users/galaz/AppData/Local/Temp/mt_admin_prof_" + Date.now();
  const port = 9247;
  const child = execSync(`"${CHROME}" --headless=new --disable-gpu --no-sandbox --user-data-dir=${prof} --remote-debugging-port=${port} --window-size=1500,1600 about:blank`, { stdio: 'ignore' });
  // We spawn sync; chrome runs in bg. Use timeout, then cleanup handled by caller.
  console.log("CHROME_SPAWN_OK");
  fs.writeFileSync("mt_chrome_port.txt", String(port));
  fs.writeFileSync("mt_prof.txt", prof);
};
run().catch(e => { console.log("FATAL", e.message); process.exit(1); });
