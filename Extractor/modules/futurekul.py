import os
import re
import json
import logging
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from Extractor import app
from config import BOT_TEXT

EMAIL = "yolesa9970@5nek.com"
PASSWORD = "123123123"
CUSTOMER_ID = 135

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_. ')
    return name if name else "Unknown_Course"

async def get_futurekul_session_and_build(session):
    # 1. Get Next.js Build ID
    build_id = None
    try:
        async with session.get("https://www.futurekul.com/", timeout=15) as resp:
            text = await resp.text()
            match = re.search(r'"buildId"\:"(.*?)"', text)
            if match:
                build_id = match.group(1)
    except Exception as e:
        logging.error(f"Error fetching Futurekul build ID: {e}")
        
    # 2. Login to get ci_session cookie
    login_url = "https://www.futurekul.com/admin/api/user-login"
    login_data = {
        "email": EMAIL,
        "password": PASSWORD,
        "logged_in_via": "web",
        "customer_id": CUSTOMER_ID
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with session.post(login_url, json=login_data, headers=headers, timeout=15) as resp:
            data = await resp.json()
            user_id = data.get("data", {}).get("user_id")
            return build_id, user_id
    except Exception as e:
        logging.error(f"Error logging into Futurekul: {e}")
        return build_id, None

async def fetch_json(session, url):
    try:
        async with session.get(url, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        pass
    return None

async def process_futurekul(bot: Client, m: Message, user_id: int):
    loop = asyncio.get_event_loop()
    CONNECTOR = aiohttp.TCPConnector(limit=100, loop=loop)

    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        editable = await m.reply_text("Fetching Futurekul courses... Please wait.")
        
        try:
            build_id, backend_user_id = await get_futurekul_session_and_build(session)
            if not build_id:
                await editable.edit("Failed to connect to Futurekul frontend.")
                return
                
            # Fetch ALL active courses from Next.js
            courses_url = f"https://www.futurekul.com/_next/data/{build_id}/en-US/courses.json"
            courses_data = await fetch_json(session, courses_url)
            
            if not courses_data or 'pageProps' not in courses_data:
                await editable.edit("Failed to fetch course list.")
                return
                
            batches = courses_data['pageProps'].get('onlineCoursesList', [])
            if not batches:
                await editable.edit("No active courses found on Futurekul.")
                return
                
            text = ''
            for cnt, batch in enumerate(batches):
                name = batch.get("title", "Unknown")
                price = batch.get("price", "Free")
                text += f"{cnt + 1}. {name} - Rs.{price}\n"
                
            course_details_file = f"{user_id}_futurekul_courses.txt"
            with open(course_details_file, 'w', encoding='utf-8') as f:
                f.write(text)
                
            caption = (
                f"🎓 <b>FUTUREKUL COURSES</b> 🎓\n\n"
                f"📚 <b>TOTAL COURSES:</b> {len(batches)}\n\n"
                f"<code>╾───• @PRO_TXT_EXTRATOR_BOT •───╼</code>\n\n"
                "Send the index number to download course"
            )
            
            await editable.delete()
            msg = await m.reply_document(
                document=course_details_file,
                caption=caption,
                file_name="futurekul_courses.txt"
            )
            
            try:
                os.remove(course_details_file)
            except:
                pass
                
            try:
                input_msg = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                user_choice = input_msg.text.strip()
                await input_msg.delete(True)
            except:
                await msg.edit("❌ <b>Timeout!</b>\n\nYou took too long to respond.")
                return
                
            if not user_choice.isdigit() or not (1 <= int(user_choice) <= len(batches)):
                await msg.edit("❌ <b>Invalid Input!</b>\n\nPlease send a valid index number.")
                return
                
            selected_idx = int(user_choice) - 1
            selected_batch = batches[selected_idx]
            course_id = selected_batch.get("id")
            batch_title = selected_batch.get("title", "Unknown Batch")
            clean_batch_name = sanitize_filename(batch_title)
            
            status_msg = await m.reply_text(
                "🔄 <b>Processing Course</b>\n"
                f"└─ Current: <code>{batch_title}</code>\n"
                f"(Futurekul API may return 'No Data Found' if course is not purchased by the dummy account.)"
            )
            
            # Fetch topics via Admin API
            # Futurekul requires the user to own the course to fetch contents!
            topics_url = f"https://www.futurekul.com/admin/api/course/topic-and-section?courseId={course_id}"
            topics_data = await fetch_json(session, topics_url)
            
            if not topics_data or topics_data.get("state") != 200 or topics_data.get("msg") == "No Data Found":
                await status_msg.edit(f"❌ <b>Access Denied or No Data</b>\n\nFuturekul server rejected access to {batch_title}. The dummy account must have purchased this course to extract topics.")
                return
                
            topics = topics_data.get("data", {}).get("topics", [])
            
            if not topics:
                await status_msg.edit("❌ No topics found for this batch.")
                return
                
            all_outputs = []
            
            # Note: For full extraction, we would loop through topics and fetch classes
            # Since we can't test it, we assume it's like Selection Way
            for topic in topics:
                topic_id = topic.get("topicId")
                topic_name = topic.get("topicName", "Unknown Topic")
                all_outputs.append(f"\n{topic_name}\n\n")
                
                classes_url = f"https://www.futurekul.com/admin/api/topics/{topic_id}/classes?courseId={course_id}"
                classes_data = await fetch_json(session, classes_url)
                classes = classes_data.get("data", {}).get("classes", []) if classes_data else []
                
                for cls in classes:
                    title = cls.get("title", "Untitled")
                    hls_link = cls.get("class_link", "")
                    if hls_link:
                        all_outputs.append(f"{title}:{hls_link}\n")
                        
                    mp4s = cls.get("mp4Recordings", [])
                    if mp4s:
                        for mp4 in mp4s:
                            url = mp4.get("url", "")
                            if url:
                                all_outputs.append(f"{title}:{url}\n")
                                
                    pdfs = cls.get("classPdf", [])
                    if pdfs:
                        for pdf in pdfs:
                            pdf_url = pdf.get("url", "")
                            if pdf_url:
                                all_outputs.append(f"{title} PDF:{pdf_url}\n")
                                
            if len(all_outputs) == 0:
                await status_msg.edit("❌ No content found.")
                return
                
            clean_file_name = f"{user_id}_{clean_batch_name}"
            content = ''.join(all_outputs)
            
            with open(f"{clean_file_name}.txt", 'w', encoding='utf-8') as f:
                f.write(content)
                
            video_count = sum(1 for line in all_outputs if not line.endswith(".pdf\\n") and "PDF:" not in line and ":" in line)
            pdf_count = sum(1 for line in all_outputs if "PDF:" in line)
            total_links = video_count + pdf_count
            
            caption = (
                f"🎓 <b>FUTUREKUL EXTRACTED</b> 🎓\n\n"
                f"📚 <b>BATCH:</b> {batch_title}\n\n"
                f"📊 <b>CONTENT STATS</b>\n"
                f"├─ 📁 Total Links: {total_links}\n"
                f"├─ 🎬 Videos: {video_count}\n"
                f"└─ 📄 PDFs: {pdf_count}\n\n"
                f"🚀 <b>Extracted by</b>: @{(await app.get_me()).username}\n\n"
                f"<code>╾───• {BOT_TEXT} •───╼</code>"
            )
            
            with open(f"{clean_file_name}.txt", 'rb') as f:
                await msg.delete()
                await status_msg.delete()
                await m.reply_document(
                    document=f,
                    caption=caption,
                    file_name=f"{clean_batch_name}.txt"
                )
                
            try:
                os.remove(f"{clean_file_name}.txt")
            except:
                pass
                
        except Exception as e:
            await m.reply_text(f"Error: {str(e)}")
            
        finally:
            await session.close()
            await CONNECTOR.close()

@app.on_callback_query(filters.regex("^futurekul_$"))
async def futurekul_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        await callback_query.answer()
        await process_futurekul(client, callback_query.message, user_id)
    except Exception as e:
        try:
            await callback_query.message.reply_text(f"Error: {str(e)}")
        except:
            pass
