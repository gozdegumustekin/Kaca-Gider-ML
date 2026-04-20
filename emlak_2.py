import os
import time
import requests
import random
import re
import pandas as pd
from bs4 import BeautifulSoup

# YENİ: Gizlilik kütüphanemizi ekliyoruz
import undetected_chromedriver as uc

# --- MERKEZİ AYARLARI ÇAĞIRALIM ---
from ayarlar import TUM_OZELLIKLER, TUM_SUTUNLAR

# 1. KLASÖR VE DOSYA YAPISINI KURMA
ANA_KLASOR = "emlak_veri_seti"
FOTO_KLASOR = os.path.join(ANA_KLASOR, "fotograflar")

if not os.path.exists(FOTO_KLASOR):
    os.makedirs(FOTO_KLASOR)

# 2. GÖRÜNMEZ (STEALTH) TARAYICIYI BAŞLATMA
print("Görünmez Chrome başlatılıyor... Arkanıza yaslanın.")
options = uc.ChromeOptions()
options.add_argument("--start-maximized") # Tarayıcıyı tam ekran açar

# Açık Chrome'a bağlanmak yerine yepyeni, iz bırakmayan bir tarayıcı oluşturuyoruz
driver = uc.Chrome(options=options)

# --- KAYDIRMA FONKSİYONLARI ---
def arama_sayfasi_kaydir(driver):
    """Arama sonuçlarındaki ilan linklerinin yüklenmesi için standart aşağı kaydırma"""
    sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    suanki_konum = 0
    while suanki_konum < sayfa_yuksekligi:
        kaydirma_miktari = random.randint(400, 800) 
        suanki_konum += kaydirma_miktari
        driver.execute_script(f"window.scrollTo(0, {suanki_konum});")
        time.sleep(random.uniform(0.1, 0.4))
        sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    time.sleep(1)

def gercekci_kaydir(driver):
    """İlan detay sayfasında insan gibi okuma ve geri yukarı çıkma taklidi (Yo-Yo)"""
    sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    suanki_konum = 0
    hedef_nokta = sayfa_yuksekligi * 0.8 # Sadece özelliklere kadar in (en dibe inme)
    
    while suanki_konum < hedef_nokta:
        kaydirma_miktari = random.randint(250, 500) 
        suanki_konum += kaydirma_miktari
        driver.execute_script(f"window.scrollTo(0, {suanki_konum});")
        time.sleep(random.uniform(0.3, 0.9)) # Özellikleri okuma molası
        
    # İnsanlar ilan okurken genelde biraz geri yukarı kaydırır
    geri_kaydirma = random.randint(300, 600)
    driver.execute_script(f"window.scrollTo(0, {suanki_konum - geri_kaydirma});")
    time.sleep(random.uniform(1.0, 2.5)) 

# LİNKLERİ OTOMATİK TOPLAYAN FONKSİYON
def linkleri_topla(driver, arama_sayfasi_url):
    toplanan_linkler = []
    print(f"\nHedef aranıyor: {arama_sayfasi_url}")
    driver.get(arama_sayfasi_url)

    # BURASI ÇOK ÖNEMLİ: Yeni tarayıcı açıldığında site sana CAPTCHA sorarsa, 
    # o ekranda elinle çöz, ilanları gördükten sonra buraya gelip ENTER'a bas.
    input("\nDİKKAT: Lütfen Chrome'a bakın. Arama sonuçları ekranını (ilanları) gördüyseniz ve CAPTCHA yoksa buraya gelip ENTER tuşuna basın...")

    print("--- Sayfadaki İlanlar Taranıyor ---")
    arama_sayfasi_kaydir(driver)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    ilan_kutulari = soup.find_all('a', class_='classifiedTitle')

    for kutu in ilan_kutulari:
        link_uzantisi = kutu.get('href')
        if link_uzantisi and not link_uzantisi.startswith("http"):
            tam_link = f"https://www.sahibinden.com{link_uzantisi}"
            toplanan_linkler.append(tam_link)

    print(f"Bulunan ham ilan link sayısı: {len(toplanan_linkler)}")

    baslangic_sayisi = len(toplanan_linkler)
    if baslangic_sayisi >= 15:
        gormezden_gelinecek = random.randint(0, 1)
        random.shuffle(toplanan_linkler)
        toplanan_linkler = toplanan_linkler[:baslangic_sayisi - gormezden_gelinecek]
        print(f"🛡️ Anti-Ban: {baslangic_sayisi} ilandan {gormezden_gelinecek} tanesi kasıtlı atlandı (İnsan Taklidi). {len(toplanan_linkler)} ilan alındı.")
    else:
        print(f"Bu sayfada {len(toplanan_linkler)} ilan linki bulundu.")

    return toplanan_linkler

# 3. STRATEJİ BELİRLEME
hedef_link = [
    # --- MERKEZ & BÜYÜK İLÇELER ---
    "https://www.sahibinden.com/satilik-mustakil-ev?pagingSize=50&address_town=594&address_town=595&address_town=596&address_town=592&address_town=593&address_city=43"
]

tum_ilan_linkleri = []
for arama_url in hedef_link:
    bulunanlar = linkleri_topla(driver, arama_url) 
    tum_ilan_linkleri.extend(bulunanlar)

tum_ilan_linkleri = list(set(tum_ilan_linkleri))

# --- YENİ ANTİ-BAN KORUMASI: LİNKLERİ KARIŞTIR VE SINIRLA ---
random.shuffle(tum_ilan_linkleri)
MAX_ILAN_SAYISI = 50 # Banlanmamak için çekilecek maksimum ilan sayısı
tum_ilan_linkleri = tum_ilan_linkleri[:MAX_ILAN_SAYISI]

print(f"\nToplam {len(tum_ilan_linkleri)} adet KARIŞIK ilan seçildi. Kazıma işlemi başlıyor!\n{'='*50}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def temel_verileri_sayisallastir(ozellikler, ilan_id, temiz_fiyat, link, soup):
    """Siteden gelen metinleri hem ham hem türetilmiş olarak döndürür."""

    il, ilce, mahalle = "Bilinmiyor", "Bilinmiyor", "Bilinmiyor"
    try:
        lokasyon_alani = soup.find('div', class_='classifiedInfo')
        if lokasyon_alani and lokasyon_alani.find('h2'):
            lokasyon_metni = lokasyon_alani.find('h2').text.replace('\n', '').strip()
            parcalar = [p.strip() for p in lokasyon_metni.split('/')]
            il = parcalar[0] if len(parcalar) > 0 else "Bilinmiyor"
            ilce = parcalar[1] if len(parcalar) > 1 else "Bilinmiyor"
            mahalle = parcalar[2] if len(parcalar) > 2 else "Bilinmiyor"
    except Exception:
        pass

    emlak_tipi = "Satılık" if "satilik" in link.lower() else "Kiralık"

    def temiz_metin(metin, default="Bilinmiyor"):
        if metin is None:
            return default
        metin = str(metin).strip()
        return metin if metin else default

    def sayi_cikar(metin):
        if not isinstance(metin, str):
            return 0.0
        rakamlar = re.findall(r'-?\d+', metin)
        return float(rakamlar[0]) if rakamlar else 0.0

    def oda_hesapla(metin):
        if not isinstance(metin, str):
            return 0.0
        rakamlar = re.findall(r'\d+', metin)
        return sum(float(r) for r in rakamlar) if rakamlar else 1.0

    def yas_hesapla_ordinal(metin):
        metin = str(metin).lower().strip()
        if "sıfır" in metin or metin == "0": return 5.0
        elif "0-5" in metin: return 4.0
        elif "6-10" in metin: return 3.0
        elif "11-15" in metin or "11-25" in metin: return 2.0
        elif "26" in metin or "üzeri" in metin: return 1.0

        sayi = sayi_cikar(metin)
        if sayi == 0: return 0.0
        elif sayi <= 5: return 4.0
        elif sayi <= 10: return 3.0
        elif sayi <= 25: return 2.0
        else: return 1.0

    def yas_hesapla_numeric(metin):
        metin = str(metin).lower().strip()
        if "sıfır" in metin or metin == "0": return 0.0
        elif "0-5" in metin: return 3.0
        elif "6-10" in metin: return 8.0
        elif "11-15" in metin: return 13.0
        elif "11-25" in metin: return 18.0
        elif "26" in metin or "üzeri" in metin: return 30.0
        return sayi_cikar(metin)

    def kat_hesapla_ordinal(metin):
        metin = str(metin).lower().strip()
        if "bodrum" in metin or "kot" in metin or "giriş altı" in metin: return 1.0
        if "çatı" in metin: return 2.0
        if "bahçe" in metin: return 4.0
        if "yüksek giriş" in metin: return 4.0
        if "müstakil" in metin or "villa" in metin: return 5.0
        if "giriş" in metin or "zemin" in metin: return 3.0

        kat_no = sayi_cikar(metin)
        if 1 <= kat_no <= 5: return 5.0
        elif 6 <= kat_no <= 10: return 4.0
        elif 11 <= kat_no <= 20: return 3.0
        elif kat_no >= 21: return 2.0
        return 0.0

    def kat_no_hesapla(metin):
        metin = str(metin).lower().strip()
        if "bodrum" in metin: return -1.0
        if "giriş altı" in metin or "kot" in metin: return -0.5
        if "bahçe" in metin: return 0.0
        if "zemin" in metin: return 0.0
        if "giriş" in metin: return 0.0
        if "yüksek giriş" in metin: return 0.5
        if "çatı" in metin: return 99.0
        if "müstakil" in metin or "villa" in metin: return 1.0
        return sayi_cikar(metin)

    def boolean_cevir(metin):
        metin = str(metin).lower()
        return 1.0 if ("var" in metin or "evet" in metin or "açık" in metin or "kapalı" in metin) else 0.0

    def isitma_puani_hesapla(metin):
        metin = str(metin).lower().strip()
        taban_puan = 0.0

        if ("kombi (doğalgaz)" in metin or "yerden" in metin or "pay ölçer" in metin or "ısı pompası" in metin or "jeotermal" in metin):
            taban_puan = 5.0
        elif "merkezi" in metin or "kat kaloriferi" in metin or "vrv" in metin:
            taban_puan = 4.0
        elif "kombi (elektrik)" in metin or "fancoil" in metin:
            taban_puan = 3.0
        elif ("doğalgaz sobası" in metin or "elektrikli radyatör" in metin or "şömine" in metin or "güneş enerjisi" in metin):
            taban_puan = 2.0
        elif metin == "yok" or "soba" in metin:
            taban_puan = 1.0

        if "klima" in metin:
            if taban_puan >= 4.0: return taban_puan + 0.5
            else: taban_puan = max(taban_puan, 3.0)
        return taban_puan if taban_puan > 0 else 0.0

    def isitma_ana_sinif(metin):
        metin = str(metin).lower().strip()
        if "yerden" in metin: return "Yerden Isitma"
        if "merkezi" in metin: return "Merkezi"
        if "kombi" in metin and "doğalgaz" in metin: return "Kombi Dogalgaz"
        if "kombi" in metin and "elektrik" in metin: return "Kombi Elektrik"
        if "kat kaloriferi" in metin: return "Kat Kaloriferi"
        if "vrv" in metin: return "VRV"
        if "fancoil" in metin: return "Fancoil"
        if "ısı pompası" in metin: return "Isi Pompası"
        if "jeotermal" in metin: return "Jeotermal"
        if "doğalgaz sobası" in metin: return "Dogalgaz Sobasi"
        if "soba" in metin: return "Soba"
        if "klima" in metin: return "Klima"
        if "şömine" in metin: return "Somine"
        if "güneş enerjisi" in metin: return "Gunes Enerjisi"
        if metin == "yok": return "Yok"
        return temiz_metin(ozellikler.get("Isıtma", "Bilinmiyor"))

    mutfak_raw = temiz_metin(ozellikler.get("Mutfak", "Bilinmiyor"))
    bina_yasi_raw = temiz_metin(ozellikler.get("Bina Yaşı", "Bilinmiyor"))
    bulundugu_kat_raw = temiz_metin(ozellikler.get("Bulunduğu Kat", "Bilinmiyor"))
    isitma_raw = temiz_metin(ozellikler.get("Isıtma", "Bilinmiyor"))

    return {
        "ilan_id": str(ilan_id),
        "il": il,
        "ilce": ilce,
        "mahalle": mahalle,
        "emlak_tipi": emlak_tipi,
        "fiyat_tl": float(temiz_fiyat),
        "bina_yasi_raw": bina_yasi_raw,
        "bulundugu_kat_raw": bulundugu_kat_raw,
        "isitma_raw": isitma_raw,
        "isitma_ana_sinif": isitma_ana_sinif(isitma_raw),
        "mutfak_raw": mutfak_raw,
        "metrekare_brut": sayi_cikar(ozellikler.get("m² (Brüt)", "0")),
        "metrekare_net": sayi_cikar(ozellikler.get("m² (Net)", "0")),
        "oda_sayisi": oda_hesapla(ozellikler.get("Oda Sayısı", "0")),
        "bina_yasi_numeric": yas_hesapla_numeric(bina_yasi_raw),
        "bina_yasi_ordinal": yas_hesapla_ordinal(bina_yasi_raw),
        "bulundugu_kat_no": kat_no_hesapla(bulundugu_kat_raw),
        "bulundugu_kat_ordinal": kat_hesapla_ordinal(bulundugu_kat_raw),
        "kat_sayisi": sayi_cikar(ozellikler.get("Kat Sayısı", "0")),
        "isitma_score": isitma_puani_hesapla(isitma_raw),
        "banyo_sayisi": sayi_cikar(ozellikler.get("Banyo Sayısı", "0")),
        "mutfak_acik_mi": 1.0 if "açık" in mutfak_raw.lower() else 0.0,
        "balkon": boolean_cevir(ozellikler.get("Balkon", "0")),
        "asansor": boolean_cevir(ozellikler.get("Asansör", "0")),
        "otopark": boolean_cevir(ozellikler.get("Otopark", "0")),
        "esyali": boolean_cevir(ozellikler.get("Eşyalı", "0")),
        "fotograf_klasoru": f"ilan_{ilan_id}"
    }

# 4. İLANLARI TEK TEK GEZME VE VERİ ÇEKME
for index, link in enumerate(tum_ilan_linkleri):

    match = re.search(r'-(\d+)(?:/detay)?$', link)
    ilan_id_test = match.group(1) if match else None
    
    if ilan_id_test:
        test_klasoru = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id_test}")
        if os.path.exists(test_klasoru):
            print(f"⏩ [{index+1}/{len(tum_ilan_linkleri)}] İlan {ilan_id_test} zaten verisetimizde var, pas geçiliyor...")
            continue 
    
    if index > 0 and index % 12 == 0:
        uzun_mola = random.uniform(45.0, 90.0)
        print(f"☕ Anti-Ban devrede. {uzun_mola:.0f} saniye kahve molası veriliyor...")
        time.sleep(uzun_mola)

    print(f"\n[{index+1}/{len(tum_ilan_linkleri)}] Şu ilana giriliyor: {link}")
    driver.get(link)
    
    time.sleep(random.uniform(2.5, 5.0)) 
    gercekci_kaydir(driver) 
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    try:
        match = re.search(r'-(\d+)(?:/detay)?$', link)
        ilan_id = match.group(1) if match else str(random.randint(10000, 99999))
        
        fiyat_kutusu = soup.find('span', class_='classified-price-wrapper')
        if fiyat_kutusu:
            ham_fiyat = fiyat_kutusu.text.strip()
            temiz_fiyat = int(ham_fiyat.replace(' TL', '').replace('.', '').strip())
        else:
            temiz_fiyat = 0
            
        ilan_ozellikleri = {}
        ozellik_listesi = soup.find('ul', class_='classifiedInfoList')
        if ozellik_listesi:
            liste_elemanlari = ozellik_listesi.find_all('li')
            for li in liste_elemanlari:
                baslik_etiketi = li.find('strong')
                deger_etiketi = li.find('span')
                if baslik_etiketi and deger_etiketi:
                    ilan_ozellikleri[baslik_etiketi.text.strip()] = deger_etiketi.text.strip()
                    
        temel_veriler_sozlugu = temel_verileri_sayisallastir(ilan_ozellikleri, ilan_id, temiz_fiyat, link, soup)        
        ilan_foto_klasoru = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id}")
        os.makedirs(ilan_foto_klasoru, exist_ok=True) 

        sehir = temel_veriler_sozlugu['il'].replace(' ', '_').capitalize()
        tip = temel_veriler_sozlugu['emlak_tipi'] 
        
        kategori_klasoru = os.path.join(ANA_KLASOR, tip)
        os.makedirs(kategori_klasoru, exist_ok=True) 
        
        dinamik_csv_yolu = os.path.join(kategori_klasoru, f"{sehir}.csv") 

        if not os.path.exists(dinamik_csv_yolu):
            df_baslangic = pd.DataFrame(columns=TUM_SUTUNLAR)
            df_baslangic.to_csv(dinamik_csv_yolu, index=False, encoding='utf-8-sig')
            print(f"📁 Yeni veri seti oluşturuldu: {tip}/{sehir}.csv")

        foto_etiketleri = soup.find_all('img') 
        foto_sayaci = 0
        for img in foto_etiketleri:
            foto_url = img.get('data-src') or img.get('src') 
            if foto_url and str(foto_url).startswith("http"):
                kucuk_harf_url = str(foto_url).lower()
                if ("jpg" in kucuk_harf_url or "jpeg" in kucuk_harf_url or "webp" in kucuk_harf_url) and "thmb" not in kucuk_harf_url:
                    if foto_sayaci >= 10: break 
                    
                    foto_isim = f"foto_{foto_sayaci+1}.jpg" 
                    foto_kayit_yolu = os.path.join(ilan_foto_klasoru, foto_isim)
                    
                    try:
                        foto_verisi = requests.get(foto_url, headers=HEADERS, timeout=10).content
                        with open(foto_kayit_yolu, 'wb') as f:
                            f.write(foto_verisi)
                        foto_sayaci += 1
                        time.sleep(0.5) 
                    except:
                        continue

        ek_ozellik_kutusu = soup.find('div', id='classifiedProperties')
        secili_ozellikler_listesi = [secili.text.strip() for secili in ek_ozellik_kutusu.find_all('li', class_='selected')] if ek_ozellik_kutusu else []
                
        ikili_matris_sozlugu = {ozellik: (1 if ozellik in secili_ozellikler_listesi else 0) for ozellik in TUM_OZELLIKLER}
        
        nihai_sozluk = {**temel_veriler_sozlugu, **ikili_matris_sozlugu}
        pd.DataFrame([nihai_sozluk]).to_csv(dinamik_csv_yolu, mode='a', header=False, index=False, encoding='utf-8-sig')        
        print(f"✅ İlan {ilan_id} -> {tip}/{sehir}.csv içine kaydedildi!")

        bekleme_suresi = random.uniform(5.0, 9.0)
        print(f"Uykuya geçiliyor... {bekleme_suresi:.1f} sn...")
        time.sleep(bekleme_suresi)
        
    except Exception as e:
        print(f"❌ İlan çekilirken hata oluştu: {e}")
        continue

print("\n🎉 Tüm Kazıma İşlemi Başarıyla Bitti!")