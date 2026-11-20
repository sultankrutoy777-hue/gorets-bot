import os
import json
import uuid
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

GIGACHAT_KEY = "".join(os.environ["GIGACHAT_KEY"].split())
RSS_SOURCES = [
    "https://" + "www.sports.ru/rss/rubric.xml?s=209",
    "https://" + "allboxing.ru/rss.xml",
    "https://" + "valetudo.ru/mma/news?format=feed&type=rss",
]

MUST_HAVE_WORDS = [
    "хабиб", "махачев", "нурмагомедов", "умар", "усман", "анкалаев",
    "евлоев", "алискеров", "шара", "буллет", "рабаданов", "забит",
    "магомедшарипов", "садулаев", "сидаков", "угуев", "дагестан",
    "кавказ", "махачкал", "хасавюрт", "вольная борьба", "вольник",
    "грэпплинг", "adcc", "чимаев", "царукян", "имавов", "мухаммад",
    "гаджиев", "магомедов", "абдулманап", "дагестанск"
]

BANNED_WORDS = [
    "водк", "пив", "алкогол", "виски", "шампанск", "пьян", "казино",
    "ставк", "букмекер", "секс", "интим", "голы", "обнажен", "стриптиз",
    "онлифанс", "onlyfans", "порно", "измен", "любовниц", "эскорт",
    "наркот", "травк", "марихуан", "драк в клубе", "ночной клуб", "поп-мма"
]

HISTORY_FILE = "history.json"
FEED_FILE = "feed.xml"

def get_gigachat_token():
    url = "https://" + "ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {GIGACHAT_KEY}",
    }
    data = urllib.parse.urlencode({"scope": "GIGACHAT_API_PERS"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]

def rewrite_with_gigachat(token, title, summary):
    url = "https://" + "gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {token}",
    }
    prompt = (
        "Ты главный редактор достойного, чистого и статусного спортивного канала «ПУТЬ ГОРЦА | LIVE» "
        "о дагестанской школе борьбы, грэпплинге и ММА (Хабиб, Ислам Махачев, Умар Нурмагомедов, Анкалаев, Садулаев и др.).\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "1. Никакой грязи, пошлости, упоминаний алкоголя, ставок, клубов, слухов о личной жизни и дешёвого трэш-тока.\n"
        "2. Пиши только о спорте, характере, дисциплине, схватках, подготовке и победах.\n"
        "3. Стиль: сдержанный, мужской, горский, с уважением, без воды. Длина — 350-550 символов.\n"
        "4. Используй 2 строгих эмодзи (🦅, 🤼‍♂️, 🏆, 🏔). В конце поставь хэштеги #ПутьГорца #Дагестан #ММА #Борьба.\n"
        "Если эта новость не касается спорта или содержит грязь — ответь одним словом: SKIP\n\n"
        f"Заголовок: {title}\nТекст: {summary[:800]}"
    )
    payload = json.dumps({
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        first_choice = res.get("choices").pop(0)
        return first_choice.get("message").get("content").strip()

def is_clean_dag_sport(title, desc):
    text = (title + " " + desc).lower()
    if any(bad in text for bad in BANNED_WORDS):
        return False
    return any(good in text for good in MUST_HAVE_WORDS)

def fetch_latest_news(posted_links):
    for rss_url in RSS_SOURCES:
        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall(".//item"):
                    link = (item.findtext("link") or "").strip()
                    title = (item.findtext("title") or "").strip()
                    desc = (item.findtext("description") or "").strip()
                    if link and link not in posted_links and title and is_clean_dag_sport(title, desc):
                        print("Отобрана чистая новость:", title)
                        return link, title, desc
        except Exception as e:
            print("RSS error:", rss_url, e)
    return None, None, None

def update_rss(posts):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "ПУТЬ ГОРЦА | LIVE"
    ET.SubElement(channel, "link").text = "https://" + "sultankrutoy777-hue.github.io/gorets-bot/"
    ET.SubElement(channel, "description").text = "Чистый спорт, школа борьбы, грэпплинг и ММА"

    for post in posts[:15]:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = post["title"]
        ET.SubElement(item, "description").text = post["text"]
        ET.SubElement(item, "guid").text = post["id"]
        ET.SubElement(item, "pubDate").text = post["date"]

    ET.ElementTree(rss).write(FEED_FILE, encoding="utf-8", xml_declaration=True)

def main():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"links": [], "posts": []}

    link, title, desc = fetch_latest_news(set(data["links"]))
    if link:
        token = get_gigachat_token()
        ai_post = rewrite_with_gigachat(token, title, desc)
        data["links"].append(link)
        if ai_post != "SKIP" and "SKIP" not in ai_post:
            print("Готовый чистый пост:\n", ai_post)
            data["posts"].insert(0, {
                "id": str(uuid.uuid4()),
                "title": title,
                "text": ai_post,
                "date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    update_rss(data["posts"])

if __name__ == "__main__":
    main()
