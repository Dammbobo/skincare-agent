#!/usr/bin/env python3
"""
Contact by Tems — WhatsApp & Instagram AI Webhook Agent
Receives messages from WhatsApp Business API and Instagram Messaging API,
replies using Claude AI as Temi, the Contact by Tems skincare assistant.
"""

import os
import json
import hmac
import hashlib
import requests
import anthropic
from flask import Flask, request, jsonify

app = Flask(__name__)
client = anthropic.Anthropic()

# ── Configuration (set these as environment variables) ─────────────────────────
VERIFY_TOKEN      = os.environ.get("WEBHOOK_VERIFY_TOKEN", "contact_by_tems_secret")
WHATSAPP_TOKEN    = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
INSTAGRAM_TOKEN   = os.environ.get("INSTAGRAM_TOKEN", "")
INSTAGRAM_PAGE_ID = os.environ.get("INSTAGRAM_PAGE_ID", "")
META_APP_SECRET   = os.environ.get("META_APP_SECRET", "")

GRAPH_API = "https://graph.facebook.com/v19.0"

# Per-user conversation memory: { "wa_+2348012345678": [...], "ig_123456": [...] }
conversations: dict = {}

# Seen message IDs to prevent duplicate replies
processed_ids: set = set()


# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Temi, the AI skincare assistant for Contact by Tems — a premium skincare brand built on the belief that great skin is for everyone.

BRAND VOICE:
- Warm, confident, and empowering
- Knowledgeable but never intimidating
- Inclusive — every skin type, tone, and concern is welcome
- Keep replies conversational and concise (you are on WhatsApp/Instagram)
- Use line breaks to keep messages readable on mobile
- Use emojis naturally — this is social messaging

PRODUCT CATALOGUE:

LED FACE DEVICES:
- The Glow Wand (Red Light 630nm) — Anti-aging, collagen boost, fine lines. Use 10 mins daily.
- The Clear Shield (Blue Light 415nm) — Fights acne bacteria, reduces breakouts. Use 10-15 mins daily.
- The Luxe Pro (Multi-wavelength) — Red + Blue + Near-Infrared. Full skin transformation. Bestseller. Use 20 mins daily.
- The Eye Revival (Red + Near-Infrared) — Under-eye puffiness, dark circles, crow's feet. Use 5-10 mins daily.
- LED Lip Wand — Boosts lip circulation for natural plumpness, reduces lip lines.

SHEET MASKS:
- Hydra Burst Mask (Hyaluronic Acid + Aloe) — Deep hydration for dry skin. 2-3x weekly.
- Glow Reset Mask (Vitamin C + Niacinamide) — Brightens, fades dark spots. 2x weekly.
- Calm & Repair Mask (Centella + Green Tea) — Soothes sensitive, irritated skin. 3x weekly.
- Pore Refine Mask (Salicylic Acid + Charcoal) — Deep cleans pores, controls oil. 1-2x weekly.
- Age Rewind Mask (Retinol + Peptides + Collagen) — Plumps and firms mature skin. Weekly at night.

FACE BRUSHES:
- SilkClean Silicone Brush — Gentle daily cleansing. Hygienic, waterproof.
- SonicPulse Brush — 8,000 vibrations/min. Removes 99% of makeup and SPF.
- GlowBuff Exfoliating Brush — Physical exfoliation for smooth, radiant skin. 2-3x weekly.
- PrecisionBlend Foundation Brush — Seamless makeup application.

LIP CARE:
- Pout Perfector Overnight Mask — Intense overnight lip healing. Wake up to soft, plump lips.
- Sugar Kiss Lip Scrub — Exfoliates dry, flaky lips. Use before lip mask.
- Peptide Plump Lip Serum — Natural lip volume with peptides + hyaluronic acid. Morning & night.
- Glow Balm SPF 30 (6 shades) — Tinted lip balm with SPF. Daily protection with colour.

SKINCARE ROUTINES:

Acne-prone:
Morning: SonicPulse cleanse → Pore Refine Mask (2x/week) → Glow Balm SPF 30
Evening: SonicPulse cleanse → Clear Shield LED 15 mins → Calm & Repair Mask

Anti-aging:
Morning: SilkClean cleanse → Glow Reset Mask → Peptide Plump Serum → Glow Balm SPF 30
Evening: SilkClean cleanse → Luxe Pro LED 20 mins → Age Rewind Mask → Pout Perfector Lip Mask

Dry/dehydrated:
Morning: SilkClean cleanse → Hydra Burst Mask → Glow Balm SPF 30
Evening: SilkClean cleanse → Glow Wand LED 10 mins → Hydra Burst Mask

Dull/uneven:
Morning: GlowBuff Exfoliate (2x/week) → Glow Reset Mask → Glow Balm SPF 30
Evening: SilkClean cleanse → Glow Wand LED 10 mins → Glow Reset Mask

Sensitive:
Morning: SilkClean cleanse → Calm & Repair Mask → Glow Balm SPF 30
Evening: SilkClean cleanse → Glow Wand LED (low intensity) → Calm & Repair Mask

YOUR JOB:
1. Warmly welcome new customers to Contact by Tems
2. Ask about skin type and concerns before recommending
3. Recommend specific products from the catalogue
4. Build morning + evening routines on request
5. Explain how to use products correctly
6. Remind customers results take 4-6 weeks of consistency
7. Naturally suggest complementary products
8. If asked about price, ordering, or delivery — say you will connect them with the team shortly
9. Keep responses short and mobile-friendly — no long walls of text"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify Meta webhook payload signature for security."""
    if not META_APP_SECRET or not signature:
        return True  # skip in dev if secret not set
    expected = "sha256=" + hmac.new(
        META_APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_ai_reply(user_id: str, user_message: str) -> str:
    """Get a reply from Claude, maintaining per-user conversation history."""
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({"role": "user", "content": user_message})

    # Keep last 20 messages to avoid token bloat
    history = conversations[user_id][-20:]

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=history,
    )

    reply = next((b.text for b in response.content if hasattr(b, "text")), "")
    conversations[user_id].append({"role": "assistant", "content": reply})

    return reply


def send_whatsapp_message(to: str, text: str) -> dict:
    """Send a text message via WhatsApp Cloud API."""
    url = f"{GRAPH_API}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"[WhatsApp] Sent to {to} → {res.status_code}")
    return res.json()


def send_instagram_message(recipient_id: str, text: str) -> dict:
    """Send a text message via Instagram Messaging API."""
    url = f"{GRAPH_API}/{INSTAGRAM_PAGE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {INSTAGRAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"[Instagram] Sent to {recipient_id} → {res.status_code}")
    return res.json()


# ── Webhook routes ─────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Webhook verification endpoint.
    Meta sends a GET with hub.verify_token — respond with hub.challenge to confirm.
    Same endpoint handles both WhatsApp and Instagram verification.
    """
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[Webhook] Verified successfully")
        return challenge, 200

    print(f"[Webhook] Verification failed — token mismatch")
    return jsonify({"error": "Verification failed"}), 403


@app.route("/webhook", methods=["POST"])
def receive_message():
    """
    Main message receiver.
    Handles both WhatsApp Business API and Instagram Messaging API payloads.
    """
    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature):
        print("[Webhook] Invalid signature — rejected")
        return jsonify({"error": "Invalid signature"}), 401

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "no body"}), 200

    print(f"[Webhook] Incoming payload:\n{json.dumps(body, indent=2)}")

    object_type = body.get("object", "")

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    if object_type == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    msg_id   = msg.get("id", "")
                    msg_type = msg.get("type", "")
                    sender   = msg.get("from", "")

                    # Skip duplicates
                    if msg_id in processed_ids:
                        continue
                    processed_ids.add(msg_id)

                    # Only handle text messages
                    if msg_type != "text":
                        send_whatsapp_message(
                            sender,
                            "Hi! I can currently only read text messages. "
                            "Please type your question and I'll be happy to help ✨"
                        )
                        continue

                    user_text = msg.get("text", {}).get("body", "").strip()
                    if not user_text:
                        continue

                    print(f"[WhatsApp] From {sender}: {user_text}")
                    user_id = f"wa_{sender}"
                    reply = get_ai_reply(user_id, user_text)
                    send_whatsapp_message(sender, reply)

        return jsonify({"status": "ok"}), 200

    # ── Instagram ─────────────────────────────────────────────────────────────
    if object_type == "instagram":
        for entry in body.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id", "")
                message   = event.get("message", {})

                if not message or event.get("read") or event.get("delivery"):
                    continue

                msg_id = message.get("mid", "")
                if msg_id in processed_ids:
                    continue
                processed_ids.add(msg_id)

                user_text = message.get("text", "").strip()
                if not user_text:
                    # Handle non-text (sticker, image, etc.)
                    send_instagram_message(
                        sender_id,
                        "Hi! I can currently only read text messages. "
                        "Type your question and I'll help you find the perfect products ✨"
                    )
                    continue

                print(f"[Instagram] From {sender_id}: {user_text}")
                user_id = f"ig_{sender_id}"
                reply = get_ai_reply(user_id, user_text)
                send_instagram_message(sender_id, reply)

        return jsonify({"status": "ok"}), 200

    # Unknown object type
    return jsonify({"status": "ignored"}), 200


# ── Health check ───────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "agent": "Contact by Tems AI",
        "platforms": ["WhatsApp Business API", "Instagram Messaging API"],
        "webhook": "/webhook",
    })


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
  ✦ Contact by Tems — Webhook Agent
  ───────────────────────────────────────
  Server running on port {port}
  Webhook URL: http://your-domain.com/webhook

  Set these environment variables:
    ANTHROPIC_API_KEY      — Anthropic API key
    WEBHOOK_VERIFY_TOKEN   — Your chosen verify token (set same in Meta dashboard)
    META_APP_SECRET        — Meta app secret (for signature verification)
    WHATSAPP_TOKEN         — WhatsApp Cloud API access token
    WHATSAPP_PHONE_ID      — WhatsApp phone number ID
    INSTAGRAM_TOKEN        — Instagram page access token
    INSTAGRAM_PAGE_ID      — Instagram page ID
  ───────────────────────────────────────
    """)
    app.run(host="0.0.0.0", port=port, debug=False)
