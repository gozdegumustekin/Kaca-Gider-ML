import os
import time
import requests
import random
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 1. KLASÖR VE DOSYA YAPISINI KURMA
ANA_KLASOR = "emlak_veri_seti"
FOTO_KLASOR = os.path.join(ANA_KLASOR, "fotograflar")
CSV_DOSYASI = os.path.join(ANA_KLASOR, "emlak_verileri.csv")

if not os.path.exists(FOTO_KLASOR):
    os.makedirs(FOTO_KLASOR)

if not os.path.exists(CSV_DOSYASI):
    df_baslangic = pd.DataFrame(columns=["ilan_id", "fiyat_tl", "metrekare", "oda_sayisi", "bina_yasi", "ilan_aciklamasi", "ek_ozellikler", "fotograf_klasoru", "durum_etiketi"])
    df_baslangic.to_csv(CSV_DOSYASI, index=False, encoding='utf-8-sig')

# 2. TARAYICIYA SIZMA (AÇIK OLAN CHROME'A BAĞLANMA)
print("Açık olan gerçek Chrome'a bağlanılıyor...")
chrome_options = Options()

# Sihirli satır: 9222 numaralı porttan senin az önce açtığın Chrome'a bağlanır
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

# Yeni Chrome açmaz, açık olanın direksiyonuna geçer!
driver = webdriver.Chrome(options=chrome_options)

def insan_gibi_kaydir(driver):
    """Sanki ilanı okuyan bir insanmış gibi sayfayı yavaşça aşağı kaydırır."""
    sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    suanki_konum = 0
    while suanki_konum < sayfa_yuksekligi:
        kaydirma_miktari = random.randint(300, 700) 
        suanki_konum += kaydirma_miktari
        driver.execute_script(f"window.scrollTo(0, {suanki_konum});")
        time.sleep(random.uniform(0.2, 0.6))
        sayfa_yuksekligi = driver.execute_script("return document.body.scrollHeight")
    time.sleep(1)

# LİNKLERİ OTOMATİK TOPLAYAN FONKSİYON 
def linkleri_topla(driver, arama_sayfasi_url, toplanacak_sayfa_sayisi=3):
    """Arama sayfalarını gezer ve tüm ilanların linklerini çıkarır."""
    toplanan_linkler = []
    print(f"\nHedef aranıyor: {arama_sayfasi_url}")
    driver.get(arama_sayfasi_url)
    
    # SÜRE SINIRI YOK: Sen ekranda ilanları görene kadar bot bekleyecek!
    input("\nDİKKAT: Lütfen Chrome'a bakın. Arama sonuçları ekranını (ilanları) gördüyseniz ve CAPTCHA yoksa buraya gelip ENTER tuşuna basın...") 
    
    for sayfa_no in range(1, toplanacak_sayfa_sayisi + 1):
        print(f"--- Arama Sonuçları: Sayfa {sayfa_no} Taranıyor ---")
        
        insan_gibi_kaydir(driver)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        ilan_kutulari = soup.find_all('a', class_='classifiedTitle') 
        
        for kutu in ilan_kutulari:
            link_uzantisi = kutu.get('href')
            if link_uzantisi and not link_uzantisi.startswith("http"):
                tam_link = f"https://www.sahibinden.com{link_uzantisi}" 
                toplanan_linkler.append(tam_link)
        
        print(f"Bu sayfada {len(ilan_kutulari)} ilan linki bulundu.")
        
        # Sonraki Sayfaya Geçiş
        if sayfa_no < toplanacak_sayfa_sayisi:
            sonraki_buton = soup.find('a', class_='prevNextBut', title='Sonraki')
            if sonraki_buton:
                yeni_sayfa_uzantisi = sonraki_buton.get('href') 
                yeni_sayfa_linki = f"https://www.sahibinden.com{yeni_sayfa_uzantisi}"
                
                bekleme = random.uniform(4.0, 7.0)
                print(f"Sonraki sayfaya geçiliyor, {bekleme:.1f} sn bekleniyor...")
                time.sleep(bekleme)
                
                driver.get(yeni_sayfa_linki) 
                time.sleep(3)
            else:
                print("Sonraki sayfa butonu bulunamadı. Toplama bitiriliyor.")
                break 
                
    return toplanan_linkler

# 3. STRATEJİ BELİRLEME
hedef_linkler = [
    "https://www.sahibinden.com/kiralik-daire/bartin?sorting=price_asc" 
]

tum_ilan_linkleri = []

for arama_url in hedef_linkler:
    bulunanlar = linkleri_topla(driver, arama_url, toplanacak_sayfa_sayisi=2) 
    tum_ilan_linkleri.extend(bulunanlar)

tum_ilan_linkleri = list(set(tum_ilan_linkleri))
print(f"\nToplam {len(tum_ilan_linkleri)} adet benzersiz ilan bulundu. Kazıma işlemi başlıyor!\n{'='*50}")

# 4. İLANLARI TEK TEK GEZME VE VERİ ÇEKME
for link in tum_ilan_linkleri:
    print(f"\nŞu ilana giriliyor: {link}")
    driver.get(link)
    
    time.sleep(random.uniform(2.5, 4.0)) 
    insan_gibi_kaydir(driver) 
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    try:
        # 1. KUSURSUZ ID ÇEKME (Regex ile sadece sondaki rakamları alır)
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
                    
        metrekare = ilan_ozellikleri.get("m² (Net)", ilan_ozellikleri.get("m² (Brüt)", "0"))
        oda_sayisi = ilan_ozellikleri.get("Oda Sayısı", "Bilinmiyor")
        bina_yasi = ilan_ozellikleri.get("Bina Yaşı", "Bilinmiyor")
                
        aciklama_kutusu = soup.find('div', id='classifiedDescription') 
        if aciklama_kutusu:
            ham_aciklama = aciklama_kutusu.get_text(separator=' ', strip=True)
            ham_aciklama = ham_aciklama.replace('\n', ' ').replace('\r', ' ')
            ham_aciklama = " ".join(ham_aciklama.split())
            aciklama = ham_aciklama if len(ham_aciklama) >= 10 else "Belirtilmemiş"
        else:
            aciklama = "Belirtilmemiş"
            
        ilan_foto_klasoru = os.path.join(FOTO_KLASOR, f"ilan_{ilan_id}")
        os.makedirs(ilan_foto_klasoru, exist_ok=True) 

        # 2. KUSURSUZ FOTOĞRAF FİLTRESİ
        foto_etiketleri = soup.find_all('img') 
        foto_sayaci = 0
        for img in foto_etiketleri:
            foto_url = img.get('data-src') or img.get('src') 
            
            # ZIRH: İçinde "ilan" kelimesi geçmeyen ikonları, logoları ve haritaları yoksay!
            if foto_url and foto_url.startswith("http") and "thmb" not in foto_url and "ilan" in foto_url.lower():
                if ".jpg" in foto_url or ".webp" in foto_url:
                    if foto_sayaci >= 10: break 
                    
                    foto_isim = f"foto_{foto_sayaci+1}.jpg" 
                    foto_kayit_yolu = os.path.join(ilan_foto_klasoru, foto_isim)
                    
                    try:
                        foto_verisi = requests.get(foto_url, timeout=5).content
                        with open(foto_kayit_yolu, 'wb') as f:
                            f.write(foto_verisi)
                        foto_sayaci += 1
                        time.sleep(0.5) 
                    except:
                        continue

        ek_ozellik_kutusu = soup.find('div', id='classifiedProperties')
        secili_ozellikler_listesi = []
        if ek_ozellik_kutusu:
            secilenler = ek_ozellik_kutusu.find_all('li', class_='selected')
            for secili in secilenler:
                secili_ozellikler_listesi.append(secili.text.strip())
                
        ek_ozellikler_metni = ", ".join(secili_ozellikler_listesi) 
        if not ek_ozellikler_metni:
            ek_ozellikler_metni = "Ek özellik belirtilmemiş"
        
        yeni_veri = pd.DataFrame([{
            "ilan_id": ilan_id,
            "fiyat_tl": temiz_fiyat,
            "metrekare": metrekare,
            "oda_sayisi": oda_sayisi,
            "bina_yasi": bina_yasi,
            "ilan_aciklamasi": aciklama,
            "ek_ozellikler": ek_ozellikler_metni,
            "fotograf_klasoru": f"ilan_{ilan_id}", 
            "durum_etiketi": "" 
        }])
        
        yeni_veri.to_csv(CSV_DOSYASI, mode='a', header=False, index=False, encoding='utf-8-sig')
        print(f"✅ İlan {ilan_id} başarıyla kaydedildi!")
        
        # 3. YAKALANMAMAK İÇİN BEKLEME SÜRESİNİ ARTTIRDIK
        bekleme_suresi = random.uniform(8.5, 12.5)
        print(f"Güvenlik için uykuya geçiliyor... {bekleme_suresi:.1f} sn...")
        time.sleep(bekleme_suresi)
        
    except Exception as e:
        print(f"❌ İlan çekilirken hata oluştu: {e}")
        continue

print("\n🎉 Tüm Kazıma İşlemi Başarıyla Bitti!")