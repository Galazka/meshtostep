// Walidacja cache guarda w kazdym HTML: skladnia JS + trzy identyczne liczby.
// Uzycie: node check_guard.js
const fs = require('fs'), path = require('path'), cp = require('child_process');
const ROOT = 'C:/Users/galaz/Desktop/MeshToStep';

const files = cp.execSync('git ls-files frontend', { cwd: ROOT, encoding: 'utf8' })
  .split('\n').filter(f => f.endsWith('.html'));

let bad = 0, checked = 0;
for (const f of files) {
  const s = fs.readFileSync(path.join(ROOT, f), 'utf8');
  const i = s.indexOf('window.__APP_V');
  if (i < 0) continue;
  checked++;
  const end = s.indexOf('</script>', i);
  const seg = s.slice(i, end);
  const code = seg.replace(/^<script>/, '');
  // 1. skladnia
  try { new Function(code); }
  catch (e) {
    console.log(`SYNTAX  ${f}: ${e.message}`);
    bad++; continue;
  }
  // 2. trzy liczby identyczne
  const nums = [...seg.matchAll(/'(\d+)'/g)].map(m => m[1]);
  const uniq = [...new Set(nums)];
  if (uniq.length > 1) {
    console.log(`MISMATCH ${f}: ${JSON.stringify(uniq)}`);
    bad++; continue;
  }
  // 3. struktura: musi zapisac sessionStorage i porownac z ta sama liczba
  const v = uniq[0];
  const ok = seg.includes(`window.__APP_V='${v}'`) &&
             seg.includes(`if(s&&s!=='${v}')`) &&
             seg.includes(`sessionStorage.setItem(k,'${v}')`);
  if (!ok) { console.log(`STRUCT ${f}: v=${v}`); bad++; }
}
console.log(`\nsprawdzonych: ${checked} | blednych: ${bad}`);
process.exit(bad ? 1 : 0);