import os
import re
from pathlib import Path
from collections import Counter

import pandas as pd
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent

INPUT_ROOT_DIR = BASE_DIR / "emlak_veri_seti"
csv_files = sorted(INPUT_ROOT_DIR.rglob("*.csv"))
OUTPUT_DIR = BASE_DIR / "emlak_veri_seti" / "weka_output"

TRAIN_ARFF = OUTPUT_DIR / "train_emlak.arff"
TEST_ARFF = OUTPUT_DIR / "test_emlak.arff"

RELATION_NAME_TRAIN = "emlak_train"
RELATION_NAME_TEST = "emlak_test"

# =========================================================
# AYARLAR
# =========================================================
RAW_TARGET_COLUMN = "fiyat_tl"          # ham sayısal fiyat
CLASS_COLUMN = "fiyat_kategorisi"       # Weka class sütunu

DROP_COLUMNS = ["ilan_id", "fotograf_klasoru"]

TEST_SIZE = 0.20
RANDOM_STATE = 42
MIN_MAHALLE_COUNT = 3

UNKNOWN_CATEGORY_TOKEN = "bilinmiyor"
RARE_MAHALLE_TOKEN = "Diger_Mahalle"

# çok uçuk / hatalı fiyatlar için üst limit
MAX_VALID_PRICE = 20_000_000_000  # 20 milyar TL

from ayarlar import TEMEL_SUTUNLAR, TUM_OZELLIKLER, TUM_SUTUNLAR

FEATURE_TEXT_CATEGORICAL_COLUMNS = [
    "il", "ilce", "mahalle", "emlak_tipi",
    "bina_yasi_raw", "bulundugu_kat_raw", "isitma_raw",
    "isitma_ana_sinif", "mutfak_raw"
]

TEXT_CATEGORICAL_COLUMNS = FEATURE_TEXT_CATEGORICAL_COLUMNS + [CLASS_COLUMN]

# TUM_OZELLIKLER'i artık binary olarak modele vermiyoruz.
# Sadece temel birkaç alan binary kalıyor.
BINARY_COLUMNS = ["balkon", "asansor", "otopark", "esyali"]

# Yeni 4 skor numeric feature olarak eklendi
NUMERIC_COLUMNS = [
    "metrekare_brut", "metrekare_net", "oda_sayisi",
    "bina_yasi", "bulundugu_kat", "kat_sayisi", "isitma", "banyo_sayisi",
    "bina_yasi_numeric", "bina_yasi_ordinal", "bulundugu_kat_no",
    "bulundugu_kat_ordinal", "isitma_score", "mutfak_acik_mi",
    "guvenlik_skoru", "luks_skoru", "sosyal_skoru", "lokasyon_skoru"
]

print("BASE_DIR:", BASE_DIR)

# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================
def clean_attr_name(name: str) -> str:
    tr_map = {
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U"
    }
    for k, v in tr_map.items():
        name = name.replace(k, v)

    name = name.replace("&", " ve ")
    name = re.sub(r"[()]", "", name)
    name = re.sub(r"[/\-]", "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name)
    return name

def clean_nominal_value(val) -> str:
    if pd.isna(val):
        return UNKNOWN_CATEGORY_TOKEN

    val = str(val).strip()

    tr_map = {
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U"
    }
    for k, v in tr_map.items():
        val = val.replace(k, v)

    val = val.replace("&", " ve ")
    val = re.sub(r"[()']", "", val)
    val = re.sub(r"[/\-]", "_", val)
    val = re.sub(r"\s+", "_", val.strip())
    val = re.sub(r"_+", "_", val)

    return val if val else UNKNOWN_CATEGORY_TOKEN

def binary_to_nominal(val) -> str:
    if pd.isna(val):
        return "yok"

    try:
        return "var" if float(val) == 1.0 else "yok"
    except Exception:
        text = str(val).strip().lower()
        return "var" if text in ["1", "var", "evet", "true"] else "yok"

def numeric_or_missing(val) -> str:
    if pd.isna(val):
        return "?"
    try:
        return str(float(val))
    except Exception:
        return "?"

def fiyat_kategorisi_belirle(fiyat):
    if pd.isna(fiyat) or fiyat <= 0:
        return UNKNOWN_CATEGORY_TOKEN

    if fiyat < 500_000:
        return "500_Bin_TL_Alti"
    elif 500_000 <= fiyat < 1_000_000:
        return "500_Bin_1_Milyon_TL_Arasi"
    elif 1_000_000 <= fiyat < 1_500_000:
        return "1_1_Bucuk_Milyon_TL_Arasi"
    elif 1_500_000 <= fiyat < 2_000_000:
        return "1_Bucuk_2_Milyon_TL_Arasi"
    elif 2_000_000 <= fiyat < 3_000_000:
        return "2_3_Milyon_TL_Arasi"
    elif 3_000_000 <= fiyat < 4_000_000:
        return "3_4_Milyon_TL_Arasi"
    elif 4_000_000 <= fiyat < 5_000_000:
        return "4_5_Milyon_TL_Arasi"
    elif 5_000_000 <= fiyat < 7_500_000:
        return "5_7_Bucuk_Milyon_TL_Arasi"
    elif 7_500_000 <= fiyat < 10_000_000:
        return "7_Bucuk_10_Milyon_TL_Arasi"
    elif 10_000_000 <= fiyat < 15_000_000:
        return "10_15_Milyon_TL_Arasi"
    elif 15_000_000 <= fiyat < 25_000_000:
        return "15_25_Milyon_TL_Arasi"
    elif 25_000_000 <= fiyat < 50_000_000:
        return "25_50_Milyon_TL_Arasi"
    elif 50_000_000 <= fiyat < 100_000_000:
        return "50_100_Milyon_TL_Arasi"
    elif 100_000_000 <= fiyat < 250_000_000:
        return "100_250_Milyon_TL_Arasi"
    elif 250_000_000 <= fiyat < 500_000_000:
        return "250_500_Milyon_TL_Arasi"
    elif 500_000_000 <= fiyat < 1_000_000_000:
        return "500_Milyon_1_Milyar_TL_Arasi"
    elif 1_000_000_000 <= fiyat < 2_000_000_000:
        return "1_2_Milyar_TL_Arasi"
    elif 2_000_000_000 <= fiyat < 4_000_000_000:
        return "2_4_Milyar_TL_Arasi"
    elif 4_000_000_000 <= fiyat < 6_000_000_000:
        return "4_6_Milyar_TL_Arasi"
    else:
        return "6_Milyar_TL_Ustu"

# --- YENİ: ÖZEL SKORLAMA (FEATURE ENGINEERING) ---
GUVENLIK_OZELLIKLERI = [
    "Alarm (Hırsız)", "Alarm (Yangın)", "24 Saat Güvenlik", "Görüntülü Diyafon",
    "Kamera Sistemi", "Yüz Tanıma & Parmak İzi", "Yangın Merdiveni"
]

LUKS_OZELLIKLERI = [
    "Akıllı Ev", "Şömine", "Hamam", "Sauna", "Jakuzi", "Yüzme Havuzu (Açık)",
    "Yüzme Havuzu (Kapalı)", "Yüzme Havuzu", "Müstakil Havuzlu", "Ebeveyn Banyosu",
    "Giyinme Odası", "Teras", "Araç Şarj İstasyonu", "Buhar Odası"
]

SOSYAL_OZELLIKLERI = [
    "Çocuk Oyun Parkı", "Kreş", "Spor Alanı", "Spor Salonu", "Tenis Kortu",
    "Köpek Parkı", "Alışveriş Merkezi", "Eğlence Merkezi", "Park", "Park & Yeşil Alan"
]

ULASIM_LOKASYON_OZELLIKLERI = [
    "Metro", "Metrobüs", "Marmaray", "Avrasya Tüneli", "Boğaz Köprüleri", "E-5", "TEM",
    "Deniz Otobüsü", "Havaalanı", "İskele", "Tramvay", "Tren İstasyonu",
    "Denize Sıfır", "Göle Sıfır", "Boğaz", "Deniz", "Sahil"
]

def ozellik_degerini_sayiya_cevir(val):
    if pd.isna(val):
        return 0.0

    # Önce doğrudan numeric dönüşüm deneyelim
    try:
        return 1.0 if float(val) > 0 else 0.0
    except Exception:
        pass

    text = str(val).strip().lower()

    pozitifler = {"1", "1.0", "var", "evet", "true", "yes", "y", "mevcut"}
    negatifler = {"0", "0.0", "yok", "hayir", "hayır", "false", "no", "n", ""}

    if text in pozitifler:
        return 1.0
    if text in negatifler:
        return 0.0

    return 0.0

def skorlari_hesapla_ve_temizle(df):
    out = df.copy()

    def sutunlari_topla(hedef_kolonlar):
        mevcut_kolonlar = [c for c in hedef_kolonlar if c in out.columns]
        if not mevcut_kolonlar:
            return pd.Series(0.0, index=out.index)

        skor_df = out[mevcut_kolonlar].apply(
            lambda col: col.map(ozellik_degerini_sayiya_cevir)
        )
        return skor_df.fillna(0).sum(axis=1)

    out["guvenlik_skoru"] = sutunlari_topla(GUVENLIK_OZELLIKLERI)
    out["luks_skoru"] = sutunlari_topla(LUKS_OZELLIKLERI)
    out["sosyal_skoru"] = sutunlari_topla(SOSYAL_OZELLIKLERI)
    out["lokasyon_skoru"] = sutunlari_topla(ULASIM_LOKASYON_OZELLIKLERI)

    silinecek_sutunlar = [c for c in TUM_OZELLIKLER if c in out.columns]
    out.drop(columns=silinecek_sutunlar, inplace=True, errors="ignore")

    return out

    # 1) 4 ana skor üret
    out["guvenlik_skoru"] = sutunlari_topla(GUVENLIK_OZELLIKLERI)
    out["luks_skoru"] = sutunlari_topla(LUKS_OZELLIKLERI)
    out["sosyal_skoru"] = sutunlari_topla(SOSYAL_OZELLIKLERI)
    out["lokasyon_skoru"] = sutunlari_topla(ULASIM_LOKASYON_OZELLIKLERI)

    # 2) Ham 150+ özellik sütununu sil
    silinecek_sutunlar = [c for c in TUM_OZELLIKLER if c in out.columns]
    out.drop(columns=silinecek_sutunlar, inplace=True, errors="ignore")

    return out

def write_arff(df: pd.DataFrame, arff_path: str, relation_name: str, attribute_schema: list):
    with open(arff_path, "w", encoding="utf-8") as f:
        f.write(f"@RELATION {clean_attr_name(relation_name)}\n\n")

        for attr_name, attr_type in attribute_schema:
            f.write(f"@ATTRIBUTE {attr_name} {attr_type}\n")

        f.write("\n@DATA\n")

        for _, row in df.iterrows():
            values = []
            for original_col, cleaned_col, col_type in COLUMN_LAYOUT:
                value = row[original_col]

                if col_type == "text_cat":
                    values.append(str(value) if not pd.isna(value) else UNKNOWN_CATEGORY_TOKEN)
                elif col_type == "binary":
                    values.append(str(value) if not pd.isna(value) else "yok")
                elif col_type == "numeric":
                    values.append(numeric_or_missing(value))
                else:
                    val_str = str(value).replace('"', "'") if not pd.isna(value) else "?"
                    values.append(f'"{val_str}"' if val_str != "?" else "?")

            f.write(",".join(values) + "\n")

def debug_print_section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

# =========================================================
# ANA AKIŞ
# =========================================================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    debug_print_section("0) CSV DOSYALARINI OKUMA VE BİRLEŞTİRME")
    tum_dataframeler = []

    for csv_dosyasi in csv_files:
        try:
            gecici_df = pd.read_csv(csv_dosyasi)
            if not gecici_df.empty:
                tum_dataframeler.append(gecici_df)
                print(f"  -> Okundu: {csv_dosyasi.name} ({len(gecici_df)} satır)")
        except Exception as e:
            print(f"  -> Atlandı: {csv_dosyasi.name} (Hata: {e})")

    if not tum_dataframeler:
        print("❌ HİÇBİR CSV DOSYASI OKUNAMADI VEYA KLASÖR BOŞ! İşlem iptal ediliyor.")
        return

    df = pd.concat(tum_dataframeler, ignore_index=True)
    print(f"\n✅ Toplam {len(df)} satırlık birleştirilmiş veri seti başarıyla oluşturuldu.")

    debug_print_section("1) SÜTUN KONTROLÜ")
    missing_expected = [c for c in TUM_SUTUNLAR if c not in df.columns]
    if missing_expected:
        print(f"Beklenen ama CSV'de olmayan sütun sayısı: {len(missing_expected)}")
        print("İlk 20 eksik sütun:", missing_expected[:20])

    existing_cols = [c for c in TUM_SUTUNLAR if c in df.columns]
    df = df[existing_cols].copy()
    print(f"Beklenen sütunlar filtrelenince shape: {df.shape}")

    debug_print_section("2) SKORLARI HESAPLAMA VE GEREKSİZLERİ KALDIRMA")

    # 150+ ham özelliği 4 güçlü sayısal skora çevir
    df = skorlari_hesapla_ve_temizle(df)

    # klasik gereksiz kolonlar
    removable = [c for c in DROP_COLUMNS if c in df.columns]
    print("Kaldırılan sütunlar:", removable)
    df.drop(columns=removable, inplace=True, errors="ignore")

    print(f"Skorlama ve kaldırma sonrası yeni shape: {df.shape}")

    debug_print_section("3) TARGET KONTROLÜ VE FİYAT TEMİZLİĞİ")
    if RAW_TARGET_COLUMN not in df.columns:
        raise ValueError(f"Hedef sütun bulunamadı: {RAW_TARGET_COLUMN}")

    df[RAW_TARGET_COLUMN] = pd.to_numeric(df[RAW_TARGET_COLUMN], errors="coerce")
    print(f"Hedef sütun: {RAW_TARGET_COLUMN}")
    print(f"NaN sayısı: {df[RAW_TARGET_COLUMN].isna().sum()}")

    onceki_len = len(df)
    df = df[df[RAW_TARGET_COLUMN].notna()].copy()
    df = df[df[RAW_TARGET_COLUMN] > 0].copy()
    df = df[df[RAW_TARGET_COLUMN] <= MAX_VALID_PRICE].copy()

    print(f"Temizlik sonrası silinen satır sayısı: {onceki_len - len(df)}")
    print(f"Kalan shape: {df.shape}")

    debug_print_section("4) TRAIN / TEST SPLIT")
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        shuffle=True
    )
    train_df = train_df.copy()
    test_df = test_df.copy()

    print(f"Train shape: {train_df.shape}")
    print(f"Test shape : {test_df.shape}")

    debug_print_section("5) FİYAT KATEGORİLERİNİ OLUŞTURMA (SABİT ARALIKLAR)")

    train_df[CLASS_COLUMN] = train_df[RAW_TARGET_COLUMN].apply(fiyat_kategorisi_belirle)
    test_df[CLASS_COLUMN] = test_df[RAW_TARGET_COLUMN].apply(fiyat_kategorisi_belirle)

    print("\nTrain fiyat kategori dağılımı:")
    print(train_df[CLASS_COLUMN].value_counts(dropna=False))

    print("\nTest fiyat kategori dağılımı:")
    print(test_df[CLASS_COLUMN].value_counts(dropna=False))

    # Ham fiyatı feature olarak kullanmayacaksan kaldır
    train_df.drop(columns=[RAW_TARGET_COLUMN], inplace=True, errors="ignore")
    test_df.drop(columns=[RAW_TARGET_COLUMN], inplace=True, errors="ignore")

    debug_print_section("6) KATEGORİK TEMİZLİK VE MAHALLE GRUPLAMA")

    for col in TEXT_CATEGORICAL_COLUMNS:
        if col in train_df.columns:
            train_df[col] = train_df[col].apply(clean_nominal_value)

    if "mahalle" in train_df.columns:
        mahalle_counts = Counter(train_df["mahalle"])
        train_df["mahalle"] = train_df["mahalle"].apply(
            lambda x: x if mahalle_counts[x] >= MIN_MAHALLE_COUNT else RARE_MAHALLE_TOKEN
        )

    for col in TEXT_CATEGORICAL_COLUMNS:
        if col in test_df.columns:
            test_df[col] = test_df[col].apply(clean_nominal_value)

    if "mahalle" in train_df.columns and "mahalle" in test_df.columns:
        allowed_mahalle = set(train_df["mahalle"].unique())
        test_df["mahalle"] = test_df["mahalle"].apply(
            lambda x: x if x in allowed_mahalle else RARE_MAHALLE_TOKEN
        )

    fallback_class = train_df[CLASS_COLUMN].mode().iloc[0]

    # class sütununa bilinmiyor eklemiyoruz; sadece feature kategoriklerde yapıyoruz
    for col in FEATURE_TEXT_CATEGORICAL_COLUMNS:
        if col == "mahalle":
            continue

        if col in train_df.columns and col in test_df.columns:
            allowed = set(train_df[col].unique())
            allowed.add(UNKNOWN_CATEGORY_TOKEN)

            test_df[col] = test_df[col].apply(
                lambda x: x if x in allowed else UNKNOWN_CATEGORY_TOKEN
            )

            if UNKNOWN_CATEGORY_TOKEN not in train_df[col].unique():
                yeni_satir = train_df.iloc[0].copy()
                yeni_satir[col] = UNKNOWN_CATEGORY_TOKEN
                yeni_satir[CLASS_COLUMN] = fallback_class
                train_df.loc[len(train_df)] = yeni_satir

    if "mahalle" in train_df.columns:
        print(f"Train mahalle kategori sayısı: {train_df['mahalle'].nunique()}")

    debug_print_section("7) BINARY KOLONLARI {yok,var} YAPMA")
    binary_existing = [c for c in BINARY_COLUMNS if c in train_df.columns]

    for col in binary_existing:
        train_df[col] = train_df[col].apply(binary_to_nominal)
        if col in test_df.columns:
            test_df[col] = test_df[col].apply(binary_to_nominal)

    print(f"Binary kolon sayısı: {len(binary_existing)}")

    debug_print_section("8) NUMERIC KOLONLARI ZORLAMA")
    numeric_existing = [c for c in NUMERIC_COLUMNS if c in train_df.columns]
    for col in numeric_existing:
        train_df[col] = pd.to_numeric(train_df[col], errors="coerce")
        if col in test_df.columns:
            test_df[col] = pd.to_numeric(test_df[col], errors="coerce")

    print("Numeric kolonlar:", numeric_existing)

    debug_print_section("9) SABİT / ZAYIF KOLONLAR İÇİN DEBUG")
    constant_cols = []
    never_var_binary = []

    for col in train_df.columns:
        nunique = train_df[col].nunique(dropna=False)
        if nunique <= 1:
            constant_cols.append(col)

    for col in binary_existing:
        unique_vals = set(train_df[col].dropna().astype(str).unique())
        if unique_vals.issubset({"yok"}) or len(unique_vals) == 0:
            never_var_binary.append(col)

    print(f"Sabit kolon sayısı: {len(constant_cols)}")
    print("İlk 20 sabit kolon:", constant_cols[:20])
    print(f"Train'de hiç 'var' olmayan binary kolon sayısı: {len(never_var_binary)}")
    print("İlk 20 hiç-var-olmayan binary kolon:", never_var_binary[:20])

    debug_print_section("10) KOLON SIRALAMA VE CLASS KONTROLÜ")
    feature_cols = [c for c in train_df.columns if c != CLASS_COLUMN]
    ordered_cols = feature_cols + [CLASS_COLUMN]

    train_df = train_df[ordered_cols].copy()
    test_df = test_df[ordered_cols].copy()

    assert train_df.columns[-1] == CLASS_COLUMN, "Train'de class sütunu en sonda değil."
    assert test_df.columns[-1] == CLASS_COLUMN, "Test'te class sütunu en sonda değil."

    print(f"Class sütunu en sonda: {train_df.columns[-1]}")

    debug_print_section("11) ATTRIBUTE SCHEMA OLUŞTURMA")
    global COLUMN_LAYOUT
    COLUMN_LAYOUT = []

    attribute_schema = []

    for col in train_df.columns:
        cleaned_col = clean_attr_name(col)

        if col in TEXT_CATEGORICAL_COLUMNS:
            unique_vals = sorted(train_df[col].dropna().astype(str).unique())

            if col in FEATURE_TEXT_CATEGORICAL_COLUMNS and col != "mahalle":
                if UNKNOWN_CATEGORY_TOKEN not in unique_vals:
                    unique_vals.append(UNKNOWN_CATEGORY_TOKEN)

            if col == "mahalle" and RARE_MAHALLE_TOKEN not in unique_vals:
                unique_vals.append(RARE_MAHALLE_TOKEN)

            attr_type = "{" + ",".join(unique_vals) + "}"
            COLUMN_LAYOUT.append((col, cleaned_col, "text_cat"))

        elif col in BINARY_COLUMNS:
            attr_type = "{yok,var}"
            COLUMN_LAYOUT.append((col, cleaned_col, "binary"))

        elif col in NUMERIC_COLUMNS:
            attr_type = "NUMERIC"
            COLUMN_LAYOUT.append((col, cleaned_col, "numeric"))

        else:
            attr_type = "STRING"
            COLUMN_LAYOUT.append((col, cleaned_col, "string"))

        attribute_schema.append((cleaned_col, attr_type))

    print(f"Toplam attribute sayısı: {len(attribute_schema)}")

    debug_print_section("12) TESTTE TRAIN DIŞI KATEGORİ KONTROLÜ")
    for col in TEXT_CATEGORICAL_COLUMNS:
        if col in train_df.columns and col in test_df.columns:
            train_set = set(train_df[col].dropna().astype(str).unique())
            test_set = set(test_df[col].dropna().astype(str).unique())
            diff = sorted(list(test_set - train_set))
            print(f"{col}: testte train dışı kategori sayısı = {len(diff)}")

    debug_print_section("13) ARFF YAZMA")
    write_arff(train_df, TRAIN_ARFF, RELATION_NAME_TRAIN, attribute_schema)
    write_arff(test_df, TEST_ARFF, RELATION_NAME_TEST, attribute_schema)

    print("Train ARFF:", TRAIN_ARFF)
    print("Test ARFF :", TEST_ARFF)

    debug_print_section("14) WEKA KULLANIM NOTU")
    print("Weka'da Explorer > Preprocess > Open file ile train_emlak.arff aç.")
    print(f"Class olarak son sütun olan {CLASS_COLUMN} seçili olmalı.")
    print("Evaluate on separate test set kullanacaksan test_emlak.arff dosyasını seç.")

if __name__ == "__main__":
    main()