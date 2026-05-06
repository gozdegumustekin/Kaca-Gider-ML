import os
import shutil
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image, UnidentifiedImageError
from pathlib import Path
from tqdm import tqdm

# --- 1. AYARLAR VE YOLLAR ---
# Kaynak klasörler (Farklı ilan ID yapılarını barındıran orijinal ana klasörler)
SOURCE_DIRS = [
    r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\fotograflar",
    r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\fotograflar_hepsi"
]

# Hedef klasör ve alt sınıflar (Ayrılmış fotoğrafların gideceği yer)
DEST_DIR = r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\imagedata"
CLASSES = ["inside", "outside"]

# Model ağırlıklarının yolu (Az önce eğittiğiniz dosya)
MODEL_WEIGHTS_PATH = "resnet18_inside_outside.pth" 

# Cihaz seçimi (CPU veya GPU)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Kullanılan cihaz: {device}")

# --- 2. HEDEF KLASÖRLERİ OLUŞTURMA ---
for cls in CLASSES:
    os.makedirs(os.path.join(DEST_DIR, cls), exist_ok=True)

# --- 3. MODELİ YÜKLEME ---
def load_model():
    # ResNet18 mimarisini yükle
    model = models.resnet18(weights=None) 
    
    # Son katmanı (fc) 2 sınıfa göre (inside, outside) uyarla
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, 2)
    
    # Kendi eğittiğimiz ağırlıkları yükle
    if os.path.exists(MODEL_WEIGHTS_PATH):
        model.load_state_dict(torch.load(MODEL_WEIGHTS_PATH, map_location=device))
        print("Model ağırlıkları (resnet18_inside_outside.pth) başarıyla yüklendi!")
    else:
        raise FileNotFoundError(f"HATA: {MODEL_WEIGHTS_PATH} dosyası bulunamadı! Lütfen bu kodla aynı klasörde olduğundan emin olun.")
        
    model = model.to(device)
    model.eval() # Çıkarım (inference) moduna al
    return model

# --- 4. GÖRÜNTÜ İŞLEME (TRANSFORMS) ---
# ResNet'in beklediği standart boyutlar ve normalizasyon değerleri
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# --- 5. SINIFLANDIRMA VE KOPYALAMA İŞLEMİ ---
def process_images(model):
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    
    # Tüm kaynak klasörlerdeki fotoğrafların yollarını topla (rglob ile tüm alt klasörler taranır)
    all_images = []
    print("Orijinal klasörler taranıyor, bu biraz sürebilir...")
    for src in SOURCE_DIRS:
        src_path = Path(src)
        if src_path.exists():
            for ext in image_extensions:
                all_images.extend(src_path.rglob(f"*{ext}"))
                all_images.extend(src_path.rglob(f"*{ext.upper()}"))
        else:
            print(f"Uyarı: Kaynak yol bulunamadı: {src}")

    print(f"Toplam {len(all_images)} fotoğraf sınıflandırılacak.\n")

    # İşlem döngüsü (tqdm ile ilerleme çubuğu)
    for img_path in tqdm(all_images, desc="Fotoğraflar Sınıflandırılıyor"):
        try:
            # Görüntüyü aç ve RGB'ye çevir
            image = Image.open(img_path).convert('RGB')
            input_tensor = transform(image).unsqueeze(0).to(device) # Batch boyutu ekle
            
            # Tahmin yap
            with torch.no_grad():
                outputs = model(input_tensor)
                _, predicted = torch.max(outputs, 1)
                
            # Tahmin edilen sınıfı al (0 -> inside, 1 -> outside)
            class_idx = predicted.item()
            predicted_class = CLASSES[class_idx]
            
            # Kopyalanacak yeni yolu oluştur
            # Aynı isimde fotoğraf çakışmasını önlemek için ilan klasörü adını dosya adına ekliyoruz
            parent_folder_name = img_path.parent.name
            new_file_name = f"{parent_folder_name}_{img_path.name}"
            dest_path = os.path.join(DEST_DIR, predicted_class, new_file_name)
            
            # Dosyayı orijinal yerinden hedefe KOPYALA
            shutil.copy2(img_path, dest_path)
            
        except (UnidentifiedImageError, OSError):
            # Web'den çekilen verilerde eksik/bozuk indirilen resimler olabilir, bunları atla
            pass
        except Exception as e:
            print(f"\nBeklenmeyen hata ({img_path}): {e}")

if __name__ == "__main__":
    resnet_model = load_model()
    process_images(resnet_model)
    print("\nİşlem tamamlandı! Fotoğraflar başarıyla 'imagedata' klasörüne ayrıştırıldı.")