# Cubecraft Production (Home Assistant)

Home Assistant custom integration for the Cubecraft Production pipeline — an
operator-driven production queue for WooCommerce orders with USPS acceptance
tracking. The interactive Lovelace workboard card is **bundled**: installing the
integration installs the card (no separate resource setup).

> This repository is a generated distribution surface for HACS. Development
> happens in the CubeOps monorepo; do not open PRs here.

## Install via HACS

1. HACS → ⋮ → **Custom repositories** → add this repo, category **Integration**.
2. Install **Cubecraft Production**, then restart Home Assistant.
3. Add the integration under **Settings → Devices & services** and configure the
   WordPress bridge URL, shared secret, USPS credentials, and notify service.
4. Add a `custom:cubecraft-production-card` card to a dashboard — it is already
   registered by the integration.

See the integration options and the companion **Cubecraft Production Bridge**
WordPress plugin for the full setup.
