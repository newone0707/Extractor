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

async def fetch_item_details(api_base, course_id, item, headers, current_path="", userid="", progress_callback=None):
    try:
        fi = item.get("id")
        vt = item.get("name") or item.get("Title", "") or item.get("title", "")
        if progress_callback:
            await progress_callback(vt)
        outputs = []
        prefix = f"[{current_path}] " if current_path else ""
        from Extractor.modules.custom_crypto import encrypt_direct_url
        
        url = f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&folder_wise_course=1&ytflag=1&video_id={fi}"
        if userid:
            url += f"&userid={userid}"

        r4 = await safe_fetch_json(url, headers)
        
        fallback_outputs = []
        item_link = item.get('file_link') or item.get('pdf_link')
        if item_link:
            if not item_link.startswith('http') and ':' in item_link:
                dec = decrypt(item_link)
                if dec: item_link = dec
            fallback_outputs.append(f"{prefix}{vt} : {encrypt_direct_url(item_link)}")

        if not r4 or not r4.get("data"):
            return fallback_outputs

        data = r4.get("data")
        vt_api = data.get("Title", "")
        vl = data.get("download_link", "")
        fl = data.get("video_id", "")
        
        if not vt: vt = vt_api
        
        if fl:
            dfl = decrypt(fl)
            if dfl:
                if '.m3u8' in dfl or '.mp4' in dfl or 'genomic' in dfl or '/' in dfl:
                    final_link = f"https://appxsignurl.vercel.app/appx/{dfl}?appxv=3"
                else:
                    final_link = f"https://youtu.be/{dfl}"
                outputs.append(f"{prefix}{vt} : {encrypt_direct_url(final_link)}")

        if vl:
            dvl = decrypt(vl)
            
            # Extract key from encrypted_links if available
            key_val = None
            encrypted_links = data.get("encrypted_links", [])
            if encrypted_links:
                k = encrypted_links[0].get("key")
                if k:
                    k1 = decrypt(k)
                    key_val = decode_base64(k1)
                    
            if dvl:
                if key_val:
                    outputs.append(f"{prefix}{vt} : {encrypt_direct_url(dvl, key_val)}")
                else:
                    outputs.append(f"{prefix}{vt} : {encrypt_direct_url(dvl)}")
        elif not fl:
            for link in data.get("encrypted_links", []):
                a = link.get("path")
                k = link.get("key")
                if a and k:
                    k1 = decrypt(k)
                    k2 = decode_base64(k1)
                    da = decrypt(a)
                    if da:
                        outputs.append(f"{prefix}{vt} : {encrypt_direct_url(da, k2)}")
                        break
                elif a:
                    if not a.startswith('http') and ':' in a:
                        da = decrypt(a)
                    else:
                        da = a
                    if da:
                        outputs.append(f"{prefix}{vt} : {encrypt_direct_url(da)}")
                        break

        for pdf_num in range(1, 3):
            pdf_link = data.get(f"pdf_link{'' if pdf_num == 1 else str(pdf_num)}", "")
            pdf_key = data.get(f"pdf{'_' if pdf_num == 1 else str(pdf_num)}_encryption_key", "")
            
            if pdf_link:
                dp = ""
                if not pdf_link.startswith('http') and ':' in pdf_link:
                    dp = decrypt(pdf_link)
                else:
                    dp = pdf_link
                
                if dp:
                    if pdf_key:
                        dpk = decrypt(pdf_key)
                        if dpk and dpk != "abcdefg":
                            outputs.append(f"{prefix}{vt} PDF{pdf_num if pdf_num > 1 else ''} : {encrypt_direct_url(dp, dpk)}")
                        else:
                            outputs.append(f"{prefix}{vt} PDF{pdf_num if pdf_num > 1 else ''} : {encrypt_direct_url(dp)}")
                    else:
                        outputs.append(f"{prefix}{vt} PDF{pdf_num if pdf_num > 1 else ''} : {encrypt_direct_url(dp)}")

        # Remove duplicates while preserving order
        seen = set()
        unique_outputs = []
        for x in outputs:
            if x not in seen:
                unique_outputs.append(x)
                seen.add(x)
        return unique_outputs if unique_outputs else fallback_outputs
        
    except Exception as e:
        logger.error(f"Error in fetch_item_details: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching item details: {e}")
        return []

async def fetch_folder_contents(api_base, course_id, folder_id, headers, current_path="", userid="", progress_callback=None):
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
                    res = await fetch_folder_contents(api_base, course_id, item.get("id"), headers, new_path, userid, progress_callback)
                else:
                    res = await fetch_item_details(api_base, course_id, item, headers, new_path, userid, progress_callback)
                
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
            
            state = {"processed": 0, "last_edit": time.time()}
            
            async def my_callback(item_name):
                state["processed"] += 1
                if state["processed"] % 5 == 0 and (time.time() - state["last_edit"] > 2):
                    state["last_edit"] = time.time()
                    try:
                        await progress_msg.edit_text(
                            "⚡ <b>𝐄𝐱𝐭𝐫𝐚𝐜𝐭𝐢𝐨𝐧 𝐈𝐧 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬...</b> ⚡\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📦 <b>Iᴛᴇᴍs Pʀᴏᴄᴇssᴇᴅ:</b> {state['processed']}\n"
                            f"🔍 <b>Cᴜʀʀᴇɴᴛ Iᴛᴇᴍ:</b>\n"
                            f"└─ <code>{item_name}</code>\n"
                            "━━━━━━━━━━━━━━━━━━━━━"
                        )
                    except Exception:
                        pass

            for item in j2["data"]:
                item_type = item.get('resource_type', item.get('type'))
                is_folder = str(item.get('is_folder')) == "1" or str(item_type) in ["2", "0"] or str(item.get('material_type')).upper() == "FOLDER"
                
                await asyncio.sleep(0.5)
                
                if is_folder:
                    res = await fetch_folder_contents(api_base, raw_text2, item.get("id"), hdr1, item.get("Title", ""), userid, my_callback)
                else:
                    res = await fetch_item_details(api_base, raw_text2, item, hdr1, "", userid, my_callback)
                
                if res:
                    all_outputs.extend(res)
                
                processed += 1

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
