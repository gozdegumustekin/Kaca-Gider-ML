import os
import shutil
import random
from tqdm import tqdm

# --- 1. DOSYA YOLLARI VE AYARLAR ---
# Kaynak klasörleriniz
SOURCE_INSIDE = r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\dataset\inside"
SOURCE_OUTSIDE = r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\dataset\outside"

# Hedef ana klasör (Eğitim verisinin oluşturulacağı yer)
TARGET_BASE = r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\transfer_learning_verisi"

# Ayırma oranı (%80 Train, %20 Validation)
SPLIT_RATIO = 0.8 

# Sınıflar sözlüğü
classes = {
    "inside": SOURCE_INSIDE,
    "outside": SOURCE_OUTSIDE
}

# --- 2. HEDEF KLASÖR HİYERARŞİSİNİ OLUŞTURMA ---
for split in ['train', 'val']:
    for cls_name in classes.keys():
        folder_path = os.path.join(TARGET_BASE, split, cls_name)
        os.makedirs(folder_path, exist_ok=True)
        
print(f"Klasör yapısı '{TARGET_BASE}' içinde oluşturuldu.\n")

# --- 3. KARIŞTIRMA VE KOPYALAMA İŞLEMİ ---
for cls_name, src_dir in classes.items():
    print(f"--- {cls_name.upper()} Sınıfı İşleniyor ---")
    
    # Sadece resim dosyalarını al
    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    files = [f for f in os.listdir(src_dir) if f.lower().endswith(valid_extensions)]
    
    if not files:
        print(f"UYARI: {src_dir} içinde hiç fotoğraf bulunamadı!")
        continue
        
    print(f"Toplam {len(files)} fotoğraf bulundu.")
    
    # Fotoğrafları rastgele karıştır (En kritik adım!)
    random.seed(42) # Her çalıştırmada aynı rastgeleliği üretmek için sabit bir seed
    random.shuffle(files)
    
    # Bölme noktasını hesapla
    split_idx = int(len(files) * SPLIT_RATIO)
    
    train_files = files[:split_idx]
    val_files = files[split_idx:]
    
    print(f"{len(train_files)} adet Train, {len(val_files)} adet Val olarak ayrıldı.")
    
    # Train dosyalarını kopyala
    for f in tqdm(train_files, desc=f"{cls_name} -> train kopyalanıyor", unit="dosya"):
        src_path = os.path.join(src_dir, f)
        dest_path = os.path.join(TARGET_BASE, 'train', cls_name, f)
        shutil.copy2(src_path, dest_path)
        
    # Val dosyalarını kopyala
    for f in tqdm(val_files, desc=f"{cls_name} -> val kopyalanıyor", unit="dosya"):
        src_path = os.path.join(src_dir, f)
        dest_path = os.path.join(TARGET_BASE, 'val', cls_name, f)
        shutil.copy2(src_path, dest_path)
        
    print("\n")

print("Tebrikler! Veri setiniz PyTorch'un beklediği klasör formatında başarıyla hazırlandı.")
print(f"Eğitim verilerinize şu yoldan ulaşabilirsiniz:\n{TARGET_BASE}")