import os
import torch
import numpy as np 
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

from ayarlar import TUM_OZELLIKLER, TEMEL_SUTUNLAR, TUM_SUTUNLAR

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

        temel_sayisal_isimler = TEMEL_SUTUNLAR[2:16] 
        temel_sayilar = satir[temel_sayisal_isimler].values.astype(float)
        ozellikler_0_1 = satir[TUM_OZELLIKLER].values.astype(float)
        birlesik_matris = np.concatenate((temel_sayilar, ozellikler_0_1))
        tabular_tensor = torch.tensor(birlesik_matris, dtype=torch.float32)

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
    
    # Dosya yolları doğruysa testi çalıştır
    if os.path.exists("emlak_veri_seti/emlak_verileri.csv"):
        dataset = EmlakMatrisDataset(csv_yolu="emlak_veri_seti/emlak_verileri.csv", 
                                     foto_klasoru="emlak_veri_seti/fotograflar")
        
        dataloader = DataLoader(dataset, batch_size=1, shuffle=False)
        
        for batch in dataloader:
            print("\n--- İLK İLAN BAŞARIYLA PYTORCH TENSÖRÜNE ÇEVRİLDİ! 🚀 ---")
            print(f"İlan ID: {batch['ilan_id'][0]}")
            print(f"Fiyat Tensörü: {batch['fiyat'][0]:.1f} TL")
            
            # BURASI ÇOK ÖNEMLİ: Eskiden bura 152 çıkardı, şimdi 166 çıkmalı!
            print(f"Tabular Matris Boyutu (Toplam Özellik): {batch['matris'].shape[1]}") 
            print(f"Fotoğraf Tensör Boyutu: {batch['fotograf'].shape}")
            break
    else:
        print("❌ CSV dosyası bulunamadı. Önce emlak.py ile biraz veri topla!")