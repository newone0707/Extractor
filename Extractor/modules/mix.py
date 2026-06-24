import asyncio
import aiohttp
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from pyrogram import filters
import cloudscraper
from Extractor import app
from config import PREMIUM_LOGS, join,BOT_TEXT
import os
import base64
import time
import requests
from datetime import datetime
from Extractor.core.utils import forward_to_log
import pytz
import config 
import logging
from bs4 import BeautifulSoup

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

join = config.join
india_timezone = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(india_timezone)
time_new = current_time.strftime("%d-%m-%Y %I:%M %p")


PREMIUM_LOGS = PREMIUM_LOGS
def decrypt(enc):
    try:
        if not enc:
            return ""
        enc = b64decode(enc.split(':')[0])
        key = '638udh3829162018'.encode('utf-8')
        iv = 'fedcba9876543210'.encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return ""

def decode_base64(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Base64 decoding error: {e}")
        return ""

semaphore = asyncio.Semaphore(5)

# Thread-safe global scraper
scraper = cloudscraper.create_scraper()

def sync_safe_fetch(url, headers):
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            js = r.json()
            if str(js.get("status")) in ["200", "1"] or js.get("success"):
                return js
            elif "data" in js:
                return js
    except Exception as e:
        pass
    return None

async def safe_fetch_json(url, headers, max_retries=10):
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    headers["Accept"] = "application/json, text/plain, */*"
    
    for attempt in range(max_retries):
        try:
            async with semaphore:
                # Run the blocking cloudscraper call in a separate thread so we don't freeze the bot
                result = await asyncio.to_thread(sync_safe_fetch, url, headers)
                if result is not None:
                    return result
        except Exception as e:
            pass
        await asyncio.sleep(2 * (attempt + 1))
    return None

async def fetch_item_details(api_base, course_id, item, headers, current_path="", userid=""):
    try:
        fi = item.get("id")
        vt = item.get("name") or item.get("Title", "") or item.get("title", "")
        prefix = f"[{current_path}] " if current_path else ""
        
        from Extractor.modules.custom_crypto import encrypt_appx_params
        token = headers.get("Authorization", "")
        
        if fi:
            enc = encrypt_appx_params(api_base, course_id, fi, token, userid)
            return [f"{prefix}{vt} : {enc}"]
            
        return []
    except Exception as e:
        logger.error(f"Error fetching item details: {e}")
        return []

async def fetch_folder_contents(api_base, course_id, folder_id, headers, current_path="", userid=""):
    try:
        outputs = []
        url = f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id={folder_id}&folder_wise_course=1"
        if userid:
            url += f"&userid={userid}"
            
        j = await safe_fetch_json(url, headers)
        if not j:
            return []

        tasks = []
        if "data" in j:
            for item in j["data"]:
                item_name = item.get("name") or item.get("Title", "") or item.get("title", "")
                item_type = item.get('resource_type', item.get('type'))
                is_folder = str(item.get('is_folder')) == "1" or str(item_type) in ["2", "0"] or str(item.get('material_type')).upper() == "FOLDER"
                
                new_path = f"{current_path} -> {item_name}" if current_path else item_name
                
                await asyncio.sleep(0.5)
                
                if is_folder:
                    res = await fetch_folder_contents(api_base, course_id, item.get("id"), headers, new_path, userid)
                else:
                    res = await fetch_item_details(api_base, course_id, item, headers, new_path, userid)
                
                if res:
                    outputs.extend(res)

        return outputs

    except Exception as e:
        logger.error(f"Error fetching folder contents: {e}")
        return []

async def v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start, end, pricing, input2, m1, m2):
    try:
        progress_msg = await message.reply_text(
            "🔄 <b>Processing Large Batch</b>\n"
            f"└─ Initializing batch: <code>{sanitized_course_name}</code>"
        )
        
        url = f"{api_base}/get/folder_contentsv2?course_id={raw_text2}&parent_id=-1&folder_wise_course=1"
        if userid:
            hdr1["User-ID"] = str(userid)
            hdr1["Authorization"] = str(token)
            hdr1["token"] = str(token)
            hdr1["appx-version"] = "2"
            hdr1["device_type"] = "WEB"
            url += f"&userid={userid}"
            
        j2 = await safe_fetch_json(url, hdr1)
        logger.info(f"ROOT FOLDER JSON: {json.dumps(j2)}")
        
        if not j2 or not j2.get("data"):
            await progress_msg.edit_text(
                "❌ <b>No Content Found</b>\n\n"
                "Try switching to v3 and retry."
            )
            return

        all_outputs = []
        tasks = []
        
        if "data" in j2:
            total_items = len(j2["data"])
            processed = 0
            
            for item in j2["data"]:
                item_type = item.get('resource_type', item.get('type'))
                is_folder = str(item.get('is_folder')) == "1" or str(item_type) in ["2", "0"] or str(item.get('material_type')).upper() == "FOLDER"
                
                await asyncio.sleep(0.5)
                
                if is_folder:
                    res = await fetch_folder_contents(api_base, raw_text2, item.get("id"), hdr1, item.get("Title", ""), userid)
                else:
                    res = await fetch_item_details(api_base, raw_text2, item, hdr1, "", userid)
                
                if res:
                    all_outputs.extend(res)
                
                processed += 1
                if processed % 5 == 0:
                    await progress_msg.edit_text(
                        "🔄 <b>Processing Large Batch</b>\n"
                        f"├─ Progress: {processed}/{total_items}\n"
                        f"└─ Current: <code>{item.get('Title', 'Unknown')}</code>"
                    )

        if not all_outputs:
            await progress_msg.edit_text("❌ <b>No content found in this batch</b>")
            return

        video_count = sum(1 for url in all_outputs if any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.mpd', '.mkv', '.zip', '/videos/']))
        pdf_count = sum(1 for url in all_outputs if any(ext in url.lower() for ext in ['.pdf', 'paid_course']))
        encrypted_count = sum(1 for url in all_outputs if 'encrypted' in url.lower() or '*' in url)

        if all_outputs:
            all_outputs.insert(0, f"BaseURL: {api_base}")

        file_name = f"{app_name}_{sanitized_course_name}_{int(datetime.now().timestamp())}.txt"
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_outputs))

        end_time = datetime.now()
        duration = end_time - datetime.fromtimestamp(start_time)
        minutes, seconds = divmod(duration.total_seconds(), 60)

        caption = (
            f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
            f"📱 <b>APP:</b> {app_name}\n"
            f"📚 <b>BATCH:</b> {sanitized_course_name}\n"
            f"⏱ <b>EXTRACTION TIME:</b> {int(minutes):02d}:{int(seconds):02d}\n"
            f"📅 <b>DATE:</b> {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y %H:%M:%S')} IST\n\n"
            f"📊 <b>CONTENT STATS</b>\n"
            f"├─ 📁 Total Links: {len(all_outputs)}\n"
            f"├─ 🎬 Videos: {video_count}\n"
            f"├─ 📄 PDFs: {pdf_count}\n"
            f"└─ 🔐 Encrypted: {encrypted_count}\n\n"
            f"🚀 <b>Extracted by:</b> @{(await app.get_me()).username}\n\n"
            f"<code>╾───• {BOT_TEXT} •───╼</code>"
        )

        await message.reply_document(document=file_name, caption=caption)
        await app.send_document(PREMIUM_LOGS, file_name, caption=caption)

        try:
            os.remove(file_name)
        except:
            pass

        for msg in [input2, m1, m2]:
            try:
                await msg.delete()
            except:
                pass

        await progress_msg.edit_text(
            "✅ <b>Extraction completed successfully!</b>\n\n"
            f"📊 𝗙𝗶𝗻𝗮𝗹 𝗦𝘁𝗮𝘁𝘂𝘀:\n"
            f"📚 Processed: {total_items} items\n"
            f"📤 File has been uploaded\n\n"
            f"Thank you for using @adxcontactbot Extractor Pro! 🌟"
        )

    except Exception as e:
        logger.error(f"Error in v2_new: {e}")
        await message.reply_text(
            "❌ <b>An error occurred</b>\n\n"
            f"Error: <code>{str(e)}</code>\n\n"
            "Please try again or contact support."
        )
