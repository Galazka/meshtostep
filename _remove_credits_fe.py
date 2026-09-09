"""Remove credit system refs from frontend index.html + admin.html."""
import os

BASE = r"C:\Users\galaz\Desktop\MeshToStep"

def read(p):
    with open(os.path.join(BASE, p), encoding="utf-8") as f:
        return f.read()

def write(p, content):
    with open(os.path.join(BASE, p), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)

# ════════════ index.html ════════════
print("=== index.html ===")
c = read("frontend/index.html")

# 1. FAQ Q2/Q3 static HTML — replace credit questions with quota/retention questions
old_faq = '''            <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)"><span data-i18n="faqQ2">Co to sa kredyty i jak dzialaja?</span><span class="arrow">&#9660;</span></button><div class="faq-a" data-i18n="faqA2">Jedna konwersja = 1 kredyt. Nowi uzytkownicy otrzymuja 3 kredyty za darmo. Kolejne kredyty kupujesz w pakietach: 5 za $0.99, 25 za $2.99, 100 za $7.99. Kredyty nie wygadaja.</div></div>
            <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)"><span data-i18n="faqQ3">Czy moge odzyskac srodki?</span><span class="arrow">&#9660;</span></button><div class="faq-a" data-i18n="faqA3">Tak, masz 14 dni na zwrot srodkow od momentu zakupu, pod warunkiem ze nie wykorzystales kredytow z danego pakietu. Skontaktuj sie z nami aby zainicjowac zwrot.</div></div>'''
new_faq = '''            <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)"><span data-i18n="faqQ2">Czy konwersja jest naprawde darmowa?</span><span class="arrow">&#9660;</span></button><div class="faq-a" data-i18n="faqA2">Tak, konwersje sa w 100% darmowe i nielimitowane. Konto jest opcjonalne — daje 100 MB przestrzeni, foldery i wlasne linki.</div></div>
            <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)"><span data-i18n="faqQ3">Czy moge uzywac bez konta?</span><span class="arrow">&#9660;</span></button><div class="faq-a" data-i18n="faqA3">Tak. Konto daje foldery, 100 MB przestrzeni i wlasne linki /u/nick/slug.</div></div>'''
assert old_faq in c, "MISSING faq html"
c = c.replace(old_faq, new_faq, 1)
print("  faq html done")

# 2. Remove kontoCredits section from account panel
old_credits_box = '''          <div class="side" style="margin-bottom:16px">
            <div style="font-weight:600;font-size:14px;margin-bottom:8px" data-i18n="kontoCredits">Kredyty</div>
            <div style="font-size:24px;font-weight:700" id="kontoCredits">0</div>
          </div>
'''
assert old_credits_box in c, "MISSING kontoCredits box"
c = c.replace(old_credits_box, '', 1)
print("  kontoCredits box removed")

# 3. Remove kontoCredits JS update in loadAccount()
old_js = "            document.getElementById('kontoCredits').textContent = u.credits || 0;\n"
assert old_js in c, "MISSING kontoCredits js"
c = c.replace(old_js, '', 1)
print("  kontoCredits js removed")

# 4. Remove doPayment function
import re
m = re.search(r"    async function doPayment\(plan\) \{.*?\n    \}\n", c, re.DOTALL)
assert m, "MISSING doPayment"
c = c.replace(m.group(0), '', 1)
print("  doPayment removed")

# 5. Remove kontoCredits i18n keys if present
for lang_key in ['kontoCredits']:
    for pat in [f"            {lang_key}: '", f'            {lang_key}: "']:
        pass
# generic: drop any line containing kontoCredits i18n definition
lines = c.split('\n')
lines = [l for l in lines if 'kontoCredits' not in l or 'id="kontoCredits"' in l]
c = '\n'.join(lines)

write("frontend/index.html", c)
print("  index.html written")

# ════════════ admin.html ════════════
print("=== admin.html ===")
a = read("frontend/admin.html")

# 1. Remove credit table header
a = a.replace('                                    <th data-i18n="thCreditsLeft">Kredyty</th>\n', '')
# 2. Remove credit cell in renderUsers
a = a.replace("                '<td class=\"credit-display\">' + (u.credits ?? '—') + '</td>' +\n", '')
# 3. Remove credit detail in renderUserDetail
a = a.replace("            '<div class=\"detail-item\"><div class=\"detail-label\">' + t('userDetailCredits') + '</div><div class=\"detail-value\" style=\"color:var(--primary)\">' + (u.credits ?? '—') + '</div></div>' +\n", '')
# 4. Remove credit adjustment form block
m2 = re.search(r"                    <h4 style=\"font-size:14px;font-weight:700;margin-bottom:8px\" data-i18n=\"creditAdjustTitle\".*?</div>\n", a, re.DOTALL)
assert m2, "MISSING credit adjust form"
a = a.replace(m2.group(0), '', 1)
# 5. Remove adjustCredits function block
m3 = re.search(r"    /\* ═+ CREDIT ADJUSTMENT ═+ \*/\n    async function adjustCredits\(\).*?\n    \}\n", a, re.DOTALL)
assert m3, "MISSING adjustCredits fn"
a = a.replace(m3.group(0), '', 1)
# 6. Remove credit reset lines in openUser
a = a.replace("        document.getElementById('creditAmount').value = '';\n", '')
a = a.replace("        document.getElementById('creditResult').textContent = '';\n", '')
# 7. Remove Enter key handler
m4 = re.search(r"    /\* Enter key on credit amount \*/\n    document\.getElementById\('creditAmount'\)\.addEventListener.*?\n", a, re.DOTALL)
if m4:
    a = a.replace(m4.group(0), '', 1)
# 8. Remove credit CSS
a = a.replace('        .credit-display { font-weight: 600; color: var(--primary); }\n', '')
a = a.replace('''        /* ── CREDIT ADJUSTMENT ── */
        .credit-form { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
        .credit-form input { width: 100px; background: var(--bg-alt); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; font-size: 14px; font-family: inherit; text-align: center; font-weight: 600; }
        .credit-form input:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }
''', '')

write("frontend/admin.html", a)
print("  admin.html written")
print("\n=== Frontend cleanup done ===")
