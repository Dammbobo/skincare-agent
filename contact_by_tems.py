import anthropic
import json
import os
from datetime import datetime
from flask import Flask, request, redirect, make_response, jsonify
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY")
print(f"API KEY LOADED: {os.environ.get('ANTHROPIC_API_KEY', 'NOT FOUND')[:20]}")

app = Flask(__name__)
conversation = []

ORDERS_FILE = "orders.json"

PRODUCT_MENU = {
    "LED Face Devices": {
        "The Glow Wand (Red Light 630nm)": 45000,
        "The Clear Shield (Blue Light 415nm)": 45000,
        "The Luxe Pro (Multi-wavelength)": 85000,
        "The Eye Revival (Red + Near-Infrared)": 38000,
    },
    "Sheet Masks (Pack of 5)": {
        "Hydra Burst Mask": 8500,
        "Glow Reset Mask": 8500,
        "Calm & Repair Mask": 8500,
        "Pore Refine Mask": 8500,
        "Age Rewind Mask": 9500,
    },
    "Face Brushes": {
        "SilkClean Silicone Brush": 18000,
        "SonicPulse Brush": 28000,
        "GlowBuff Exfoliating Brush": 15000,
        "PrecisionBlend Foundation Brush": 12000,
    },
    "Lip Care": {
        "Pout Perfector Overnight Mask": 6500,
        "Sugar Kiss Lip Scrub": 5500,
        "Peptide Plump Lip Serum": 9500,
        "Glow Balm SPF 30": 7500,
        "LED Lip Wand (Red Light)": 32000,
    },
}

# Flat lookup: product name -> price
ALL_PRODUCTS = {name: price for cat in PRODUCT_MENU.values() for name, price in cat.items()}

SYSTEM_PROMPT = """You are Temi, the AI skincare assistant for Contact by Tems — a premium skincare brand.

BRAND VOICE:
- Direct, confident, and professional
- Friendly but concise — no filler phrases or excessive enthusiasm
- Skip greetings like "Great question!" or "Absolutely!" — just answer
- Give clear recommendations with reasons, not lengthy preambles
- One or two sentences of context is enough before the recommendation

PRODUCT CATALOGUE WITH PRICES (Nigerian Naira):

1. LED FACE DEVICES
   - The Glow Wand (Red Light 630nm) — ₦45,000: Boosts collagen, reduces fine lines and wrinkles, firms skin. Use 10 mins daily after cleansing.
   - The Clear Shield (Blue Light 415nm) — ₦45,000: Targets acne-causing bacteria, reduces breakouts and inflammation. Use 10-15 mins daily on affected areas.
   - The Luxe Pro (Multi-wavelength) — ₦85,000: Combines red, blue, and near-infrared light for complete skin transformation. Bestseller. Use 20 mins daily.
   - The Eye Revival (Red + Near-Infrared) — ₦38,000: Specifically designed for under-eye area. Reduces puffiness, dark circles, and crow's feet. Use 5-10 mins daily.
   Best for: Anti-aging, acne, dullness, uneven texture, dark spots

2. SHEET MASKS (Pack of 5)
   - Hydra Burst Mask (Hyaluronic Acid + Aloe) — ₦8,500: Intense hydration for dry and dehydrated skin. Use 2-3x weekly.
   - Glow Reset Mask (Vitamin C + Niacinamide) — ₦8,500: Brightens dull skin, fades dark spots, evens skin tone. Use 2x weekly.
   - Calm & Repair Mask (Centella Asiatica + Green Tea) — ₦8,500: Soothes redness, irritation, and sensitive skin. Use 3x weekly.
   - Pore Refine Mask (Salicylic Acid + Charcoal) — ₦8,500: Deep cleans pores, controls oil, prevents breakouts. Use 1-2x weekly.
   - Age Rewind Mask (Retinol + Peptides + Collagen) — ₦9,500: Plumps, firms, and smooths mature skin. Use 1x weekly at night.
   Best for: Quick skin boosts between LED sessions or as standalone treatment

3. FACE BRUSHES
   - SilkClean Silicone Brush — ₦18,000: Ultra-soft silicone bristles for daily gentle cleansing. Hygienic, waterproof, battery-powered.
   - SonicPulse Brush — ₦28,000: 8,000 vibrations/min sonic cleansing. Removes 99% of makeup, SPF, and impurities. Waterproof.
   - GlowBuff Exfoliating Brush — ₦15,000: Gentle physical exfoliation for smooth, radiant skin. Use 2-3x weekly.
   - PrecisionBlend Foundation Brush — ₦12,000: Seamless, streak-free makeup application. Flat kabuki style.
   Tips: Clean brushes after every use. Replace cleansing brush heads every 3 months.
   Best for: Deep cleansing before applying sheet masks or LED treatments

4. LIP CARE
   - Pout Perfector Overnight Mask — ₦6,500: Intense overnight lip treatment. Wake up to soft, plump, healed lips.
   - Sugar Kiss Lip Scrub — ₦5,500: Gently exfoliates dry, flaky lips. Use before lip mask for best results.
   - Peptide Plump Lip Serum — ₦9,500: Stimulates lip volume naturally with peptides and hyaluronic acid. Use morning and night.
   - Glow Balm SPF 30 (6 shades) — ₦7,500: Tinted lip balm with SPF protection. Everyday wear with a hint of colour.
   - LED Lip Wand (Red Light) — ₦32,000: Boosts circulation for natural plumpness and targets lip lines. Use 5 mins daily.

SKINCARE ROUTINES BY CONCERN:

Acne-prone skin:
Morning: SonicPulse Brush cleanse → Pore Refine Mask (2x/week) → Glow Balm SPF 30
Evening: SonicPulse Brush cleanse → Clear Shield LED 15 mins → Calm & Repair Mask (3x/week)

Anti-aging:
Morning: SilkClean Brush cleanse → Glow Reset Mask (2x/week) → Peptide Plump Serum → Glow Balm SPF 30
Evening: SilkClean Brush cleanse → The Luxe Pro LED 20 mins → Age Rewind Mask (weekly) → Pout Perfector Overnight Mask

Dry/dehydrated skin:
Morning: SilkClean Brush cleanse → Hydra Burst Mask (3x/week) → Glow Balm SPF 30
Evening: SilkClean Brush cleanse → Glow Wand LED 10 mins → Hydra Burst Mask

Dull/uneven skin:
Morning: GlowBuff Exfoliating Brush (2x/week) → Glow Reset Mask → Glow Balm SPF 30
Evening: SilkClean Brush cleanse → Glow Wand LED 10 mins → Glow Reset Mask

Sensitive skin:
Morning: SilkClean Brush cleanse → Calm & Repair Mask (3x/week) → Glow Balm SPF 30
Evening: SilkClean Brush cleanse → Glow Wand LED 10 mins (low intensity) → Calm & Repair Mask

YOUR JOB:
1. Ask about skin type and concerns before recommending — keep it to one focused question
2. Recommend specific products with prices and a brief reason why
3. Build morning + evening routines when asked — list them cleanly
4. Explain usage in one sentence per product
5. Mention that results take 4-6 weeks of consistent use, once — don't repeat it
6. Suggest complementary products only when genuinely relevant
7. Never recommend products not in our catalogue
8. When a customer is ready to order, direct them to the "Place an Order" button

Skin types: Normal, Dry, Oily, Combination, Sensitive, Mature
Concerns: Acne, Aging, Dullness, Dark spots, Dryness, Large pores, Uneven texture, Lip care"""


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contact by Tems — Skincare Assistant</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', Georgia, sans-serif;
    background: #0d0d0d;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 30px 16px;
  }

  .header {
    text-align: center;
    margin-bottom: 28px;
  }

  .brand {
    font-size: 11px;
    letter-spacing: 6px;
    color: #c9a96e;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .logo {
    font-size: 32px;
    font-weight: 300;
    color: #f5f0e8;
    letter-spacing: 4px;
    text-transform: uppercase;
  }

  .logo span {
    color: #c9a96e;
    font-weight: 700;
  }

  .divider {
    width: 60px;
    height: 1px;
    background: linear-gradient(to right, transparent, #c9a96e, transparent);
    margin: 14px auto;
  }

  .tagline {
    font-size: 12px;
    color: #888;
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  .quick-btns {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 720px;
  }

  .qbtn {
    background: transparent;
    border: 1px solid #c9a96e;
    color: #c9a96e;
    padding: 7px 16px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s;
    letter-spacing: 1px;
    text-transform: uppercase;
    text-decoration: none;
    display: inline-block;
  }

  .qbtn:hover {
    background: #c9a96e;
    color: #0d0d0d;
  }

  .qbtn.order-btn {
    background: linear-gradient(135deg, #c9a96e, #b8933a);
    color: #0d0d0d;
    border: none;
    font-weight: 700;
  }

  .qbtn.order-btn:hover {
    opacity: 0.85;
  }

  .chat-box {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    width: 100%;
    max-width: 720px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }

  .chat-top {
    background: linear-gradient(135deg, #1a1408, #2d2006);
    border-bottom: 1px solid #c9a96e33;
    padding: 18px 24px;
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .avatar {
    width: 46px;
    height: 46px;
    background: linear-gradient(135deg, #c9a96e, #e8c98a);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
  }

  .agent-meta h2 {
    color: #f5f0e8;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 1px;
  }

  .agent-meta p {
    color: #c9a96e;
    font-size: 11px;
    margin-top: 3px;
    letter-spacing: 1px;
  }

  .dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    background: #4caf50;
    border-radius: 50%;
    margin-right: 5px;
  }

  #chat {
    padding: 24px;
    min-height: 420px;
    max-height: 500px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }

  .msg {
    display: flex;
    flex-direction: column;
  }

  .msg.user { align-items: flex-end; }
  .msg.agent { align-items: flex-start; }

  .msg-label {
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #555;
    margin-bottom: 5px;
    font-weight: 600;
  }

  .msg.user .msg-label { color: #c9a96e88; }

  .bubble {
    max-width: 72%;
    padding: 13px 18px;
    font-size: 14px;
    line-height: 1.7;
    border-radius: 16px;
    white-space: pre-wrap;
  }

  .bubble.user {
    background: linear-gradient(135deg, #c9a96e, #b8933a);
    color: #0d0d0d;
    border-bottom-right-radius: 4px;
    font-weight: 500;
  }

  .bubble.agent {
    background: #242424;
    color: #e8e0d0;
    border-bottom-left-radius: 4px;
    border: 1px solid #2e2e2e;
  }

  .input-row {
    padding: 16px 20px;
    border-top: 1px solid #2a2a2a;
    display: flex;
    gap: 10px;
    background: #161616;
  }

  input[type=text] {
    flex: 1;
    padding: 12px 18px;
    background: #222;
    border: 1px solid #333;
    border-radius: 25px;
    color: #f0e8d8;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
  }

  input[type=text]:focus { border-color: #c9a96e; }
  input[type=text]::placeholder { color: #555; }

  .send-btn {
    padding: 12px 22px;
    background: linear-gradient(135deg, #c9a96e, #b8933a);
    color: #0d0d0d;
    border: none;
    border-radius: 25px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: opacity 0.2s;
  }

  .send-btn:hover { opacity: 0.85; }

  .footer {
    text-align: center;
    margin-top: 20px;
    font-size: 10px;
    color: #444;
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  #chat::-webkit-scrollbar { width: 4px; }
  #chat::-webkit-scrollbar-track { background: #1a1a1a; }
  #chat::-webkit-scrollbar-thumb { background: #c9a96e44; border-radius: 2px; }
</style>
</head>
<body>

  <div class="header">
    <div class="brand">Premium Skincare</div>
    <div class="logo">Contact <span>by Tems</span></div>
    <div class="divider"></div>
    <div class="tagline">Your Skin. Your Ritual. Your Glow.</div>
  </div>

  <div class="quick-btns">
    <form method="post" action="/chat" style="display:contents">
      <button class="qbtn" name="msg" type="submit" value="Tell me about the LED face devices">LED Devices</button>
      <button class="qbtn" name="msg" type="submit" value="What sheet masks do you have?">Sheet Masks</button>
      <button class="qbtn" name="msg" type="submit" value="Tell me about your face brushes">Face Brushes</button>
      <button class="qbtn" name="msg" type="submit" value="What lip care products do you sell?">Lip Care</button>
      <button class="qbtn" name="msg" type="submit" value="Build me a personalised skincare routine">My Routine</button>
    </form>
    <a href="/order" class="qbtn order-btn">Place an Order</a>
  </div>

  <div class="chat-box">
    <div class="chat-top">
      <div class="avatar">&#10022;</div>
      <div class="agent-meta">
        <h2>TEMI</h2>
        <p><span class="dot"></span>Contact by Tems &middot; Skincare AI</p>
      </div>
    </div>

    <div id="chat">
      <div class="msg agent">
        <div class="msg-label">Temi</div>
        <div class="bubble agent">Hi, I'm Temi. What's your main skin concern?</div>
      </div>
      MESSAGES_PLACEHOLDER
    </div>

    <form class="input-row" method="post" action="/chat">
      <input type="text" name="msg" placeholder="Ask about your skin, our products, or get a routine..." autofocus autocomplete="off">
      <button class="send-btn" type="submit">Send</button>
    </form>
  </div>

  <div class="footer">&copy; Contact by Tems &middot; Powered by AI &middot; All Rights Reserved</div>

  <script>
    const chat = document.getElementById('chat');
    chat.scrollTop = chat.scrollHeight;
  </script>

</body>
</html>"""


ORDER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Place an Order — Contact by Tems</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Georgia, sans-serif;
    background: #0d0d0d;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 30px 16px;
    color: #e8e0d0;
  }
  .header { text-align: center; margin-bottom: 32px; }
  .brand { font-size: 11px; letter-spacing: 6px; color: #c9a96e; text-transform: uppercase; margin-bottom: 8px; }
  .logo { font-size: 28px; font-weight: 300; color: #f5f0e8; letter-spacing: 4px; text-transform: uppercase; }
  .logo span { color: #c9a96e; font-weight: 700; }
  .divider { width: 60px; height: 1px; background: linear-gradient(to right, transparent, #c9a96e, transparent); margin: 14px auto; }
  .page-title { font-size: 18px; letter-spacing: 3px; color: #c9a96e; text-transform: uppercase; margin-top: 4px; }

  .order-wrap {
    width: 100%;
    max-width: 760px;
    display: flex;
    flex-direction: column;
    gap: 28px;
  }

  .card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    padding: 28px;
  }

  .card h3 {
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #c9a96e;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid #2a2a2a;
  }

  .category { margin-bottom: 24px; }
  .category:last-child { margin-bottom: 0; }
  .category-name {
    font-size: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 12px;
  }

  .product-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid #222;
    gap: 12px;
  }
  .product-row:last-child { border-bottom: none; }

  .product-info { flex: 1; }
  .product-name { font-size: 14px; color: #f0e8d8; margin-bottom: 2px; }
  .product-price { font-size: 12px; color: #c9a96e; }

  .qty-control {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .qty-control input[type=number] {
    width: 60px;
    padding: 6px 10px;
    background: #222;
    border: 1px solid #333;
    border-radius: 8px;
    color: #f0e8d8;
    font-size: 14px;
    text-align: center;
    outline: none;
  }
  .qty-control input[type=number]:focus { border-color: #c9a96e; }

  .field-group { display: flex; flex-direction: column; gap: 16px; }
  .field label {
    display: block;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 6px;
  }
  .field input, .field textarea {
    width: 100%;
    padding: 12px 16px;
    background: #222;
    border: 1px solid #333;
    border-radius: 10px;
    color: #f0e8d8;
    font-size: 14px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
    resize: vertical;
  }
  .field input:focus, .field textarea:focus { border-color: #c9a96e; }
  .field input::placeholder, .field textarea::placeholder { color: #555; }

  .total-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 0;
    border-top: 1px solid #2a2a2a;
    margin-top: 8px;
  }
  .total-label { font-size: 12px; letter-spacing: 2px; text-transform: uppercase; color: #888; }
  #total-display { font-size: 22px; color: #c9a96e; font-weight: 700; }

  .submit-btn {
    width: 100%;
    padding: 16px;
    background: linear-gradient(135deg, #c9a96e, #b8933a);
    color: #0d0d0d;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    cursor: pointer;
    transition: opacity 0.2s;
    margin-top: 8px;
  }
  .submit-btn:hover { opacity: 0.85; }

  .back-link {
    display: inline-block;
    margin-bottom: 20px;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #c9a96e;
    text-decoration: none;
  }
  .back-link:hover { text-decoration: underline; }

  .footer {
    text-align: center;
    margin-top: 24px;
    font-size: 10px;
    color: #444;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
</style>
</head>
<body>

<div class="header">
  <div class="brand">Premium Skincare</div>
  <div class="logo">Contact <span>by Tems</span></div>
  <div class="divider"></div>
  <div class="page-title">Place an Order</div>
</div>

<div class="order-wrap">
  <a href="/" class="back-link">&larr; Back to Temi</a>

  <form method="post" action="/place_order">

    <div class="card" style="margin-bottom:28px">
      <h3>Select Products &amp; Quantities</h3>
      PRODUCT_ROWS_PLACEHOLDER
      <div class="total-bar">
        <span class="total-label">Order Total</span>
        <span id="total-display">&#8358;0</span>
      </div>
    </div>

    <div class="card" style="margin-bottom:28px">
      <h3>Your Details</h3>
      <div class="field-group">
        <div class="field">
          <label>Full Name</label>
          <input type="text" name="customer_name" placeholder="e.g. Adaeze Okonkwo" required>
        </div>
        <div class="field">
          <label>Phone Number</label>
          <input type="tel" name="phone" placeholder="e.g. 08012345678" required>
        </div>
        <div class="field">
          <label>Delivery Address</label>
          <textarea name="address" rows="3" placeholder="House number, street, area, city, state" required></textarea>
        </div>
      </div>
    </div>

    <button class="submit-btn" type="submit">Confirm Order</button>
  </form>
</div>

<div class="footer">&copy; Contact by Tems &middot; All Rights Reserved</div>

<script>
  const prices = PRICES_JSON_PLACEHOLDER;

  function updateTotal() {
    let total = 0;
    document.querySelectorAll('input[type=number]').forEach(function(input) {
      const qty = parseInt(input.value) || 0;
      const price = prices[input.name] || 0;
      total += qty * price;
    });
    document.getElementById('total-display').textContent =
      '\u20a6' + total.toLocaleString('en-NG');
  }

  document.querySelectorAll('input[type=number]').forEach(function(input) {
    input.addEventListener('input', updateTotal);
  });
</script>
</body>
</html>"""


CONFIRMATION_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Order Confirmed — Contact by Tems</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Georgia, sans-serif;
    background: #0d0d0d;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 16px;
    color: #e8e0d0;
  }
  .header { text-align: center; margin-bottom: 36px; }
  .brand { font-size: 11px; letter-spacing: 6px; color: #c9a96e; text-transform: uppercase; margin-bottom: 8px; }
  .logo { font-size: 28px; font-weight: 300; color: #f5f0e8; letter-spacing: 4px; text-transform: uppercase; }
  .logo span { color: #c9a96e; font-weight: 700; }
  .divider { width: 60px; height: 1px; background: linear-gradient(to right, transparent, #c9a96e, transparent); margin: 14px auto; }

  .confirm-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    padding: 36px 32px;
    width: 100%;
    max-width: 600px;
  }

  .check-icon {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, #c9a96e, #b8933a);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    margin: 0 auto 20px;
    color: #0d0d0d;
  }

  .confirm-title {
    text-align: center;
    font-size: 20px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #c9a96e;
    margin-bottom: 6px;
  }

  .confirm-subtitle {
    text-align: center;
    font-size: 13px;
    color: #888;
    margin-bottom: 28px;
  }

  .order-id {
    text-align: center;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #555;
    margin-bottom: 28px;
  }

  .section { margin-bottom: 24px; }
  .section-label {
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #2a2a2a;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 14px;
  }
  .detail-row .label { color: #888; }
  .detail-row .value { color: #f0e8d8; text-align: right; max-width: 60%; }

  .item-row {
    display: flex;
    justify-content: space-between;
    padding: 7px 0;
    font-size: 13px;
    border-bottom: 1px solid #222;
  }
  .item-row:last-child { border-bottom: none; }
  .item-row .item-name { color: #e8e0d0; }
  .item-row .item-subtotal { color: #c9a96e; }

  .total-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 14px;
    margin-top: 4px;
    border-top: 1px solid #2a2a2a;
  }
  .total-row .label { font-size: 12px; letter-spacing: 2px; text-transform: uppercase; color: #888; }
  .total-row .value { font-size: 22px; color: #c9a96e; font-weight: 700; }

  .btn-group {
    display: flex;
    gap: 12px;
    margin-top: 28px;
  }
  .btn {
    flex: 1;
    padding: 13px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
  }
  .btn-primary {
    background: linear-gradient(135deg, #c9a96e, #b8933a);
    color: #0d0d0d;
    border: none;
  }
  .btn-secondary {
    background: transparent;
    color: #c9a96e;
    border: 1px solid #c9a96e;
  }

  .footer {
    text-align: center;
    margin-top: 24px;
    font-size: 10px;
    color: #444;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
</style>
</head>
<body>

<div class="header">
  <div class="brand">Premium Skincare</div>
  <div class="logo">Contact <span>by Tems</span></div>
  <div class="divider"></div>
</div>

<div class="confirm-card">
  <div class="check-icon">&#10003;</div>
  <div class="confirm-title">Order Confirmed!</div>
  <div class="confirm-subtitle">Thank you for your order. We'll be in touch soon.</div>
  <div class="order-id">Order ID: ORDER_ID_PLACEHOLDER</div>

  <div class="section">
    <div class="section-label">Customer Details</div>
    <div class="detail-row"><span class="label">Name</span><span class="value">CUSTOMER_NAME_PLACEHOLDER</span></div>
    <div class="detail-row"><span class="label">Phone</span><span class="value">PHONE_PLACEHOLDER</span></div>
    <div class="detail-row"><span class="label">Delivery Address</span><span class="value">ADDRESS_PLACEHOLDER</span></div>
    <div class="detail-row"><span class="label">Order Date</span><span class="value">ORDER_DATE_PLACEHOLDER</span></div>
  </div>

  <div class="section">
    <div class="section-label">Order Summary</div>
    ITEM_ROWS_PLACEHOLDER
    <div class="total-row">
      <span class="label">Total</span>
      <span class="value">&#8358;TOTAL_PLACEHOLDER</span>
    </div>
  </div>

  <div class="btn-group">
    <a href="/order" class="btn btn-secondary">Order More</a>
    <a href="/" class="btn btn-primary">Back to Temi</a>
  </div>
</div>

<div class="footer">&copy; Contact by Tems &middot; All Rights Reserved</div>
</body>
</html>"""


def to_field_name(product_name):
    return product_name.replace(" ", "_").replace("(", "").replace(")", "").replace("+", "").replace("/", "_")


def field_name_to_product(field_name):
    for name in ALL_PRODUCTS:
        if to_field_name(name) == field_name:
            return name
    return None


def build_product_rows():
    rows_html = ""
    for category, products in PRODUCT_MENU.items():
        rows_html += f'<div class="category"><div class="category-name">{category}</div>'
        for name, price in products.items():
            field_name = to_field_name(name)
            rows_html += f"""
        <div class="product-row">
          <div class="product-info">
            <div class="product-name">{name}</div>
            <div class="product-price">&#8358;{price:,}</div>
          </div>
          <div class="qty-control">
            <input type="number" name="{field_name}" value="0" min="0" max="99">
          </div>
        </div>"""
        rows_html += "</div>"
    return rows_html


def save_order(order):
    orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r") as f:
                orders = json.load(f)
        except (json.JSONDecodeError, IOError):
            orders = []
    orders.append(order)
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2)


def format_messages(msgs):
    html = ""
    for m in msgs:
        if m["role"] == "user":
            content = m["content"]
            html += f'''      <div class="msg user">
        <div class="msg-label">You</div>
        <div class="bubble user">{content}</div>
      </div>\n'''
        else:
            content = m["content"] if isinstance(m["content"], str) else ""
            html += f'''      <div class="msg agent">
        <div class="msg-label">Temi</div>
        <div class="bubble agent">{content}</div>
      </div>\n'''
    return html


@app.route("/", methods=["GET"])
def index():
    page = HTML.replace("MESSAGES_PLACEHOLDER", format_messages(conversation))
    return make_response(page)


@app.route("/order", methods=["GET"])
def order_page():
    prices_json = json.dumps({to_field_name(name): price for name, price in ALL_PRODUCTS.items()})
    page = ORDER_HTML.replace("PRODUCT_ROWS_PLACEHOLDER", build_product_rows())
    page = page.replace("PRICES_JSON_PLACEHOLDER", prices_json)
    return make_response(page)


@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.form.get("msg", "").strip()

    if user_msg:
        conversation.append({"role": "user", "content": user_msg})

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        print(f"API KEY STATUS: {'FOUND' if api_key else 'NOT FOUND'}")
        if not api_key:
            return jsonify({"error": "API key not configured"}), 500
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=conversation,
        )

        reply = next((b.text for b in response.content if hasattr(b, "text")), "")
        conversation.append({"role": "assistant", "content": reply})

    return redirect("/")


@app.route("/place_order", methods=["POST"])
def place_order():
    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    items = []
    total = 0
    for field_name, value in request.form.items():
        if field_name in ("customer_name", "phone", "address"):
            continue
        qty = int(value) if value.isdigit() else 0
        if qty <= 0:
            continue
        product_name = field_name_to_product(field_name)
        if product_name and product_name in ALL_PRODUCTS:
            price = ALL_PRODUCTS[product_name]
            subtotal = price * qty
            total += subtotal
            items.append({"product": product_name, "qty": qty, "unit_price": price, "subtotal": subtotal})

    if not items or not customer_name or not phone or not address:
        return redirect("/order")

    now = datetime.now()
    order_id = f"CBT-{now.strftime('%Y%m%d%H%M%S')}"
    order_date = now.strftime("%d %B %Y, %I:%M %p")

    order = {
        "order_id": order_id,
        "order_date": now.isoformat(),
        "customer_name": customer_name,
        "phone": phone,
        "address": address,
        "items": items,
        "total": total,
    }
    save_order(order)

    item_rows_html = ""
    for item in items:
        item_rows_html += f"""
        <div class="item-row">
          <span class="item-name">{item['product']} &times; {item['qty']}</span>
          <span class="item-subtotal">&#8358;{item['subtotal']:,}</span>
        </div>"""

    page = CONFIRMATION_HTML
    page = page.replace("ORDER_ID_PLACEHOLDER", order_id)
    page = page.replace("CUSTOMER_NAME_PLACEHOLDER", customer_name)
    page = page.replace("PHONE_PLACEHOLDER", phone)
    page = page.replace("ADDRESS_PLACEHOLDER", address)
    page = page.replace("ORDER_DATE_PLACEHOLDER", order_date)
    page = page.replace("ITEM_ROWS_PLACEHOLDER", item_rows_html)
    page = page.replace("TOTAL_PLACEHOLDER", f"{total:,}")
    return make_response(page)


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8081))
    print("\n  Contact by Tems — Skincare AI Agent")
    print(f"  Open your browser at: http://localhost:{PORT}")
    print(f"  Orders will be saved to: {ORDERS_FILE}")
    print("  Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=PORT)
