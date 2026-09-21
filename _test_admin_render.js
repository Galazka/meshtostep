const { JSDOM } = require("jsdom");
const fs = require("fs");

// Deterministic render test for admin_print.js loadAdminOrders.
// Stubs window.fetch with sample order payload — no network, no auth needed.
// Proves switchPrintTab('orders') -> loadAdminOrders fills #adminOrders.

async function main() {
  const html = fs.readFileSync("C:/Users/galaz/Desktop/MeshToStep/frontend/admin.html", "utf8");

  const dom = new JSDOM(html, {
    url: "https://3dfile.link/admin",
    runScripts: "dangerously",
    resources: "usable",
    pretendToBeVisual: true,
    storageQuota: 10000000,
  });

  const w = dom.window;
  w.localStorage.setItem("mt_token", "FAKE_TOKEN");

  // Stub fetch BEFORE admin_print.js runs so loadAdminOrders gets fake data.
  w.fetch = async (url, opts) => {
    const u = String(url);
    if (u.includes("/api/orders") && !u.includes("/export")) {
      return {
        ok: true,
        json: async () => ({
          ok: true,
          total: 1,
          limit: 50,
          orders: [{
            id: 20, created_at: "2026-09-20T12:00:00Z",
            customer_name: "Tom Test", customer_email: "t@t.pl", customer_phone: "600000000",
            customer_city: "Gdansk", customer_country: "PL",
            items: [{ model_name: "box.stl", material: "PLA", color: "czarny + bialy", quantity: 2, job_uuid: "abc123" }],
            filament_grams: 42, printing_hours: 3, filament_cost: 3.0, margin_pln: 20,
            electricity_cost: 1.0, shipping_cost: 9.9, total: 55.5, currency: "PLN",
            status: "drukowane", is_paid: true, job_id: 99,
          }],
        }),
      };
    }
    if (u.includes("/api/orders/20")) {
      const body = opts && opts.body; // urllib-ish; PATCH returns ok
      return { ok: true, json: async () => ({ ok: true }) };
    }
    return { ok: false, json: async () => ({}) };
  };

  await new Promise(r => setTimeout(r, 600)); // let scripts load

  console.log("switchPrintTab:", typeof w.switchPrintTab);
  console.log("loadAdminOrders:", typeof w.loadAdminOrders);
  console.log("has #adminOrders:", !!w.document.getElementById("adminOrders"));
  console.log("esc(loadAdminOrders def):", w.document.getElementById("adminOrders") != null);

  try { w.switchPrintTab("orders"); } catch(e) { console.log("SWITCH ERR:", e.message); }
  await new Promise(r => setTimeout(r, 400));

  const ao = w.document.getElementById("adminOrders");
  const html2 = ao ? ao.innerHTML : "(null)";
  console.log("\n=== #adminOrders AFTER switchPrintTab('orders') ===");
  console.log("len:", html2.length);
  console.log("has table:", html2.includes("<table"));
  console.log("has row #20:", html2.includes(">#20"));
  console.log("has czarny + bialy:", html2.includes("czarny + bialy"));
  console.log("has 3D link:", html2.includes("/download/abc123?format=stl"));
  console.log("has Tom Test:", html2.includes("Tom Test"));
  console.log("first 300:", html2.substring(0, 300));
}

main().catch(e => { console.error(e); process.exit(1); });
