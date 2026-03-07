import os
import time
import requests
import random
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# --- DEVASA ÖZELLİK LİSTEMİZ (SÜTUN İSİMLERİ) ---
TUM_OZELLIKLER = [
    "Batı", "Doğu", "Güney", "Kuzey", "ADSL", "Ahşap Doğrama", "Akıllı Ev", "Alarm (Hırsız)", 
    "Alarm (Yangın)", "Alaturka Tuvalet", "Alüminyum Doğrama", "Amerikan Kapı", "Ankastre Fırın", 
    "Barbekü", "Beyaz Eşya", "Boyalı", "Bulaşık Makinesi", "Buzdolabı", "Çamaşır Kurutma Makinesi", 
    "Çamaşır Makinesi", "Çamaşır Odası", "Çelik Kapı", "Duşakabin", "Duvar Kağıdı", "Ebeveyn Banyosu", 
    "Fırın", "Fiber İnternet", "Giyinme Odası", "Gömme Dolap", "Görüntülü Diyafon", "Hilton Banyo", 
    "Intercom Sistemi", "Isıcam", "Jakuzi", "Kartonpiyer", "Kiler", "Klima", "Küvet", "Laminat Zemin", 
    "Marley", "Mobilya", "Mutfak (Ankastre)", "Mutfak (Laminat)", "Mutfak Doğalgazı", "Panjur/Jaluzi", 
    "Parke Zemin", "PVC Doğrama", "Seramik Zemin", "Set Üstü Ocak", "Spot Aydınlatma", "Şofben", 
    "Şömine", "Teras", "Termosifon", "Vestiyer", "Yüz Tanıma & Parmak İzi", "Araç Şarj İstasyonu", 
    "24 Saat Güvenlik", "Apartman Görevlisi", "Buhar Odası", "Çocuk Oyun Parkı", "Hamam", "Hidrofor", 
    "Isı Yalıtımı", "Jeneratör", "Kablo TV", "Kamera Sistemi", "Köpek Parkı", "Kreş", "Müstakil Havuzlu", 
    "Sauna", "Ses Yalıtımı", "Siding", "Spor Alanı", "Su Deposu", "Tenis Kortu", "Uydu", "Yangın Merdiveni", 
    "Yüzme Havuzu (Açık)", "Yüzme Havuzu (Kapalı)", "Alışveriş Merkezi", "Belediye", "Cami", "Cemevi", 
    "Denize Sıfır", "Eczane", "Eğlence Merkezi", "Fuar", "Göle Sıfır", "Hastane", "Havra", "İlkokul-Ortaokul", 
    "İtfaiye", "Kilise", "Lise", "Market", "Park", "Plaj", "Polis Merkezi", "Sağlık Ocağı", "Semt Pazarı", 
    "Spor Salonu", "Şehir Merkezi", "Üniversite", "Anayol", "Avrasya Tüneli", "Boğaz Köprüleri", "Cadde", 
    "Deniz Otobüsü", "Dolmuş", "E-5", "Havaalanı", "İskele", "Marmaray", "Metro", "Metrobüs", "Minibüs", 
    "Otobüs Durağı", "Sahil", "TEM", "Tramvay", "Tren İstasyonu", "Boğaz", "Deniz", "Doğa", "Göl", "Havuz", 
    "Nehir", "Park & Yeşil Alan", "Şehir", "Dubleks", "En Üst Kat", "Ara Kat", "Ara Kat Dubleks", 
    "Bahçe Dubleksi", "Çatı Dubleksi", "Forleks", "Ters Dubleks", "Tripleks", "Araç Park Yeri", 
    "Engelliye Uygun Asansör", "Engelliye Uygun Banyo", "Engelliye Uygun Mutfak", "Engelliye Uygun Park", 
    "Geniş Koridor", "Giriş / Rampa", "Merdiven", "Oda Kapısı", "Priz / Elektrik Anahtarı", 
    "Tutamak / Korkuluk", "Tuvalet", "Yüzme Havuzu"
]

# 1. KLASÖR VE DOSYA YAPISINI KURMA
ANA_KLASOR = "emlak_veri_seti"
FOTO_KLASOR = os.path.join(ANA_KLASOR, "fotograflar")
CSV_DOSYASI = os.path.join(ANA_KLASOR, "emlak_verileri.csv")

if not os.path.exists(FOTO_KLASOR):
    os.makedirs(FOTO_KLASOR)

if not os.path.exists(CSV_DOSYASI):
    temel_sutunlar = [
        "ilan_id", "fiyat_tl", "metrekare_brut", "metrekare_net", "oda_sayisi", 
        "bina_yasi", "bulundugu_kat", "kat_sayisi", "isitma", "banyo_sayisi", 
        "mutfak", "balkon", "asansor", "otopark", "esyali", "kullanim_durumu", "fotograf_klasoru"
    ]
    tum_sutunlar = temel_sutunlar + TUM_OZELLIKLER
    df_baslangic = pd.DataFrame(columns=tum_sutunlar)
    df_baslangic.to_csv(CSV_DOSYASI, index=False, encoding='utf-8-sig')

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
    "https://www.sahibinden.com/satilik-daire/artvin-borcka-borcka" 
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
                    
        temel_veriler_sozlugu = {
            "ilan_id": ilan_id,
            "fiyat_tl": temiz_fiyat,
            "metrekare_brut": ilan_ozellikleri.get("m² (Brüt)", "Bilinmiyor"),
            "metrekare_net": ilan_ozellikleri.get("m² (Net)", "Bilinmiyor"),
            "oda_sayisi": ilan_ozellikleri.get("Oda Sayısı", "Bilinmiyor"),
            "bina_yasi": ilan_ozellikleri.get("Bina Yaşı", "Bilinmiyor"),
            "bulundugu_kat": ilan_ozellikleri.get("Bulunduğu Kat", "Bilinmiyor"),
            "kat_sayisi": ilan_ozellikleri.get("Kat Sayısı", "Bilinmiyor"),
            "isitma": ilan_ozellikleri.get("Isıtma", "Bilinmiyor"),
            "banyo_sayisi": ilan_ozellikleri.get("Banyo Sayısı", "Bilinmiyor"),
            "mutfak": ilan_ozellikleri.get("Mutfak", "Bilinmiyor"),
            "balkon": ilan_ozellikleri.get("Balkon", "Bilinmiyor"),
            "asansor": ilan_ozellikleri.get("Asansör", "Bilinmiyor"),
            "otopark": ilan_ozellikleri.get("Otopark", "Bilinmiyor"),
            "esyali": ilan_ozellikleri.get("Eşyalı", "Bilinmiyor"),
            "kullanim_durumu": ilan_ozellikleri.get("Kullanım Durumu", "Bilinmiyor"),
            "fotograf_klasoru": f"ilan_{ilan_id}"
        }
            
        ilan_foto_klasoru = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id}")
        os.makedirs(ilan_foto_klasoru, exist_ok=True) 

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
        
        yeni_veri.to_csv(CSV_DOSYASI, mode='a', header=False, index=False, encoding='utf-8-sig')
        print(f"✅ İlan {ilan_id} matris formatında kaydedildi! ({foto_sayaci} fotoğraf indirildi)")
        
        bekleme_suresi = random.uniform(5.0, 8.0)
        print(f"Uykuya geçiliyor... {bekleme_suresi:.1f} sn...")
        time.sleep(bekleme_suresi)
        
    except Exception as e:
        print(f"❌ İlan çekilirken hata oluştu: {e}")
        continue

print("\n🎉 Tüm Kazıma İşlemi Başarıyla Bitti!")