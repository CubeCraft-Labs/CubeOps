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

  connectedCallback() { this._render(); }
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
        :host { display:block; font-family:var(--primary-font-family, sans-serif); color:var(--primary-text-color); }
        .shell { background:var(--card-background-color); border-radius:12px; overflow:hidden; box-shadow:var(--ha-card-box-shadow, none); }
        .title { display:flex; justify-content:space-between; align-items:center; padding:16px 18px 10px; font-size:20px; font-weight:600; }
        .board { display:grid; grid-auto-flow:column; grid-auto-columns:minmax(260px, 1fr); overflow-x:auto; gap:10px; padding:0 12px 14px; }
        .column { background:var(--secondary-background-color); border-radius:10px; min-height:280px; }
        .column header { display:flex; justify-content:space-between; padding:12px; font-weight:650; position:sticky; left:0; }
        .column header span { background:var(--primary-color); color:var(--text-primary-color); border-radius:999px; padding:1px 8px; font-size:12px; }
        .stack { display:grid; gap:8px; padding:0 8px 8px; }
        article { background:var(--card-background-color); border-radius:8px; padding:10px; border-left:4px solid var(--primary-color); }
        article.blocked { border-color:var(--error-color); }
        .order-head { display:flex; justify-content:space-between; gap:10px; font-weight:650; }
        .items, .subtle { margin:7px 0; font-size:13px; color:var(--secondary-text-color); }
        .exception { color:var(--error-color); font-size:12px; margin:7px 0; }
        .actions { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
        button, a { border:0; background:var(--primary-color); color:var(--text-primary-color); border-radius:6px; padding:6px 8px; font:inherit; font-size:12px; cursor:pointer; text-decoration:none; }
        button.secondary { background:var(--secondary-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); }
        .empty, .error { padding:12px; color:var(--secondary-text-color); font-size:13px; }
      </style>
      <div class="shell"><div class="title"><span>${escapeHtml(this.config.title)}</span><button class="secondary" id="refresh">Refresh</button></div>
      ${this.error ? `<p class="error">${escapeHtml(this.error)}</p>` : ""}<main class="board">${orderColumns}</main></div>`;
    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => { this._requested = false; this.error = null; this._load(); });
    this.shadowRoot.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", event => this._action(event.currentTarget)));
  }

  _order(order) {
    const name = this.config.show_pii ? [order.customer?.first_name, order.customer?.last_name].filter(Boolean).join(" ") : "Packing details restricted";
    const address = this.config.show_pii ? [order.customer?.address_1, order.customer?.address_2, [order.customer?.city, order.customer?.state, order.customer?.postcode].filter(Boolean).join(" ")].filter(Boolean).join(" · ") : "";
    const items = (order.items || []).map(item => `${item.quantity || 1}× ${escapeHtml(item.name || item.product_name || "Item")}`).join("<br>");
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

function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }
function escapeAttribute(value) { return escapeHtml(value).replace(/`/g, "&#96;"); }
customElements.define("cubecraft-production-card", CubecraftProductionCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "cubecraft-production-card", name: "Cubecraft Production", description: "Interactive production workboard for WooCommerce orders." });
