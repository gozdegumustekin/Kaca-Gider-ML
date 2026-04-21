"""
Kaça Gider - Sahibinden.com Gelişmiş Stealth Scraper (FINAL v2)
================================================================
FIX: Türkçe Cloudflare "Basılı Tut" doğrulaması artık tespit ediliyor.
     Boş/eksik veriler CSV'ye yazılmıyor, retry mekanizması var.

KULLANIM: Bir önceki sürümle aynı.
  1. Chrome'u debug modda açın (port 9222)
  2. sahibinden.com'a gidin, Cloudflare'i geçin
  3. İstediğiniz aramayı ayarlayın
  4. python scraper.py çalıştırın → ENTER
"""

import os
import time
import json
import random
import re
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
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)

try:
    from ayarlar import TUM_OZELLIKLER, TUM_SUTUNLAR
except ImportError:
    TUM_OZELLIKLER = []
    TUM_SUTUNLAR   = None


# ═══════════════════════════════════════════════
#  GENEL AYARLAR
# ═══════════════════════════════════════════════
DEBUG_PORT    = "127.0.0.1:9222"

ANA_KLASOR    = "emlak_veri_seti"
FOTO_KLASOR   = os.path.join(ANA_KLASOR, "fotograflar")
LOG_DOSYASI   = os.path.join(ANA_KLASOR, "scraper_log.json")
DURUM_DOSYASI = os.path.join(ANA_KLASOR, "cekilen_ilanlar.json")

MAX_ILAN_SAYISI    = 200
MAX_FOTO_SAYISI    = 10
KAHVE_MOLASI_ADET  = 15
KISA_BEKLEME       = (6, 12)      # Artırıldı: Cloudflare'i çok tetiklememek için
UZUN_BEKLEME       = (60, 150)    # Artırıldı
FOTO_BEKLEME       = (0.3, 0.8)
MAX_RETRY          = 2            # Başarısız ilan için deneme sayısı

os.makedirs(FOTO_KLASOR, exist_ok=True)


# ═══════════════════════════════════════════════
#  DURUM KAYDI
# ═══════════════════════════════════════════════
def durum_yukle() -> set:
    if os.path.exists(DURUM_DOSYASI):
        try:
            with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                icerik = f.read().strip()
                if not icerik:
                    return set()
                return set(json.loads(icerik))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  ⚠️  Durum dosyası bozuk ({e}). Sıfırdan başlanıyor.")
            # Bozuk dosyayı yedekle
            try:
                os.rename(DURUM_DOSYASI, DURUM_DOSYASI + ".bozuk")
            except Exception:
                pass
            return set()
    return set()

def durum_kaydet(cekilen_idler: set):
    with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(list(cekilen_idler), f, ensure_ascii=False, indent=2)

def log_kaydet(mesaj: str):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        f.write(satir + "\n")


# ═══════════════════════════════════════════════
#  DEBUG CHROME'A BAĞLAN
# ═══════════════════════════════════════════════
def tarayiciya_baglan() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", DEBUG_PORT)
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except WebDriverException as e:
        print()
        print("❌ Chrome'a bağlanılamadı!")
        print(f"   Hata: {str(e)[:200]}")
        print()
        print("   Chrome şu komutla açılmış olmalı:")
        print('   "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^')
        print("     --remote-debugging-port=9222 ^")
        print('     --user-data-dir="C:\\scraper_profil"')
        print()
        raise
    log_kaydet(f"Chrome'a bağlanıldı. Sekme: {driver.title}")
    return driver


# ═══════════════════════════════════════════════
#  CLOUDFLARE TESPİTİ (YENİLENDİ - TÜRKÇE DESTEKLİ)
# ═══════════════════════════════════════════════
def cloudflare_var_mi(driver) -> bool:
    """
    Sayfa bir Cloudflare/DDoS doğrulama ekranı mı kontrol eder.
    Hem Türkçe hem İngilizce işaretler hem de içerik yokluğu kontrol edilir.
    """
    try:
        source = driver.page_source.lower()
        title  = driver.title.lower()
        url    = driver.current_url.lower()
    except Exception:
        return False

    # 1) Türkçe Cloudflare/Sahibinden koruma ifadeleri
    turkce_isaretler = [
        "bağlantınız kontrol ediliyor",
        "basılı tut",
        "olağan dışı erişim",
        "olagan dışı erişim",
        "referans kimliği",
        "devam edebilmek için",
        "lütfen aşağıdaki",
        "lütfen tekrar deneyin",
        "robot olmadığınızı",
        "doğrulama gerekli",
    ]
    # 2) İngilizce Cloudflare ifadeleri
    ingilizce_isaretler = [
        "checking your browser",
        "cf-browser-verification",
        "cf-challenge",
        "just a moment",
        "attention required",
        "press and hold",
        "turnstile",
        "ray id:",
    ]
    # 3) Tab başlığı işaretleri
    baslik_isaretler = [
        "olağan dışı",
        "olagan disi",
        "just a moment",
        "attention required",
        "bir dakika",
    ]

    for s in turkce_isaretler + ingilizce_isaretler:
        if s in source:
            return True
    for s in baslik_isaretler:
        if s in title:
            return True
    # Bazı durumlarda URL challenge sayfasına yönlenir
    if "challenge" in url or "__cf_chl" in url:
        return True

    return False


def cloudflare_bekle(driver, mesaj_ek: str = ""):
    """Cloudflare tespit edilene kadar kullanıcıyı bekler (döngüsel)."""
    deneme = 0
    while cloudflare_var_mi(driver):
        deneme += 1
        print()
        log_kaydet("⚠️  CLOUDFLARE 'BASILI TUT' DOĞRULAMASI TESPİT EDİLDİ")
        if mesaj_ek:
            print(f"    {mesaj_ek}")
        print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  1. Chrome penceresine geçin")
        print("  2. 'Basılı Tut' butonuna basın ve ~5-10 saniye BIRAKMADAN TUTUN")
        print("  3. Sayfa ilan sayfasına dönene kadar bekleyin")
        print("  4. Buraya dönüp ENTER'a basın")
        if deneme >= 3:
            print("  💡 İpucu: Çok sık tekrar ediyorsa Chrome'u yeniden başlatıp")
            print("     script'i yeniden çalıştırın. Ara ara uzun mola verin.")
        print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        input("  >>> Doğrulamayı geçtikten sonra ENTER: ")
        time.sleep(3)

        # Hâlâ varsa sayfayı yenilemeyi dene
        if cloudflare_var_mi(driver) and deneme < 5:
            log_kaydet("Sayfa yenileniyor...")
            try:
                driver.refresh()
                time.sleep(random.uniform(3, 6))
            except Exception:
                pass

        if deneme >= 5:
            log_kaydet("❌ Cloudflare 5 denemede geçilemedi. Bu ilan atlanıyor.")
            return False
    return True


# ═══════════════════════════════════════════════
#  İNSANSI HAREKET
# ═══════════════════════════════════════════════
def insansi_mouse_hareket(driver):
    try:
        actions = ActionChains(driver)
        actions.move_by_offset(random.randint(-80, 80), random.randint(-40, 40))
        actions.perform()
        time.sleep(random.uniform(0.1, 0.3))
    except Exception:
        pass

def insansi_kaydir(driver, hedef_oran: float = 0.85):
    sayfa_h = driver.execute_script("return document.body.scrollHeight")
    hedef   = int(sayfa_h * hedef_oran)
    konum   = driver.execute_script("return window.pageYOffset")
    while konum < hedef:
        adim = random.randint(180, 450)
        konum = min(konum + adim, hedef)
        driver.execute_script(f"window.scrollTo(0, {konum});")
        time.sleep(random.uniform(0.15, 0.55))
        if random.random() < 0.20:
            geri = random.randint(60, 200)
            konum = max(konum - geri, 0)
            driver.execute_script(f"window.scrollTo(0, {konum});")
            time.sleep(random.uniform(0.3, 0.8))
        if random.random() < 0.08:
            insansi_mouse_hareket(driver)
    if random.random() < 0.6:
        yukari = random.randint(150, 400)
        driver.execute_script(f"window.scrollTo(0, {konum - yukari});")
        time.sleep(random.uniform(0.8, 2.0))

def arama_sayfasi_kaydir(driver):
    sayfa_h = driver.execute_script("return document.body.scrollHeight")
    konum   = 0
    while konum < sayfa_h:
        adim = random.randint(350, 700)
        konum += adim
        driver.execute_script(f"window.scrollTo(0, {konum});")
        time.sleep(random.uniform(0.12, 0.45))
        sayfa_h = driver.execute_script("return document.body.scrollHeight")
        if random.random() < 0.05:
            insansi_mouse_hareket(driver)
    time.sleep(random.uniform(0.8, 1.5))


# ═══════════════════════════════════════════════
#  SAYFA BEKLEMELERİ
# ═══════════════════════════════════════════════
def sayfa_yuklenene_kadar_bekle(driver, timeout: int = 15):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass

def ilan_sayfa_bekle(driver, timeout: int = 12):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "classified-price-wrapper"))
        )
        return True
    except TimeoutException:
        return False


# ═══════════════════════════════════════════════
#  İLAN LİNKLERİNİ TOPLAMA
# ═══════════════════════════════════════════════
def linkleri_topla(driver) -> list:
    toplanan = []
    sayfa_no = 1

    while len(toplanan) < MAX_ILAN_SAYISI:
        log_kaydet(f"Sayfa {sayfa_no} taranıyor...")

        if cloudflare_var_mi(driver):
            cloudflare_bekle(driver, "Arama sayfası için doğrulama gerekli.")

        arama_sayfasi_kaydir(driver)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        ilan_kutulari = soup.find_all("a", class_="classifiedTitle")
        if not ilan_kutulari:
            log_kaydet("Bu sayfada ilan bulunamadı, tarama durduruluyor.")
            break

        yeni_sayisi = 0
        for kutu in ilan_kutulari:
            href = kutu.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.sahibinden.com{href}"
            if href and href not in toplanan:
                toplanan.append(href)
                yeni_sayisi += 1

        log_kaydet(f"  Sayfa {sayfa_no}: {len(ilan_kutulari)} ilan ({yeni_sayisi} yeni). Toplam: {len(toplanan)}")

        sonraki = soup.find("a", {"title": "Sonraki"}) or soup.find("a", {"rel": "next"})
        if not sonraki or len(toplanan) >= MAX_ILAN_SAYISI:
            break

        sonraki_url = sonraki.get("href", "")
        if sonraki_url and not sonraki_url.startswith("http"):
            sonraki_url = f"https://www.sahibinden.com{sonraki_url}"

        log_kaydet(f"  Sonraki sayfaya geçiliyor...")
        driver.execute_script(f"window.location.href = '{sonraki_url}';")
        sayfa_no += 1
        time.sleep(random.uniform(4, 8))
        sayfa_yuklenene_kadar_bekle(driver)

    random.shuffle(toplanan)
    toplanan = toplanan[:MAX_ILAN_SAYISI]
    log_kaydet(f"Toplam {len(toplanan)} ilan linki toplandı.")
    return toplanan


# ═══════════════════════════════════════════════
#  VERİ ÇIKARMA YARDIMCILARI
# ═══════════════════════════════════════════════
def sayi_cikar(metin) -> float:
    if not isinstance(metin, str):
        return 0.0
    rakamlar = re.findall(r"-?\d+", metin)
    return float(rakamlar[0]) if rakamlar else 0.0

def temiz_metin(metin, default="Bilinmiyor") -> str:
    if metin is None:
        return default
    metin = str(metin).strip()
    return metin if metin else default

def oda_hesapla(metin) -> float:
    if not isinstance(metin, str):
        return 0.0
    r = re.findall(r"\d+", metin)
    return sum(float(x) for x in r) if r else 1.0

def yas_hesapla_ordinal(metin) -> float:
    metin = str(metin).lower().strip()
    if "sıfır" in metin or metin == "0":         return 5.0
    elif "0-5"  in metin:                         return 4.0
    elif "6-10" in metin:                         return 3.0
    elif "11-15" in metin or "11-25" in metin:    return 2.0
    elif "26" in metin or "üzeri" in metin:       return 1.0
    s = sayi_cikar(metin)
    if s == 0:    return 0.0
    elif s <= 5:  return 4.0
    elif s <= 10: return 3.0
    elif s <= 25: return 2.0
    else:         return 1.0

def yas_hesapla_numeric(metin) -> float:
    metin = str(metin).lower().strip()
    if "sıfır" in metin or metin == "0":         return 0.0
    elif "0-5"  in metin:                         return 3.0
    elif "6-10" in metin:                         return 8.0
    elif "11-15" in metin:                        return 13.0
    elif "11-25" in metin:                        return 18.0
    elif "26" in metin or "üzeri" in metin:       return 30.0
    return sayi_cikar(metin)

def kat_no_hesapla(metin) -> float:
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

def kat_ordinal(metin) -> float:
    metin = str(metin).lower().strip()
    if "bodrum" in metin or "kot" in metin or "giriş altı" in metin: return 1.0
    if "çatı" in metin:   return 2.0
    if "bahçe" in metin:  return 4.0
    if "yüksek giriş" in metin: return 4.0
    if "müstakil" in metin or "villa" in metin: return 5.0
    if "giriş" in metin or "zemin" in metin: return 3.0
    k = sayi_cikar(metin)
    if 1 <= k <= 5:     return 5.0
    elif 6 <= k <= 10:  return 4.0
    elif 11 <= k <= 20: return 3.0
    elif k >= 21:       return 2.0
    return 0.0

def boolean_cevir(metin) -> float:
    metin = str(metin).lower()
    return 1.0 if any(k in metin for k in ["var", "evet", "açık", "kapalı"]) else 0.0

def isitma_puani(metin) -> float:
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

def isitma_sinif(metin) -> str:
    metin = str(metin).lower().strip()
    eslesme = [
        ("yerden",        "Yerden Isitma"),
        ("merkezi",       "Merkezi"),
        ("kombi",         "Kombi Dogalgaz" if "doğalgaz" in metin else "Kombi Elektrik"),
        ("kat kaloriferi","Kat Kaloriferi"),
        ("vrv",           "VRV"),
        ("fancoil",       "Fancoil"),
        ("ısı pompası",   "Isi Pompasi"),
        ("jeotermal",     "Jeotermal"),
        ("doğalgaz sobası","Dogalgaz Sobasi"),
        ("soba",          "Soba"),
        ("klima",         "Klima"),
        ("şömine",        "Somine"),
        ("güneş enerjisi","Gunes Enerjisi"),
    ]
    for a, d in eslesme:
        if a in metin:
            return d
    if metin == "yok":
        return "Yok"
    return temiz_metin(metin)


def sayfa_parsla(soup, link: str, ilan_id: str) -> tuple:
    """
    Sayfa soup'unu parse eder ve (temel_dict, fiyat, ozellikler_dict) döner.
    Eğer zorunlu alanlar (fiyat, lokasyon) bulunamazsa None döner.
    """
    # Fiyat
    fiyat_kutusu = soup.find("span", class_="classified-price-wrapper")
    if not fiyat_kutusu:
        return None
    try:
        ham = fiyat_kutusu.text.strip()
        temiz_fiyat = int(re.sub(r"[^\d]", "", ham.replace(" TL", "")) or 0)
    except Exception:
        return None

    if temiz_fiyat == 0:
        return None

    # Lokasyon
    il, ilce, mahalle = "Bilinmiyor", "Bilinmiyor", "Bilinmiyor"
    lok = soup.find("div", class_="classifiedInfo")
    if lok and lok.find("h2"):
        parcalar = [p.strip() for p in lok.find("h2").text.replace("\n","").strip().split("/")]
        il      = parcalar[0] if len(parcalar) > 0 else "Bilinmiyor"
        ilce    = parcalar[1] if len(parcalar) > 1 else "Bilinmiyor"
        mahalle = parcalar[2] if len(parcalar) > 2 else "Bilinmiyor"

    if il == "Bilinmiyor":
        return None

    # Özellikler
    ozellikler = {}
    oz_listesi = soup.find("ul", class_="classifiedInfoList")
    if oz_listesi:
        for li in oz_listesi.find_all("li"):
            baslik = li.find("strong")
            deger  = li.find("span")
            if baslik and deger:
                ozellikler[baslik.text.strip()] = deger.text.strip()

    emlak_tipi = "Satılık" if "satilik" in link.lower() else "Kiralık"
    mutfak_raw        = temiz_metin(ozellikler.get("Mutfak"))
    bina_yasi_raw     = temiz_metin(ozellikler.get("Bina Yaşı"))
    bulundugu_kat_raw = temiz_metin(ozellikler.get("Bulunduğu Kat"))
    isitma_raw        = temiz_metin(ozellikler.get("Isıtma"))

    temel = {
        "ilan_id":              str(ilan_id),
        "link":                 link,
        "tarih":                datetime.now().strftime("%Y-%m-%d %H:%M"),
        "il":                   il,
        "ilce":                 ilce,
        "mahalle":              mahalle,
        "emlak_tipi":           emlak_tipi,
        "fiyat_tl":             float(temiz_fiyat),
        "bina_yasi_raw":        bina_yasi_raw,
        "bulundugu_kat_raw":    bulundugu_kat_raw,
        "isitma_raw":           isitma_raw,
        "isitma_ana_sinif":     isitma_sinif(isitma_raw),
        "mutfak_raw":           mutfak_raw,
        "metrekare_brut":       sayi_cikar(ozellikler.get("m² (Brüt)", "0")),
        "metrekare_net":        sayi_cikar(ozellikler.get("m² (Net)", "0")),
        "oda_sayisi":           oda_hesapla(ozellikler.get("Oda Sayısı", "0")),
        "bina_yasi_numeric":    yas_hesapla_numeric(bina_yasi_raw),
        "bina_yasi_ordinal":    yas_hesapla_ordinal(bina_yasi_raw),
        "bulundugu_kat_no":     kat_no_hesapla(bulundugu_kat_raw),
        "bulundugu_kat_ordinal":kat_ordinal(bulundugu_kat_raw),
        "kat_sayisi":           sayi_cikar(ozellikler.get("Kat Sayısı", "0")),
        "isitma_score":         isitma_puani(isitma_raw),
        "banyo_sayisi":         sayi_cikar(ozellikler.get("Banyo Sayısı", "0")),
        "mutfak_acik_mi":       1.0 if "açık" in mutfak_raw.lower() else 0.0,
        "balkon":               boolean_cevir(ozellikler.get("Balkon", "0")),
        "asansor":              boolean_cevir(ozellikler.get("Asansör", "0")),
        "otopark":              boolean_cevir(ozellikler.get("Otopark", "0")),
        "esyali":               boolean_cevir(ozellikler.get("Eşyalı", "0")),
        "fotograf_klasoru":     f"ilan_{ilan_id}",
    }
    return temel, soup


# ═══════════════════════════════════════════════
#  FOTOĞRAF İNDİRME
# ═══════════════════════════════════════════════
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.sahibinden.com/",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def fotograflari_indir(soup, klasor: str) -> int:
    sayac = 0
    for img in soup.find_all("img"):
        if sayac >= MAX_FOTO_SAYISI:
            break
        foto_url = img.get("data-src") or img.get("src", "")
        if not (foto_url and str(foto_url).startswith("http")):
            continue
        kucuk = foto_url.lower()
        if not any(x in kucuk for x in ["jpg", "jpeg", "webp"]):
            continue
        if "thmb" in kucuk or "logo" in kucuk or "icon" in kucuk:
            continue
        try:
            veri = requests.get(foto_url, headers=HEADERS, timeout=12).content
            if len(veri) < 5000:
                continue
            with open(os.path.join(klasor, f"foto_{sayac+1}.jpg"), "wb") as f:
                f.write(veri)
            sayac += 1
            time.sleep(random.uniform(*FOTO_BEKLEME))
        except Exception:
            continue
    return sayac


# ═══════════════════════════════════════════════
#  CSV KAYIT
# ═══════════════════════════════════════════════
def csv_kaydet(sozluk: dict):
    sehir = sozluk.get("il", "Bilinmiyor").replace(" ", "_").capitalize()
    tip   = sozluk.get("emlak_tipi", "Bilinmiyor")

    kategori_klasoru = os.path.join(ANA_KLASOR, tip)
    os.makedirs(kategori_klasoru, exist_ok=True)
    csv_yolu = os.path.join(kategori_klasoru, f"{sehir}.csv")

    dosya_var = os.path.exists(csv_yolu)
    if not dosya_var:
        log_kaydet(f"  📁 Yeni CSV oluşturuldu: {tip}/{sehir}.csv")

    pd.DataFrame([sozluk]).to_csv(
        csv_yolu,
        mode="a" if dosya_var else "w",
        header=not dosya_var,
        index=False,
        encoding="utf-8-sig"
    )


# ═══════════════════════════════════════════════
#  TEK İLAN İŞLEME (retry destekli)
# ═══════════════════════════════════════════════
def tek_ilan_cek(driver, link: str, ilan_id: str) -> dict | None:
    """
    Bir ilanı çeker, doğrularsa sözlük döner, aksi halde None.
    Cloudflare ve eksik veri durumlarını ele alır.
    """
    for deneme in range(MAX_RETRY + 1):
        if deneme > 0:
            log_kaydet(f"  🔄 Deneme {deneme+1}/{MAX_RETRY+1}: sayfa yenileniyor...")
            try:
                driver.execute_script("location.reload();")
            except Exception:
                driver.execute_script(f"window.location.href = '{link}';")
            time.sleep(random.uniform(4, 8))

        sayfa_yuklenene_kadar_bekle(driver)

        # 1) Cloudflare kontrolü
        if cloudflare_var_mi(driver):
            if not cloudflare_bekle(driver, f"İlan #{ilan_id} için doğrulama gerekli."):
                return None

        # 2) İlan elementi yüklendi mi
        ilan_sayfa_bekle(driver, timeout=10)

        # 3) İnsansı kaydırma
        insansi_kaydir(driver, hedef_oran=random.uniform(0.75, 0.90))

        # 4) Sayfayı parse et
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Bir kez daha Cloudflare kontrol (ara ara görünür)
        if cloudflare_var_mi(driver):
            if not cloudflare_bekle(driver, f"İlan #{ilan_id} ara doğrulama."):
                return None
            soup = BeautifulSoup(driver.page_source, "html.parser")

        sonuc = sayfa_parsla(soup, link, ilan_id)
        if sonuc is None:
            log_kaydet(f"  ⚠️  Veri eksik/geçersiz (fiyat veya lokasyon bulunamadı).")
            continue   # Tekrar dene

        return sonuc   # (temel_dict, soup)

    return None


# ═══════════════════════════════════════════════
#  ANA KAZIMA DÖNGÜSÜ
# ═══════════════════════════════════════════════
def ilanlar_isle(driver, linkler: list, cekilen_idler: set):
    basarili = 0
    hatali   = 0
    atlanan  = 0

    for index, link in enumerate(linkler):
        m = re.search(r"-(\d+)(?:/detay)?$", link)
        ilan_id = m.group(1) if m else None

        if ilan_id and ilan_id in cekilen_idler:
            log_kaydet(f"⏩ [{index+1}/{len(linkler)}] #{ilan_id} daha önce çekilmiş.")
            continue

        if ilan_id:
            klasor = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id}")
            if os.path.exists(klasor) and len(os.listdir(klasor)) > 0:
                log_kaydet(f"⏩ [{index+1}/{len(linkler)}] #{ilan_id} fotoğraflar mevcut.")
                cekilen_idler.add(ilan_id)
                durum_kaydet(cekilen_idler)
                continue

        # Kahve molası
        if index > 0 and index % KAHVE_MOLASI_ADET == 0:
            sure = random.uniform(*UZUN_BEKLEME)
            log_kaydet(f"☕ Kahve molası: {sure:.0f} sn... ({index}/{len(linkler)})")
            time.sleep(sure)

        log_kaydet(f"\n[{index+1}/{len(linkler)}] Giriliyor: {link}")

        try:
            # driver.get() yerine JS ile navigasyon (CF fingerprint'ine takılmamak için)
            driver.execute_script(f"window.location.href = '{link}';")
            time.sleep(random.uniform(3.5, 5.5))

            if not ilan_id:
                m2 = re.search(r"-(\d+)(?:/detay)?$", driver.current_url)
                ilan_id = m2.group(1) if m2 else str(random.randint(100000, 999999))

            # Tek ilanı retry mekanizmasıyla çek
            sonuc = tek_ilan_cek(driver, link, ilan_id)

            if sonuc is None:
                atlanan += 1
                log_kaydet(f"⏭️  #{ilan_id} atlandı (veri çekilemedi).")
                # Yine de uzun bekle, sık sık hata bot sinyalidir
                time.sleep(random.uniform(10, 20))
                continue

            temel, soup = sonuc

            # Fotoğraflar
            foto_klasoru = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id}")
            os.makedirs(foto_klasoru, exist_ok=True)
            foto_sayisi = fotograflari_indir(soup, foto_klasoru)

            # İkili matris
            ek_kutu = soup.find("div", id="classifiedProperties")
            secili = []
            if ek_kutu:
                secili = [li.text.strip() for li in ek_kutu.find_all("li", class_="selected")]
            matris = {oz: (1 if oz in secili else 0) for oz in TUM_OZELLIKLER}

            nihai = {**temel, **matris}
            csv_kaydet(nihai)

            cekilen_idler.add(ilan_id)
            durum_kaydet(cekilen_idler)

            basarili += 1
            log_kaydet(
                f"✅ #{ilan_id} | "
                f"Fiyat: {int(temel['fiyat_tl']):,} TL | "
                f"Foto: {foto_sayisi} | "
                f"{temel['il']}/{temel['ilce']}"
            )

            bekleme = random.uniform(*KISA_BEKLEME) + random.gauss(0, 1.5)
            bekleme = max(bekleme, 5.0)
            log_kaydet(f"  💤 {bekleme:.1f} sn bekleniyor...")
            time.sleep(bekleme)

        except KeyboardInterrupt:
            print()
            log_kaydet("Kullanıcı tarafından durduruldu (Ctrl+C).")
            raise
        except WebDriverException as e:
            hatali += 1
            log_kaydet(f"❌ WebDriver hatası: {str(e)[:120]}")
            time.sleep(random.uniform(10, 20))
            continue
        except Exception as e:
            hatali += 1
            log_kaydet(f"❌ Genel hata: {str(e)[:120]}")
            continue

    return basarili, hatali, atlanan


# ═══════════════════════════════════════════════
#  ANA PROGRAM
# ═══════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  KAÇA GİDER — Sahibinden.com Stealth Scraper v2 (CF-fix)")
    print("=" * 70)
    print()
    print("📋 KULLANIM:")
    print("  1. Tüm Chrome pencerelerini kapatın.")
    print("  2. Chrome'u debug modda açın:")
    print('     "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^')
    print('       --remote-debugging-port=9222 ^')
    print('       --user-data-dir="C:\\scraper_profil"')
    print("  3. sahibinden.com'a gidin, Cloudflare'i geçin.")
    print("  4. İstediğiniz aramayı yapın, ilan listesini görün.")
    print()
    print("⚠️  CLOUDFLARE 'BASILI TUT' ile karşılaşırsanız:")
    print("    Script size haber verecek, butona ~5-10 sn basılı tutun.")
    print()
    print(f"  ⚙️  Max ilan: {MAX_ILAN_SAYISI}  |  Her {KAHVE_MOLASI_ADET} ilanda mola")
    print(f"  ⚙️  İlan arası bekleme: {KISA_BEKLEME[0]}-{KISA_BEKLEME[1]} sn")
    print()

    cekilen_idler = durum_yukle()
    if cekilen_idler:
        print(f"  📂 Hafızada {len(cekilen_idler)} ilan (daha önce çekilmiş).")
        print()

    input("  >>> Chrome hazır, sahibinden.com açık mı? ENTER'a basın: ")
    print()

    try:
        driver = tarayiciya_baglan()
    except WebDriverException:
        return

    print()
    log_kaydet(f"Aktif sayfa: {driver.title}")
    log_kaydet(f"URL: {driver.current_url}")

    if "sahibinden" not in driver.current_url.lower():
        print()
        print("  ⚠️  Chrome'da sahibinden.com açık değil.")
        input("  Lütfen sayfayı açıp ENTER'a basın: ")

    if cloudflare_var_mi(driver):
        cloudflare_bekle(driver, "Başlangıç sayfası için doğrulama gerekli.")

    print()
    linkler = linkleri_topla(driver)
    if not linkler:
        print("❌ Hiç ilan linki toplanamadı.")
        return

    print()
    print(f"  ✅ {len(linkler)} ilan bulundu. Detaylar çekiliyor...")
    print()

    try:
        basarili, hatali, atlanan = ilanlar_isle(driver, linkler, cekilen_idler)
    except KeyboardInterrupt:
        print()
        print("  ⚠️  Kullanıcı durdurdu. Mevcut ilerleme kaydedildi.")
        return

    print()
    print("=" * 70)
    print(f"  🎉 Tarama tamamlandı!")
    print(f"     ✅ Başarılı : {basarili}")
    print(f"     ❌ Hatalı   : {hatali}")
    print(f"     ⏭️  Atlanan  : {atlanan}")
    print(f"     📂 Veriler  : {os.path.abspath(ANA_KLASOR)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
