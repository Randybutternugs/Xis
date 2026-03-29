"""
HTML Email Templates
====================

Branded HTML wrappers for all transactional emails.
Each function returns an HTML string for Postmark's HtmlBody field.
"""

import html

LOGO_URL = "https://tullhydro.com/static/images/Tulllogo.svg"

CATEGORY_COLORS = {
    'General': '#8B8B8B',
    'Technical': '#F97316',
    'Order': '#5bc0de',
    'Feature': '#6ABD45',
}


def _category_badge_html(category):
    """Return an inline-styled category badge span."""
    color = CATEGORY_COLORS.get(category, '#8B8B8B')
    return (
        f'<span style="display:inline-block;background:{color};color:#000;'
        f'padding:4px 10px;border-radius:3px;font-family:monospace;'
        f'font-size:11px;font-weight:600;letter-spacing:1px;'
        f'text-transform:uppercase;">{html.escape(category)}</span>'
    )


def _wrap(body_html):
    """Wrap email content in the branded HTML shell."""
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="background-color:#000000;padding:28px 40px;">
              <img src="{LOGO_URL}" alt="Tull Hydroponics" width="100" style="display:block;" />
            </td>
          </tr>
          <!-- Green accent -->
          <tr>
            <td style="background-color:#6ABD45;height:4px;font-size:0;line-height:0;">&nbsp;</td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="background-color:#ffffff;padding:32px 40px;">
              {body_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#ffffff;padding:24px 40px;border-top:1px solid #e8e8e8;">
              <p style="margin:0;font-size:12px;color:#999999;">Tull Hydroponics LLC</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def contact_confirmation_html(ref_number, category):
    badge = _category_badge_html(category)
    body = f"""\
<div style="margin:0 0 20px;">
  {badge}
  <span style="color:#999;font-size:13px;margin-left:10px;font-family:monospace;">{ref_number}</span>
</div>
<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#333333;">
  Thank you for contacting Tull Hydroponics. Your message has been received.
</p>
<p style="margin:0;font-size:14px;line-height:1.6;color:#666666;">
  We typically respond within 24 hours.
</p>"""
    return _wrap(body)


def admin_notification_html(feedback, ref_number, site_url=''):
    category = feedback.feedbacktype
    badge = _category_badge_html(category)

    rows = f"""\
  <tr>
    <td style="padding:4px 0;font-size:14px;color:#999999;">From</td>
    <td style="padding:4px 0;font-size:14px;color:#333333;">{html.escape(feedback.feedbackmail)}</td>
  </tr>"""

    if feedback.serial_number:
        rows += f"""
  <tr>
    <td style="padding:4px 0;font-size:14px;color:#999999;">Serial #</td>
    <td style="padding:4px 0;font-size:14px;color:#333333;">{html.escape(feedback.serial_number)}</td>
  </tr>"""

    if feedback.feedbackorderid:
        rows += f"""
  <tr>
    <td style="padding:4px 0;font-size:14px;color:#999999;">Order ID</td>
    <td style="padding:4px 0;font-size:14px;color:#333333;">{html.escape(feedback.feedbackorderid)}</td>
  </tr>"""

    message = html.escape(feedback.feedbackfullfield).replace('\n', '<br>')

    deep_link = ''
    if site_url:
        link_url = f"{site_url.rstrip('/')}/viewdb/feedbackview#feedback-{feedback.id}"
        deep_link = (
            f'<a href="{link_url}" style="display:inline-block;background:#000;'
            f'color:#fff;padding:10px 20px;border-radius:4px;font-size:13px;'
            f'text-decoration:none;font-weight:500;margin-top:8px;">View in Feedback Panel</a>'
        )

    body = f"""\
<div style="margin:0 0 20px;">
  {badge}
  <span style="color:#999;font-size:13px;margin-left:10px;font-family:monospace;">{ref_number}</span>
</div>
<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#333333;">
  New contact form submission received.
</p>
<table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
{rows}
</table>
<div style="padding:16px;background-color:#f8f8f8;border-radius:4px;">
  <p style="margin:0 0 4px;font-size:12px;color:#999999;text-transform:uppercase;letter-spacing:1px;">Message</p>
  <p style="margin:0;font-size:14px;line-height:1.6;color:#333333;">{message}</p>
</div>
{deep_link}"""
    return _wrap(body)


def order_confirmation_html(customer_name, product, total):
    body = f"""\
<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#333333;">
  Hi {html.escape(customer_name)},
</p>
<p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#333333;">
  Thank you for your order!
</p>
<table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
  <tr>
    <td style="padding:4px 0;font-size:14px;color:#999999;width:100px;">Product</td>
    <td style="padding:4px 0;font-size:14px;color:#333333;">{html.escape(product)}</td>
  </tr>
  <tr>
    <td style="padding:4px 0;font-size:14px;color:#999999;">Total</td>
    <td style="padding:4px 0;font-size:14px;color:#333333;font-weight:600;">{html.escape(total)}</td>
  </tr>
</table>
<p style="margin:0;font-size:14px;line-height:1.6;color:#666666;">
  We'll follow up with shipping details soon.
</p>"""
    return _wrap(body)


def payment_failed_html(customer_name):
    body = f"""\
<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#333333;">
  Hi {html.escape(customer_name)},
</p>
<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#333333;">
  Unfortunately, your payment could not be processed.
</p>
<p style="margin:0;font-size:14px;line-height:1.6;color:#666666;">
  Please try ordering again with a different payment method.
</p>"""
    return _wrap(body)


def feedback_reply_html(message, ref, category=None):
    message_escaped = html.escape(message).replace('\n', '<br>')
    badge_row = ''
    if category:
        badge = _category_badge_html(category)
        badge_row = f'<div style="margin:0 0 20px;">{badge} <span style="color:#999;font-size:13px;margin-left:10px;font-family:monospace;">{ref}</span></div>'

    body = f"""\
{badge_row}
<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#333333;">
  Hi,
</p>
<p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#333333;">
  {message_escaped}
</p>
<p style="margin:0;font-size:12px;color:#999999;">
  Ref: {ref}
</p>"""
    return _wrap(body)
