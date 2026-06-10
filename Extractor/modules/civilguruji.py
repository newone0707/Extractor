import re
import requests
import threading
import asyncio
from Extractor import app


async def civil_guru(app, message):
    input1 = await app.ask(message.chat.id, text="Send **ID & Password** in this manner, otherwise, the bot will not respond.\n\nSend like this: **ID*Password**")
    raw_text = input1.text
    ph, pas = raw_text.split("*")
    await input1.delete(True)

    url1 = "https://civilguruji.com/api/user/signin"
    payload1 = {
        "phoneNumber": "",
        "countryCode": "+91",
        "email": ph,
        "from": "email"
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://civilguruji.com/login",
        "Origin": "https://civilguruji.com"
    }

    r1 = requests.post(url1, json=payload1, headers=headers).json()
    id = r1['_id']

    url2 = "https://civilguruji.com/api/user/signin-with-password"
    payload2 = {
        "userId": id,
        "password": pas
    }
    r2 = requests.post(url2, json=payload2, headers=headers).json()
    token = r2['access_token']

    await message.reply_text(f"**Login Successful...**")

    headers1 = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://civilguruji.com/foryou",
        "Origin": "https://civilguruji.com",
        "X-Access-Token": token
    }

    url3 = "https://civilguruji.com/api/course/list-purchased-courses"
    payload3 = {
        "userId": id,
    }

    r3 = requests.post(url3, json=payload3, headers=headers1).json()
    ff = "BATCH-ID - BATCH NAME\n\n"
    for data in r3:
        batch_id = data.get('_id')
        batch_name = data.get('name')
        ff += f"`{batch_id}`   -   **{batch_name}**\n\n"
       
    await message.reply_text(f"**YOU HAVE THESE BATCHES:\n\n{ff}")
    input2 = await app.ask(message.chat.id, text="**Now send the Batch ID to Download**")
    raw_text2 = input2.text

    headers2 = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://civilguruji.com/api/course/package/package-details",
        "X-Access-Token": token
    }
    url4 = f"https://civilguruji.com/api/course/package/package-details/{raw_text2}"
    r4 = requests.get(url4, headers=headers2)
    if r4.status_code == 200:
        data = r4.json()['courses']
        mm = ""
        txt_name = r4.json()['name']
        for course in data:
            course_id = course['course']['_id']
            course_name = course['course']['name']
            mm += f"{course_name}:{course_id}$"
    else:
        print(f"Error: {r4.status_code}")

    num_id = mm.split('$')
    for x in range(0, len(num_id) - 1):
        id_text = num_id[x]
        print(id_text)
        id_n, id_i = id_text.split(':')
        id = id_n.replace(" ", "%20")
        headers3 = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": f"https://civilguruji.com/course/{id}/{id_i}",
            "X-Access-Token": token
        }
        url5 = f"https://civilguruji.com/api/course/course-details/{id_i}"
        r5 = requests.get(url5, headers=headers3)
        if r5.status_code == 200:
            data = r5.json()['courseDetail']['courseContents']
            name = r5.json()['name']
            mm = ""
            url_pattern = r'https?://\S+'

            for course in data:
                courseSubContents = course['courseSubContents']
                for ii in courseSubContents:
                    n = ii['name']
                    if ii.get('videoUrl'):
                        vurl = ii['videoUrl']
                        url_p = r'src="([^"]+)"'
                        urls = re.findall(url_p, vurl)
                        if urls:
                            vurl = urls[0]
                        mm += f"{name}-{n} (Video): {vurl}\n"
                    if ii.get('modelUrl'):
                        l = ii['modelUrl']
                        urls = re.findall(url_pattern, l)
                        if urls:
                            murl = urls[0]
                        mm += f"{name}-{n} (Model): {murl}\n"

                    if ii.get('attachments'):
                        for d in ii['attachments']:
                            label = d.get('label')
                            aurl = d.get('data')
                            mm += f"{name}-{label}: {aurl}\n"

            with open(f"{txt_name}.txt", 'a') as f:
                f.write(f"{mm}")

        else:
            print(f"Error: {r5.status_code}")

    c_txt = f"**App Name: Civil Guruji\nBatch Name: `{txt_name}`**"
    await app.send_document(message.chat.id, document=f"{txt_name}.txt", caption=c_txt)
