import requests
import xml.etree.ElementTree as ET
import re
import json
import os
import sys
import time
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
            
        news_items = []
        for item in root.findall('.//item'):
            try:
                link_elem = item.find('link')
                title_elem = item.find('title')
                description_elem = item.find('description')
                
                link = link_elem.text if link_elem is not None else "#"
                title = title_elem.text if title_elem is not None else "No Title"
                
                # Lấy mô tả và làm sạch HTML tags
                description = description_elem.text if description_elem is not None else ""
                description = re.sub('<[^<]+?>', '', description)  # Remove HTML tags
                description = description.strip()
                
                # Giới hạn độ dài mô tả
                if len(description) > 200:
                    description = description[:197] + "..."
                
                # Lấy pubDate và xử lý lỗi định dạng
                pub_date_elem = item.find('pubDate')
                pub_date = pub_date_elem.text if pub_date_elem is not None else ""
                
                # Chuyển đổi pub_date thành timestamp để so sánh
                try:
                    pub_date_obj = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
                except ValueError:
                    try:
                        pub_date_obj = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %z')
                    except ValueError:
                        pub_date_obj = datetime.now()
                
                news_items.append({
                    'link': link.strip(),
                    'title': title,
                    'description': description,
                    'pub_date': pub_date_obj.timestamp()
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

def send_telegram_photo(photo_url, caption):
    try:
        if not BOT_TOKEN or not CHAT_ID:
            return False
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        data = {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, data=data, timeout=15)
        result = response.json()
        
        return result.get('ok', False)
            
    except Exception as e:
        print(f"Photo send error: {e}")
        return False

def send_telegram_message(message):
    try:
        if not BOT_TOKEN or not CHAT_ID:
            return False
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
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

def format_caption(item):
    """Format caption with link at bottom"""
    title = item['title']
    description = item['description']
    
    # Remove duplication: if description starts with title, remove title from description
    if description.startswith(title):
        description = description[len(title):].strip()
    
    # Limit description length (caption has 1024 char limit)
    if len(description) > 800:
        description = description[:800] + "..."
    
    # Format caption: title + description + link at bottom
    caption = f"{title}\n\n{description}\n\n➡️ Read more: {item['link']}"
    
    return caption

def main():
    print("=" * 60)
    print("🤖 Starting Coin68 Telegram Bot")
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
    
    # Send news
    success_count = 0
    for i, item in enumerate(items_to_send):
        try:
            print(f"\nSending item {i+1}/{len(items_to_send)}...")
            print(f"Time: {item['pub_date_obj']}")
            
            # Format caption with link at bottom
            caption = format_caption(item)
            
            # Send photo with caption if image available
            if item['image_url']:
                if send_telegram_photo(item['image_url'], caption):
                    sent_links.append(item['link'])
                    success_count += 1
                    print(f"✅ Item {i+1} sent successfully with photo")
                else:
                    # Fallback: send as text if photo fails
                    print("🔄 Photo send failed, trying text...")
                    if send_telegram_message(caption):
                        sent_links.append(item['link'])
                        success_count += 1
                        print(f"✅ Item {i+1} sent successfully as text")
                    else:
                        print(f"❌ Item {i+1} failed")
            else:
                # Send as text if no image
                if send_telegram_message(caption):
                    sent_links.append(item['link'])
                    success_count += 1
                    print(f"✅ Item {i+1} sent successfully as text")
                else:
                    print(f"❌ Item {i+1} failed")
            
            # Wait between messages
            if i < len(items_to_send) - 1:
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
