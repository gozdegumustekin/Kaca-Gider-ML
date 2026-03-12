"""import os
import torch
import torch.nn as nn
import pandas as pd
from PIL import Image
from torchvision import transforms
import torchvision.models as models
import random

# ==========================================
# 1. MODEL MİMARİSİ (Aynı kalmak zorunda)
# ==========================================
class EmlakKahinModeli(nn.Module):
    def __init__(self, tabular_ozellik_sayisi):
        super(EmlakKahinModeli, self).__init__()
        
        self.gorsel_beyin = models.resnet18(weights=None) # Ağırlıkları kendi dosyamızdan alacağız
        resnet_son_katman = self.gorsel_beyin.fc.in_features
        self.gorsel_beyin.fc = nn.Sequential(
            nn.Linear(resnet_son_katman, 256),
            nn.ReLU(),
            nn.Linear(256, 64) 
        )

        self.sayisal_beyin = nn.Sequential(
            nn.Linear(tabular_ozellik_sayisi, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.3),     
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32) 
        )

        self.karar_merkezi = nn.Sequential(
            nn.Linear(64 + 32, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1) 
        )

    def forward(self, gorsel_tensor, tabular_tensor):
        gorsel_ozellikler = self.gorsel_beyin(gorsel_tensor)
        sayisal_ozellikler = self.sayisal_beyin(tabular_tensor)
        birlesik_ozellikler = torch.cat((gorsel_ozellikler, sayisal_ozellikler), dim=1)
        tahmini_fiyat = self.karar_merkezi(birlesik_ozellikler)
        return tahmini_fiyat

# ==========================================
# 2. TAHMİN (INFERENCE) İŞLEMİ
# ==========================================
if __name__ == "__main__":
    print("🧠 Eğitilmiş Yapay Zeka Beyni Yükleniyor...\n")
    
    # Ayarlar
    CSV_YOLU = "emlak_veri_seti/emlak_verileri.csv"
    FOTO_KLASORU = "emlak_veri_seti/fotograflar"
    MODEL_DOSYASI = "emlak_kahini_modeli.pth"
    OZELLIK_SAYISI = 152 # TUM_OZELLIKLER sayımız
    
    # 1. Modeli Kur ve Eğitilmiş Ağırlıkları Yükle
    model = EmlakKahinModeli(tabular_ozellik_sayisi=OZELLIK_SAYISI)
    
    try:
        model.load_state_dict(torch.load(MODEL_DOSYASI, weights_only=True))
        model.eval() # Modeli "Test/Kullanım" moduna alıyoruz (Eğitimi durdurur)
    except Exception as e:
        print(f"Hata: {MODEL_DOSYASI} bulunamadı! Önce eğitimi tamamladığına emin ol.")
        exit()

    # 2. CSV'den Rastgele Bir Ev Seç
    df = pd.read_csv(CSV_YOLU)
    rastgele_index = random.randint(0, len(df) - 1)
    secilen_ev = df.iloc[rastgele_index]
    
    ilan_id = secilen_ev.iloc[0]
    gercek_fiyat = float(secilen_ev.iloc[1])
    
    print(f"🏠 Seçilen İlan ID: {ilan_id}")
    
    # 3. Verileri Tensöre Çevir
    # Matris verisi (17. sütundan sonrası)
    matris_verileri = secilen_ev.iloc[17:].values.astype(float)
    tabular_tensor = torch.tensor(matris_verileri, dtype=torch.float32).unsqueeze(0) # [1, 152] boyutu için
    
    # Fotoğraf verisi
    transform = transforms.Compose([
        transforms.Resize((224, 224)), 
        transforms.ToTensor(),         
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    klasor_yolu = os.path.join(FOTO_KLASORU, f"ilan_{ilan_id}")
    foto_tensor = torch.zeros((1, 3, 224, 224), dtype=torch.float32) # Varsayılan siyah ekran
    
    if os.path.exists(klasor_yolu):
        fotolar = [f for f in os.listdir(klasor_yolu) if f.endswith('.jpg')]
        if len(fotolar) > 0:
            ilk_foto_yolu = os.path.join(klasor_yolu, fotolar[0])
            try:
                resim = Image.open(ilk_foto_yolu).convert('RGB')
                foto_tensor = transform(resim).unsqueeze(0) # [1, 3, 224, 224] boyutu için
            except:
                pass

    # 4. YAPAY ZEKA TAHMİN YAPIYOR!
    with torch.no_grad(): # Gradient hesaplama, sadece tahmin et!
        tahmin_milyon = model(foto_tensor, tabular_tensor)
        tahmini_fiyat_tl = tahmin_milyon.item() * 1000000.0

    # 5. Sonuçları Göster
    print("-" * 40)
    print(f"💰 Gerçek Fiyat:        {gercek_fiyat:,.0f} TL")
    print(f"🤖 Yapay Zeka Tahmini:  {tahmini_fiyat_tl:,.0f} TL")
    
    fark = abs(gercek_fiyat - tahmini_fiyat_tl)
    print(f"📊 Yanılma Payı:        {fark:,.0f} TL")
    print("-" * 40)"""