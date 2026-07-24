"""Constants for Cubecraft Production."""

from __future__ import annotations

DOMAIN = "cubecraft_production"
PLATFORMS = ["sensor", "binary_sensor"]
WEBHOOK_PREFIX = "cubecraft_production"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.orders"

CONF_BRIDGE_URL = "bridge_url"
CONF_SHARED_SECRET = "shared_secret"
CONF_USPS_CLIENT_ID = "usps_client_id"
CONF_USPS_CLIENT_SECRET = "usps_client_secret"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_POLL_MINUTES = "poll_minutes"
CONF_ESCALATION_HOURS = "escalation_hours"
CONF_USPS_TRACKING_URL = "usps_tracking_url"
CONF_USPS_TOKEN_URL = "usps_token_url"

DEFAULT_POLL_MINUTES = 30
DEFAULT_ESCALATION_HOURS = 24
# USPS's OAuth2 platform is apis.usps.com (production) / apis-tem.usps.com (testing).
DEFAULT_USPS_TRACKING_URL = "https://apis.usps.com/tracking/v3/tracking/{tracking_number}"
DEFAULT_USPS_TOKEN_URL = "https://apis.usps.com/oauth2/v3/token"

STAGES = ("queued", "printing", "qa_assembly", "packed", "awaiting_usps", "done")
ACTIVE_STAGES = STAGES[:-1]
NEXT_STAGE = {
    "queued": "printing",
    "printing": "qa_assembly",
    "qa_assembly": "packed",
    "packed": "awaiting_usps",
    "awaiting_usps": "done",
}
USER_STAGE_TRANSITIONS = {
    "queued": {"printing"},
    "printing": {"qa_assembly"},
    "qa_assembly": {"packed"},
    "packed": {"awaiting_usps"},
    "awaiting_usps": set(),
    "done": set(),
}
EVENT_ORDER_PROCESSING = "order.processing"
EVENT_ORDER_CHANGED = "order.changed"
EVENT_ORDER_CANCELLED = "order.cancelled"
EVENT_SHIPMENT_LABEL = "shipment.label_created"
# Operators advance work by hashtagging a WooCommerce order note (e.g. "#packed").
EVENT_STAGE_REQUESTED = "order.stage_requested"
EVENTS = {
    EVENT_ORDER_PROCESSING,
    EVENT_ORDER_CHANGED,
    EVENT_ORDER_CANCELLED,
    EVENT_SHIPMENT_LABEL,
    EVENT_STAGE_REQUESTED,
}
ACCEPTANCE_KEYWORDS = ("accepted", "usps in possession", "acceptance", "picked up")
