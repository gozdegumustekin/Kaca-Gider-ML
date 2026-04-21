"""
Kaça Gider - Hepsiemlak.com Scraper
=====================================
Sahibinden CSV formatıyla uyumlu, AYRI klasöre kaydeder.
Sahibinden verilerine dokunmaz.

KULLANIM:
  1. Tüm Chrome pencerelerini KAPATIN.
  2. Chrome'u debug modda açın:
     "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^
       --remote-debugging-port=9222 ^
       --user-data-dir="C:\\chrome_scraper"
  3. Açılan Chrome'da hepsiemlak.com'a gidin.
  4. İstediğiniz aramanın ilan listesini görün.
  5. python scraper_hepsi.py çalıştırın → ENTER'a basın.

VERİ ÇEKME YÖNTEMİ:
  Her ilan sayfasındaki <script type="application/ld+json"> bloğunu
  parse eder — çok hızlı ve güvenilir.
"""

import os
import re
import json
import time
import random
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ─────────────────────────────────────────────
#  ayarlar.py'den sütun listelerini al
# ─────────────────────────────────────────────
try:
    from ayarlar import TUM_OZELLIKLER, TUM_SUTUNLAR
except ImportError:
    # ayarlar.py yoksa buradan okur
    TEMEL_SUTUNLAR = [
        "ilan_id","il","ilce","mahalle","emlak_tipi","fiyat_tl",
        "bina_yasi_raw","bulundugu_kat_raw","isitma_raw","isitma_ana_sinif","mutfak_raw",
        "metrekare_brut","metrekare_net","oda_sayisi",
        "bina_yasi_numeric","bina_yasi_ordinal",
        "bulundugu_kat_no","bulundugu_kat_ordinal",
        "kat_sayisi","isitma_score","banyo_sayisi",
        "mutfak_acik_mi","balkon","asansor","otopark","esyali",
        "fotograf_klasoru"
    ]
    TUM_OZELLIKLER = [
        "Batı","Doğu","Güney","Kuzey","ADSL","Ahşap Doğrama","Akıllı Ev","Alarm (Hırsız)",
        "Alarm (Yangın)","Alaturka Tuvalet","Alüminyum Doğrama","Amerikan Kapı","Ankastre Fırın",
        "Barbekü","Beyaz Eşya","Boyalı","Bulaşık Makinesi","Buzdolabı","Çamaşır Kurutma Makinesi",
        "Çamaşır Makinesi","Çamaşır Odası","Çelik Kapı","Duşakabin","Duvar Kağıdı","Ebeveyn Banyosu",
        "Fırın","Fiber İnternet","Giyinme Odası","Gömme Dolap","Görüntülü Diyafon","Hilton Banyo",
        "Intercom Sistemi","Isıcam","Jakuzi","Kartonpiyer","Kiler","Klima","Küvet","Laminat Zemin",
        "Marley","Mobilya","Mutfak (Ankastre)","Mutfak (Laminat)","Mutfak Doğalgazı","Panjur/Jaluzi",
        "Parke Zemin","PVC Doğrama","Seramik Zemin","Set Üstü Ocak","Spot Aydınlatma","Şofben",
        "Şömine","Teras","Termosifon","Vestiyer","Yüz Tanıma & Parmak İzi","Araç Şarj İstasyonu",
        "24 Saat Güvenlik","Apartman Görevlisi","Buhar Odası","Çocuk Oyun Parkı","Hamam","Hidrofor",
        "Isı Yalıtımı","Jeneratör","Kablo TV","Kamera Sistemi","Köpek Parkı","Kreş","Müstakil Havuzlu",
        "Sauna","Ses Yalıtımı","Siding","Spor Alanı","Su Deposu","Tenis Kortu","Uydu","Yangın Merdiveni",
        "Yüzme Havuzu (Açık)","Yüzme Havuzu (Kapalı)","Alışveriş Merkezi","Belediye","Cami","Cemevi",
        "Denize Sıfır","Eczane","Eğlence Merkezi","Fuar","Göle Sıfır","Hastane","Havra","İlkokul-Ortaokul",
        "İtfaiye","Kilise","Lise","Market","Park","Plaj","Polis Merkezi","Sağlık Ocağı","Semt Pazarı",
        "Spor Salonu","Şehir Merkezi","Üniversite","Anayol","Avrasya Tüneli","Boğaz Köprüleri","Cadde",
        "Deniz Otobüsü","Dolmuş","E-5","Havaalanı","İskele","Marmaray","Metro","Metrobüs","Minibüs",
        "Otobüs Durağı","Sahil","TEM","Tramvay","Tren İstasyonu","Boğaz","Deniz","Doğa","Göl","Havuz",
        "Nehir","Park & Yeşil Alan","Şehir","Dubleks","En Üst Kat","Ara Kat","Ara Kat Dubleks",
        "Bahçe Dubleksi","Çatı Dubleksi","Forleks","Ters Dubleks","Tripleks","Araç Park Yeri",
        "Engelliye Uygun Asansör","Engelliye Uygun Banyo","Engelliye Uygun Mutfak","Engelliye Uygun Park",
        "Geniş Koridor","Giriş / Rampa","Merdiven","Oda Kapısı","Priz / Elektrik Anahtarı",
        "Tutamak / Korkuluk","Tuvalet","Yüzme Havuzu"
    ]
    TUM_SUTUNLAR = TEMEL_SUTUNLAR + TUM_OZELLIKLER


# ═══════════════════════════════════════════════
#  GENEL AYARLAR
# ═══════════════════════════════════════════════
DEBUG_PORT     = "127.0.0.1:9222"

ANA_KLASOR     = "emlak_veri_seti"
FOTO_KLASOR    = os.path.join(ANA_KLASOR, "fotograflar_hepsi")
LOG_DOSYASI    = os.path.join(ANA_KLASOR, "scraper_hepsi_log.txt")
DURUM_DOSYASI  = os.path.join(ANA_KLASOR, "cekilen_hepsi.json")

MAX_ILAN       = 3
MAX_FOTO       = 10
KAHVE_ADET     = 12
KISA_BEKLE     = (5, 10)
UZUN_BEKLE     = (60, 130)
FOTO_BEKLE     = (0.3, 0.7)

os.makedirs(FOTO_KLASOR, exist_ok=True)

# Hepsiemlak → Sahibinden özellik adı eşleştirmesi
# Sağdaki = sahibinden TUM_OZELLIKLER'deki karşılığı
HEPSI_ESLESTIRME = {
    # İç özellikler
    "ADSL":                    "ADSL",
    "Akıllı Ev":               "Akıllı Ev",
    "Alarm (Hırsız)":          "Alarm (Hırsız)",
    "Alarm (Yangın)":          "Alarm (Yangın)",
    "Alaturka Tuvalet":        "Alaturka Tuvalet",
    "Alüminyum Doğrama":       "Alüminyum Doğrama",
    "Ahşap Doğrama":           "Ahşap Doğrama",
    "Ankastre Mutfak":         "Mutfak (Ankastre)",   # Hepsi farklı isim kullanıyor
    "Beyaz Eşya":              "Beyaz Eşya",
    "Bulaşık Makinesi":        "Bulaşık Makinesi",
    "Buzdolabı":               "Buzdolabı",
    "Çamaşır Makinesi":        "Çamaşır Makinesi",
    "Çelik Kapı":              "Çelik Kapı",
    "Duşakabin":               "Duşakabin",
    "Duvar Kağıdı":            "Duvar Kağıdı",
    "Ebeveyn Banyolu":         "Ebeveyn Banyosu",
    "Fırın":                   "Fırın",
    "Gömme Dolap":             "Gömme Dolap",
    "Görüntülü Diyafon":       "Görüntülü Diyafon",
    "Görüntülü Diafon":        "Görüntülü Diyafon",
    "Kapalı Balkon":           "Balkon",
    "Parke - Lamine":          "Parke Zemin",
    "Saten Alçı":              "Boyalı",
    "WiFi":                    "ADSL",
    "Hilton Banyo":            "Hilton Banyo",
    "Intercom Sistemi":        "Intercom Sistemi",
    "Isıcam":                  "Isıcam",
    "İnternet":                "ADSL",                # Hepsi "İnternet" = sahibinden "ADSL" + "Fiber İnternet"
    "Fiber İnternet":          "Fiber İnternet",
    "Jakuzi":                  "Jakuzi",
    "Kablo TV-Uydu":           "Kablo TV",
    "Kablo TV":                "Kablo TV",
    "Kartonpiyer":             "Kartonpiyer",
    "Kiler":                   "Kiler",
    "Klima":                   "Klima",
    "Küvet":                   "Küvet",
    "Laminat Zemin":           "Laminat Zemin",
    "Marley":                  "Marley",
    "Mobilya":                 "Mobilya",
    "Mutfak (Laminat)":        "Mutfak (Laminat)",
    "Mutfak Doğalgazı":        "Mutfak Doğalgazı",
    "Panel Kapı":              "Amerikan Kapı",        # En yakın karşılık
    "Panjur/Jaluzi":           "Panjur/Jaluzi",
    "Parke Zemin":             "Parke Zemin",
    "PVC Doğrama":             "PVC Doğrama",
    "Seramik Zemin":           "Seramik Zemin",
    "Set Üstü Ocak":           "Set Üstü Ocak",
    "Spot Aydınlatma":         "Spot Aydınlatma",
    "Şofben":                  "Şofben",
    "Şömine":                  "Şömine",
    "Teras":                   "Teras",
    "Termosifon":              "Termosifon",
    "Vestiyer":                "Vestiyer",
    # Dış özellikler
    "Açık Yüzme Havuzu":       "Yüzme Havuzu (Açık)",
    "Kapalı Yüzme Havuzu":     "Yüzme Havuzu (Kapalı)",
    "Buhar Odası":             "Buhar Odası",
    "Çocuk Oyun Parkı":        "Çocuk Oyun Parkı",
    "Hamam":                   "Hamam",
    "Hidrofor":                "Hidrofor",
    "Isı Yalıtımı":            "Isı Yalıtımı",
    "Jeneratör":               "Jeneratör",
    "Kamera Sistemi":          "Kamera Sistemi",
    "Kreş":                    "Kreş",
    "Müstakil Havuzlu":        "Müstakil Havuzlu",
    "Otopark - Açık":          "otopark",             # temel sütun
    "Otopark - Kapalı":        "otopark",             # temel sütun
    "Sauna":                   "Sauna",
    "Ses Yalıtımı":            "Ses Yalıtımı",
    "Siding":                  "Siding",
    "Spor Alanı":              "Spor Alanı",
    "Su deposu":               "Su Deposu",
    "Su Deposu":               "Su Deposu",
    "Tenis Kortu":             "Tenis Kortu",
    "Uydu":                    "Uydu",
    "Yangın Merdiveni":        "Yangın Merdiveni",
    # Konum/Çevre
    "Anayol":                  "Anayol",
    "E-5'e yakın":             "E-5",
    "E-5":                     "E-5",
    "İlköğretim Okulu":        "İlkokul-Ortaokul",
    "İlkokul":                 "İlkokul-Ortaokul",
    "Lise":                    "Lise",
    "Market":                  "Market",
    "Minibüs / Dolmuşa yakın": "Dolmuş",
    "Minibüs":                 "Minibüs",
    "Poliklinik":              "Sağlık Ocağı",
    "Şehir merkezinde":        "Şehir Merkezi",
    "Şehir Merkezi":           "Şehir Merkezi",
    "Hastane":                 "Hastane",
    "Cami":                    "Cami",
    "Park":                    "Park",
    "Eczane":                  "Eczane",
    "Üniversite":              "Üniversite",
    "Alışveriş Merkezi":       "Alışveriş Merkezi",
    "Otobüs Durağı":           "Otobüs Durağı",
    # Cephe
    "Güney":                   "Güney",
    "Kuzey":                   "Kuzey",
    "Doğu":                    "Doğu",
    "Batı":                    "Batı",
    # Konut şekli
    "Ara Kat":                 "Ara Kat",
    "Dubleks":                 "Dubleks",
    "Tripleks":                "Tripleks",
}


# ═══════════════════════════════════════════════
#  DURUM & LOG
# ═══════════════════════════════════════════════
def durum_yukle() -> set:
    if os.path.exists(DURUM_DOSYASI):
        try:
            with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                icerik = f.read().strip()
                return set(json.loads(icerik)) if icerik else set()
        except Exception:
            return set()
    return set()

def durum_kaydet(idler: set):
    with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(list(idler), f, ensure_ascii=False, indent=2)

def log(mesaj: str):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        f.write(satir + "\n")


# ═══════════════════════════════════════════════
#  CHROME BAĞLANTISI
# ═══════════════════════════════════════════════
def chrome_baglan() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", DEBUG_PORT)
    try:
        driver = webdriver.Chrome(options=options)
        log(f"Chrome bağlandı: {driver.title}")
        return driver
    except WebDriverException as e:
        print(f"\n❌ Chrome'a bağlanılamadı: {str(e)[:200]}")
        print("Chrome debug modda açık mı? (port 9222)")
        raise


# ═══════════════════════════════════════════════
#  CLOUDFLARE TESPİTİ
# ═══════════════════════════════════════════════
def cf_var_mi(driver) -> bool:
    try:
        source = driver.page_source.lower()
        title  = driver.title.lower()
    except Exception:
        return False
    isaretler = [
        "bağlantınız kontrol ediliyor", "basılı tut", "olağan dışı erişim",
        "referans kimliği", "devam edebilmek için", "lütfen tekrar deneyin",
        "checking your browser", "just a moment", "press and hold", "turnstile",
    ]
    if any(s in source for s in isaretler):
        return True
    if any(s in title for s in ["olağan dışı", "just a moment"]):
        return True
    return False

def cf_bekle(driver):
    while cf_var_mi(driver):
        print()
        log("⚠️  CLOUDFLARE TESPİT EDİLDİ!")
        print("  Chrome'a geçin, doğrulamayı tamamlayın.")
        input("  >>> Tamamladıktan sonra ENTER: ")
        time.sleep(3)


# ═══════════════════════════════════════════════
#  İNSANSI HAREKETLER
# ═══════════════════════════════════════════════
def kaydir(driver, oran=0.80):
    sayfa_h = driver.execute_script("return document.body.scrollHeight")
    hedef   = int(sayfa_h * oran)
    konum   = 0
    while konum < hedef:
        adim = random.randint(200, 450)
        konum = min(konum + adim, hedef)
        driver.execute_script(f"window.scrollTo(0, {konum});")
        time.sleep(random.uniform(0.15, 0.50))
        if random.random() < 0.15:
            geri = random.randint(80, 200)
            konum = max(konum - geri, 0)
            driver.execute_script(f"window.scrollTo(0, {konum});")
            time.sleep(random.uniform(0.2, 0.6))

def liste_kaydir(driver):
    sayfa_h = driver.execute_script("return document.body.scrollHeight")
    konum   = 0
    while konum < sayfa_h:
        adim = random.randint(300, 600)
        konum += adim
        driver.execute_script(f"window.scrollTo(0, {konum});")
        time.sleep(random.uniform(0.1, 0.35))
        sayfa_h = driver.execute_script("return document.body.scrollHeight")
    time.sleep(1)


# ═══════════════════════════════════════════════
#  İLAN LİNKLERİNİ TOPLAMA (hepsiemlak selector)
# ═══════════════════════════════════════════════
def linkleri_topla(driver) -> list:
    toplanan = []
    sayfa_no = 1

    while len(toplanan) < MAX_ILAN:
        log(f"Sayfa {sayfa_no} taranıyor...")
        cf_bekle(driver)
        liste_kaydir(driver)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Hepsiemlak ilan linkleri — farklı 2 selector dene
        ilan_linkleri = soup.find_all("a", class_=re.compile(r"card-link|listing-item|classified-title", re.I))

        # Fallback: href pattern ile bul
        if not ilan_linkleri:
            ilan_linkleri = [
                a for a in soup.find_all("a", href=True)
                if re.search(r"/daire/\d+-\d+|/konut/\d+|satilik.+/\d+-\d+", a["href"])
                and "hepsiemlak" not in a["href"]  # harici linkleri atla
            ]

        yeni = 0
        for a in ilan_linkleri:
            href = a.get("href", "")
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://www.hepsiemlak.com{href}"
            # Sadece ilan detay URL'si al (liste/arama sayfaları değil)
            if re.search(r"hepsiemlak\.com/.+-satilik/.+/\d+-\d+", href):
                if href not in toplanan:
                    toplanan.append(href)
                    yeni += 1

        log(f"  Sayfa {sayfa_no}: {yeni} yeni ilan. Toplam: {len(toplanan)}")

        if yeni == 0:
            log("Bu sayfada ilan bulunamadı veya artık yeni yok.")
            break

        if len(toplanan) >= MAX_ILAN:
            break

        # Sonraki sayfa butonu
        sonraki = soup.find("a", {"title": "Sonraki"}) or soup.find("a", {"rel": "next"})
        if not sonraki:
            # Hepsiemlak pagination linki (sayfa=2 tarzı)
            sonraki = soup.find("a", href=re.compile(r"sayfa=\d+"))

        if not sonraki:
            log("Sonraki sayfa bulunamadı, tarama tamamlandı.")
            break

        sonraki_url = sonraki.get("href", "")
        if sonraki_url.startswith("/"):
            sonraki_url = f"https://www.hepsiemlak.com{sonraki_url}"

        log(f"  Sonraki sayfaya geçiliyor...")
        driver.execute_script(f"window.location.href = '{sonraki_url}';")
        sayfa_no += 1
        time.sleep(random.uniform(4, 8))

    random.shuffle(toplanan)
    toplanan = toplanan[:MAX_ILAN]
    log(f"Toplam {len(toplanan)} ilan linki toplandı.")
    return toplanan


# ═══════════════════════════════════════════════
#  VERİ DÖNÜŞÜM YARDIMCILARI
# ═══════════════════════════════════════════════
def sayi_cikar(metin) -> float:
    if not isinstance(metin, (str, int, float)):
        return 0.0
    rakamlar = re.findall(r"-?\d+", str(metin))
    return float(rakamlar[0]) if rakamlar else 0.0

def temiz(metin, default="Bilinmiyor") -> str:
    if metin is None:
        return default
    metin = str(metin).replace("\xa0", " ").strip()
    return metin if metin else default

def metin_norm(metin: str) -> str:
    return re.sub(r"\s+", " ", temiz(metin, "")).strip()

def tr_title_slug(slug: str) -> str:
    slug = temiz(slug, "").replace("-", " ").strip()
    if not slug:
        return "Bilinmiyor"
    return " ".join(kelime.capitalize() for kelime in slug.split())

def url_lokasyon_cek(url: str):
    """URL'den il / ilçe / mahalle slug'ını çözmeye çalışır."""
    m = re.search(r"hepsiemlak\.com/([a-z0-9-]+)-(satilik|kiralik)/", url, re.I)
    if not m:
        return None, None, None

    parcalar = [p for p in m.group(1).split("-") if p]
    if len(parcalar) < 2:
        return None, None, None

    il = tr_title_slug(parcalar[0])
    ilce = tr_title_slug(parcalar[1]) if len(parcalar) >= 2 else None
    mahalle = None

    if len(parcalar) >= 3:
        mahalle_slug = parcalar[2]
        mahalle = tr_title_slug(mahalle_slug)
        if mahalle and not re.search(r"\b(mah|mh|köy|koyu|köyü|mevkii)\b", mahalle, re.I):
            mahalle = f"{mahalle} Mah."

    return il or None, ilce or None, mahalle or None

def m2_coz(metin: str):
    """137 m2 / 125 m2 gibi alanları m² içindeki 2 rakamına takılmadan çözer."""
    metin = metin_norm(metin).lower()
    if not metin or metin == "bilinmiyor":
        return 0.0, 0.0

    temiz_metin = re.sub(r"m\s*[²2]", " ", metin)
    sayilar = [float(s.replace(",", ".")) for s in re.findall(r"\d+(?:[\.,]\d+)?", temiz_metin)]

    if len(sayilar) >= 2:
        return sayilar[0], sayilar[1]
    if len(sayilar) == 1:
        return sayilar[0], sayilar[0]
    return 0.0, 0.0

def ozellik_metni_temizle(metin: str) -> str:
    metin = metin_norm(metin)
    if not metin:
        return ""

    if " - " in metin:
        metin = metin.split(" - ")[-1].strip()

    metin = metin.replace("Diafon", "Diyafon")
    metin = metin.replace("Parke - Lamine", "Parke Zemin")
    return metin

def oda_hesapla(metin: str) -> float:
    if not isinstance(metin, str):
        return 0.0
    rakamlar = re.findall(r"\d+", metin)
    return sum(float(r) for r in rakamlar) if rakamlar else 1.0

def yas_ordinal(metin: str) -> float:
    metin = str(metin).lower().strip()
    if "sıfır" in metin or metin == "0":          return 5.0
    elif "0-5" in metin:                           return 4.0
    elif "6-10" in metin:                          return 3.0
    elif "11-15" in metin or "11-25" in metin:     return 2.0
    elif "26" in metin or "üzeri" in metin:        return 1.0
    s = sayi_cikar(metin)
    if s == 0:    return 0.0
    elif s <= 5:  return 4.0
    elif s <= 10: return 3.0
    elif s <= 25: return 2.0
    else:         return 1.0

def yas_numeric(metin: str) -> float:
    metin = str(metin).lower().strip()
    if "sıfır" in metin or metin == "0":           return 0.0
    elif "0-5" in metin:                            return 3.0
    elif "6-10" in metin:                           return 8.0
    elif "11-15" in metin:                          return 13.0
    elif "11-25" in metin:                          return 18.0
    elif "26" in metin or "üzeri" in metin:         return 30.0
    return sayi_cikar(metin)

def kat_no(metin: str) -> float:
    metin = str(metin).lower().strip()
    if "bodrum" in metin:          return -1.0
    if "giriş altı" in metin or "kot" in metin: return -0.5
    if "bahçe" in metin:           return 0.0
    if "zemin" in metin:           return 0.0
    if "giriş" in metin:           return 0.0
    if "yüksek giriş" in metin:    return 0.5
    if "çatı" in metin:            return 99.0
    if "müstakil" in metin or "villa" in metin: return 1.0
    return sayi_cikar(metin)

def kat_ordinal(metin: str) -> float:
    metin = str(metin).lower().strip()
    if "bodrum" in metin or "kot" in metin: return 1.0
    if "çatı" in metin:    return 2.0
    if "bahçe" in metin:   return 4.0
    if "zemin" in metin or "giriş" in metin: return 3.0
    if "müstakil" in metin or "villa" in metin: return 5.0
    k = sayi_cikar(metin)
    if 1 <= k <= 5:   return 5.0
    elif 6 <= k <= 10: return 4.0
    elif 11 <= k <= 20: return 3.0
    elif k >= 21:       return 2.0
    return 0.0

def isitma_score(metin: str) -> float:
    metin = str(metin).lower().strip()
    puan = 0.0
    if any(k in metin for k in ["kombi (doğalgaz)", "yerden", "pay ölçer", "ısı pompası", "jeotermal"]):
        puan = 5.0
    elif any(k in metin for k in ["merkezi", "kat kaloriferi", "vrv"]):
        puan = 4.0
    elif any(k in metin for k in ["kombi (elektrik)", "fancoil"]):
        puan = 3.0
    elif any(k in metin for k in ["doğalgaz sobası", "elektrikli radyatör", "şömine", "güneş enerjisi"]):
        puan = 2.0
    elif metin == "yok" or "soba" in metin:
        puan = 1.0
    if "klima" in metin:
        puan = puan + 0.5 if puan >= 4.0 else max(puan, 3.0)
    return puan
def isitma_birlestir(isitma_raw: str, yakit_raw: str) -> str:
    isitma = temiz(isitma_raw, "Bilinmiyor")
    yakit = temiz(yakit_raw, "Bilinmiyor")

    isitma_l = isitma.lower()
    yakit_l = yakit.lower()

    if isitma == "Bilinmiyor":
        return isitma

    # Zaten içinde yakıt bilgisi varsa tekrar ekleme
    if any(k in isitma_l for k in ["doğalgaz", "dogalgaz", "elektrik", "kömür", "odun", "fuel-oil", "güneş"]):
        return isitma

    if yakit != "Bilinmiyor":
        return f"{isitma} ({yakit})"

    return isitma

def isitma_sinif(metin: str) -> str:
    metin = str(metin).lower().strip()
    eslesme = [
        ("yerden", "Yerden Isitma"), ("merkezi", "Merkezi"),
        ("kombi", "Kombi Dogalgaz" if "doğalgaz" in metin else "Kombi Elektrik"),
        ("kat kaloriferi", "Kat Kaloriferi"), ("vrv", "VRV"), ("fancoil", "Fancoil"),
        ("ısı pompası", "Isi Pompasi"), ("jeotermal", "Jeotermal"),
        ("doğalgaz sobası", "Dogalgaz Sobasi"), ("soba", "Soba"),
        ("klima", "Klima"), ("şömine", "Somine"), ("güneş enerjisi", "Gunes Enerjisi"),
    ]
    for a, d in eslesme:
        if a in metin:
            return d
    return temiz(metin)


# ═══════════════════════════════════════════════
#  HEPSIEMLAK JSON-LD PARSE
# ═══════════════════════════════════════════════
def json_ld_cek(soup) -> list:
    """Sayfadaki tüm JSON-LD bloklarını liste halinde döndürür."""
    bloklar = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            icerik = script.string or script.get_text() or ""
            if not icerik.strip():
                continue
            veri = json.loads(icerik)
            if isinstance(veri, list):
                bloklar.extend([v for v in veri if isinstance(v, dict)])
            elif isinstance(veri, dict):
                bloklar.append(veri)
        except Exception:
            continue
    return bloklar

def ilan_id_cek(url: str) -> str:
    """URL'den ilan ID çıkarır: .../122738-502 → 122738-502"""
    m = re.search(r"/(\d+-\d+)$", url)
    return m.group(1) if m else re.sub(r"[^a-zA-Z0-9]", "_", url[-20:])


def jld_icerisinden_nesne_bul(bloklar: list, tipler: tuple[str, ...]):
    tipler_lower = {t.lower() for t in tipler}

    def uygun_mu(nesne):
        tip = nesne.get("@type")
        if isinstance(tip, list):
            return any(str(t).lower() in tipler_lower for t in tip)
        return str(tip).lower() in tipler_lower

    for blok in bloklar:
        if not isinstance(blok, dict):
            continue
        if uygun_mu(blok):
            return blok

        graph = blok.get("@graph")
        if isinstance(graph, list):
            for oge in graph:
                if isinstance(oge, dict) and uygun_mu(oge):
                    return oge

        main = blok.get("mainEntity")
        if isinstance(main, dict) and uygun_mu(main):
            return main

    return {}

def jld_fiyat_bul(bloklar: list, main: dict) -> float:
    adaylar = []

    if isinstance(main, dict):
        if isinstance(main.get("offers"), dict):
            adaylar.append(main["offers"])
        if isinstance(main.get("aggregateOffer"), dict):
            adaylar.append(main["aggregateOffer"])

    for blok in bloklar:
        if not isinstance(blok, dict):
            continue
        if isinstance(blok.get("offers"), dict):
            adaylar.append(blok["offers"])
        graph = blok.get("@graph")
        if isinstance(graph, list):
            for oge in graph:
                if isinstance(oge, dict) and isinstance(oge.get("offers"), dict):
                    adaylar.append(oge["offers"])

    for offer in adaylar:
        try:
            fiyat = float(str(offer.get("price", "0")).replace(".", "").replace(",", "."))
            if fiyat > 0:
                return fiyat
        except Exception:
            continue
    return 0.0

def spec_ekle(specs: dict, anahtar: str, deger: str):
    anahtar = metin_norm(anahtar)
    deger = metin_norm(deger)
    if anahtar and deger and anahtar not in specs:
        specs[anahtar] = deger

def metinden_spec_cek(soup) -> dict:
    specs = {}
    metin = soup.get_text("\n", strip=True)
    satirlar = [metin_norm(s) for s in metin.split("\n") if metin_norm(s)]

    hedefler = {
        "İlan no", "Son Güncelleme", "İlan Durumu", "Konut Tipi", "Konut Şekli",
        "Oda Sayısı", "Banyo Sayısı", "Brüt / Net M2", "Kat Sayısı", "Bulunduğu Kat",
        "Bina Yaşı", "Isınma Tipi", "Yakıt Tipi", "Krediye Uygunluk", "Tapu Durumu",
        "Eşya Durumu", "Yapı Tipi", "Yapının Durumu", "Kullanım Durumu", "Cephe",
        "Aidat", "Takas", "Mutfak"
    }

    for i, satir in enumerate(satirlar[:-1]):
        if satir in hedefler:
            j = i + 1
            while j < len(satirlar):
                sonraki = satirlar[j]
                if sonraki in hedefler or sonraki in {"İlan özellikleri", "İlan Açıklaması", "Özellikler", "Çevre", "Emlak Endeksi"}:
                    break
                if satir == "Brüt / Net M2":
                    if re.search(r"\d", sonraki):
                        spec_ekle(specs, satir, sonraki)
                        break
                else:
                    spec_ekle(specs, satir, sonraki)
                    break
                j += 1

    return specs

def bolum_ozelliklerini_cek(soup) -> list:
    secili = []
    gorulen = set()

    # 1) Klasik li yapıları
    for li in soup.find_all("li"):
        metin = ozellik_metni_temizle(li.get_text(" ", strip=True))
        if not metin:
            continue
        dusuk = metin.lower()
        if len(metin) > 80 or re.search(r"\d+\s*(m|km|tl)", dusuk):
            continue
        if any(k in dusuk for k in ["favori", "paylaş", "telefon", "mesaj gönder", "yükleniyor", "güncelleme"]):
            continue

        if (metin in TUM_OZELLIKLER) or (metin in HEPSI_ESLESTIRME) or any(k in dusuk for k in ["asansör", "balkon", "otopark"]):
            if metin not in gorulen:
                secili.append(metin)
                gorulen.add(metin)

    # 2) Metinden bölüm bazlı fallback
    metin = soup.get_text("\n", strip=True)
    bolumler = ["İç Özellikler", "Dış Özellikler", "Muhit", "Ulaşım", "Manzara", "Konut Tipi", "Cephe", "Engelliye Uygun"]
    for bolum in bolumler:
        if bolum not in metin:
            continue
        parca = metin.split(bolum, 1)[1]
        for dur in bolumler + ["İlan Açıklaması", "Çevre", "Emlak Endeksi", "Bu ilanın"]:
            if dur != bolum and dur in parca:
                parca = parca.split(dur, 1)[0]
        for satir in parca.split("\n"):
            aday = ozellik_metni_temizle(satir)
            if not aday or len(aday) > 80 or re.search(r"\d+\s*(m|km|tl)", aday.lower()):
                continue
            if (aday in TUM_OZELLIKLER) or (aday in HEPSI_ESLESTIRME) or any(k in aday.lower() for k in ["asansör", "balkon", "otopark"]):
                if aday not in gorulen:
                    secili.append(aday)
                    gorulen.add(aday)

    return secili

def ozellik_matris_olustur(secili_ozellikler: list) -> dict:
    """
    Hepsiemlak özellik listesini (string list) → sahibinden formatı matrise çevirir.
    Eşleşmeyenler 0 kalır.
    """
    matris = {oz: 0 for oz in TUM_OZELLIKLER}

    for oz in secili_ozellikler:
        oz_temiz = ozellik_metni_temizle(oz)
        if not oz_temiz:
            continue

        # Balkon temel sütuna gidiyor; cephe sütununa yanlış yazılmasın
        if oz_temiz.lower() == "balkon":
            continue

        if oz_temiz in matris:
            matris[oz_temiz] = 1
            continue

        karsilik = HEPSI_ESLESTIRME.get(oz_temiz)
        if karsilik and karsilik in matris:
            matris[karsilik] = 1

    return matris

def cephe_isle(cephe_str: str, matris: dict) -> dict:
    """Cephe bilgisini matrise yaz (Güney, Kuzey, Doğu, Batı)."""
    if not cephe_str:
        return matris
    for yon in ["Güney", "Kuzey", "Doğu", "Batı"]:
        if yon.lower() in cephe_str.lower() and yon in matris:
            matris[yon] = 1
    return matris

def ilan_parse_et(soup, url: str, ilan_id: str) -> dict | None:
    """
    Hepsiemlak ilan sayfasını parse eder.
    Hem JSON-LD hem de HTML tablosundan veri çeker.
    Geçersizse None döner.
    """
    # ── 1. JSON-LD bloklarını çek ───────────────────────────
    jld_bloklari = json_ld_cek(soup)
    main = jld_icerisinden_nesne_bul(jld_bloklari, ("Apartment", "Residence", "SingleFamilyResidence", "House", "Product"))

    # ── 2. Fiyat (JSON-LD > HTML > görünür metin) ───────────
    fiyat = jld_fiyat_bul(jld_bloklari, main)

    if fiyat == 0:
        fiyat_el = soup.find(["p", "span", "div"], class_=re.compile(r"price|fiyat", re.I))
        if fiyat_el:
            fiyat_str = re.sub(r"[^\d]", "", fiyat_el.get_text(" ", strip=True))
            fiyat = float(fiyat_str) if fiyat_str else 0

    if fiyat == 0:
        sayfa_metni = soup.get_text("\n", strip=True)
        m = re.search(r"([\d\.,]+)\s*TL", sayfa_metni, re.I)
        if m:
            fiyat = float(m.group(1).replace(".", "").replace(",", "."))

    if fiyat == 0:
        return None

    # ── 3. Lokasyon ──────────────────────────────────────────
    il, ilce, mahalle = "Bilinmiyor", "Bilinmiyor", "Bilinmiyor"

    if isinstance(main, dict) and isinstance(main.get("address"), dict):
        addr = main["address"]
        il = temiz(addr.get("addressRegion"), il)
        ilce = temiz(addr.get("addressLocality"), ilce)
        street = temiz(addr.get("streetAddress"), "")
        if street:
            mahalle = street.split(",")[0].strip()

    url_il, url_ilce, url_mahalle = url_lokasyon_cek(url)
    if il == "Bilinmiyor" and url_il:
        il = url_il
    if ilce == "Bilinmiyor" and url_ilce:
        ilce = url_ilce
    if mahalle == "Bilinmiyor" and url_mahalle:
        mahalle = url_mahalle

    # ── 4. HTML spec tablosunu parse et ────────────────────
    specs = {}

    for spec_tablo in soup.find_all("table"):
        for row in spec_tablo.find_all("tr"):
            hucreler = row.find_all(["th", "td"])
            if len(hucreler) >= 2:
                anahtar = metin_norm(hucreler[0].get_text(" ", strip=True))
                deger = metin_norm(hucreler[1].get_text(" ", strip=True))
                if anahtar and deger:
                    specs[anahtar] = deger

    if not specs:
        info_divler = soup.find_all("div", class_=re.compile(r"detail-info|spec-item|adv-info|classifiedInfo", re.I))
        for div in info_divler:
            baslik = div.find("th") or div.find(class_=re.compile(r"txt|label|title|name", re.I))
            deger = div.find("td") or div.find("span", class_=re.compile(r"value|val", re.I)) or div.find("div", class_=re.compile(r"value|val", re.I))
            if baslik and deger:
                specs[metin_norm(baslik.get_text(" ", strip=True))] = metin_norm(deger.get_text(" ", strip=True))

    # Görünür metinden de spec çıkar
    gorunen_specs = metinden_spec_cek(soup)
    for k, v in gorunen_specs.items():
        specs.setdefault(k, v)

    # JSON-LD'den bazı alanları da ekle
    if isinstance(main, dict):
        if main.get("yearBuilt"):
            specs.setdefault("Bina Yaşı", str(main["yearBuilt"]))
        if main.get("numberOfFullBathrooms"):
            specs.setdefault("Banyo Sayısı", str(main["numberOfFullBathrooms"]))
        if main.get("numberOfRooms"):
            specs.setdefault("Oda Sayısı", str(main["numberOfRooms"]))
        if isinstance(main.get("floorSize"), dict):
            specs.setdefault("m² (Brüt)", str(main["floorSize"].get("value", 0)))

    def s(key, *alt_keys):
        for k in (key, *alt_keys):
            v = specs.get(k)
            if v:
                return metin_norm(v)
        return "Bilinmiyor"

    bina_yasi_raw     = s("Bina Yaşı", "İnşaat Yılı")
    bulundugu_kat_raw = s("Bulunduğu Kat", "Kat")
    isitma_tip_raw    = s("Isınma Tipi", "Isıtma", "Isınma")
    yakit_raw         = s("Yakıt Tipi", "Yakıt")
    isitma_raw        = isitma_birlestir(isitma_tip_raw, yakit_raw)
    mutfak_raw        = s("Mutfak")

    # Yıl geldiyse yaşa çevir
    if bina_yasi_raw.isdigit() and int(bina_yasi_raw) > 1900:
        yil_sayisal = datetime.now().year - int(bina_yasi_raw)
        bina_yasi_raw = f"{yil_sayisal} Yıl"

    # Brüt/Net m²
    brut_str = s("Brüt / Net M2", "m² (Brüt)", "Brüt M2", "Metrekare")
    metrekare_brut, metrekare_net = m2_coz(brut_str)
    if metrekare_brut == 0:
        metrekare_brut = sayi_cikar(brut_str)
    if metrekare_net == 0:
        metrekare_net = metrekare_brut

    oda_raw = s("Oda Sayısı", "Oda")

    # ── 6. Özellik matrisi ─────────────────────────────────
    secili_ozellikler = []
    gorulen = set()

    if isinstance(main, dict) and isinstance(main.get("amenityFeature"), list):
        for feat in main["amenityFeature"]:
            if not isinstance(feat, dict):
                continue
            deger = feat.get("value")
            if deger in [True, "true", "True", 1, "1"]:
                ad = ozellik_metni_temizle(feat.get("name", ""))
                if ad and ad not in gorulen:
                    secili_ozellikler.append(ad)
                    gorulen.add(ad)

    for oz in bolum_ozelliklerini_cek(soup):
        if oz not in gorulen:
            secili_ozellikler.append(oz)
            gorulen.add(oz)

    matris = ozellik_matris_olustur(secili_ozellikler)

    cephe_raw = s("Cephe", "Konum")
    matris = cephe_isle(cephe_raw, matris)

    emlak_tipi = "Satılık" if "satilik" in url.lower() else "Kiralık"

    sayfa_metni_alt = soup.get_text(" ", strip=True).lower()
    asansor_var = any("asansör" in o.lower() for o in secili_ozellikler) or ("asansör" in sayfa_metni_alt)
    otopark_var = any("otopark" in o.lower() for o in secili_ozellikler) or any(k in sayfa_metni_alt for k in ["otopark", "garaj", "kapalı garaj", "açık garaj"])
    esyali_var = s("Eşya Durumu", "Eşyalı").lower() not in ["eşyalı değil", "bilinmiyor", "hayır"]
    balkon_var = any("balkon" in o.lower() for o in secili_ozellikler) or ("balkon" in sayfa_metni_alt)

    banyo_sayisi = sayi_cikar(s("Banyo Sayısı"))
    if banyo_sayisi == 0 and isinstance(main, dict):
        banyo_sayisi = float(main.get("numberOfFullBathrooms", 0) or 0)

    temel = {
        "ilan_id": ilan_id,
        "il": il,
        "ilce": ilce,
        "mahalle": mahalle,
        "emlak_tipi": emlak_tipi,
        "fiyat_tl": float(fiyat),
        "bina_yasi_raw": bina_yasi_raw,
        "bulundugu_kat_raw": bulundugu_kat_raw,
        "isitma_raw": isitma_raw,
        "isitma_ana_sinif": isitma_sinif(isitma_raw),
        "mutfak_raw": mutfak_raw,
        "metrekare_brut": metrekare_brut,
        "metrekare_net": metrekare_net,
        "oda_sayisi": oda_hesapla(oda_raw),
        "bina_yasi_numeric": yas_numeric(bina_yasi_raw),
        "bina_yasi_ordinal": yas_ordinal(bina_yasi_raw),
        "bulundugu_kat_no": kat_no(bulundugu_kat_raw),
        "bulundugu_kat_ordinal": kat_ordinal(bulundugu_kat_raw),
        "kat_sayisi": sayi_cikar(s("Kat Sayısı", "Toplam Kat")),
        "isitma_score": isitma_score(isitma_raw),
        "banyo_sayisi": banyo_sayisi,
        "mutfak_acik_mi": 1.0 if "açık" in mutfak_raw.lower() else 0.0,
        "balkon": 1.0 if balkon_var else 0.0,
        "asansor": 1.0 if asansor_var else 0.0,
        "otopark": 1.0 if otopark_var else 0.0,
        "esyali": 1.0 if esyali_var else 0.0,
        "fotograf_klasoru": f"hepsi_{ilan_id}",
    }

    return {**temel, **matris}



# ═══════════════════════════════════════════════
#  FOTOĞRAF İNDİRME
# ═══════════════════════════════════════════════
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Referer":         "https://www.hepsiemlak.com/",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def foto_indir(jld_bloklari: list, soup, klasor: str) -> int:
    """JSON-LD bloklarından ve HTML'den fotoğraf URL'lerini topla, indir."""
    foto_urls = []

    def ekle(url):
        if isinstance(url, str) and url and url not in foto_urls:
            foto_urls.append(url)

    for blok in jld_bloklari or []:
        if not isinstance(blok, dict):
            continue

        for kaynak in [blok, blok.get("mainEntity") if isinstance(blok.get("mainEntity"), dict) else None]:
            if not isinstance(kaynak, dict):
                continue
            fotolar = kaynak.get("photo") or kaynak.get("image") or []
            if isinstance(fotolar, dict):
                fotolar = [fotolar]
            elif isinstance(fotolar, str):
                fotolar = [fotolar]
            for foto in fotolar:
                if isinstance(foto, dict):
                    ekle(foto.get("contentUrl") or foto.get("url"))
                else:
                    ekle(foto)

        graph = blok.get("@graph")
        if isinstance(graph, list):
            for oge in graph:
                if not isinstance(oge, dict):
                    continue
                for alan in ["image", "photo"]:
                    veri = oge.get(alan) or []
                    if isinstance(veri, str):
                        veri = [veri]
                    elif isinstance(veri, dict):
                        veri = [veri]
                    for foto in veri:
                        if isinstance(foto, dict):
                            ekle(foto.get("contentUrl") or foto.get("url"))
                        else:
                            ekle(foto)

    if len(foto_urls) < 3:
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original", "")
            if src and ("hepsiemlak" in src or "hemlak.com" in src):
                ekle(src)

    sayac = 0
    for url in foto_urls[:MAX_FOTO]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if len(r.content) < 5000:
                continue
            yol = os.path.join(klasor, f"foto_{sayac+1}.jpg")
            with open(yol, "wb") as f:
                f.write(r.content)
            sayac += 1
            time.sleep(random.uniform(*FOTO_BEKLE))
        except Exception:
            continue
    return sayac


# ═══════════════════════════════════════════════
#  CSV KAYIT
# ═══════════════════════════════════════════════
def csv_kaydet(sozluk: dict):
    sehir = sozluk.get("il", "Bilinmiyor").replace(" ", "_").capitalize()
    tip   = sozluk.get("emlak_tipi", "Bilinmiyor")

    # Ayrı klasör: Satılık_Hepsi / Kiralık_Hepsi
    kategori = os.path.join(ANA_KLASOR, f"{tip}_Hepsi")
    os.makedirs(kategori, exist_ok=True)
    csv_yolu = os.path.join(kategori, f"{sehir}.csv")

    dosya_var = os.path.exists(csv_yolu)
    if not dosya_var:
        log(f"  📁 Yeni CSV: {tip}_Hepsi/{sehir}.csv")

    pd.DataFrame([sozluk]).to_csv(
        csv_yolu,
        mode="a" if dosya_var else "w",
        header=not dosya_var,
        index=False,
        encoding="utf-8-sig"
    )


# ═══════════════════════════════════════════════
#  ANA KAZIMA DÖNGÜSÜ
# ═══════════════════════════════════════════════
def ilanlar_isle(driver, linkler: list, cekilen: set):
    basarili = hatali = atlanan = 0

    for idx, link in enumerate(linkler):
        ilan_id = ilan_id_cek(link)

        if ilan_id in cekilen:
            log(f"⏩ [{idx+1}/{len(linkler)}] #{ilan_id} daha önce çekilmiş.")
            continue

        foto_kl = os.path.join(FOTO_KLASOR, f"hepsi_{ilan_id}")
        if os.path.exists(foto_kl) and len(os.listdir(foto_kl)) > 0:
            log(f"⏩ [{idx+1}/{len(linkler)}] #{ilan_id} fotoğraflar mevcut.")
            cekilen.add(ilan_id)
            durum_kaydet(cekilen)
            continue

        if idx > 0 and idx % KAHVE_ADET == 0:
            sure = random.uniform(*UZUN_BEKLE)
            log(f"☕ Kahve molası: {sure:.0f} sn ({idx}/{len(linkler)})")
            time.sleep(sure)

        log(f"\n[{idx+1}/{len(linkler)}] → {link}")

        try:
            driver.execute_script(f"window.location.href = '{link}';")
            time.sleep(random.uniform(2.5, 4.5))

            # Sayfa yüklenme bekle
            try:
                WebDriverWait(driver, 12).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                pass

            # Cloudflare
            cf_bekle(driver)

            # İnsansı kaydırma
            kaydir(driver, oran=random.uniform(0.75, 0.88))

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Tekrar CF kontrolü
            cf_bekle(driver)
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # JSON-LD bloklarını al
            jld = json_ld_cek(soup)

            # İlanı parse et
            sonuc = None
            for _ in range(2):  # 2 deneme
                sonuc = ilan_parse_et(soup, link, ilan_id)
                if sonuc:
                    break
                log("  ⚠️ Veri eksik, sayfa yenileniyor...")
                driver.execute_script("location.reload();")
                time.sleep(random.uniform(3, 5))
                cf_bekle(driver)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                jld  = json_ld_cek(soup)

            if not sonuc:
                atlanan += 1
                log(f"⏭️  #{ilan_id} atlandı (veri alınamadı).")
                time.sleep(random.uniform(8, 15))
                continue

            # Fotoğraflar
            os.makedirs(foto_kl, exist_ok=True)
            foto_sayisi = foto_indir(jld, soup, foto_kl)

            # CSV kaydet
            csv_kaydet(sonuc)

            cekilen.add(ilan_id)
            durum_kaydet(cekilen)
            basarili += 1

            log(
                f"✅ #{ilan_id} | "
                f"{int(sonuc['fiyat_tl']):,} TL | "
                f"{sonuc['metrekare_brut']}m² | "
                f"Foto: {foto_sayisi} | "
                f"{sonuc['il']}/{sonuc['ilce']}"
            )

            bekle = random.uniform(*KISA_BEKLE) + random.gauss(0, 1.5)
            bekle = max(bekle, 5.0)
            log(f"  💤 {bekle:.1f} sn...")
            time.sleep(bekle)

        except KeyboardInterrupt:
            log("Ctrl+C ile durduruldu.")
            raise
        except WebDriverException as e:
            hatali += 1
            log(f"❌ WebDriver: {str(e)[:100]}")
            time.sleep(random.uniform(10, 20))
        except Exception as e:
            hatali += 1
            log(f"❌ Hata: {str(e)[:100]}")

    return basarili, hatali, atlanan


# ═══════════════════════════════════════════════
#  ANA PROGRAM
# ═══════════════════════════════════════════════
def main():
    print("=" * 68)
    print("  KAÇA GİDER — Hepsiemlak Scraper")
    print("  (Sahibinden CSV formatıyla uyumlu, AYRI klasöre kaydeder)")
    print("=" * 68)
    print()
    print("📋 KULLANIM:")
    print('  Chrome\'u debug modda açın:')
    print('  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^')
    print('    --remote-debugging-port=9222 --user-data-dir="C:\\chrome_scraper"')
    print()
    print("  hepsiemlak.com'a gidin → istediğiniz arama → ilan listesini görün.")
    print()
    print(f"  ⚙️  Max ilan: {MAX_ILAN} | Kahve molası: her {KAHVE_ADET} ilanda")
    print(f"  📂 Çıktı: emlak_veri_seti/Satılık_Hepsi/ (mevcut veriye dokunmaz)")
    print()

    cekilen = durum_yukle()
    if cekilen:
        print(f"  📂 Hafızada {len(cekilen)} ilan.")
        print()

    input("  >>> Chrome hazır, hepsiemlak açık mı? ENTER: ")
    print()

    try:
        driver = chrome_baglan()
    except WebDriverException:
        return

    log(f"Aktif sayfa: {driver.title}")
    log(f"URL: {driver.current_url}")

    if "hepsiemlak" not in driver.current_url.lower():
        print("  ⚠️  hepsiemlak.com açık değil gibi görünüyor.")
        input("  Lütfen açıp ENTER'a basın: ")

    cf_bekle(driver)

    print()
    linkler = linkleri_topla(driver)

    if not linkler:
        print("❌ Hiç ilan linki toplanamadı.")
        print("  Hepsiemlak'ta ilan listesi sayfasında mısınız?")
        return

    print()
    print(f"  ✅ {len(linkler)} ilan bulundu. Detaylar çekiliyor...")
    print()

    try:
        basarili, hatali, atlanan = ilanlar_isle(driver, linkler, cekilen)
    except KeyboardInterrupt:
        print()
        print("  ⚠️  Durduruldu. İlerleme kaydedildi.")
        return

    print()
    print("=" * 68)
    print(f"  🎉 Tamamlandı!")
    print(f"     ✅ Başarılı : {basarili}")
    print(f"     ❌ Hatalı   : {hatali}")
    print(f"     ⏭️  Atlanan  : {atlanan}")
    print(f"     📂 Veriler  : {os.path.abspath(ANA_KLASOR)}")
    print("=" * 68)


if __name__ == "__main__":
    main()
