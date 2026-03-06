#!/usr/bin/env python3
"""Slack teavituste saatja OpenClaw pipeline'ile."""

import os, sys, json, argparse, urllib.request, urllib.error
from datetime import datetime

def get_webhook_url():
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if url:
        return url
    env_file = "/root/.openclaw/.env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SLACK_WEBHOOK_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

def send_slack(webhook_url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        print(f"Slack saatmine ebaõnnestus: {e}", file=sys.stderr)
        return False

def build_triaged_message(subject, score, sender):
    emoji = "🟢" if int(score) >= 6 else "🟡" if int(score) >= 4 else "⚪"
    action = "→ Kirjutaja" if int(score) >= 6 else "→ Vahele jäetud"
    return {"blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} Postiluure: triaaž"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Teema:*\n{subject}"},
            {"type": "mrkdwn", "text": f"*Saatja:*\n{sender}"},
            {"type": "mrkdwn", "text": f"*Skoor:*\n{score}/10"},
            {"type": "mrkdwn", "text": f"*Otsus:*\n{action}"},
        ]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"}]},
    ]}

def build_drafted_message(subject, docs_link=None):
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📝 Kirjutaja: draft valmis"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{subject}*"}},
    ]
    if docs_link:
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "📄 Ava Google Docsis"}, "url": docs_link, "action_id": "open_draft"},
        ]})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"}]})
    return {"blocks": blocks}

def build_error_message(error_text):
    return {"blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": "🔴 Pipeline viga"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"```{error_text}```"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"}]},
    ]}

def main():
    parser = argparse.ArgumentParser(description="Slack teavituste saatja")
    parser.add_argument("message", nargs="?", help="Lihtne tekstsõnum")
    parser.add_argument("--triaged", metavar="SUBJECT", help="Triaaži teavitus")
    parser.add_argument("--score", default="0", help="Triaaži skoor")
    parser.add_argument("--from-addr", default="?", help="Saatja")
    parser.add_argument("--drafted", metavar="SUBJECT", help="Draft valmis teavitus")
    parser.add_argument("--docs-link", help="Google Docs link")
    parser.add_argument("--error", metavar="TEXT", help="Veateade")
    parser.add_argument("--webhook-url", help="Webhook URL (override)")
    args = parser.parse_args()

    webhook_url = args.webhook_url or get_webhook_url()
    if not webhook_url:
        print("VIGA: SLACK_WEBHOOK_URL puudub!", file=sys.stderr)
        sys.exit(1)

    if args.triaged:
        payload = build_triaged_message(args.triaged, args.score, args.from_addr)
    elif args.drafted:
        payload = build_drafted_message(args.drafted, args.docs_link)
    elif args.error:
        payload = build_error_message(args.error)
    elif args.message:
        payload = {"text": args.message}
    else:
        parser.print_help()
        sys.exit(1)

    ok = send_slack(webhook_url, payload)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
