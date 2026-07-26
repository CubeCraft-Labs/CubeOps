class CubecraftProductionCard extends HTMLElement {
  static getStubConfig() { return { title: "Cubecraft Production", show_pii: true, kiosk: false }; }
  setConfig(config) {
    if (!config) throw new Error("A configuration is required");
    this.config = { title: "Cubecraft Production", show_pii: true, kiosk: false, hide_done: false, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._requested) this._load();
  }

  connectedCallback() {
    ensureBrandFont();
    this._render();
    // Stages advance from WooCommerce notes, so nothing here triggers a reload.
    // Poll instead, so a display left open keeps up on its own.
    this._timer = setInterval(() => { this._requested = false; this._load(); }, REFRESH_MS);
  }

  disconnectedCallback() { clearInterval(this._timer); }
  getCardSize() { return 12; }

  // Sections view: default to the full section width but stay resizable, and
  // let the height follow the content instead of being fixed.
  getGridOptions() {
    return { columns: "full", min_columns: 6, rows: "auto", min_rows: 2 };
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      const result = await this._hass.callWS({ type: "cubecraft_production/orders", entry_id: this.config?.entry_id || undefined });
      this.orders = result.orders || [];
      this._requested = true;
    } catch (error) {
      this.error = error.message || String(error);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _render() {
    if (!this.config) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const kiosk = !!this.config.kiosk;
    const stages = [["queued", "Queued"], ["printing", "Printing"], ["qa_assembly", "QA / assembly"], ["packed", "Packed"], ["awaiting_usps", "Awaiting USPS"], ["done", "Done"]]
      .filter(([key]) => !(this.config.hide_done && key === "done"));
    const orderColumns = stages.map(([key, label]) => {
      const cards = (this.orders || []).filter(order => order.stage === key).sort((a, b) => a.created_at.localeCompare(b.created_at)).map(order => this._order(order)).join("");
      return `<section class="column"><header>${label}<span>${(this.orders || []).filter(o => o.stage === key).length}</span></header><div class="stack">${cards || "<p class='empty'>No orders</p>"}</div></section>`;
    }).join("");
    this.shadowRoot.innerHTML = `
      <style>
        /* CubeCraft Creations design system — brand gradient #3B3AB8 → #A035CC,
           Nunito type, pill controls, 4px spacing scale. Surfaces fall back to
           Home Assistant theme variables so the board still reads in dark mode. */
        :host {
          display:block;
          --cc-blue:#3B3AB8; --cc-purple:#A035CC;
          --cc-gradient:linear-gradient(135deg, #3B3AB8 0%, #A035CC 100%);
          --cc-primary-50:#EBEBF8; --cc-primary-500:#3B3AB8; --cc-primary-700:#201F7A;
          --cc-neutral-0:#FFFFFF; --cc-neutral-50:#FAFAFA; --cc-neutral-100:#F4F4F6;
          --cc-neutral-150:#EDEDF1; --cc-neutral-200:#E4E4EA; --cc-neutral-400:#9898A8;
          --cc-neutral-600:#52525E; --cc-neutral-900:#18181D;
          --cc-success:#16A34A; --cc-warning:#D97706; --cc-warning-bg:#FEF3C7;
          --cc-error:#DC2626; --cc-error-bg:#FEE2E2;
          --cc-radius-sm:6px; --cc-radius-md:8px; --cc-radius-lg:12px;
          --cc-radius-xl:16px; --cc-radius-brand:20px; --cc-radius-full:9999px;
          --cc-shadow-sm:0 2px 6px 0 rgba(0,0,0,.08);
          --cc-shadow-md:0 4px 12px 0 rgba(0,0,0,.10);
          --cc-shadow-brand:0 4px 20px 0 rgba(59,58,184,.25);
          --cc-ease:cubic-bezier(0,0,.2,1); --cc-dur:200ms;
          /* Surfaces: HA theme first, brand neutrals as fallback */
          --cc-surface:var(--ha-card-background, var(--card-background-color, var(--cc-neutral-0)));
          --cc-surface-sunken:var(--secondary-background-color, var(--cc-neutral-100));
          --cc-text:var(--primary-text-color, var(--cc-neutral-900));
          --cc-text-muted:var(--secondary-text-color, var(--cc-neutral-600));
          --cc-border:var(--divider-color, var(--cc-neutral-150));
          font-family:'Nunito','Nunito Fallback',var(--primary-font-family,system-ui),sans-serif;
          color:var(--cc-text);
        }
        .shell { background:var(--cc-surface); border-radius:var(--cc-radius-brand); overflow:hidden; box-shadow:var(--cc-shadow-md); }
        .title {
          display:flex; justify-content:space-between; align-items:center; gap:12px;
          padding:16px 20px; background:var(--cc-gradient); color:#fff;
          font-size:1.25rem; font-weight:800; letter-spacing:-.01em;
        }
        /* Columns wrap to fit whatever width the card is given, rather than
           scrolling off the edge. min() keeps a single column from overflowing
           a very narrow card. */
        .board {
          display:grid;
          grid-template-columns:repeat(auto-fit, minmax(min(200px, 100%), 1fr));
          align-items:start; gap:12px; padding:16px;
        }
        /* Sized to content: a tall min-height wastes a lot of space once the
           columns wrap and stack on a narrow card. */
        .column { background:var(--cc-surface-sunken); border-radius:var(--cc-radius-lg); min-height:96px; }
        .column header {
          display:flex; justify-content:space-between; align-items:center; gap:8px;
          padding:12px 12px 8px; position:sticky; left:0;
          font-size:.75rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
          color:var(--cc-text-muted);
        }
        .column header span {
          background:var(--cc-gradient); color:#fff; border-radius:var(--cc-radius-full);
          padding:2px 9px; font-size:.75rem; font-weight:700; letter-spacing:0;
        }
        .stack { display:grid; gap:8px; padding:0 8px 12px; }
        article {
          background:var(--cc-surface); border-radius:var(--cc-radius-md); padding:12px;
          border-left:4px solid var(--cc-primary-500); box-shadow:var(--cc-shadow-sm);
          transition:transform var(--cc-dur) var(--cc-ease), box-shadow var(--cc-dur) var(--cc-ease);
        }
        article:hover { transform:translateY(-1px); box-shadow:var(--cc-shadow-md); }
        article.blocked { border-left-color:var(--cc-error); background:linear-gradient(0deg, var(--cc-error-bg) 0%, var(--cc-error-bg) 100%), var(--cc-surface); }
        .order-head { display:flex; justify-content:space-between; align-items:baseline; gap:10px; font-weight:800; font-size:.9375rem; }
        .order-head span:last-child { font-size:.75rem; font-weight:600; color:var(--cc-text-muted); }
        .items { margin:8px 0; font-size:.875rem; line-height:1.5; }
        .subtle { margin:8px 0; font-size:.8125rem; line-height:1.5; color:var(--cc-text-muted); }
        .exception { color:var(--cc-error); font-size:.75rem; font-weight:600; margin:8px 0; }
        .trail { margin:8px 0 0; font-size:.75rem; }
        .trail summary {
          cursor:pointer; color:var(--cc-text-muted); font-weight:700;
          letter-spacing:.02em; list-style:none; padding:2px 0;
        }
        .trail summary::-webkit-details-marker { display:none; }
        .trail summary::before { content:"▸ "; display:inline-block; transition:transform var(--cc-dur) var(--cc-ease); }
        .trail[open] summary::before { transform:rotate(90deg); }
        .trail .note {
          display:grid; gap:1px; padding:6px 0; border-top:1px solid var(--cc-border);
          color:var(--cc-text); line-height:1.45;
        }
        .trail .note span { color:var(--cc-text-muted); font-size:.6875rem; }
        .actions { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
        button, .actions a {
          display:inline-flex; align-items:center; justify-content:center;
          border:0; border-radius:var(--cc-radius-full); padding:8px 16px;
          font-family:inherit; font-size:.8125rem; font-weight:700; letter-spacing:.02em; line-height:1;
          cursor:pointer; text-decoration:none; white-space:nowrap;
          background:var(--cc-gradient); color:#fff; box-shadow:var(--cc-shadow-brand);
          transition:transform var(--cc-dur) var(--cc-ease), filter var(--cc-dur) var(--cc-ease);
        }
        button:hover, .actions a:hover { transform:scale(1.03); filter:brightness(1.08); }
        button:active, .actions a:active { transform:scale(.97); }
        button:focus-visible, .actions a:focus-visible { outline:2px solid var(--cc-purple); outline-offset:2px; }
        button.secondary {
          background:var(--cc-neutral-100); color:var(--cc-neutral-900);
          box-shadow:none; border:1px solid var(--cc-border);
        }
        .title button.secondary { background:rgba(255,255,255,.18); color:#fff; border-color:rgba(255,255,255,.35); }
        /* Kiosk: a 1080p panel read from across the room. Scale type and
           spacing up, and drop hover affordances nothing will ever hover. */
        /* Fill the panel: header on top, board taking the rest, columns of equal
           height — the usual wall-mounted kanban shape rather than a short card
           floating in empty space. */
        .shell.kiosk { border-radius:0; box-shadow:none; min-height:100vh; display:flex; flex-direction:column; }
        .shell.kiosk .board { flex:1; align-items:stretch; }
        .shell.kiosk .title { padding:20px 28px; font-size:1.75rem; }
        .shell.kiosk .board { gap:16px; padding:20px; grid-template-columns:repeat(auto-fit, minmax(min(260px, 100%), 1fr)); }
        .shell.kiosk .column header { font-size:.9375rem; padding:16px 14px 10px; }
        .shell.kiosk .column header span { font-size:.9375rem; padding:3px 12px; }
        .shell.kiosk article { padding:16px; }
        .shell.kiosk article:hover { transform:none; box-shadow:var(--cc-shadow-sm); }
        .shell.kiosk .order-head { font-size:1.125rem; }
        .shell.kiosk .items { font-size:1rem; }
        .shell.kiosk .subtle { font-size:.9375rem; }
        .shell.kiosk .exception { font-size:.875rem; }
        .shell.kiosk .empty { font-size:.9375rem; }
        .shell.kiosk .trail, .shell.kiosk .actions { display:none; }
        .empty { padding:16px 12px; color:var(--cc-text-muted); font-size:.8125rem; text-align:center; }
        .error { margin:0; padding:12px 20px; background:var(--cc-error-bg); color:var(--cc-error); font-size:.8125rem; font-weight:600; }
      </style>
      <div class="shell${kiosk ? " kiosk" : ""}"><div class="title"><span>${escapeHtml(this.config.title)}</span>${kiosk ? "" : `<button class="secondary" id="refresh">Refresh</button>`}</div>
      ${this.error ? `<p class="error">${escapeHtml(this.error)}</p>` : ""}<main class="board">${orderColumns}</main></div>`;
    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => { this._requested = false; this.error = null; this._load(); });
  }

  _order(order) {
    const name = this.config.show_pii ? [order.customer?.first_name, order.customer?.last_name].filter(Boolean).join(" ") : "Packing details restricted";
    const address = this.config.show_pii ? [order.customer?.address_1, order.customer?.address_2, [order.customer?.city, order.customer?.state, order.customer?.postcode].filter(Boolean).join(" ")].filter(Boolean).join(" · ") : "";
    const items = asList(order.items).map(item => `${item.quantity || 1}× ${escapeHtml(item.name || item.product_name || "Item")}`).join("<br>");
    const link = order.order_url ? `<a href="${escapeAttribute(order.order_url)}" target="_blank" rel="noopener">Open Woo</a>` : "";
    const tracking = (order.shipments || []).map(s => `${s.tracking_number}: ${s.accepted_at ? "Accepted" : s.status}`).join(" · ");
    const note = order.customer_note ? `<div class="subtle">Customer note: ${escapeHtml(order.customer_note)}</div>` : "";
    const owner = order.assigned_to ? `<span>${escapeHtml(order.assigned_to)}</span>` : "";
    // The hashtag workflow builds an audit trail; show it, collapsed, newest first.
    const trail = asList(order.notes).slice(-NOTE_LIMIT).reverse();
    const notes = trail.length ? `<details class="trail"><summary>History (${asList(order.notes).length})</summary>${
      trail.map(entry => `<div class="note"><span>${escapeHtml(shortTime(entry.at))} · ${escapeHtml(entry.author)}</span>${escapeHtml(entry.message)}</div>`).join("")
    }</details>` : "";
    return `<article class="${order.blocked ? "blocked" : ""}"><div class="order-head"><span>#${escapeHtml(order.order_number)}</span>${owner}</div><div class="items">${items}</div><div class="subtle">${escapeHtml(name)}${address ? `<br>${escapeHtml(address)}` : ""}${order.shipping_method ? `<br>${escapeHtml(order.shipping_method)}` : ""}${tracking ? `<br>${escapeHtml(tracking)}` : ""}</div>${note}${order.exception ? `<div class="exception">${escapeHtml(order.exception)}</div>` : ""}${notes}${link ? `<div class="actions">${link}</div>` : ""}</article>`;
  }

}

// @font-face is ignored inside a shadow root, so the brand font has to be
// declared once in the document itself. Served by the integration alongside
// the card; falls back to system-ui if unavailable.
const REFRESH_MS = 30000;
const NOTE_LIMIT = 6;
const FONT_STYLE_ID = "cubecraft-production-font";
function ensureBrandFont() {
  if (document.getElementById(FONT_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = FONT_STYLE_ID;
  style.textContent = "@font-face{font-family:'Nunito';src:url('/cubecraft_production/nunito.woff2') format('woff2');font-weight:400 800;font-style:normal;font-display:swap;}";
  document.head.appendChild(style);
}

// Line items may arrive as an array or, from bridges that keep WooCommerce's
// item-ID keys, as an object. Normalize so .map is always safe.
function asList(value) { return Array.isArray(value) ? value : value && typeof value === "object" ? Object.values(value) : []; }
// WooCommerce stores text HTML-encoded ("Ground Advantage&#8482;"). Decode before
// escaping, or the ampersand gets escaped again and the entity renders literally.
// A detached textarea decodes entities without parsing markup, so this stays safe.
// Compact timestamp for the history trail; falls back to the raw value.
function shortTime(value) {
  const at = new Date(value);
  if (isNaN(at)) return String(value ?? "");
  return at.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
function decodeEntities(value) {
  const text = String(value ?? "");
  if (!text.includes("&")) return text;
  const el = document.createElement("textarea");
  el.innerHTML = text;
  return el.value;
}
function escapeHtml(value) { return decodeEntities(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }
function escapeAttribute(value) { return escapeHtml(value).replace(/`/g, "&#96;"); }
// The card may be loaded both as a Lovelace resource and via extra_module_url;
// defining twice throws, so only define once.
if (!customElements.get("cubecraft-production-card")) {
  customElements.define("cubecraft-production-card", CubecraftProductionCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "cubecraft-production-card", name: "Cubecraft Production", description: "Production workboard for WooCommerce orders." });
}
