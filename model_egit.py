import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, models, transforms
from torch.utils.data import DataLoader
import os
import time
import copy

# --- 1. AYARLAR VE VERİ YOLU ---
DATA_DIR = r"C:\Users\gozde\OneDrive\Masaüstü\antiemlak\emlak_veri_seti\transfer_learning_verisi"
NUM_EPOCHS = 10  # Veriyi kaç kez baştan sona görecek
BATCH_SIZE = 32  # Tek seferde işlenecek fotoğraf sayısı

# --- 2. VERİ ARTIRMA (AUGMENTATION) VE NORMALİZASYON ---
# Eğitim (train) verisine rastgele çevirmeler ekliyoruz ki model ezberlemesin.
# Doğrulama (val) verisine dokunmuyoruz, sadece boyutlandırıyoruz.
data_transforms = {
    'train': transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(), # Rastgele yatay çevirme
        transforms.RandomRotation(10),     # Hafif sağa/sola döndürme
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ]),
    'val': transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ]),
}

# --- 3. VERİ YÜKLEYİCİLER (DATALOADERS) ---
image_datasets = {x: datasets.ImageFolder(os.path.join(DATA_DIR, x), data_transforms[x])
                  for x in ['train', 'val']}

dataloaders = {x: DataLoader(image_datasets[x], batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
               for x in ['train', 'val']}

dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}
class_names = image_datasets['train'].classes

print(f"Sınıflar: {class_names}")
print(f"Eğitim verisi: {dataset_sizes['train']} adet")
print(f"Doğrulama verisi: {dataset_sizes['val']} adet\n")

# Cihaz seçimi (Ekran kartı varsa CUDA, yoksa CPU)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(f"Kullanılacak cihaz: {device}\n")

# --- 4. MODELİ KURMA (TRANSFER LEARNING) ---
# Önceden eğitilmiş modeli indir
model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)

# Sadece son katmanı (fc) değiştir (Bizde 2 sınıf var: inside, outside)
num_ftrs = model.fc.in_features
model.fc = nn.Linear(num_ftrs, len(class_names))

model = model.to(device)

# Hata fonksiyonu ve Optimizasyon
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.fc.parameters(), lr=0.001) # SADECE fc (son katman) ağırlıklarını günceller

# --- 5. EĞİTİM DÖNGÜSÜ (TRAINING LOOP) ---
def train_model(model, criterion, optimizer, num_epochs=10):
    since = time.time()
    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

    for epoch in range(num_epochs):
        print(f'Epoch {epoch+1}/{num_epochs}')
        print('-' * 10)

        # Her epoch'ta önce eğitim (train), sonra doğrulama (val) yapılır
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()  # Modeli eğitim moduna al
            else:
                model.eval()   # Modeli değerlendirme moduna al

            running_loss = 0.0
            running_corrects = 0

            # Verileri iterasyonla al
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # Gradientleri sıfırla
                optimizer.zero_grad()

                # İleri yayılım (Forward)
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)

                    # Sadece eğitim fazındaysa geriye yayılım (Backward) ve optimize et
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                # İstatistikleri hesapla
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]

            print(f'{phase.capitalize()} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

            # En iyi modeli kaydet
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())

        print()

    time_elapsed = time.time() - since
    print(f'Eğitim tamamlandı. Süre: {time_elapsed // 60:.0f}m {time_elapsed % 60:.0f}s')
    print(f'En İyi Doğrulama (Val) Doğruluğu: {best_acc:.4f}')

    # Modeli en iyi ağırlıklarla geri yükle
    model.load_state_dict(best_model_wts)
    return model

# --- 6. BAŞLAT VE KAYDET ---
if __name__ == '__main__':
    # Eğitimi başlat
    trained_model = train_model(model, criterion, optimizer, num_epochs=NUM_EPOCHS)
    
    # En başarılı modeli bilgisayara kaydet
    SAVE_PATH = "resnet18_inside_outside.pth"
    torch.save(trained_model.state_dict(), SAVE_PATH)
    print(f"\nModel başarıyla kaydedildi: {SAVE_PATH}")