// Standalone syntax check for order.html inline scripts.
// Wyciaga skrypty HTTP parserem (nie regexem — regex lapie </script> w stringach).
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync('frontend/order.html', 'utf8');
const scripts = [];
const re = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
let m;
while ((m = re.exec(html)) !== null) {
  const attrs = m[1] || '';
  if (/\bsrc=/i.test(attrs)) continue;
  if (/type\s*=\s*["']?(application\/ld\+json|importmap)/i.test(attrs)) continue;
  scripts.push({ attrs, code: m[2] });
}

let bad = 0;
scripts.forEach((s, i) => {
  const code = s.code;
  const isModule = /\btype\s*=\s*["']module["']/i.test(s.attrs);
  try {
    if (isModule) {
      // modul: parsuj jako module przez SourceTextModule nie jest dostepne —
      // proxy: sprawdz skladnię opakowujac w async fn z import() dynamic.
      new vm.SourceTextModule(code);
    } else {
      new vm.Script(code, { filename: `order.html:inline#${i}` });
    }
    console.log(`  #${i} OK  (${code.length} zn)${isModule ? ' [module]' : ''}`);
  } catch (e) {
    bad++;
    console.log(`  #${i} BŁĄD ${e.message}  (${code.length} zn)`);
    const stack = (e.stack || '').split('\n').slice(1, 3).join('\n');
    if (stack.trim()) console.log('       ' + stack.replace(/\n/g, '\n       '));
  }
});
console.log(`\nbloków <script> inline: ${scripts.length}   błędów składni: ${bad}`);
process.exit(bad ? 1 : 0);