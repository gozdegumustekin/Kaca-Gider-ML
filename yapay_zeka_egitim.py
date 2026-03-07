import os
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import torchvision.models as models

# ==========================================
# 1. SABİTLER VE SÜTUN İSİMLERİ (ZIRH)
# ==========================================
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

TEMEL_SUTUNLAR = [
    "ilan_id", "fiyat_tl", "metrekare_brut", "metrekare_net", "oda_sayisi", 
    "bina_yasi", "bulundugu_kat", "kat_sayisi", "isitma", "banyo_sayisi", 
    "mutfak", "balkon", "asansor", "otopark", "esyali", "kullanim_durumu", "fotograf_klasoru"
]
TUM_SUTUNLAR = TEMEL_SUTUNLAR + TUM_OZELLIKLER
OZELLIK_SAYISI = len(TUM_OZELLIKLER) # Otomatik hesaplar (Yaklaşık 152)

# ==========================================
# 2. VERİ OKUYUCU (DATASET KÖPRÜSÜ)
# ==========================================
class EmlakMatrisDataset(Dataset):
    def __init__(self, csv_yolu, foto_klasoru):
        self.foto_klasoru = foto_klasoru
        
        # CSV Zırhı
        ilk_okuma = pd.read_csv(csv_yolu, nrows=1)
        if 'fiyat_tl' not in ilk_okuma.columns:
            self.df = pd.read_csv(csv_yolu, names=TUM_SUTUNLAR, header=None)
        else:
            self.df = pd.read_csv(csv_yolu)
            
        # ResNet Görüntü Ayarları
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)), 
            transforms.ToTensor(),         
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        satir = self.df.iloc[idx]
        
        # Fiyatı 1 Milyona bölerek (Örn: 3.5 Milyon TL) modele veriyoruz
        hedef_fiyat = torch.tensor(float(satir['fiyat_tl']) / 1000000.0, dtype=torch.float32)

        # Tabular (0-1) Verisi: İlk 17 sütundan sonrakiler bizim özelliklerimiz
        matris_verileri = satir.iloc[17:].values.astype(float)
        tabular_tensor = torch.tensor(matris_verileri, dtype=torch.float32)

        # Görsel Veri (Fotoğraflar)
        ilan_id = satir['ilan_id']
        klasor_yolu = os.path.join(self.foto_klasoru, f"ilan_{ilan_id}")
        
        foto_tensor = None
        if os.path.exists(klasor_yolu):
            fotolar = [f for f in os.listdir(klasor_yolu) if f.endswith('.jpg')]
            if len(fotolar) > 0:
                ilk_foto_yolu = os.path.join(klasor_yolu, fotolar[0])
                try:
                    resim = Image.open(ilk_foto_yolu).convert('RGB')
                    foto_tensor = self.transform(resim)
                except Exception as e:
                    pass
                    
        if foto_tensor is None:
            foto_tensor = torch.zeros((3, 224, 224), dtype=torch.float32)

        return {
            'ilan_id': str(ilan_id),
            'fiyat': hedef_fiyat,
            'matris': tabular_tensor,
            'fotograf': foto_tensor
        }

# ==========================================
# 3. YAPAY ZEKA MİMARİSİ (ÇOK MODLU BEYİN)
# ==========================================
class EmlakKahinModeli(nn.Module):
    def __init__(self, tabular_ozellik_sayisi):
        super(EmlakKahinModeli, self).__init__()
        
        # --- GÖRSEL BEYİN (ResNet18) ---
        self.gorsel_beyin = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        resnet_son_katman = self.gorsel_beyin.fc.in_features
        self.gorsel_beyin.fc = nn.Sequential(
            nn.Linear(resnet_son_katman, 256),
            nn.ReLU(),
            nn.Linear(256, 64) # Fotoğraftan 64 tane Lüks/Bakım skoru çıkar
        )

        # --- SAYISAL BEYİN (0-1 Matrisini İşleyen Ağ) ---
        self.sayisal_beyin = nn.Sequential(
            nn.Linear(tabular_ozellik_sayisi, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.3),     
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32) # Sayılardan 32 özellik çıkar
        )

        # --- KARAR MERKEZİ (Birleştirici Başlık) ---
        self.karar_merkezi = nn.Sequential(
            nn.Linear(64 + 32, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1) # ÇIKIŞ: Tek bir tahmin (Ev Fiyatı)
        )

    def forward(self, gorsel_tensor, tabular_tensor):
        gorsel_ozellikler = self.gorsel_beyin(gorsel_tensor)
        sayisal_ozellikler = self.sayisal_beyin(tabular_tensor)
        
        birlesik_ozellikler = torch.cat((gorsel_ozellikler, sayisal_ozellikler), dim=1)
        tahmini_fiyat = self.karar_merkezi(birlesik_ozellikler)
        return tahmini_fiyat

# ==========================================
# 4. EĞİTİM MOTORU (TRAINING LOOP)
# ==========================================
if __name__ == "__main__":
    print("🚀 YAPAY ZEKA EĞİTİMİ (TRAINING) BAŞLIYOR! 🚀\n")

    # Verileri Yükle
    dataset = EmlakMatrisDataset(csv_yolu="emlak_veri_seti/emlak_verileri.csv", 
                                 foto_klasoru="emlak_veri_seti/fotograflar")
    
    # Modele evleri 4'erli gruplar halinde veriyoruz
    dataloader = DataLoader(dataset, batch_size=4, shuffle=True)

    # Modeli Başlat
    model = EmlakKahinModeli(tabular_ozellik_sayisi=OZELLIK_SAYISI)

    # Ekran kartı (GPU) varsa kullan, yoksa işlemci (CPU) kullan
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"Sistem şu an {device} gücünü kullanıyor!\n")

    # Öğretmen (Hata Ölçücü) ve Optimize Edici (Öğrenci Beynini Güncelleyen)
    criterion = nn.L1Loss() # Fiyat tahmini sapmasını TL cinsinden ölçer
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Model tüm verileri kaç kere baştan sona görecek?
    EPOCH_SAYISI = 50 

    for epoch in range(EPOCH_SAYISI):
        toplam_hata = 0.0

        for batch_idx, batch in enumerate(dataloader):
            fotograflar = batch['fotograf'].to(device)
            matrisler = batch['matris'].to(device)
            gercek_fiyatlar = batch['fiyat'].to(device).view(-1, 1) 

            tahmini_fiyatlar = model(fotograflar, matrisler)
            hata = criterion(tahmini_fiyatlar, gercek_fiyatlar)

            optimizer.zero_grad() 
            hata.backward()       
            optimizer.step()      

            toplam_hata += hata.item()

        # Hatayı model 'Milyon' üzerinden verdiği için ekrana yazarken tekrar 1 Milyon ile çarpıyoruz
        ortalama_hata_milyon = toplam_hata / len(dataloader)
        gercek_tl_hatasi = ortalama_hata_milyon * 1000000
        
        print(f"Epoch [{epoch+1}/{EPOCH_SAYISI}] | Ortalama Sapma (Hata): {gercek_tl_hatasi:,.0f} TL")

    print("\n🎉 EĞİTİM TAMAMLANDI! Model emlak fiyatlarını öğrendi.")
    torch.save(model.state_dict(), "emlak_kahini_modeli.pth")
    print("💾 Modelin zekası 'emlak_kahini_modeli.pth' dosyasına kaydedildi!")