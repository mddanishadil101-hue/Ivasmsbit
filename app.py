from flask import Flask, request, jsonify
import os
import requests
import logging
import json
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Telegram Bot Token
BOT_TOKEN = "8483512471:AAHMHkHFpk9vsvRbdkV-WZfiI88p6NBzJTw"

@app.route('/')
def home():
    return "🤖 IVAS SMS Telegram Bot is Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        logging.info(f"Received update: {data}")
        
        if 'message' in data:
            chat_id = data['message']['chat']['id']
            text = data['message'].get('text', '')
            username = data['message']['chat'].get('username', 'Unknown')
            
            logging.info(f"Message from {username}: {text}")
            
            # Command handling
            if text == '/start':
                welcome_msg = f"""👋 Hello {username}!

🤖 <b>Welcome to IVAS SMS Bot</b>

📊 <b>Get your SMS data directly on Telegram!</b>

<b>Available Commands:</b>
/start - Show welcome message
/sms - Get SMS data for today
/help - Show help guide

<b>Example:</b>
<code>/sms 18/01/2025</code>"""
                send_telegram_message(chat_id, welcome_msg)
                
            elif text.startswith('/sms'):
                parts = text.split()
                if len(parts) == 1:
                    # Default to today's date
                    today = datetime.now().strftime('%d/%m/%Y')
                    date_str = today
                elif len(parts) == 2:
                    date_str = parts[1]
                    try:
                        datetime.strptime(date_str, '%d/%m/%Y')
                    except ValueError:
                        send_telegram_message(chat_id, "❌ <b>Invalid date format!</b>\n\nPlease use: <code>DD/MM/YYYY</code>\nExample: <code>/sms 18/01/2025</code>")
                        return jsonify({"status": "success"})
                else:
                    send_telegram_message(chat_id, "❌ <b>Invalid command!</b>\n\nUsage: <code>/sms</code> or <code>/sms DD/MM/YYYY</code>")
                    return jsonify({"status": "success"})
                
                # Send processing message
                processing_msg = f"⏳ <b>Fetching SMS data for</b> <code>{date_str}</code>\n\nPlease wait..."
                send_telegram_message(chat_id, processing_msg)
                
                # Call your IVAS SMS API
                try:
                    vercel_url = os.getenv('VERCEL_URL', 'your-app.vercel.app')
                    sms_api_url = f"https://{vercel_url}/sms?date={date_str}"
                    
                    response = requests.get(sms_api_url, timeout=30)
                    
                    if response.status_code == 200:
                        sms_data = response.json()
                        
                        if 'data' in sms_data:
                            stats = sms_data['data']
                            result_msg = f"""📊 <b>SMS Report - {date_str}</b>

📨 <b>Total SMS:</b> {stats.get('count_sms', '0')}
✅ <b>Paid SMS:</b> {stats.get('paid_sms', '0')}
❌ <b>Unpaid SMS:</b> {stats.get('unpaid_sms', '0')}
💰 <b>Revenue:</b> ${stats.get('revenue', '0')}

📈 <b>Country Stats:</b>"""
                            
                            # Add country details
                            for detail in stats.get('sms_details', [])[:5]:  # First 5 countries
                                result_msg += f"\n🌍 {detail['country_number']}: {detail['count']} SMS"
                            
                            if len(stats.get('sms_details', [])) > 5:
                                result_msg += f"\n... and {len(stats.get('sms_details', [])) - 5} more countries"
                                
                        else:
                            result_msg = f"✅ <b>SMS data for {date_str}</b>\n\n{sms_data.get('message', 'Data retrieved successfully!')}"
                        
                    else:
                        result_msg = "❌ <b>Failed to fetch SMS data</b>\n\nPlease try again later or check your IVAS SMS login."
                    
                except Exception as e:
                    logging.error(f"SMS API error: {e}")
                    result_msg = "❌ <b>Error fetching data</b>\n\nPlease check if your IVAS SMS API is working."
                
                send_telegram_message(chat_id, result_msg)
                
            elif text == '/help':
                help_msg = """🆘 <b>IVAS SMS Bot Help</b>

<b>Commands:</b>
• /start - Start the bot
• /sms - Get today's SMS data
• /sms DD/MM/YYYY - Get SMS data for specific date
• /help - Show this help

<b>Date Format:</b>
<code>DD/MM/YYYY</code>

<b>Examples:</b>
<code>/sms</code> - Today's data
<code>/sms 18/01/2025</code>
<code>/sms 20/01/2025</code>

<b>Note:</b>
Make sure your IVAS SMS API is properly configured with valid cookies."""
                send_telegram_message(chat_id, help_msg)
            
            else:
                send_telegram_message(chat_id, "🤖 <b>I didn't understand that!</b>\n\nUse /help to see available commands.")
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return jsonify({"status": "error"})

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logging.error(f"Telegram send message error: {e}")

# Webhook setup endpoint
@app.route('/set_webhook')
def set_webhook():
    vercel_url = os.getenv('VERCEL_URL')
    if not vercel_url:
        return "❌ VERCEL_URL environment variable not set"
    
    webhook_url = f"https://{vercel_url}/webhook"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(url)
        result = response.json()
        return jsonify({
            "status": "success" if result.get('ok') else "error",
            "message": result.get('description', 'Unknown error')
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Remove webhook
@app.route('/remove_webhook')
def remove_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url="
    try:
        response = requests.get(url)
        return response.json()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=False)
