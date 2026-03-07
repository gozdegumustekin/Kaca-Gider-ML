import os
import torch
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

# --- CSV'DE BAŞLIK SİLİNMESİNE KARŞI ZIRHIMIZ (SÜTUN İSİMLERİ) ---
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

class EmlakMatrisDataset(Dataset):
    def __init__(self, csv_yolu, foto_klasoru):
        self.foto_klasoru = foto_klasoru
        
        # 1. ZIRHLI CSV OKUMA: Başlık silinmişse bile biz veriyoruz!
        ilk_okuma = pd.read_csv(csv_yolu, nrows=1)
        if 'fiyat_tl' not in ilk_okuma.columns:
            # Başlık yokmuş, o yüzden isimleri kendimiz zorluyoruz
            self.df = pd.read_csv(csv_yolu, names=TUM_SUTUNLAR, header=None)
        else:
            # Başlık varsa normal oku
            self.df = pd.read_csv(csv_yolu)
        
        # 2. Fotoğraf Ayarları (ResNet formatı)
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)), 
            transforms.ToTensor(),         
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        satir = self.df.iloc[idx]
        
        hedef_fiyat = torch.tensor(float(satir['fiyat_tl']), dtype=torch.float32)

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
                    
        # Eğer fotoğraf yoksa veya bozuksa siyah bir tensör ver
        if foto_tensor is None:
            foto_tensor = torch.zeros((3, 224, 224), dtype=torch.float32)

        return {
            'ilan_id': str(ilan_id),
            'fiyat': hedef_fiyat,
            'matris': tabular_tensor,
            'fotograf': foto_tensor
        }

# ==========================================
# TEST KISMI
# ==========================================
if __name__ == "__main__":
    print("PyTorch Veri Seti Yükleniyor...")
    
    dataset = EmlakMatrisDataset(csv_yolu="emlak_veri_seti/emlak_verileri.csv", 
                                 foto_klasoru="emlak_veri_seti/fotograflar")
    
    dataloader = DataLoader(dataset, batch_size=1, shuffle=False)
    
    for batch in dataloader:
        print("\n--- İLK İLAN BAŞARIYLA PYTORCH TENSÖRÜNE ÇEVRİLDİ! 🚀 ---")
        print(f"İlan ID: {batch['ilan_id'][0]}")
        print(f"Fiyat Tensörü: {batch['fiyat']} (Boyut: {batch['fiyat'].shape})")
        
        print(f"Tabular Matris Boyutu: {batch['matris'].shape} (0 ve 1'ler)") 
        
        print(f"Fotoğraf Tensör Boyutu: {batch['fotograf'].shape} (ResNet Formatı)")
        break