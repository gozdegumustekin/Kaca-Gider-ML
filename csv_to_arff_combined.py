import os
import re
from pathlib import Path
from collections import Counter

import pandas as pd
from sklearn.model_selection import train_test_split

from ayarlar import TEMEL_SUTUNLAR, TUM_OZELLIKLER, TUM_SUTUNLAR

BASE_DIR = Path(__file__).resolve().parent

INPUT_ROOT_DIR = BASE_DIR / "emlak_veri_seti"
OUTPUT_DIR = BASE_DIR / "emlak_veri_seti" / "weka_output_combined"

TRAIN_ARFF = OUTPUT_DIR / "combined_train.arff"
TEST_ARFF = OUTPUT_DIR / "combined_test.arff"

RELATION_NAME_TRAIN = "combined_emlak_train"
RELATION_NAME_TEST = "combined_emlak_test"

TARGET_COLUMN = "fiyat_tl"
DROP_COLUMNS = ["ilan_id", "fotograf_klasoru"]

TEST_SIZE = 0.20
RANDOM_STATE = 42
MIN_MAHALLE_COUNT = 3

UNKNOWN_CATEGORY_TOKEN = "bilinmiyor"
RARE_MAHALLE_TOKEN = "Diger_Mahalle"

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


def debug_print_section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


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
    name = re.sub(r"[/\\-]", "_", name)
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
    val = re.sub(r"[/\\-]", "_", val)
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


def write_arff(df: pd.DataFrame, arff_path: Path, relation_name: str, attribute_schema: list, column_layout: list):
    with open(arff_path, "w", encoding="utf-8") as f:
        f.write(f"@RELATION {clean_attr_name(relation_name)}\n\n")

        for attr_name, attr_type in attribute_schema:
            f.write(f"@ATTRIBUTE {attr_name} {attr_type}\n")

        f.write("\n@DATA\n")

        for _, row in df.iterrows():
            values = []
            for original_col, _, col_type in column_layout:
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


def load_and_align_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    # sadece beklenen sütunları tut
    existing_cols = [c for c in TUM_SUTUNLAR if c in df.columns]
    df = df[existing_cols].copy()

    # eksik beklenen sütunları ekle
    missing_cols = [c for c in TUM_SUTUNLAR if c not in df.columns]
    for col in missing_cols:
        df[col] = pd.NA

    # sütun sırasını sabitle
    df = df[TUM_SUTUNLAR].copy()
    df["__source_file__"] = str(csv_path)
    return df


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    debug_print_section("1) CSV DOSYALARINI BULMA")
    print("BASE_DIR:", BASE_DIR)
    print("INPUT_ROOT_DIR:", INPUT_ROOT_DIR)
    print("INPUT_ROOT_DIR exists?:", INPUT_ROOT_DIR.exists())

    if not INPUT_ROOT_DIR.exists():
        raise FileNotFoundError(f"Girdi klasörü bulunamadı: {INPUT_ROOT_DIR}")

    csv_files = sorted(INPUT_ROOT_DIR.rglob("*.csv"))
    csv_files = [p for p in csv_files if "weka_output" not in str(p) and "weka_output_combined" not in str(p)]

    print("Bulunan CSV sayısı:", len(csv_files))
    for p in csv_files[:20]:
        print("-", p)

    if not csv_files:
        raise FileNotFoundError(f"Hiç CSV bulunamadı: {INPUT_ROOT_DIR}")

    debug_print_section("2) TÜM CSV'LERİ BİRLEŞTİRME")
    frames = []
    for csv_path in csv_files:
        try:
            df_part = load_and_align_csv(csv_path)
            frames.append(df_part)
            print(f"OK -> {csv_path.name}: {df_part.shape}")
        except Exception as e:
            print(f"HATA -> {csv_path}")
            print(e)
            print("Bu dosya atlandı.")

    if not frames:
        raise ValueError("Hiçbir CSV başarıyla yüklenemedi.")

    df = pd.concat(frames, ignore_index=True)
    print("Birleşik shape:", df.shape)

    debug_print_section("3) GEREKSİZ SÜTUNLARI KALDIRMA")
    removable = [c for c in DROP_COLUMNS if c in df.columns]
    print("Kaldırılan sütunlar:", removable)
    df.drop(columns=removable, inplace=True, errors="ignore")
    print("Sonraki shape:", df.shape)

    debug_print_section("4) TARGET KONTROLÜ")
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Hedef sütun bulunamadı: {TARGET_COLUMN}")

    df[TARGET_COLUMN] = pd.to_numeric(df[TARGET_COLUMN], errors="coerce")
    missing_target_count = df[TARGET_COLUMN].isna().sum()
    print("Hedef NaN sayısı:", missing_target_count)

    if missing_target_count > 0:
        print("Hedefi eksik satırlar siliniyor.")
        df = df.dropna(subset=[TARGET_COLUMN]).copy()

    print("Target sonrası shape:", df.shape)

    if len(df) < 10:
        raise ValueError("Birleşik veri seti train/test için çok küçük.")

    debug_print_section("5) TRAIN / TEST SPLIT")
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        shuffle=True
    )
    train_df = train_df.copy()
    test_df = test_df.copy()

    print("Train shape:", train_df.shape)
    print("Test shape :", test_df.shape)

    debug_print_section("6) KATEGORİK TEMİZLİK")
    for col in TEXT_CATEGORICAL_COLUMNS:
        if col in train_df.columns:
            train_df[col] = train_df[col].apply(clean_nominal_value)
        if col in test_df.columns:
            test_df[col] = test_df[col].apply(clean_nominal_value)

    debug_print_section("7) MAHALLE GRUPLAMA")
    if "mahalle" in train_df.columns:
        mahalle_counts = Counter(train_df["mahalle"])
        train_df["mahalle"] = train_df["mahalle"].apply(
            lambda x: x if mahalle_counts[x] >= MIN_MAHALLE_COUNT else RARE_MAHALLE_TOKEN
        )

        allowed_mahalle = set(train_df["mahalle"].unique())
        test_df["mahalle"] = test_df["mahalle"].apply(
            lambda x: x if x in allowed_mahalle else RARE_MAHALLE_TOKEN
        )

        print("Train mahalle kategori sayısı:", train_df["mahalle"].nunique())
        print(train_df["mahalle"].value_counts().head(20))

    debug_print_section("8) TESTTE TRAIN DISI KATEGORILER")
    for col in ["il", "ilce", "emlak_tipi"]:
        if col in train_df.columns and col in test_df.columns:
            allowed = set(train_df[col].unique())
            allowed.add(UNKNOWN_CATEGORY_TOKEN)
            test_df[col] = test_df[col].apply(lambda x: x if x in allowed else UNKNOWN_CATEGORY_TOKEN)

            if UNKNOWN_CATEGORY_TOKEN not in train_df[col].unique():
                new_row = train_df.iloc[0].copy()
                new_row[col] = UNKNOWN_CATEGORY_TOKEN
                new_row[TARGET_COLUMN] = train_df[TARGET_COLUMN].median()
                train_df.loc[len(train_df)] = new_row

            diff = sorted(list(set(test_df[col].unique()) - set(train_df[col].unique())))
            print(f"{col}: train disi kategori sayisi = {len(diff)}")

    debug_print_section("9) BINARY KOLONLARI DONUSTURME")
    binary_existing = [c for c in BINARY_COLUMNS if c in train_df.columns]
    for col in binary_existing:
        train_df[col] = train_df[col].apply(binary_to_nominal)
        if col in test_df.columns:
            test_df[col] = test_df[col].apply(binary_to_nominal)

    print("Binary kolon sayısı:", len(binary_existing))

    debug_print_section("10) NUMERIC KOLONLARI DONUSTURME")
    numeric_existing = [c for c in NUMERIC_COLUMNS if c in train_df.columns]
    for col in numeric_existing:
        train_df[col] = pd.to_numeric(train_df[col], errors="coerce")
        if col in test_df.columns:
            test_df[col] = pd.to_numeric(test_df[col], errors="coerce")

    print("Numeric kolonlar:", numeric_existing)

    debug_print_section("11) KOLON SIRALAMA")
    feature_cols = [c for c in train_df.columns if c != TARGET_COLUMN and c != "__source_file__"]
    ordered_cols = feature_cols + [TARGET_COLUMN]

    train_df = train_df[ordered_cols].copy()
    test_df = test_df[ordered_cols].copy()

    assert train_df.columns[-1] == TARGET_COLUMN
    assert test_df.columns[-1] == TARGET_COLUMN

    print("Class sütunu:", train_df.columns[-1])

    debug_print_section("12) ATTRIBUTE SCHEMA")
    column_layout = []
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
            column_layout.append((col, cleaned_col, "text_cat"))

        elif col in BINARY_COLUMNS:
            attr_type = "{yok,var}"
            column_layout.append((col, cleaned_col, "binary"))

        elif col in NUMERIC_COLUMNS:
            attr_type = "NUMERIC"
            column_layout.append((col, cleaned_col, "numeric"))

        else:
            attr_type = "STRING"
            column_layout.append((col, cleaned_col, "string"))

        attribute_schema.append((cleaned_col, attr_type))

    print("Toplam attribute sayısı:", len(attribute_schema))
    print("İlk 15 attribute:")
    for item in attribute_schema[:15]:
        print(item)

    debug_print_section("13) ARFF YAZMA")
    write_arff(train_df, TRAIN_ARFF, RELATION_NAME_TRAIN, attribute_schema, column_layout)
    write_arff(test_df, TEST_ARFF, RELATION_NAME_TEST, attribute_schema, column_layout)

    print("Train ARFF:", TRAIN_ARFF)
    print("Test ARFF :", TEST_ARFF)

    debug_print_section("14) BİTTİ")
    print("Weka'da combined_train.arff aç.")
    print("Son sütun fiyat_tl class olmalı.")
    print("Supplied test set ile combined_test.arff kullanılabilir.")


if __name__ == "__main__":
    main()