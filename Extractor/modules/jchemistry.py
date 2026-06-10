import re
import json
import urllib.parse
import requests
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor import app

# Constants for Edmingle
BASE_URL = "https://jchemistry-api.edmingle.com/nuSource/api/v1"

async def get_org_id(token):
    headers = {
        "APIKEY": token,
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(f"{BASE_URL}/user/usermeta", headers=headers).json()
    orgs = r.get("user", {}).get("org_data", [])
    if orgs:
        return str(orgs[0].get("organization_id"))
    return ""

async def jchemistry(app, message):
    input1 = await app.ask(message.chat.id, text="Send **ID & Password** in this manner, otherwise, the bot will not respond.\n\nSend like this: **ID*Password**")
    raw_text = input1.text
    try:
        ph, pas = raw_text.split("*")
    except ValueError:
        await message.reply_text("Invalid format! Send as ID*Password")
        return
        
    await input1.delete(True)
    
    msg = await message.reply_text("Logging in...")
    
    url = f"{BASE_URL}/tutor/login"
    payload = {
        "username": ph,
        "password": pas,
        "persistent_login": True
    }
    data = {"JSONString": json.dumps(payload)}
    
    try:
        r = requests.post(url, data=data).json()
        
        if r.get("message") != "Login successful":
            await msg.edit_text(f"Login Failed! Error: {r.get('message', 'Invalid Credentials')}")
            return
            
        token = r.get("user", {}).get("apikey")
        
        # We need the Org ID to fetch courses
        org_id = await get_org_id(token)
        
        headers = {
            "APIKEY": token,
            "ORGID": org_id,
            "User-Agent": "Mozilla/5.0"
        }
        
        # Fetch batches
        await msg.edit_text("Login Successful! Fetching batches...")
        
        # tag_ids=9 usually means purchased courses in Edmingle
        course_url = f"{BASE_URL}/student/masterbatches?tag_ids=9"
        r2 = requests.get(course_url, headers=headers).json()
        
        batches = r2.get("batches", [])
        if not batches:
            await msg.edit_text("No purchased batches found!")
            return
            
        keyboard = []
        for batch in batches:
            name = batch.get("name", "Unknown Course")
            course_id = batch.get("id")
            # Format: app_courseId_orgId_token
            callback_data = f"jchem_{course_id}_{org_id}_{token[:10]}"
            keyboard.append([InlineKeyboardButton(name, callback_data=callback_data)])
            
        # Store full token locally since callback data has length limits
        app.jchem_tokens = getattr(app, 'jchem_tokens', {})
        app.jchem_tokens[token[:10]] = token
            
        await msg.edit_text(
            f"**Login Successful!**\nFound {len(batches)} batches.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await msg.edit_text(f"Error during login: {str(e)}")

@app.on_callback_query(filters.regex(r"^jchem_"))
async def jchemistry_course(client, query):
    try:
        data = query.data.split("_")
        course_id = data[1]
        org_id = data[2]
        short_token = data[3]
        
        token = client.jchem_tokens.get(short_token)
        if not token:
            await query.answer("Session expired. Please login again.", show_alert=True)
            return
            
        headers = {
            "APIKEY": token,
            "ORGID": org_id,
            "User-Agent": "Mozilla/5.0"
        }
        
        await query.message.edit_text("Fetching subjects... please wait.")
        
        # Get subjects for course
        url = f"{BASE_URL}/student/masterbatches/classes/{course_id}?get_tags=1&show_overview=1"
        r = requests.get(url, headers=headers).json()
        
        subjects = r.get("classes", [])
        if not subjects:
            await query.message.edit_text("No subjects found in this course.")
            return
            
        # Generate Txt format
        txt = f"**Course Data**\n\n"
        for sub in subjects:
            sub_id = sub.get("class_id")
            sub_name = sub.get("name")
            txt += f"📚 **{sub_name}**\n"
            
            # Get videos and PDFs inside subject
            res_url = f"{BASE_URL}/student/classcurriculum/{sub_id}/resources"
            r2 = requests.get(res_url, headers=headers).json()
            
            resources = r2.get("resources", [])
            for res in resources:
                if res.get("resource_type") == "video":
                    v_url = res.get("video_url", "No Link")
                    if not v_url or v_url == "No Link":
                        if res.get("vdocipher_video_id"):
                            v_url = f"https://player.vdocipher.com/v2/?otp=dummy&playbackInfo=dummy&videoId={res.get('vdocipher_video_id')}"
                        elif res.get("gumlet_asset_id"):
                            v_url = f"https://video.gumlet.io/{res.get('gumlet_asset_id')}/main.m3u8"
                        elif res.get("videocrypt_video_id"):
                            v_url = f"videocrypt://{res.get('videocrypt_video_id')}"
                    v_url = res.get("video_url", "No Link")
                    txt += f"🎥 {res.get('title')}: {v_url}\n"
                elif res.get("resource_type") in ["document", "pdf"]:
                    d_url = res.get("media_url", "No Link")
                    txt += f"📄 {res.get('title')}: {d_url}\n"
            
            txt += "\n"
            
        # Send text file
        with open("jchemistry_course.txt", "w", encoding="utf-8") as f:
            f.write(txt)
            
        await query.message.reply_document("jchemistry_course.txt")
        await query.message.delete()
        
    except Exception as e:
        await query.message.edit_text(f"Error fetching course data: {str(e)}")
