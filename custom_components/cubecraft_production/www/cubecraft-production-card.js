class CubecraftProductionCard extends HTMLElement {
  static getStubConfig() { return { title: "Cubecraft Production", show_pii: true }; }
  setConfig(config) {
    if (!config) throw new Error("A configuration is required");
    this.config = { title: "Cubecraft Production", show_pii: true, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._requested) this._load();
  }

  connectedCallback() { ensureBrandFont(); this._render(); }
  getCardSize() { return 12; }

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
    const stages = [["queued", "Queued"], ["printing", "Printing"], ["qa_assembly", "QA / assembly"], ["packed", "Packed"], ["awaiting_usps", "Awaiting USPS"], ["done", "Done"]];
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
        .board { display:grid; grid-auto-flow:column; grid-auto-columns:minmax(268px, 1fr); overflow-x:auto; gap:12px; padding:16px; }
        .column { background:var(--cc-surface-sunken); border-radius:var(--cc-radius-lg); min-height:280px; }
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
        .empty { padding:16px 12px; color:var(--cc-text-muted); font-size:.8125rem; text-align:center; }
        .error { margin:0; padding:12px 20px; background:var(--cc-error-bg); color:var(--cc-error); font-size:.8125rem; font-weight:600; }
      </style>
      <div class="shell"><div class="title"><span>${escapeHtml(this.config.title)}</span><button class="secondary" id="refresh">Refresh</button></div>
      ${this.error ? `<p class="error">${escapeHtml(this.error)}</p>` : ""}<main class="board">${orderColumns}</main></div>`;
    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => { this._requested = false; this.error = null; this._load(); });
    this.shadowRoot.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", event => this._action(event.currentTarget)));
  }

  _order(order) {
    const name = this.config.show_pii ? [order.customer?.first_name, order.customer?.last_name].filter(Boolean).join(" ") : "Packing details restricted";
    const address = this.config.show_pii ? [order.customer?.address_1, order.customer?.address_2, [order.customer?.city, order.customer?.state, order.customer?.postcode].filter(Boolean).join(" ")].filter(Boolean).join(" · ") : "";
    const items = asList(order.items).map(item => `${item.quantity || 1}× ${escapeHtml(item.name || item.product_name || "Item")}`).join("<br>");
    const next = { queued:"printing", printing:"qa_assembly", qa_assembly:"packed", packed:"awaiting_usps" }[order.stage];
    const action = next && !order.blocked ? `<button data-action="advance" data-id="${order.order_id}" data-stage="${next}">Advance</button>` : "";
    const claim = !order.assigned_to && !order.blocked ? `<button class="secondary" data-action="claim" data-id="${order.order_id}">Claim</button>` : order.assigned_to ? `<button class="secondary" data-action="release" data-id="${order.order_id}">Release</button>` : "";
    const resolve = order.blocked ? `<button data-action="resolve" data-id="${order.order_id}">Resolve</button>` : "";
    const addNote = `<button class="secondary" data-action="note" data-id="${order.order_id}">Note</button>`;
    const link = order.order_url ? `<a href="${escapeAttribute(order.order_url)}" target="_blank" rel="noopener">Open Woo</a>` : "";
    const tracking = (order.shipments || []).map(s => `${s.tracking_number}: ${s.accepted_at ? "Accepted" : s.status}`).join(" · ");
    const note = order.customer_note ? `<div class="subtle">Customer note: ${escapeHtml(order.customer_note)}</div>` : "";
    return `<article class="${order.blocked ? "blocked" : ""}"><div class="order-head"><span>#${escapeHtml(order.order_number)}</span><span>${escapeHtml(order.assigned_to || "Unclaimed")}</span></div><div class="items">${items}</div><div class="subtle">${escapeHtml(name)}${address ? `<br>${escapeHtml(address)}` : ""}${order.shipping_method ? `<br>${escapeHtml(order.shipping_method)}` : ""}${tracking ? `<br>${escapeHtml(tracking)}` : ""}</div>${note}${order.exception ? `<div class="exception">${escapeHtml(order.exception)}</div>` : ""}<div class="actions">${claim}${action}${addNote}${resolve}${link}</div></article>`;
  }

  async _action(button) {
    const id = Number(button.dataset.id);
    const action = button.dataset.action;
    try {
      if (action === "advance") await this._hass.callService("cubecraft_production", "set_stage", { order_id: id, stage: button.dataset.stage, entry_id: this.config.entry_id || undefined });
      if (action === "claim") await this._hass.callService("cubecraft_production", "claim", { order_id: id, entry_id: this.config.entry_id || undefined });
      if (action === "release") await this._hass.callService("cubecraft_production", "release", { order_id: id, entry_id: this.config.entry_id || undefined });
      if (action === "resolve") await this._hass.callService("cubecraft_production", "resolve_exception", { order_id: id, entry_id: this.config.entry_id || undefined, note: "Resolved from production workboard" });
      if (action === "note") {
        const message = window.prompt("Internal production note");
        if (!message) return;
        await this._hass.callService("cubecraft_production", "add_note", { order_id: id, entry_id: this.config.entry_id || undefined, message });
      }
      this._requested = false; await this._load();
    } catch (error) { this.error = error.message || String(error); this._render(); }
  }
}

// @font-face is ignored inside a shadow root, so the brand font has to be
// declared once in the document itself. Served by the integration alongside
// the card; falls back to system-ui if unavailable.
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
function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }
function escapeAttribute(value) { return escapeHtml(value).replace(/`/g, "&#96;"); }
customElements.define("cubecraft-production-card", CubecraftProductionCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "cubecraft-production-card", name: "Cubecraft Production", description: "Interactive production workboard for WooCommerce orders." });
