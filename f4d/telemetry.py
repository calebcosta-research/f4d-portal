"""Application Insights telemetry, for the Azure deployment.

Dormant unless APPLICATIONINSIGHTS_CONNECTION_STRING is set: nothing is
imported and nothing is sent, which is how it behaves on Posit Connect. The
Azure Monitor package is imported only once a connection string exists, so it
need not be installed where telemetry isn't used.

Authentication follows App Service's convention: by default the connection
string alone is used. If APPLICATIONINSIGHTS_AUTHENTICATION_STRING contains
"Authorization=AAD", telemetry is sent with the App Service's managed identity
instead -- required when the App Insights resource has local auth disabled. A
"ClientId=<guid>" in that string selects a user-assigned identity.

Only the app's own "f4d" logger is exported, not Streamlit's or the Azure
SDK's. Events carry internal numeric IDs and page names only -- never
usernames, passwords, or anything a user typed into a form.
"""
import logging
import os
import threading

log = logging.getLogger("f4d")
# Without a handler, Python prints warnings from an unconfigured logger to
# stderr itself. The NullHandler keeps output exactly as it was wherever
# telemetry is off.
log.addHandler(logging.NullHandler())

_lock = threading.Lock()
_started = False


def setup():
    """Start exporting to Application Insights, once per process.

    Streamlit re-runs the entry script on every interaction, so this is called
    many times; only the first call does anything. It never raises: a
    telemetry problem must not take the app down.
    """
    global _started
    if _started:
        return
    with _lock:
        if _started:
            return
        _started = True

        conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
        if not conn:
            return
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            options = {"connection_string": conn, "logger_name": "f4d"}
            credential = _managed_identity()
            if credential is not None:
                options["credential"] = credential
            # Shows as the "cloud role" in App Insights.
            os.environ.setdefault("OTEL_SERVICE_NAME", "f4d-portal")
            # The SDK otherwise reports its own usage ("statsbeat") to a
            # Microsoft endpoint outside this App Insights resource. Off by
            # default for an internal-only tenant; set the variable to false to
            # allow it.
            os.environ.setdefault("APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL", "true")
            configure_azure_monitor(**options)
            log.setLevel(logging.INFO)
            log.info("telemetry started")
        except Exception:  # noqa: BLE001 - never let telemetry break the app
            logging.getLogger(__name__).exception(
                "Application Insights setup failed; continuing without telemetry")


def _managed_identity():
    """A managed-identity credential if the auth string asks for one."""
    auth = os.environ.get("APPLICATIONINSIGHTS_AUTHENTICATION_STRING", "")
    parts = dict(p.split("=", 1) for p in auth.split(";") if "=" in p)
    if parts.get("Authorization", "").strip().upper() != "AAD":
        return None
    from azure.identity import ManagedIdentityCredential
    client_id = parts.get("ClientId", "").strip()
    return ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()


def event(name, **properties):
    """Record a named custom event.

    Properties should be internal IDs or labels (page names, numeric IDs),
    never personal data or form content. A no-op when telemetry is off.
    """
    if log.isEnabledFor(logging.INFO):
        # Telemetry attributes can't be None; drop those rather than warn.
        props = {k: v for k, v in properties.items() if v is not None}
        log.info(name, extra={"microsoft.custom_event.name": name, **props})
