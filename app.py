from flask import Flask, request, jsonify
from datetime import datetime
import cloudscraper
import json
from bs4 import BeautifulSoup
import logging
import os
import gzip
import brotli

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IVASSMSClient:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.base_url = "https://www.ivasms.com"
        self.logged_in = False
        self.csrf_token = None
        
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def decompress_response(self, response):
        encoding = response.headers.get('Content-Encoding', '').lower()
        content = response.content
        try:
            if encoding == 'gzip':
                content = gzip.decompress(content)
            elif encoding == 'br':
                content = brotli.decompress(content)
            return content.decode('utf-8', errors='replace')
        except Exception as e:
            return response.text

    def load_cookies(self):
        try:
            cookies_env = os.getenv("COOKIES_JSON")
            if not cookies_env:
                logger.error("COOKIES_JSON environment variable not set")
                return None
            
            cookies_raw = json.loads(cookies_env)
            logger.info("Cookies loaded from environment")
            
            if isinstance(cookies_raw, list):
                cookies_dict = {}
                for cookie in cookies_raw:
                    if 'name' in cookie and 'value' in cookie:
                        cookies_dict[cookie['name']] = cookie['value']
                return cookies_dict
            else:
                logger.error("Invalid cookies format")
                return None
                
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return None

    def login_with_cookies(self):
        cookies = self.load_cookies()
        if not cookies:
            return False
        
        # Clear existing cookies and set new ones
        self.scraper.cookies.clear()
        for name, value in cookies.items():
            self.scraper.cookies.set(name, value, domain="www.ivasms.com")
        
        try:
            response = self.scraper.get(f"{self.base_url}/portal/sms/received", timeout=15)
            if response.status_code == 200:
                html_content = self.decompress_response(response)
                soup = BeautifulSoup(html_content, 'html.parser')
                csrf_input = soup.find('input', {'name': '_token'})
                if csrf_input:
                    self.csrf_token = csrf_input.get('value')
                    self.logged_in = True
                    logger.info("✅ Successfully logged in to IVAS SMS")
                    return True
                else:
                    logger.error("❌ CSRF token not found")
                    return False
            else:
                logger.error(f"❌ Login failed with status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False

    def get_sms_data(self, from_date="", to_date=""):
        if not self.logged_in:
            return None
        
        try:
            payload = {
                'from': from_date,
                'to': to_date,
                '_token': self.csrf_token
            }
            
            headers = {
                'Accept': 'text/html, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/portal/sms/received"
            }
            
            response = self.scraper.post(
                f"{self.base_url}/portal/sms/received/getsms",
                data=payload,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                html_content = self.decompress_response(response)
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract statistics
                count_sms = soup.select_one("#CountSMS").text if soup.select_one("#CountSMS") else '0'
                paid_sms = soup.select_one("#PaidSMS").text if soup.select_one("#PaidSMS") else '0'
                unpaid_sms = soup.select_one("#UnpaidSMS").text if soup.select_one("#UnpaidSMS") else '0'
                revenue_sms = soup.select_one("#RevenueSMS").text.replace(' USD', '') if soup.select_one("#RevenueSMS") else '0'
                
                # Extract country/number details
                sms_details = []
                items = soup.select("div.item")
                for item in items:
                    try:
                        country_number = item.select_one(".col-sm-4").text.strip()
                        count = item.select_one(".col-3:nth-child(2) p").text.strip()
                        paid = item.select_one(".col-3:nth-child(3) p").text.strip()
                        unpaid = item.select_one(".col-3:nth-child(4) p").text.strip()
                        revenue = item.select_one(".col-3:nth-child(5) p span.currency_cdr").text.strip()
                        
                        sms_details.append({
                            'country_number': country_number,
                            'count': count,
                            'paid': paid,
                            'unpaid': unpaid,
                            'revenue': revenue
                        })
                    except Exception as e:
                        continue
                
                return {
                    'count_sms': count_sms,
                    'paid_sms': paid_sms,
                    'unpaid_sms': unpaid_sms,
                    'revenue': revenue_sms,
                    'sms_details': sms_details
                }
            else:
                logger.error(f"Failed to get SMS data: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting SMS data: {e}")
            return None

# Initialize client
client = IVASSMSClient()

@app.route('/')
def home():
    return jsonify({
        'message': '🚀 IVAS SMS API - Vercel Deployment',
        'status': 'Ready',
        'endpoints': {
            '/health': 'Check API health',
            '/login': 'Manual login',
            '/sms': 'Get SMS data (add ?date=DD/MM/YYYY)'
        },
        'example': 'https://your-app.vercel.app/sms?date=18/01/2025'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'logged_in': client.logged_in,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/login')
def login():
    if client.login_with_cookies():
        return jsonify({
            'status': 'success',
            'message': 'Logged in successfully',
            'logged_in': True
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Login failed - check COOKIES_JSON',
            'logged_in': False
        }), 401

@app.route('/sms')
def get_sms():
    # Auto-login if not logged in
    if not client.logged_in:
        if not client.login_with_cookies():
            return jsonify({
                'error': 'Authentication failed'
            }), 401
    
    date_str = request.args.get('date', '')
    to_date_str = request.args.get('to_date', '')
    
    # Validate date format
    if date_str:
        try:
            datetime.strptime(date_str, '%d/%m/%Y')
        except ValueError:
            return jsonify({
                'error': 'Invalid date format. Use DD/MM/YYYY'
            }), 400
    
    if to_date_str:
        try:
            datetime.strptime(to_date_str, '%d/%m/%Y')
        except ValueError:
            return jsonify({
                'error': 'Invalid to_date format. Use DD/MM/YYYY'
            }), 400
    
    logger.info(f"Fetching SMS data for: {date_str} to {to_date_str}")
    
    result = client.get_sms_data(from_date=date_str, to_date=to_date_str)
    
    if result:
        return jsonify({
            'status': 'success',
            'from_date': date_str,
            'to_date': to_date_str,
            'data': result
        })
    else:
        return jsonify({
            'error': 'Failed to fetch SMS data'
        }), 500

# Vercel handler
if __name__ == '__main__':
    app.run(debug=False)
