import asyncio
from playwright.async_api import async_playwright
import re
import requests

async def get_m3u_url_and_content():
    m3u_url_text = None
    m3u_content = None
    page_url = "https://xtream.storesat.vip/iptv.php"
    button_text = "توليد الروابط الآن"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"يتم الآن الانتقال إلى: {page_url}...")
        try:
            await page.goto(page_url, wait_until="networkidle", timeout=60000)
            print("تم تحميل الصفحة بنجاح.")
        except Exception as e:
            print(f"فشل تحميل الصفحة: {page_url}. الخطأ: {e}")
            await browser.close()
            return None, None

        print(f"البحث عن زر بالنص: '{button_text}'")
        try:
            button_selector_std = f"button:has-text('{button_text}')"
            button_selector_input = f"input[type='button'][value='{button_text}'], input[type='submit'][value='{button_text}']"
            clicked = False
            if await page.is_visible(button_selector_std, timeout=5000):
                print(f"تم العثور على الزر (button). جاري الضغط على '{button_text}'...")
                await page.click(button_selector_std, timeout=10000)
                clicked = True
            elif await page.is_visible(button_selector_input, timeout=5000):
                print(f"تم العثور على الزر (input). جاري الضغط على '{button_text}'...")
                await page.click(button_selector_input, timeout=10000)
                clicked = True
            if clicked:
                print("تم الضغط على الزر. الانتظار لتحميل/تحديث رابط M3U...")
                await page.wait_for_timeout(7000)
            else:
                print(f"لم يتم العثور على الزر '{button_text}' أو أنه غير مرئي. سيتم محاولة استخراج الرابط مباشرة إذا كان موجودًا.")
        except Exception as e:
            print(f"لم يتمكن من الضغط على الزر أو أن الضغط غير ضروري: {e}")
            print("محاولة استخراج رابط M3U مباشرة.")

        print("البحث عن رابط M3U داخل وسم <code>...")
        try:
            code_element_selector = "code:has-text('get.php'):has-text('type=m3u')"
            await page.wait_for_selector(code_element_selector, timeout=20000)
            m3u_url_element = await page.query_selector(code_element_selector)
            if m3u_url_element:
                m3u_url_text = await m3u_url_element.inner_text()
                m3u_url_text = m3u_url_text.strip()
                if m3u_url_text.startswith("http") and "get.php" in m3u_url_text:
                    print(f"تم العثور على رابط M3U: {m3u_url_text}")
                else:
                    print(f"النص المستخرج لا يبدو كرابط M3U صالح: {m3u_url_text}")
                    m3u_url_text = None
            else:
                print("لم يتم العثور على عنصر رابط M3U (<code>) بعد محاولة الضغط أو مباشرة.")
        except Exception as e:
            print(f"خطأ في استخراج رابط M3U من وسم <code>: {e}")
            print("محاولة استخراج رابط M3U باستخدام البحث العام في الصفحة...")
            page_content_for_regex = await page.content()
            match = re.search(r'(https://xtream\\.storesat\\.vip/get\\.php\\?[^\s\'\"]*type=m3u[8]?)', page_content_for_regex)
            if match:
                m3u_url_text = match.group(1)
                print(f"تم العثور على رابط M3U باستخدام البحث العام: {m3u_url_text}")
            else:
                print("لم يتم العثور على رابط M3U في الصفحة حتى باستخدام البحث العام.")

        if m3u_url_text:
            print(f"جاري تحميل محتوى M3U من: {m3u_url_text}")
            try:
                response = requests.get(m3u_url_text, timeout=60)
                response.raise_for_status()
                response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
                m3u_content = response.text
                print("تم تحميل محتوى M3U بنجاح.")
            except requests.exceptions.RequestException as e:
                print(f"فشل تحميل محتوى M3U: {e}")
                m3u_content = None

        await browser.close()
    return m3u_url_text, m3u_content

def parse_m3u_content(m3u_content):
    if not m3u_content:
        return []
    channels = []
    lines = m3u_content.splitlines()
    current_channel_info = {}
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            current_channel_info = {}
            name_match = re.search(r'tvg-name="([^"]*)"', line)
            if name_match and name_match.group(1).strip():
                current_channel_info['name'] = name_match.group(1).strip()
            else:
                parts = line.split(',')
                if len(parts) > 1:
                    current_channel_info['name'] = parts[-1].strip()
                else:
                    current_channel_info['name'] = "اسم غير معروف"
        elif line.startswith("http") and 'name' in current_channel_info:
            current_channel_info['url'] = line
            channels.append(current_channel_info)
            current_channel_info = {}
        elif not line or line.startswith("#EXTM3U"):
            continue
    return channels

def save_channels_to_m3u(channels, output_file="channels.m3u"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for channel in channels:
            name = channel.get("name", "اسم غير معروف")
            url = channel.get("url", "")
            f.write(f'#EXTINF:-1 tvg-name="{name}",{name}\n{url}\n')
    print(f"تم حفظ القنوات في ملف: {output_file}")

async def main():
    print("بدء عملية جلب وتحليل IPTV...")
    m3u_url, m3u_content_data = await get_m3u_url_and_content()
    if m3u_content_data:
        print("\nجاري تحليل محتوى M3U...")
        parsed_channels = parse_m3u_content(m3u_content_data)
        if parsed_channels:
            print(f"تم بنجاح تحليل {len(parsed_channels)} قناة.")
            save_channels_to_m3u(parsed_channels)
            print("\nعينة من القنوات المستخرجة:")
            for i, channel in enumerate(parsed_channels[:5]):
                print(f"  القناة {i+1}: الاسم='{channel['name']}', الرابط='{channel['url']}'")
        else:
            print("لم يتم العثور على قنوات أو فشل تحليل محتوى M3U.")
    else:
        print("فشل استرداد رابط M3U أو تحميل محتواه. لا يمكن المتابعة.")

if __name__ == "__main__":
    asyncio.run(main())
