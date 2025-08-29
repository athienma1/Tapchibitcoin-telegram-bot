import requests
import xml.etree.ElementTree as ET
import re
import json
import os
import sys
from datetime import datetime

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GIST_TOKEN = os.getenv('GIST_TOKEN')
GIST_ID = os.getenv('GIST_ID')

# Config
MAX_NEWS_PER_RUN = 10
DELAY_BETWEEN_MESSAGES = 2

def debug_env():
    """Debug environment variables"""
    print("DEBUG ENVIRONMENT VARIABLES:")
    print(f"BOT_TOKEN: {'SET' if BOT_TOKEN else 'MISSING'}")
    print(f"CHAT_ID: {'SET' if CHAT_ID else 'MISSING'}")
    print(f"GIST_TOKEN: {'SET' if GIST_TOKEN else 'MISSING'}")
    print(f"GIST_ID: {'SET' if GIST_ID else 'MISSING'}")
    print("-" * 50)

def get_rss_data():
    try:
        print("Connecting to TapchiBitcoin RSS...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/xml, text/xml, */*'
        }
        
        response = requests.get(
            'https://tapchibitcoin.io/feed', 
            headers=headers, 
            timeout=15
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"HTTP Error: {response.status_code}")
            return None
            
        # Parse XML
        try:
            root = ET.fromstring(response.content)
            print("XML parse successful")
        except ET.ParseError as e:
            print(f"XML parse error: {e}")
            return None
            
        namespaces = {
            'media': 'http://search.yahoo.com/mrss/',
            'content': 'http://purl.org/rss/1.0/modules/content/'
        }
        
        news_items = []
        for item in root.findall('.//item'):
            try:
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else "No title"
                link = link_elem.text if link_elem is not None else "#"
                pub_date = pub_date_elem.text if pub_date_elem is not None else ""

                # Convert pub_date to datetime object for sorting
                try:
                    pub_date_obj = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
                except:
                    try:
                        pub_date_obj = datetime.strptime(pub_date, '%Y-%m-%dT%H:%M:%S%z')
                    except:
                        pub_date_obj = datetime.now()
                
                news_items.append({
                    'title': title,
                    'link': link, 
                    'pub_date_obj': pub_date_obj
                })
                
            except Exception as e:
                print(f"Item processing error: {e}")
                continue
        
        print(f"Got {len(news_items)} news items from TapchiBitcoin")
        return news_items
        
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return None
    except Exception as e:
        print(f"Unknown error: {e}")
        import traceback
        traceback.print_exc()
        return None

def send_telegram_message(message):
    try:
        if not BOT_TOKEN or not CHAT_ID:
            return False
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False  # QUAN TRỌNG: để Telegram tự tạo preview
        }
        
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        
        return result.get('ok', False)
            
    except Exception as e:
        print(f"Message send error: {e}")
        return False

def load_sent_links():
    """Load sent links from GitHub Gist"""
    if not GIST_TOKEN or not GIST_ID:
        print("GIST_TOKEN or GIST_ID not configured")
        return []
    
    try:
        print(f"Connecting to Gist: {GIST_ID}")
        headers = {
            'Authorization': f'token {GIST_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(
            f'https://api.github.com/gists/{GIST_ID}',
            headers=headers,
            timeout=10
        )
        
        print(f"Gist response status: {response.status_code}")
        
        if response.status_code == 200:
            gist_data = response.json()
            content = gist_data['files']['sent_links.json']['content']
            sent_links = json.loads(content)
            print(f"Loaded {len(sent_links)} links from Gist")
            return sent_links
        else:
            print(f"Error loading Gist: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Gist connection error: {e}")
        return []

def save_sent_links(links):
    """Save sent links to GitHub Gist"""
    if not GIST_TOKEN or not GIST_ID:
        print("GIST_TOKEN or GIST_ID not configured")
        return False
    
    try:
        # Keep only latest 200 links
        if len(links) > 200:
            links = links[-200:]
        
        print(f"Saving {len(links)} links to Gist...")
        
        # Prepare data for Gist update
        data = {
            "files": {
                "sent_links.json": {
                    "content": json.dumps(links, ensure_ascii=False, indent=2)
                }
            }
        }
        
        headers = {
            'Authorization': f'token {GIST_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.patch(
            f'https://api.github.com/gists/{GIST_ID}',
            headers=headers,
            json=data,
            timeout=10
        )
        
        print(f"Gist save response: {response.status_code}")
        
        if response.status_code == 200:
            print(f"Saved {len(links)} links to Gist")
            return True
        else:
            print(f"Error saving Gist: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Gist save error: {e}")
        return False

def main():
    print("=" * 60)
    print("🤖 Starting TapchiBitcoin Telegram Bot")
    print("=" * 60)
    
    debug_env()
    
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: Missing BOT_TOKEN or CHAT_ID")
        sys.exit(1)
    
    # Load sent links
    sent_links = load_sent_links()
    print(f"Previously sent links: {len(sent_links)}")
    
    # Get RSS data
    news_items = get_rss_data()
    if not news_items:
        print("No RSS data")
        sys.exit(1)
    
    # Filter unsent news
    new_items = [item for item in news_items if item['link'] not in sent_links]
    print(f"New items: {len(new_items)}")
    
    if not new_items:
        print("No new news")
        sys.exit(0)
    
    # Sort by time: oldest first, newest last
    new_items.sort(key=lambda x: x['pub_date_obj'])
    
    # Limit number of items to send
    items_to_send = new_items[:MAX_NEWS_PER_RUN]
    print(f"Will send {len(items_to_send)} items")
    print("Sending order: Old → New (newest will be at bottom)")
    
    # Send news - CHỈ GỬI LINK
    success_count = 0
    for i, item in enumerate(items_to_send):
        try:
            print(f"\nSending item {i+1}/{len(items_to_send)}...")
            print(f"Time: {item['pub_date_obj']}")
            
            # CHỈ GỬI LINK - Telegram tự tạo preview
            message = item['link']
            
            # Gửi tin nhắn
            if send_telegram_message(message):
                sent_links.append(item['link'])
                success_count += 1
                print(f"✅ Item {i+1} sent successfully")
            else:
                print(f"❌ Item {i+1} failed")
            
            # Wait between messages
            if i < len(items_to_send) - 1:
                import time
                time.sleep(DELAY_BETWEEN_MESSAGES)
                
        except Exception as e:
            print(f"❌ Error sending item {i+1}: {e}")
    
    # Save sent links
    save_sent_links(sent_links)
    
    print("\n" + "=" * 60)
    print(f"🎉 COMPLETED! Sent {success_count}/{len(items_to_send)} new items")
    print(f"💾 Total sent links: {len(sent_links)}")
    print("=" * 60)
    
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
