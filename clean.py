"""
ai-ready-data-tool — أداة تجهيز ملفات CSV للنمذجة.

تقرأ ملفاً خاماً، توحّد أسماء الأعمدة، تعالج القيم المفقودة، وتصدّر ملفاً نظيفاً
جاهزاً لمرحلة النمذجة. مكتوبة بالمكتبة القياسية وحدها — لا تحتاج أي تثبيت للعمل.

الاستخدام:
    python clean.py                      # يقرأ الإعدادات من config.yaml
    python clean.py --input data/raw/x.csv --output output/x.csv
"""

import argparse
import csv
import os
import re
import statistics
import sys

CONFIG_PATH = "config.yaml"


# ─────────────────────────── الإعدادات ───────────────────────────
def load_config(path=CONFIG_PATH):
    """قارئ إعدادات بسيط بصيغة key: value — بلا مكتبات خارجية."""
    cfg = {}
    if not os.path.exists(path):
        return cfg
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            cfg[key.strip()] = value
    return cfg


# ─────────────────────────── القراءة والكتابة ───────────────────────────
def read_rows(path):
    """يقرأ ملف CSV ويعيد (العناوين، الصفوف). ملف مفقود أو فارغ لا يُسقط البرنامج."""
    if not os.path.exists(path):
        print(f"warning: input file not found: {path}", file=sys.stderr)
        return [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def write_rows(header, rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)


# ─────────────────────────── التحويلات ───────────────────────────
def normalize_columns(header):
    """يوحّد أسماء الأعمدة: حروف صغيرة، شرطة سفلية، بلا رموز."""
    out = []
    for name in header:
        name = name.strip().lower()
        name = re.sub(r"[^\w\s]", "", name)   # احذف الرموز
        name = re.sub(r"\s+", "_", name.strip())  # المسافات ← شرطة سفلية
        out.append(name.strip("_"))
    return out


def _numeric_column(rows, index):
    values = []
    for row in rows:
        if index >= len(row):
            continue
        cell = row[index].strip()
        if cell == "":
            continue
        try:
            values.append(float(cell))
        except ValueError:
            return None  # العمود ليس رقمياً
    return values


def fill_missing(header, rows, strategy="mean"):
    """
    يعالج الخلايا الفارغة في الأعمدة الرقمية.

    strategy = mean   → المتوسط الحسابي
    strategy = median → الوسيط  (أمتن أمام القيم الشاذة)
    strategy = drop   → حذف الصف كاملاً
    """
    if strategy == "drop":
        return [r for r in rows if all(str(c).strip() != "" for c in r)]

    rows = [list(r) for r in rows]
    for index in range(len(header)):
        values = _numeric_column(rows, index)
        if not values:
            continue
        replacement = statistics.mean(values) if strategy == "mean" else statistics.median(values)
        for row in rows:
            if index < len(row) and row[index].strip() == "":
                row[index] = f"{replacement:.4f}".rstrip("0").rstrip(".")
    return rows


def drop_duplicates(rows):
    seen, out = set(), []
    for row in rows:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


# ─────────────────────────── التشغيل ───────────────────────────
def clean(input_path, output_path, strategy="mean", dedupe=True):
    header, rows = read_rows(input_path)
    if not header:
        write_rows([], [], output_path)
        return {"rows_in": 0, "rows_out": 0}

    rows_in = len(rows)
    header = normalize_columns(header)
    rows = fill_missing(header, rows, strategy)
    if dedupe:
        rows = drop_duplicates(rows)
    write_rows(header, rows, output_path)
    return {"rows_in": rows_in, "rows_out": len(rows)}


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="AI-Ready Data Processing Tool")
    parser.add_argument("--input", default=cfg.get("input", "data/raw/sales_sample.csv"))
    parser.add_argument("--output", default=cfg.get("output", "output/clean.csv"))
    parser.add_argument("--strategy", default=cfg.get("missing_strategy", "mean"),
                        choices=["mean", "median", "drop"])
    args = parser.parse_args()

    stats = clean(args.input, args.output, args.strategy, bool(cfg.get("drop_duplicates", True)))
    print(f"[ok] {args.input} -> {args.output}")
    print(f"     strategy={args.strategy}  rows_in={stats['rows_in']}  rows_out={stats['rows_out']}")


if __name__ == "__main__":
    main()
