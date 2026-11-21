import os, re, json, uuid, ssl
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

ssl._create_default_https_context = ssl._create_unverified_context

GIGACHAT_KEY = "".join(os.environ["GIGACHAT_KEY"].split())
MAX_SESSION = os.environ.get("MAX_SESSION", "").strip()
CHANNEL_NAME = "ПУТЬ ГОРЦА"

RSS_SOURCES = [
    "https://" + "www.sports.ru/rss/rubric.xml?s=209",
    "https://" + "allboxing.ru/rss.xml",
    "https://" + "valetudo.ru/mma/news?format=feed&type=rss",
    "https://" + "://championat.com",
]

MUST_HAVE = [
    "хабиб", "махачев", "нурмагомедов", "умар", "усман", "анкалаев", "евлоев",
    "алискеров", "шара", "буллет", "рабаданов", "забит", "садулаев", "сидаков",
    "угуев", "дагестан", "кавказ", "махачкал", "хасавюрт", "вольная борьба",
    "вольник", "грэпплинг", "adcc", "чимаев", "царукян", "имавов", "мухаммад",
    "гаджиев", "магомедов", "абдулманап", "дагестанск", "фсбр", "олимпи"
]

TOP_WORDS = [
    "хабиб", "махачев", "анкалаев", "умар", "усман", "садулаев",
    "сидаков", "чимаев", "царукян", "шара", "титул", "чемпион", "ufc"
]

BANNED = [
    "водк", "пив", "алкогол", "виски", "шампанск", "пьян", "казино", "ставк",
    "букмекер", "секс", "интим", "голы", "обнажен", "стриптиз", "онлифанс",
    "onlyfans", "порно", "измен", "любовниц", "эскорт", "наркот", "травк",
    "марихуан", "драк в клубе", "ночной клуб", "поп-мма"
]

HISTORY_FILE = "history.json"
TEMP_IMG = "post_image.jpg"

def get_rubric():
    h = (datetime.now(timezone.utc) + timedelta(hours=3)).hour
    if 6 <= h < 11:
        return "РУБРИКА «УТРЕННИЙ НАСТРОЙ 🏔»: акцент на характер, дисциплину и труд в зале."
    if 19 <= h <= 23:
        return "РУБРИКА «ВЕЧЕРНИЙ РАЗБОР 🦅»: разбери суть и в конце задай подписчикам 1 сильный вопрос."
    return "РУБРИКА «ГЛАВНОЕ ЗА ДЕНЬ 🏆»: чёткая, динамичная главная спортивная сводка."

def get_token():
    url = "https://" + "ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json", "User-Agent": "Mozilla/5.0", "RqUID": str(uuid.uuid4()), "Authorization": f"Basic {GIGACHAT_KEY}"}
    data = urllib.parse.urlencode({"scope": "GIGACHAT_API_PERS"}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method="POST"), timeout=25) as r:
        return json.loads(r.read().decode("utf-8")).get("access_token")

def rewrite_ai(token, title, summary):
    url = "https://" + "gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0", "Authorization": f"Bearer {token}"}
    prompt = (
        "Ты редактор чистого статусного канала «ПУТЬ ГОРЦА | LIVE» о дагестанской школе борьбы, грэпплинге и ММА.\n"
        f"{get_rubric()}\nПРАВИЛА: Без грязи, пошлости, алкоголя, ставок, клубов, слухов и трэш-тока. Только спорт и характер. "
        "Сдержанный мужской стиль, 350-550 символов, 2 строгих эмодзи (🦅, 🤼‍♂️, 🏆, 🏔), в конце хэштеги #ПутьГорца #Дагестан #ММА #Борьба. "
        f"Если новость не о спорте или грязная — ответь: SKIP\n\nЗаголовок: {title}\nТекст: {summary[:800]}"
    )
    payload = json.dumps({"model": "GigaChat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.55}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=payload, headers=headers, method="POST"), timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("choices").pop(0).get("message").get("content").strip()

def is_clean(title, desc):
    t = (title + " " + desc).lower()
    return not any(b in t for b in BANNED) and any(g in t for g in MUST_HAVE)

def get_img_url(item, desc):
    enc = item.find("enclosure")
    if enc is not None and enc.get("url"):
        return enc.get("url").strip()
    for el in item.iter():
        if el.tag.endswith("content") and el.get("url"):
            return el.get("url").strip()
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    return m.group(1).strip() if m else ""

def download_img(url):
    if not url or not url.startswith("http"):
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
            b = r.read()
            if len(b) > 5000:
                with open(TEMP_IMG, "wb") as f:
                    f.write(b)
                return os.path.abspath(TEMP_IMG)
    except Exception:
        pass
    return None

def fetch_best(posted):
    cands = []
    for u in RSS_SOURCES:
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
                for it in ET.fromstring(r.read()).findall(".//item"):
                    lk = (it.findtext("link") or "").strip()
                    tt = (it.findtext("title") or "").strip()
                    ds = (it.findtext("description") or "").strip()
                    if lk and lk not in posted and tt and is_clean(tt, ds):
                        im = get_img_url(it, ds)
                        pr = sum(2 for w in TOP_WORDS if w in (tt + " " + ds).lower()) + (1 if im else 0)
                        cands.append({"pr": pr, "lk": lk, "tt": tt, "ds": ds, "im": im})
        except Exception:
            pass
    if not cands:
        return None, None, None, ""
    cands.sort(key=lambda x: x.get("pr"), reverse=True)
    b = cands.pop(0)
    print("Выбрана топ-новость:", b.get("tt"))
    return b.get("lk"), b.get("tt"), b.get("ds"), b.get("im")

def post_max(text, img_path=None):
    if not MAX_SESSION:
        return
    sd = json.loads(MAX_SESSION)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36")
        if sd.get("cookies"):
            clist = []
            for pt in sd["cookies"].split(";"):
                if "=" in pt:
                    pr = pt.strip().split("=", 1)
                    clist.append({"name": pr.pop(0), "value": pr.pop(0), "domain": "web.max.ru", "path": "/"})
            if clist:
                ctx.add_cookies(clist)
        pg = ctx.new_page()
        pg.goto("https://" + "web.max.ru/", wait_until="domcontentloaded")
        pg.evaluate("(items) => { for (const [k, v] of Object.entries(items)) { localStorage.setItem(k, v); } }", sd.get("ls", {}))
        pg.reload(wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        pg.get_by_text(CHANNEL_NAME, exact=False).first.click(force=True, timeout=15000)
        pg.wait_for_timeout(3000)
        if img_path and os.path.exists(img_path):
            try:
                fi = pg.locator("input[type='file']").first
                if fi.count() > 0:
                    fi.set_input_files(img_path)
                    pg.wait_for_timeout(3000)
            except Exception:
                pass
        pg.mouse.click(800, 760)
        pg.wait_for_timeout(500)
        pg.keyboard.insert_text(text)
        pg.wait_for_timeout(1000)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(4000)
        print("ГОТОВО! Отправлено в MAX!")
        br.close()

def main():
    data = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else {"links": [], "posts": []}
    lk, tt, ds, im = fetch_best(set(data.get("links", [])))
    if lk:
        post = rewrite_ai(get_token(), tt, ds)
        data["links"].append(lk)
        if post != "SKIP" and "SKIP" not in post:
            print("Пост:\n", post)
            post_max(post, download_img(im))
            data["posts"].insert(0, {"id": str(uuid.uuid4()), "title": tt, "text": post, "date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
