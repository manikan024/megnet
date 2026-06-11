#!/usr/bin/env python3
"""Seed the local demo knowledge base with 50 articles and illustrated PNG images."""

import argparse
import json
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_ROOT = os.path.join(ROOT, "data", "local_kb")
ARTICLES_DIR = os.path.join(KB_ROOT, "articles")
IMAGES_DIR = os.path.join(KB_ROOT, "images")

# (filename, title, accent_rgb, drawing_style)
IMAGE_SPECS = [
    ("dashboard-overview.png", "Dashboard Overview", (37, 99, 235), "dashboard"),
    ("billing-flow.png", "Billing Flow", (5, 150, 105), "billing"),
    ("team-settings.png", "Team Settings", (124, 58, 237), "team"),
    ("mobile-app.png", "Mobile App", (219, 39, 119), "mobile"),
    ("integrations-hub.png", "Integrations Hub", (234, 88, 12), "integrations"),
    ("security-center.png", "Security Center", (220, 38, 38), "security"),
    ("reports-analytics.png", "Reports & Analytics", (8, 145, 178), "reports"),
    ("onboarding-wizard.png", "Onboarding Wizard", (79, 70, 229), "onboarding"),
    ("ticket-workflow.png", "Ticket Workflow", (13, 148, 136), "workflow"),
    ("api-console.png", "API Console", (100, 116, 139), "api"),
    ("notification-center.png", "Notification Center", (202, 138, 4), "notifications"),
    ("help-center.png", "Help Center", (147, 51, 234), "help"),
]

W, H = 640, 360
BG = (248, 250, 252)
PANEL = (255, 255, 255)
MUTED = (148, 163, 184)
LINE = (226, 232, 240)
TEXT = (15, 23, 42)

ARTICLE_IMAGE_MAP = {
    "001": "dashboard-overview.png",
    "006": "onboarding-wizard.png",
    "010": "billing-flow.png",
    "015": "team-settings.png",
    "020": "integrations-hub.png",
    "025": "security-center.png",
    "030": "mobile-app.png",
    "035": "reports-analytics.png",
    "040": "ticket-workflow.png",
    "045": "api-console.png",
    "048": "notification-center.png",
    "050": "help-center.png",
}

CATEGORIES = {
    "Onboarding": [
        ("Getting Started with AcmeDesk", "Create your account, verify email, and complete the welcome checklist. Navigate to Settings > Profile to update your display name and timezone."),
        ("Inviting Team Members", "Go to Team > Invite. Enter email addresses and assign roles: Admin, Agent, or Viewer. Invites expire after 7 days."),
        ("Workspace Setup Checklist", "Configure business hours, default ticket queue, and notification preferences before going live."),
        ("Understanding the Dashboard", "The dashboard shows open tickets, SLA breaches, team activity, and quick actions. Customize widgets from the gear icon."),
        ("First Ticket Walkthrough", "Create a ticket from Tickets > New. Add subject, priority, assignee, and tags. Reply from the conversation panel."),
        ("Importing Existing Data", "Use Admin > Import to upload CSV contacts and tickets. Download the template first to match required columns."),
        ("Keyboard Shortcuts", "Press ? to open shortcuts. Common: N new ticket, / search, G then T go to tickets."),
    ],
    "Billing": [
        ("Subscription Plans Overview", "AcmeDesk offers Starter, Professional, and Enterprise plans. Compare limits at Billing > Plans."),
        ("Updating Payment Method", "Billing > Payment Methods > Add card. Primary card is charged on renewal date."),
        ("Viewing Invoices", "All invoices are under Billing > Invoices. Download PDF or email to accounting."),
        ("Upgrading Your Plan", "Billing > Change Plan. Upgrades apply immediately; downgrades at end of billing cycle."),
        ("Usage Limits and Overages", "Starter: 3 agents, 1K tickets/mo. Professional: 15 agents, 10K tickets. Enterprise: custom."),
        ("Canceling Subscription", "Billing > Cancel. Data export available for 30 days after cancellation."),
        ("Billing FAQ", "Tax receipts include VAT where applicable. Contact billing@acmedesk.example for PO invoices."),
    ],
    "Features": [
        ("Ticket Queues and Routing", "Create queues per team. Auto-assign by round-robin or load-based rules."),
        ("SLA Policies", "Define response and resolution targets by priority. Breach notifications go to assignee and manager."),
        ("Canned Responses", "Save reusable replies under Library > Canned. Use /shortcut in composer to insert."),
        ("Tags and Custom Fields", "Admin > Fields to add dropdowns, dates, or text fields. Tags filter views and reports."),
        ("Automation Rules", "Triggers on create/update/schedule. Actions: assign, tag, email, webhook."),
        ("Knowledge Base Publishing", "Draft articles in KB > New. Publish to public help center or internal only."),
        ("Customer Portal", "Enable portal at Settings > Portal. Customers log in to view and reply to their tickets."),
    ],
    "Integrations": [
        ("Slack Integration", "Connect at Integrations > Slack. Route notifications to channels by queue or priority."),
        ("Email Channel Setup", "Add support@yourdomain.com. Verify DNS records: SPF, DKIM, MX forwarding."),
        ("Webhook Configuration", "POST JSON to your URL on ticket events. Retry 3 times with exponential backoff."),
        ("API Authentication", "Generate API keys at Admin > API. Use Bearer token in Authorization header."),
        ("Zapier Connector", "Search AcmeDesk in Zapier. Triggers: new ticket, status change. Actions: create ticket, add note."),
        ("Salesforce Sync", "Map contacts and cases bidirectionally. Enterprise plan required."),
        ("Google Workspace SSO", "Configure SAML in Security > SSO. Test with a pilot group before org-wide rollout."),
    ],
    "Security": [
        ("Two-Factor Authentication", "Profile > Security > Enable 2FA. Supports authenticator apps and SMS backup."),
        ("Role Permissions Matrix", "Admin: full access. Agent: tickets + KB edit. Viewer: read-only reports."),
        ("IP Allowlisting", "Enterprise: restrict admin login to corporate IP ranges under Security > Network."),
        ("Audit Log", "Admin > Audit shows who changed settings, exported data, or deleted tickets."),
        ("Data Retention Policy", "Default: tickets archived after 2 years. Configure per plan in Admin > Retention."),
        ("GDPR Data Export", "Request full user data export from Profile > Privacy. Processed within 72 hours."),
        ("Session Timeout", "Default 8 hours idle logout. Admins can set 1–24 hours under Security > Sessions."),
    ],
    "Mobile": [
        ("Installing the Mobile App", "Download AcmeDesk from iOS App Store or Google Play. Sign in with workspace URL."),
        ("Push Notifications", "Enable in app Settings. Choose ticket assigned, mentions, or SLA breach alerts."),
        ("Offline Mode", "Draft replies offline; sync when connection returns. Read-only for ticket list cache."),
        ("Mobile Attachments", "Photos and files up to 25MB. Compress large images automatically."),
    ],
    "Admin": [
        ("User Roles and Teams", "Organize agents into teams. Managers see team queues and performance reports."),
        ("Branding Customization", "Upload logo and brand colors under Settings > Branding. Applies to portal and emails."),
        ("Business Hours", "Set timezone and hours per queue. After-hours auto-replies use Business Hours message."),
        ("Email Templates", "Customize outbound templates with {{ticket.id}} and {{customer.name}} placeholders."),
        ("Sandbox Environment", "Enterprise: clone production to sandbox for testing automations without live impact."),
        ("Bulk User Management", "CSV import users or deactivate in bulk from Admin > Users."),
    ],
    "Troubleshooting": [
        ("Login Issues", "Reset password from login page. If SSO fails, verify IdP certificate expiry."),
        ("Email Not Creating Tickets", "Check forwarding rule and spam folder. Verify domain DNS in Integrations > Email."),
        ("Slow Dashboard Loading", "Clear browser cache. Large date ranges in reports may take longer; narrow filters."),
        ("Webhook Delivery Failures", "View failure log at Integrations > Webhooks > History. Fix 4xx/5xx on your endpoint."),
        ("Missing Notifications", "Check profile notification settings and Do Not Disturb schedule."),
        ("Export Errors", "Exports over 50K rows run async. Download link emailed when ready."),
        ("Contact Support", "Email help@acmedesk.example or use in-app chat. Include workspace ID and ticket ID if applicable."),
    ],
}


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "Arial.ttf",
    ):
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _rounded_rect(draw, xy, radius, fill, outline=LINE, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _header(draw, title: str, accent: tuple):
    draw.rectangle([0, 0, W, 52], fill=accent)
    draw.text((20, 16), title, fill=(255, 255, 255), font=_font(18))
    for x in (W - 88, W - 56, W - 24):
        draw.ellipse([x, 18, x + 16, 34], fill=(200, 220, 255), outline=(255, 255, 255))


def _sidebar(draw, accent: tuple):
    draw.rectangle([0, 52, 140, H], fill=(241, 245, 249))
    draw.line([140, 52, 140, H], fill=LINE, width=1)
    for i, y in enumerate(range(72, 220, 36)):
        w = 90 if i == 0 else 70
        _rounded_rect(draw, [20, y, 20 + w, y + 22], 6, accent if i == 0 else PANEL)


def _draw_dashboard(draw, accent):
    _sidebar(draw, accent)
    for i, (x, y) in enumerate([(160, 72), (400, 72), (160, 200), (400, 200)]):
        _rounded_rect(draw, [x, y, x + 220, y + 110], 10, PANEL)
        draw.rectangle([x + 16, y + 16, x + 120, y + 28], fill=LINE)
        if i == 3:
            for j, h in enumerate([40, 65, 50, 80, 55]):
                bx = x + 20 + j * 36
                draw.rectangle([bx, y + 90 - h, bx + 24, y + 90], fill=accent if j == 2 else MUTED)
        else:
            draw.line([x + 16, y + 44, x + 200, y + 44], fill=LINE, width=1)
            draw.line([x + 16, y + 64, x + 160, y + 64], fill=LINE, width=1)


def _draw_billing(draw, accent):
    _rounded_rect(draw, [180, 80, 460, 300], 14, PANEL)
    draw.text((200, 98), "Invoice #1042", fill=TEXT, font=_font(16))
    draw.text((200, 126), "Professional Plan · $49/mo", fill=MUTED, font=_font(13))
    _rounded_rect(draw, [200, 160, 420, 200], 8, (236, 253, 245))
    draw.text((216, 172), "Payment method", fill=accent, font=_font(13))
    draw.text((216, 192), "•••• 4242", fill=TEXT, font=_font(14))
    _rounded_rect(draw, [200, 220, 300, 256], 8, accent)
    draw.text((218, 232), "Pay now", fill=(255, 255, 255), font=_font(13))


def _draw_team(draw, accent):
    for i, x in enumerate([120, 240, 360, 480]):
        _rounded_rect(draw, [x - 40, 100, x + 40, 240], 12, PANEL)
        draw.ellipse([x - 24, 118, x + 24, 166], fill=accent if i == 0 else MUTED)
        draw.rectangle([x - 30, 182, x + 30, 192], fill=LINE)
        draw.rectangle([x - 22, 204, x + 22, 214], fill=LINE)
    draw.text((220, 268), "Admin · Agent · Viewer roles", fill=MUTED, font=_font(13))


def _draw_mobile(draw, accent):
    _rounded_rect(draw, [250, 60, 390, 310], 24, PANEL, outline=accent, width=3)
    draw.rectangle([280, 78, 360, 98], fill=LINE)
    for y in (120, 160, 200, 240):
        _rounded_rect(draw, [270, y, 370, y + 28], 6, (252, 231, 243) if y == 120 else (241, 245, 249))
    draw.ellipse([305, 286, 335, 296], fill=accent)


def _draw_integrations(draw, accent):
    cx, cy = 320, 190
    draw.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=accent)
    draw.text((cx - 10, cy - 10), "Hub", fill=(255, 255, 255), font=_font(13))
    for i, (x, y) in enumerate([(140, 100), (500, 100), (140, 260), (500, 260)]):
        _rounded_rect(draw, [x - 50, y - 28, x + 50, y + 28], 8, PANEL)
        draw.line([x, y, cx, cy], fill=accent, width=2)
        draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=MUTED if i else accent)


def _draw_security(draw, accent):
    pts = [(320, 70), (390, 110), (390, 190), (320, 240), (250, 190), (250, 110)]
    draw.polygon(pts, fill=(254, 226, 226), outline=accent, width=3)
    draw.rectangle([300, 150, 340, 190], fill=accent)
    draw.arc([305, 120, 335, 165], 180, 0, fill=accent, width=4)
    _rounded_rect(draw, [180, 260, 460, 310], 10, PANEL)
    draw.text((200, 276), "2FA enabled · SSO · Audit log", fill=TEXT, font=_font(13))


def _draw_reports(draw, accent):
    _rounded_rect(draw, [100, 80, 540, 300], 12, PANEL)
    draw.text((120, 96), "Weekly ticket volume", fill=TEXT, font=_font(15))
    base = 260
    for i, h in enumerate([80, 120, 95, 150, 110, 170, 130]):
        x = 130 + i * 58
        draw.rectangle([x, base - h, x + 36, base], fill=accent if i == 5 else MUTED)
    draw.line([120, base, 520, base], fill=LINE, width=2)


def _draw_onboarding(draw, accent):
    steps = [(120, 180, "1", "Account"), (280, 180, "2", "Team"), (440, 180, "3", "Go live")]
    for i, (x, y, num, label) in enumerate(steps):
        color = accent if i == 1 else MUTED
        draw.ellipse([x - 28, y - 28, x + 28, y + 28], fill=color)
        draw.text((x - 6, y - 10), num, fill=(255, 255, 255), font=_font(16))
        draw.text((x - 30, y + 40), label, fill=TEXT, font=_font(13))
        if i < 2:
            draw.line([x + 32, y, steps[i + 1][0] - 32, y], fill=accent, width=3)


def _draw_workflow(draw, accent):
    boxes = [(80, 150, "New"), (220, 150, "Assign"), (360, 150, "Resolve"), (500, 150, "Close")]
    for i, (x, y, label) in enumerate(boxes):
        _rounded_rect(draw, [x, y, x + 90, y + 50], 8, accent if i == 1 else PANEL, outline=accent if i == 1 else LINE)
        draw.text((x + 14, y + 16), label, fill=TEXT if i != 1 else (255, 255, 255), font=_font(13))
        if i < 3:
            draw.polygon([(x + 98, y + 25), (x + 118, y + 25), (x + 108, y + 18)], fill=accent)
            draw.polygon([(x + 98, y + 25), (x + 118, y + 25), (x + 108, y + 32)], fill=accent)


def _draw_api(draw, accent):
    _rounded_rect(draw, [120, 70, 520, 300], 12, (30, 41, 59))
    draw.rectangle([120, 70, 520, 100], fill=(51, 65, 85))
    for i, c in enumerate(["#", "GET /api/v1/tickets", "Authorization: Bearer …", '{ "status": "open" }']):
        draw.text((140, 118 + i * 36), c, fill=(134, 239, 172) if i else MUTED, font=_font(13))
    draw.ellipse([132, 82, 148, 98], fill=(248, 113, 113))
    draw.ellipse([156, 82, 172, 98], fill=(250, 204, 21))
    draw.ellipse([180, 82, 196, 98], fill=(74, 222, 128))


def _draw_notifications(draw, accent):
    draw.ellipse([280, 90, 360, 170], fill=accent)
    draw.polygon([(300, 170), (340, 170), (320, 210)], fill=accent)
    draw.ellipse([350, 88, 372, 110], fill=(220, 38, 38))
    draw.text((356, 90), "3", fill=(255, 255, 255), font=_font(11))
    for y, txt in [(230, "Ticket assigned to you"), (262, "SLA breach warning"), (294, "New mention in #support")]:
        _rounded_rect(draw, [140, y, 500, y + 24], 6, PANEL)
        draw.ellipse([152, y + 8, 162, y + 18], fill=accent)
        draw.text((172, y + 4), txt, fill=TEXT, font=_font(12))


def _draw_help(draw, accent):
    _rounded_rect(draw, [200, 80, 440, 280], 14, PANEL)
    draw.rectangle([200, 80, 440, 120], fill=accent)
    draw.text((220, 92), "Help Center", fill=(255, 255, 255), font=_font(16))
    draw.text((260, 150), "?", fill=accent, font=_font(48))
    for y in (210, 238):
        draw.rectangle([220, y, 420, y + 10], fill=LINE)


DRAWERS = {
    "dashboard": _draw_dashboard,
    "billing": _draw_billing,
    "team": _draw_team,
    "mobile": _draw_mobile,
    "integrations": _draw_integrations,
    "security": _draw_security,
    "reports": _draw_reports,
    "onboarding": _draw_onboarding,
    "workflow": _draw_workflow,
    "api": _draw_api,
    "notifications": _draw_notifications,
    "help": _draw_help,
}


def _make_image(filename: str, title: str, rgb: tuple, style: str, force: bool = False) -> None:
    os.makedirs(IMAGES_DIR, exist_ok=True)
    path = os.path.join(IMAGES_DIR, filename)
    if os.path.isfile(path) and not force:
        return

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _header(draw, title, rgb)
    drawer = DRAWERS.get(style)
    if drawer:
        drawer(draw, rgb)
    else:
        _rounded_rect(draw, [80, 80, W - 80, H - 40], 12, PANEL)
        draw.text((100, 160), title, fill=TEXT, font=_font(20))

    img.save(path, "PNG", optimize=True)


def _build_articles():
    articles = []
    idx = 1
    for category, items in CATEGORIES.items():
        for title, content in items:
            aid = f"{idx:03d}"
            slug = title.lower().replace(" ", "-").replace("&", "and")[:40]
            article = {
                "id": aid,
                "title": title,
                "category": category,
                "tags": [category.lower(), slug.split("-")[0]],
                "content": content + f" Category: {category}. Article ID: {aid}.",
                "updated_at": str(date.today()),
            }
            img_file = ARTICLE_IMAGE_MAP.get(aid)
            if img_file:
                article["image"] = {
                    "path": f"images/{img_file}",
                    "caption": title,
                }
            articles.append(article)
            idx += 1
            if idx > 50:
                return articles
    return articles


def main():
    parser = argparse.ArgumentParser(description="Seed local KB articles and illustration images.")
    parser.add_argument("--force-images", action="store_true", help="Regenerate PNG illustrations even if they exist.")
    args = parser.parse_args()

    os.makedirs(ARTICLES_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    for filename, title, rgb, style in IMAGE_SPECS:
        _make_image(filename, title, rgb, style, force=args.force_images)

    articles = _build_articles()
    manifest = {
        "version": 1,
        "count": len(articles),
        "updated_at": str(date.today()),
        "articles": [{"id": a["id"], "title": a["title"], "category": a["category"]} for a in articles],
    }

    for article in articles:
        slug = article["title"].lower().replace(" ", "-")[:50]
        path = os.path.join(ARTICLES_DIR, f"{article['id']}-{slug}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)

    manifest_path = os.path.join(KB_ROOT, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Seeded {len(articles)} articles in {KB_ROOT}")
    print(f"Created {len(IMAGE_SPECS)} images in {IMAGES_DIR}")


if __name__ == "__main__":
    main()
