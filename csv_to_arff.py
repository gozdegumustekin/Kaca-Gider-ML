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
TARGET_COLUMN = "fiyat_tl"
DROP_COLUMNS = ["ilan_id", "fotograf_klasoru"]

TEST_SIZE = 0.20
RANDOM_STATE = 42
MIN_MAHALLE_COUNT = 3

# Testte train'de hiç görülmeyen il/ilçe/emlak_tipi değerleri gelirse:
UNKNOWN_CATEGORY_TOKEN = "bilinmiyor"
RARE_MAHALLE_TOKEN = "Diger_Mahalle"

from ayarlar import TEMEL_SUTUNLAR, TUM_OZELLIKLER, TUM_SUTUNLAR

TEXT_CATEGORICAL_COLUMNS = ["il", "ilce", "mahalle", "emlak_tipi"]

BINARY_COLUMNS = ["mutfak", "balkon", "asansor", "otopark", "esyali"] + TUM_OZELLIKLER

NUMERIC_COLUMNS = [
    "fiyat_tl",
    "metrekare_brut",
    "metrekare_net",
    "oda_sayisi",
    "bina_yasi",
    "bulundugu_kat",
    "kat_sayisi",
    "isitma",
    "banyo_sayisi"
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
                    values.append("?")

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

    missing_expected = [c for c in TUM_SUTUNLAR if c not in df.columns]
    if missing_expected:
        print(f"Beklenen ama CSV'de olmayan sütun sayısı: {len(missing_expected)}")
        print("İlk 20 eksik sütun:", missing_expected[:20])

    existing_cols = [c for c in TUM_SUTUNLAR if c in df.columns]
    df = df[existing_cols].copy()
    print(f"Beklenen sütunlar filtrelenince shape: {df.shape}")

    debug_print_section("2) GEREKSİZ SÜTUNLARI KALDIRMA")
    removable = [c for c in DROP_COLUMNS if c in df.columns]
    print("Kaldırılan sütunlar:", removable)
    df.drop(columns=removable, inplace=True, errors="ignore")
    print(f"Kaldırma sonrası shape: {df.shape}")

    debug_print_section("3) TARGET KONTROLÜ")
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Hedef sütun bulunamadı: {TARGET_COLUMN}")

    df[TARGET_COLUMN] = pd.to_numeric(df[TARGET_COLUMN], errors="coerce")
    missing_target_count = df[TARGET_COLUMN].isna().sum()
    print(f"Hedef sütun: {TARGET_COLUMN}")
    print(f"Hedef NaN sayısı: {missing_target_count}")

    if missing_target_count > 0:
        print("Uyarı: Hedefi eksik satırlar siliniyor.")
        df = df.dropna(subset=[TARGET_COLUMN]).copy()

    print(f"Target temizliği sonrası shape: {df.shape}")

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

    debug_print_section("5) KATEGORİK TEMİZLİK VE MAHALLE GRUPLAMA")

    # Train tarafında temizle
    for col in ["il", "ilce", "emlak_tipi", "mahalle"]:
        if col in train_df.columns:
            train_df[col] = train_df[col].apply(clean_nominal_value)

    # Rare mahalle train üzerinden hesaplanır
    if "mahalle" in train_df.columns:
        mahalle_counts = Counter(train_df["mahalle"])
        train_df["mahalle"] = train_df["mahalle"].apply(
            lambda x: x if mahalle_counts[x] >= MIN_MAHALLE_COUNT else RARE_MAHALLE_TOKEN
        )

    # Test tarafında aynı mantık: önce temizle
    for col in ["il", "ilce", "emlak_tipi", "mahalle"]:
        if col in test_df.columns:
            test_df[col] = test_df[col].apply(clean_nominal_value)

    # Test mahalleleri train final kategorilerine göre map et
    if "mahalle" in train_df.columns and "mahalle" in test_df.columns:
        allowed_mahalle = set(train_df["mahalle"].unique())
        test_df["mahalle"] = test_df["mahalle"].apply(
            lambda x: x if x in allowed_mahalle else RARE_MAHALLE_TOKEN
        )

    # il, ilce, emlak_tipi için testte train dışı kategori varsa bilinmiyor yap
    for col in ["il", "ilce", "emlak_tipi"]:
        if col in train_df.columns and col in test_df.columns:
            allowed = set(train_df[col].unique())
            allowed.add(UNKNOWN_CATEGORY_TOKEN)
            test_df[col] = test_df[col].apply(lambda x: x if x in allowed else UNKNOWN_CATEGORY_TOKEN)
            if UNKNOWN_CATEGORY_TOKEN not in train_df[col].unique():
                train_df.loc[len(train_df)] = train_df.iloc[0].copy()
                train_df.iloc[-1, train_df.columns.get_loc(col)] = UNKNOWN_CATEGORY_TOKEN
                train_df.iloc[-1, train_df.columns.get_loc(TARGET_COLUMN)] = train_df[TARGET_COLUMN].median()

    if "mahalle" in train_df.columns:
        print(f"Train mahalle kategori sayısı: {train_df['mahalle'].nunique()}")
        print("İlk 20 train mahalle kategorisi:")
        print(train_df["mahalle"].value_counts().head(20))

    debug_print_section("6) BINARY KOLONLARI {yok,var} YAPMA")
    binary_existing = [c for c in BINARY_COLUMNS if c in train_df.columns]

    for col in binary_existing:
        train_df[col] = train_df[col].apply(binary_to_nominal)
        if col in test_df.columns:
            test_df[col] = test_df[col].apply(binary_to_nominal)

    print(f"Binary kolon sayısı: {len(binary_existing)}")

    debug_print_section("7) NUMERIC KOLONLARI ZORLAMA")
    numeric_existing = [c for c in NUMERIC_COLUMNS if c in train_df.columns]
    for col in numeric_existing:
        train_df[col] = pd.to_numeric(train_df[col], errors="coerce")
        if col in test_df.columns:
            test_df[col] = pd.to_numeric(test_df[col], errors="coerce")

    print("Numeric kolonlar:", numeric_existing)

    debug_print_section("8) SABİT / ZAYIF KOLONLAR İÇİN DEBUG")
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

    debug_print_section("9) KOLON SIRALAMA VE CLASS KONTROLÜ")
    feature_cols = [c for c in train_df.columns if c != TARGET_COLUMN]
    ordered_cols = feature_cols + [TARGET_COLUMN]

    train_df = train_df[ordered_cols].copy()
    test_df = test_df[ordered_cols].copy()

    assert train_df.columns[-1] == TARGET_COLUMN, "Train'de class sütunu en sonda değil."
    assert test_df.columns[-1] == TARGET_COLUMN, "Test'te class sütunu en sonda değil."

    print(f"Class sütunu en sonda: {train_df.columns[-1]}")

    debug_print_section("10) ATTRIBUTE SCHEMA OLUŞTURMA")
    global COLUMN_LAYOUT
    COLUMN_LAYOUT = []

    attribute_schema = []

    for col in train_df.columns:
        cleaned_col = clean_attr_name(col)

        if col in TEXT_CATEGORICAL_COLUMNS:
            unique_vals = sorted(train_df[col].dropna().astype(str).unique())
            if UNKNOWN_CATEGORY_TOKEN not in unique_vals and col != "mahalle":
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
    print("İlk 15 attribute:")
    for a in attribute_schema[:15]:
        print(a)

    debug_print_section("11) TESTTE TRAIN DIŞI KATEGORİ KONTROLÜ")
    for col in TEXT_CATEGORICAL_COLUMNS:
        if col in train_df.columns and col in test_df.columns:
            train_set = set(train_df[col].dropna().astype(str).unique())
            test_set = set(test_df[col].dropna().astype(str).unique())
            diff = sorted(list(test_set - train_set))
            print(f"{col}: testte train dışı kategori sayısı = {len(diff)}")
            if diff:
                print("İlk 10:", diff[:10])

    debug_print_section("12) ARFF YAZMA")
    write_arff(train_df, TRAIN_ARFF, RELATION_NAME_TRAIN, attribute_schema)
    write_arff(test_df, TEST_ARFF, RELATION_NAME_TEST, attribute_schema)

    print("Train ARFF:", TRAIN_ARFF)
    print("Test ARFF :", TEST_ARFF)

    debug_print_section("13) WEKA KULLANIM NOTU")
    print("Weka'da Explorer > Preprocess > Open file ile train_emlak.arff aç.")
    print("Class olarak son sütun olan fiyat_tl seçili olmalı.")
    print("Evaluate on separate test set kullanacaksan test_emlak.arff dosyasını seç.")
    print("Train ve test aynı attribute şemasına sahip olacak şekilde üretildi.")


if __name__ == "__main__":
    main()