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
KEYWORDS = [
    "ufc", "мма", "mma", "бой", "боя", "бои", "грэпплинг", "борьб",
    "aca", "pfl", "bellator", "adcc", "махачев", "хабиб", "анкалаев",
    "царукян", "чимаев", "петр ян", "пётр ян", "волков", "павлович",
    "умар", "усман", "евлоев", "нокаут", "сабмишн", "октагон", "пояс"
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
        "Ты редактор дерзкого и статусного спортивного канала «ПУТЬ ГОРЦА | LIVE» про ММА, UFC и грэпплинг. "
        "Перепиши эту новость коротким, живым, цепляющим постом (до 500 символов) с характером гор, "
        "уважением к бойцам и 2-3 уместными эмодзи. Без воды и ссылок. В конце добавь хэштеги #ММА #Грэпплинг #ПутьГорца.\n\n"
        f"Заголовок: {title}\nТекст: {summary[:800]}"
    )
    payload = json.dumps({
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choices = res.get("choices")
        return choices[0].get("message").get("content").strip()

def is_mma_news(title, desc):
    text = (title + " " + desc).lower()
    return any(word in text for word in KEYWORDS)

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
                    if link and link not in posted_links and title and is_mma_news(title, desc):
                        print("Найдена новость ММА:", title)
                        return link, title, desc
        except Exception as e:
            print("RSS error:", rss_url, e)
    return None, None, None

def update_rss(posts):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "ПУТЬ ГОРЦА | LIVE"
    ET.SubElement(channel, "link").text = "https://" + "sultankrutoy777-hue.github.io/gorets-bot/"
    ET.SubElement(channel, "description").text = "Главные новости ММА и грэпплинга 24/7"

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
        print("Готовый пост:\n", ai_post)

        data["links"].append(link)
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
