"""HTML + plain-text cards for wearable / hub alerts (Gmail-safe tables)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from app.livewell.brand import brand_name

_IST = timezone(timedelta(hours=5, minutes=30), name="IST")

_SEVERITY_UI = {
    "critical": {
        "badge": "SOS ALERT",
        "headline": "Needs immediate attention",
        "header_bg": "#7f1d1d",
        "accent": "#b42318",
        "badge_bg": "#fecaca",
        "badge_fg": "#7f1d1d",
    },
    "warning": {
        "badge": "WARNING",
        "headline": "Please check on the client",
        "header_bg": "#7c2d12",
        "accent": "#c2410c",
        "badge_bg": "#fed7aa",
        "badge_fg": "#7c2d12",
    },
    "info": {
        "badge": "UPDATE",
        "headline": "LiveWell360 alert",
        "header_bg": "#134e4a",
        "accent": "#0f766e",
        "badge_bg": "#ccfbf1",
        "badge_fg": "#134e4a",
    },
}


def format_alert_time(dt: datetime | None = None) -> str:
    when = dt or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    local = when.astimezone(_IST)
    return local.strftime("%d %b %Y, %I:%M:%S %p IST").replace(" 0", " ")


def _brand(text: str) -> str:
    from app.livewell.brand import with_brand

    return with_brand(text)


def format_mac(mac: str | None) -> str:
    raw = (mac or "").strip()
    if not raw:
        return ""
    hex_only = "".join(c for c in raw if c.isalnum())
    if len(hex_only) == 12:
        return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2)).upper()
    return raw.upper()


def _row(label: str, value: str) -> str:
    if not (value or "").strip():
        return ""
    safe_label = escape(label)
    safe_value = escape(value)
    return (
        "<tr>"
        f'<td style="padding:10px 16px;font-size:12px;color:#64748b;width:34%;'
        f'vertical-align:top;border-bottom:1px solid #eef2f6;">{safe_label}</td>'
        f'<td style="padding:10px 16px;font-size:14px;color:#0f172a;font-weight:600;'
        f'border-bottom:1px solid #eef2f6;">{safe_value}</td>'
        "</tr>"
    )


def _plain_row(label: str, value: str) -> str:
    if not (value or "").strip():
        return ""
    return f"{label}: {value}\n"


def render_iot_alert_email(
    *,
    title: str,
    severity: str,
    client_name: str,
    occurred_at: datetime | None = None,
    event_label: str | None = None,
    device_label: str | None = None,
    device_id: str | None = None,
    hub_id: str | None = None,
    mac_address: str | None = None,
    incident_id: str | None = None,
    status: str = "Open",
    note: str | None = None,
) -> tuple[str, str]:
    """Return (plain_text, html) for a wearable alert."""
    brand = brand_name()
    theme = _SEVERITY_UI.get((severity or "info").lower()) or _SEVERITY_UI["info"]
    when = format_alert_time(occurred_at)
    mac = format_mac(mac_address)
    device = (device_label or "").strip() or (device_id or "").strip()
    note_clean = (note or "").strip()
    event = (event_label or title).strip()

    fields = [
        ("Time", when),
        ("Client", client_name),
        ("Event", event),
        ("Device", device),
        ("Hub", (hub_id or "").strip()),
        ("MAC address", mac),
        ("Incident", (incident_id or "").strip()),
        ("Status", (status or "Open").strip().title()),
    ]

    rows_html = "".join(_row(label, value) for label, value in fields)
    note_html = ""
    if note_clean:
        note_html = (
            '<tr><td colspan="2" style="padding:14px 16px 4px;font-size:12px;color:#64748b;">'
            "Details</td></tr>"
            '<tr><td colspan="2" style="padding:0 16px 16px;font-size:14px;color:#334155;'
            f'line-height:1.5;">{escape(note_clean)}</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:0;background:#eef2f6;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;">{escape(theme["badge"])} for {escape(client_name or "client")} at {escape(when)}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f6;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;">
          <tr>
            <td style="background:{theme["header_bg"]};padding:22px 24px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="font-size:13px;letter-spacing:0.12em;color:#ccfbf1;font-weight:700;">{escape(brand.upper())}</td>
                  <td align="right">
                    <span style="display:inline-block;background:{theme["badge_bg"]};color:{theme["badge_fg"]};font-size:11px;font-weight:800;letter-spacing:0.08em;padding:5px 10px;border-radius:999px;">{escape(theme["badge"])}</span>
                  </td>
                </tr>
              </table>
              <div style="margin-top:14px;font-size:22px;line-height:1.3;color:#ffffff;font-weight:700;">{escape(title)}</div>
              <div style="margin-top:6px;font-size:14px;color:#fecaca;">{escape(_brand(theme["headline"]))}</div>
            </td>
          </tr>
          <tr>
            <td style="height:4px;background:{theme["accent"]};font-size:0;line-height:0;">&nbsp;</td>
          </tr>
          <tr>
            <td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {rows_html}
                {note_html}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 24px 22px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;line-height:1.5;">
              Open the family portal to acknowledge this alert. For a medical emergency, call local emergency services first.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    plain_bits = [
        f"{brand} — {theme['badge']}\n",
        f"{title}\n",
        f"{_brand(theme['headline'])}\n\n",
    ]
    plain_bits.extend(_plain_row(label, value) for label, value in fields)
    if note_clean:
        plain_bits.append(f"\nDetails:\n{note_clean}\n")
    plain_bits.append(
        "\nOpen the family portal to acknowledge this alert. "
        "For a medical emergency, call local emergency services first.\n"
    )
    return "".join(plain_bits), html


def render_iot_alert_sms(
    *,
    title: str,
    client_name: str,
    hub_id: str | None = None,
    mac_address: str | None = None,
    occurred_at: datetime | None = None,
) -> str:
    """Staff SMS / WhatsApp / Telegram. Plain words: no hub or device ids (those stay in the email)."""
    from app.livewell.brand import with_brand

    when = format_alert_time(occurred_at)
    # Plain ASCII: keeps each SMS in GSM-7 (160 chars) and closer to a DLT template.
    title = title.replace("—", "-").replace("–", "-").replace("·", "-").replace("→", "->")
    return with_brand(
        f"LiveWell360 ALERT: {title}\n{client_name} - {when}\n"
        "Acknowledge now: https://ops.kushalaya.com/kushalaya/alerts"
    )
