import os
import time
import requests
import random
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# --- MERKEZİ AYARLARI ÇAĞIRALIM ---
from ayarlar import TUM_OZELLIKLER, TUM_SUTUNLAR

# 1. KLASÖR VE DOSYA YAPISINI KURMA
ANA_KLASOR = "emlak_veri_seti"
FOTO_KLASOR = os.path.join(ANA_KLASOR, "fotograflar")
CSV_DOSYASI = os.path.join(ANA_KLASOR, "emlak_verileri.csv")

if not os.path.exists(FOTO_KLASOR):
    os.makedirs(FOTO_KLASOR)

# Eğer CSV dosyası daha önce oluşturulmadıysa (Sadece bir kez çalışır)
if not os.path.exists(CSV_DOSYASI):
    # Artık 'temel_sutunlar'ı burada tanımlamaya gerek yok, TUM_SUTUNLAR her şeyi biliyor.
    df_baslangic = pd.DataFrame(columns=TUM_SUTUNLAR)
    df_baslangic.to_csv(CSV_DOSYASI, index=False, encoding='utf-8-sig')
    print(f"✅ {CSV_DOSYASI} oluşturuldu ve başlıklar eklendi.")
    
# 2. TARAYICIYA SIZMA (AÇIK OLAN CHROME'A BAĞLANMA)
print("Açık olan gerçek Chrome'a bağlanılıyor...")
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=chrome_options)

def insan_gibi_kaydir(driver):
    sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    suanki_konum = 0
    while suanki_konum < sayfa_yuksekligi:
        kaydirma_miktari = random.randint(300, 700) 
        suanki_konum += kaydirma_miktari
        driver.execute_script(f"window.scrollTo(0, {suanki_konum});")
        time.sleep(random.uniform(0.2, 0.6))
        sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    time.sleep(1)

# LİNKLERİ OTOMATİK TOPLAYAN FONKSİYON (SADECE 1 SAYFA)
def linkleri_topla(driver, arama_sayfasi_url):
    toplanan_linkler = []
    print(f"\nHedef aranıyor: {arama_sayfasi_url}")
    driver.get(arama_sayfasi_url)
    
    input("\nDİKKAT: Lütfen Chrome'a bakın. Arama sonuçları ekranını (ilanları) gördüyseniz ve CAPTCHA yoksa buraya gelip ENTER tuşuna basın...") 
    
    print("--- Sayfadaki İlanlar Taranıyor ---")
    insan_gibi_kaydir(driver)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    ilan_kutulari = soup.find_all('a', class_='classifiedTitle') 
    
    for kutu in ilan_kutulari:
        link_uzantisi = kutu.get('href')
        if link_uzantisi and not link_uzantisi.startswith("http"):
            tam_link = f"https://www.sahibinden.com{link_uzantisi}" 
            toplanan_linkler.append(tam_link)
    
    print(f"Bu sayfada {len(toplanan_linkler)} ilan linki bulundu.")
    return toplanan_linkler

# 3. STRATEJİ BELİRLEME
hedef_linkler = [
    # --- MERKEZ & BÜYÜK İLÇELER ---
    "https://www.sahibinden.com/satilik-daire/edirne-merkez",
    "https://www.sahibinden.com/kiralik-daire/edirne-merkez"
]

tum_ilan_linkleri = []
for arama_url in hedef_linkler:
    bulunanlar = linkleri_topla(driver, arama_url) 
    tum_ilan_linkleri.extend(bulunanlar)

tum_ilan_linkleri = list(set(tum_ilan_linkleri))
print(f"\nToplam {len(tum_ilan_linkleri)} adet benzersiz ilan bulundu. Kazıma işlemi başlıyor!\n{'='*50}")

# FOTOĞRAF İNDİRİRKEN BOT OLDUĞUMUZU GİZLEYEN KİMLİK KARTI
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
def temel_verileri_sayisallastir(ozellikler, ilan_id, temiz_fiyat, link, soup):
    """Siteden gelen metinleri sayısallaştırır ve lokasyon bilgisini çeker."""
    
    # --- 1. LOKASYON VE EMLAK TİPİ BULUCU ---
    il, ilce, mahalle = "Bilinmiyor", "Bilinmiyor", "Bilinmiyor"
    try:
        # Sahibinden başlığının altındaki lokasyon div'i (Örn: Edirne / Merkez / Şükrüpaşa Mh.)
        lokasyon_alani = soup.find('div', class_='classifiedInfo')
        if lokasyon_alani and lokasyon_alani.find('h2'):
            lokasyon_metni = lokasyon_alani.find('h2').text.replace('\n', '').strip()
            parcalar = [p.strip() for p in lokasyon_metni.split('/')]
            il = parcalar[0] if len(parcalar) > 0 else "Bilinmiyor"
            ilce = parcalar[1] if len(parcalar) > 1 else "Bilinmiyor"
            mahalle = parcalar[2] if len(parcalar) > 2 else "Bilinmiyor"
    except:
        pass

    # Linkte 'satilik' kelimesi geçiyorsa Satılık, yoksa Kiralık
    emlak_tipi = "Satılık" if "satilik" in link.lower() else "Kiralık"

    # --- 2. SAYISALLAŞTIRICI YARDIMCILAR ---
    def sayi_cikar(metin):
        if not isinstance(metin, str): return 0.0
        rakamlar = re.findall(r'-?\d+', metin)
        return float(rakamlar[0]) if rakamlar else 0.0

    def oda_hesapla(metin):
        if not isinstance(metin, str): return 0.0
        rakamlar = re.findall(r'\d+', metin)
        return sum(float(r) for r in rakamlar) if rakamlar else 1.0

    def yas_hesapla(metin):
        metin = str(metin).lower()
        if "0" in metin or "sıfır" in metin: return 4.0
        if "0-5" in metin: return 3.0
        if "6-10" in metin: return 2.0
        if "11-25" in metin: return 1.0
        if "26" in metin or "üzeri" in metin: return 0.0
        return sayi_cikar(metin)

    def kat_hesapla(metin):
        metin = str(metin).lower().strip()

        # Kategori 1 (En Düşük Puan): Eksi Kotlar ve Bodrum
        # "giriş altı" ifadesi "giriş" kelimesiyle çakışmasın diye ilk sıraya koyduk.
        if "bodrum" in metin or "kot" in metin or "giriş altı" in metin:
            return 1

        # Kategori 2 (Düşük Puan): Çatı Katı ve Çok Yüksek Katlar
        if "çatı" in metin or "30 ve" in metin:
            return 2

        # Kategori 4 (Yüksek Puan): Bahçe Katı ve Yüksek Giriş
        if "bahçe" in metin or "yüksek giriş" in metin:
            return 4

        # Kategori 5 (En Yüksek Puan): Müstakil ve Villa Tipi Yaşam Alanları
        if "müstakil" in metin or "villa" in metin:
            return 5

        # Kategori 3 (Orta Puan): Standart Giriş ve Zemin Katlar
        # Yukarıdaki "yüksek giriş" ve "giriş altı" kontrollerinden geçemeyenler buraya düşer.
        if "giriş" in metin or "zemin" in metin:
            return 3

        # Geriye sadece rakam içeren standart katlar kaldı
        kat_no = sayi_cikar(metin)

        if kat_no is not None:
            if 1 <= kat_no <= 5:
                return 5  # Kategori 5: En çok tercih edilen ara katlar
            elif 6 <= kat_no <= 10:
                return 4  # Kategori 4: Orta üst katlar
            elif 11 <= kat_no <= 20:
                return 3  # Kategori 3: Yüksek katlar
            elif kat_no >= 21:
                return 2  # Kategori 2: Çok yüksek katlar

        # Beklenmeyen bir format gelirse veri temizliği için varsayılan bir değer (örneğin 0) döndür
        return 0

    def boolean_cevir(metin):
        metin = str(metin).lower()
        return 1.0 if "var" in metin or "evet" in metin or "açık" in metin or "kapalı" in metin else 0.0

    def isitma_puani_hesapla(metin):
        metin = str(metin).lower().strip()
        
        taban_puan = 0
        ekstra_sistem_var_mi = False

        # 5 Puanlık Ana Sistemler
        if "kombi (doğalgaz)" in metin or "yerden" in metin or "pay ölçer" in metin or "ısı pompası" in metin or "jeotermal" in metin:
            taban_puan = 5

        # 4 Puanlık Ana Sistemler (Eğer henüz 5 puan almadıysa)
        elif "merkezi" in metin or "kat kaloriferi" in metin or "vrv" in metin:
            taban_puan = 4

        # 3 Puanlık Sistemler
        elif "kombi (elektrik)" in metin or "fancoil" in metin:
            taban_puan = 3

        # 2 Puanlık Sistemler
        elif "doğalgaz sobası" in metin or "elektrikli radyatör" in metin or "şömine" in metin or "güneş enerjisi" in metin:
            taban_puan = 2

        # 1 Puanlık Sistemler
        elif metin == "yok" or "soba" in metin:
            taban_puan = 1

        # ---- KLİMA VEYA ŞÖMİNE GİBİ EKSTRALAR KONTROLÜ ----
        # Klima genelde ana ısıtma değil destekleyicidir. Kombi+Klima varsa ekstra puan veriyoruz.
        if "klima" in metin:
            if taban_puan >= 4:  # Zaten iyi bir sistemi var, klimayı lüks/ekstra say
                return taban_puan + 0.5 
            else: # Ana ısıtma sistemi yok veya zayıfsa klimayı ana sistem say (3 puan)
                taban_puan = max(taban_puan, 3) 

        return taban_puan if taban_puan > 0 else 0

    # DİKKAT: Sıralama ayarlar.py içindeki TEMEL_SUTUNLAR ile birebir aynı olmak ZORUNDA!
    return {
        "ilan_id": str(ilan_id),
        "il": il,
        "ilce": ilce,
        "mahalle": mahalle,
        "emlak_tipi": emlak_tipi,
        "fiyat_tl": float(temiz_fiyat),
        "metrekare_brut": sayi_cikar(ozellikler.get("m² (Brüt)", "0")),
        "metrekare_net": sayi_cikar(ozellikler.get("m² (Net)", "0")),
        "oda_sayisi": oda_hesapla(ozellikler.get("Oda Sayısı", "0")),
        "bina_yasi": yas_hesapla(ozellikler.get("Bina Yaşı", "0")),
        "bulundugu_kat": kat_hesapla(ozellikler.get("Bulunduğu Kat", "0")),
        "kat_sayisi": sayi_cikar(ozellikler.get("Kat Sayısı", "0")),
        "isitma": isitma_puani_hesapla(ozellikler.get("Isıtma", "0")),
        "banyo_sayisi": sayi_cikar(ozellikler.get("Banyo Sayısı", "0")), #buradan
        "mutfak": 1.0 if "açık" in str(ozellikler.get("Mutfak", "")).lower() else 0.0,
        "balkon": boolean_cevir(ozellikler.get("Balkon", "0")),
        "asansor": boolean_cevir(ozellikler.get("Asansör", "0")),
        "otopark": boolean_cevir(ozellikler.get("Otopark", "0")),
        "esyali": boolean_cevir(ozellikler.get("Eşyalı", "0")),
        "fotograf_klasoru": f"ilan_{ilan_id}"
    }

# 4. İLANLARI TEK TEK GEZME VE VERİ ÇEKME
for link in tum_ilan_linkleri:
    print(f"\nŞu ilana giriliyor: {link}")
    driver.get(link)
    
    time.sleep(random.uniform(2.5, 4.0)) 
    insan_gibi_kaydir(driver) 
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    try:
        # ID VE TEMEL VERİLER
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
                    baslik = baslik_etiketi.text.strip()
                    deger = deger_etiketi.text.strip()
                    ilan_ozellikleri[baslik] = deger
                    
        # YERİNE SADECE BUNU YAZIYORSUN:
        temel_veriler_sozlugu = temel_verileri_sayisallastir(ilan_ozellikleri, ilan_id, temiz_fiyat, link, soup)        
        ilan_foto_klasoru = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id}")
        os.makedirs(ilan_foto_klasoru, exist_ok=True) 

        sehir = temel_veriler_sozlugu['il'].replace(' ', '_')
        tip = temel_veriler_sozlugu['emlak_tipi'] 
        dosya_adi = f"{sehir}_{tip}.csv"
        dinamik_csv_yolu = os.path.join(ANA_KLASOR, dosya_adi)

        if not os.path.exists(dinamik_csv_yolu):
            from ayarlar import TUM_SUTUNLAR
            df_baslangic = pd.DataFrame(columns=TUM_SUTUNLAR)
            df_baslangic.to_csv(dinamik_csv_yolu, index=False, encoding='utf-8-sig')
            print(f"📁 Yeni kategori dosyası oluşturuldu: {dosya_adi}")

        # FOTOĞRAF İNDİRME ZIRHI (Güncellendi)
        foto_etiketleri = soup.find_all('img') 
        foto_sayaci = 0
        for img in foto_etiketleri:
            foto_url = img.get('data-src') or img.get('src') 
            
            # URL http ile başlamalı ve uzantısı jpg/jpeg/webp olmalı
            if foto_url and str(foto_url).startswith("http"):
                kucuk_harf_url = str(foto_url).lower()
                if ("jpg" in kucuk_harf_url or "jpeg" in kucuk_harf_url or "webp" in kucuk_harf_url) and "thmb" not in kucuk_harf_url:
                    if foto_sayaci >= 10: break 
                    
                    foto_isim = f"foto_{foto_sayaci+1}.jpg" 
                    foto_kayit_yolu = os.path.join(ilan_foto_klasoru, foto_isim)
                    
                    try:
                        # HEADERS ekledik, sunucu artık bot olduğumuzu anlamayacak
                        foto_verisi = requests.get(foto_url, headers=HEADERS, timeout=10).content
                        with open(foto_kayit_yolu, 'wb') as f:
                            f.write(foto_verisi)
                        foto_sayaci += 1
                        time.sleep(0.5) 
                    except Exception as e:
                        continue

        # MATRİS OLUŞTURMA (0 VE 1'LER)
        ek_ozellik_kutusu = soup.find('div', id='classifiedProperties')
        secili_ozellikler_listesi = []
        if ek_ozellik_kutusu:
            secilenler = ek_ozellik_kutusu.find_all('li', class_='selected')
            for secili in secilenler:
                secili_ozellikler_listesi.append(secili.text.strip())
                
        ikili_matris_sozlugu = {}
        for ozellik in TUM_OZELLIKLER:
            if ozellik in secili_ozellikler_listesi:
                ikili_matris_sozlugu[ozellik] = 1
            else:
                ikili_matris_sozlugu[ozellik] = 0
        
        # TEMEL VERİLERLE MATRİSİ BİRLEŞTİRİP KAYDETME
        nihai_sozluk = {**temel_veriler_sozlugu, **ikili_matris_sozlugu}
        yeni_veri = pd.DataFrame([nihai_sozluk])
        
        yeni_veri.to_csv(dinamik_csv_yolu, mode='a', header=False, index=False, encoding='utf-8-sig')        
        print(f"✅ İlan {ilan_id} -> {dosya_adi} içine kaydedildi!")

        bekleme_suresi = random.uniform(5.0, 8.0)
        print(f"Uykuya geçiliyor... {bekleme_suresi:.1f} sn...")
        time.sleep(bekleme_suresi)
        
    except Exception as e:
        print(f"❌ İlan çekilirken hata oluştu: {e}")
        continue

print("\n🎉 Tüm Kazıma İşlemi Başarıyla Bitti!")