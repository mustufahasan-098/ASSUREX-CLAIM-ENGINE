"""AssureX Claim Engine - Claim Summary Card generator (Step 2, v2).

Renders one visual Claim Summary Card for every claim in the stratified
dataset splits:

  train  : 2 visual variations per claim -> 2,100 images (SRS minimum)
  val    : 1 canonical card per claim    ->  225 images (never trained on)
  test   : 1 canonical card per claim    ->  225 images (never trained on)

Variations change layout, font size, background, spacing, image quality and
date format ONLY - never the claim information or the class label (SRS 1.2).

DESIGN NOTE (v2): the v1 design reached ~70% Teachable Machine accuracy.
Root cause: TM resizes cards to 224x224, where the small status chips lose
salience, and the Valid class is defined by the ABSENCE of flags - a weak
signal for CNNs. v2 adds a high-salience VALIDATION CHECKS section with
large full-width status pills rendering the factual rule findings
(src.rules.factual_flags), coloured by the policy severity categories
(hard-fail = red, review-level = amber, clean = green). Cards contain
factual claim information ONLY - no model prediction, no confidence score,
no final decision, no class names (SRS req xx).

Run from the project root:
    python -m card_generator.generate_cards
"""
import csv
import random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.features import compute_derived, parse_date, to_bool, warranty_expiry
from src.rules import factual_flags, load_policies

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CARDS = DATA / "cards"

BASE_W, BASE_H = 560, 1200
LABEL_W = 150

INK = (33, 37, 41)
MUTED = (108, 117, 125)
WHITE = (255, 255, 255)
HEADER = (23, 42, 82)

STYLES = {
    "green": ((198, 239, 206), (21, 87, 36)),
    "red": ((255, 205, 210), (183, 28, 28)),
    "amber": ((255, 236, 179), (130, 86, 0)),
    "gray": ((233, 236, 239), (73, 80, 87)),
}

     
PILL_STYLES = {
    "green": ((21, 122, 62), WHITE),
    "red": ((184, 32, 32), WHITE),
    "amber": ((199, 122, 11), WHITE),
}

DOCS = [
    ("receipt", "Receipt"),
    ("warranty_card", "Warranty Card"),
    ("product_image", "Product Image"),
    ("serial_evidence", "Serial Evidence"),
    ("fault_evidence", "Fault Evidence"),
    ("repair_report", "Repair Report"),
]

_FONTS = {}

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # older Pillow
    RESAMPLE = Image.LANCZOS


def font(size, bold=False):
    key = (int(size), bold)
    if key in _FONTS:
        return _FONTS[key]
    paths = (["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"] if bold
             else ["C:/Windows/Fonts/arial.ttf"])
    f = None
    for p in paths:
        try:
            f = ImageFont.truetype(p, int(size))
            break
        except OSError:
            continue
    if f is None:
        try:
            f = ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
                                   int(size))
        except OSError:
            f = ImageFont.load_default()
    _FONTS[key] = f
    return f


def render_card(claim, policy, bg=(255, 255, 255), pad=26, bold_values=False,
                date_fmt="%d-%m-%Y"):
    """Render one Claim Summary Card image for a claim dict."""
    img = Image.new("RGB", (BASE_W, BASE_H), bg)
    d = ImageDraw.Draw(img)

    f_title = font(28, True)
    f_cid = font(24, True)
    f_label = font(20)
    f_value = font(22, bold_values)
    f_chip = font(19, True)
    f_section = font(19, True)
    f_doc = font(20)
    f_stat = font(20, True)

    x0, x1 = pad, BASE_W - pad

     
    d.rectangle([0, 0, BASE_W, 56], fill=HEADER)
    d.text((x0, 14), "ASSUREX  CLAIM SUMMARY CARD", font=f_title, fill=WHITE)
    y = 72
    d.text((x0, y), f"Claim ID: {claim['claim_id']}", font=f_cid, fill=INK)
    y += 42

    def draw_chip(x, cy, text, kind):
        fill, fg = STYLES[kind]
        tw = d.textlength(text, font=f_chip)
        d.rounded_rectangle([x, cy, x + tw + 20, cy + 30], radius=9, fill=fill)
        d.text((x + 10, cy + 4), text, font=f_chip, fill=fg)
        return x + tw + 20

    def row(label, value=None, chip=None, note=None):
        nonlocal y
        d.text((x0, y + 3), label, font=f_label, fill=MUTED)
        cx = x0 + LABEL_W
        if value is not None:
            d.text((cx, y), str(value), font=f_value, fill=INK)
            cx += d.textlength(str(value), font=f_value) + 12
        if chip is not None:
            kind, text = chip
            cx = draw_chip(cx, y, text, kind) + 10
        if note is not None:
            d.text((cx, y + 2), str(note), font=f_label, fill=MUTED)
        y += 44

    def big_pill(text, kind):
        """Large full-width status pill - the primary signal Teachable
        Machine learns from (survives the 224x224 resize)."""
        nonlocal y
        fill, fg = PILL_STYLES[kind]
        size = 25
        while d.textlength(text, font=font(size, True)) > (x1 - x0 - 30) and size > 15:
            size -= 1
        f_pill = font(size, True)
        d.rounded_rectangle([x0, y, x1, y + 46], radius=10, fill=fill)
        tw = d.textlength(text, font=f_pill)
        d.text((x0 + (x1 - x0 - tw) / 2, y + 10), text, font=f_pill, fill=fg)
        y += 56

     
    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])
    claim_d = parse_date(claim["claim_date"])
    repair_d = parse_date(claim.get("last_repair_date") or "")
    expiry = warranty_expiry(claim)
    der = compute_derived(claim, policy)

    def fmt(dt):
        return dt.strftime(date_fmt) if dt else "N/A"

    row("Product", value=f"{claim['brand']} {claim['model']}")
    row("Category", value=claim["product_category"])
    row("Purchase Date", value=fmt(purchase))

    if fault and fault > expiry:
        if der["within_grace"]:
            wchip = ("amber", "GRACE PERIOD")
        else:
            wchip = ("red", "EXPIRED")
        wnote = f"expired {fmt(expiry)}"
    else:
        wchip = ("green", "ACTIVE")
        left = der["warranty_days_remaining"]
        wnote = f"{left}d left - ends {fmt(expiry)}" if left is not None \
            else f"ends {fmt(expiry)}"
    row("Warranty", chip=wchip, note=wnote)

    row("Fault", value=claim["fault_category"], note=fmt(fault))
    covered = claim["fault_category"] in policy["covered_faults"]
    row("Fault Coverage", chip=("green", "COVERED") if covered else ("red", "EXCLUDED"))

    dtr = der["days_to_report"]
    limit = int(policy["claim_reporting_period_days"])
    if dtr is None:
        rchip, rnote = ("gray", "UNKNOWN"), ""
    elif dtr < 0:
        rchip, rnote = ("red", "CONFLICT"), "claim before fault"
    elif dtr <= limit:
        rchip, rnote = ("green", "ON TIME"), f"{dtr}d - limit {limit}d"
    else:
        rchip, rnote = ("red", "LATE"), f"{dtr}d - limit {limit}d"
    row("Reporting", chip=rchip, note=rnote)

    age = der["product_age_days"]
    if age is None:
        achip, aval = ("gray", "UNKNOWN"), "N/A"
    elif age < 0:
        achip, aval = ("red", "INCONSISTENT"), f"{age}d"
    else:
        aval = f"{age // 365}y {(age % 365) // 30}m ({age}d)"
        achip = ("amber", "EARLY LIFE") if age <= int(policy["early_fault_review_days"]) \
            else ("green", "NORMAL")
    row("Product Age", value=aval, chip=achip)

    row("Serial Check", chip=("green", "MATCH")
        if to_bool(claim.get("serial_match", True)) else ("red", "MISMATCH"))

    rc = int(claim.get("repair_count") or 0)
    if rc == 0:
        reps, rchip2 = "None", ("gray", "NONE")
    else:
        reps = f"{rc} repair(s)"
        if rc > int(policy["max_prior_repairs"]):
            rchip2 = ("amber", "EXCESSIVE")
        elif to_bool(claim.get("authorized_repair", True)):
            rchip2 = ("green", "AUTHORIZED")
        else:
            rchip2 = ("red", "UNAUTHORIZED")
    row("Repair History", value=reps, chip=rchip2)

    pc = int(claim.get("prior_claim_count") or 0)
    dup = to_bool(claim.get("duplicate_invoice", False))
    if pc > 0 or dup:
        pchip, pnote = ("amber", "DUPLICATE RISK"), \
            f"{pc} prior" + (" - invoice reused" if dup else "")
    else:
        pchip, pnote = ("green", "NONE"), ""
    row("Prior Claims", chip=pchip, note=pnote)

    row("Replacement", chip=("green", "NONE")
        if not to_bool(claim.get("replaced_before", False))
        else ("red", "REPLACED BEFORE"))

    conflict = bool(
        (claim_d and purchase and claim_d < purchase)
        or (fault and purchase and fault < purchase)
        or (fault and claim_d and fault > claim_d)
        or (repair_d and purchase and repair_d < purchase))
    row("Date Check", chip=("red", "CONFLICT") if conflict else ("green", "CONSISTENT"))

     
    y += 10
    d.text((x0, y), "VALIDATION CHECKS", font=f_section, fill=MUTED)
    y += 36
    flags = factual_flags(claim, policy)
    if not flags:
        big_pill("ALL CHECKS PASSED", "green")
    else:
        for sev, text in flags[:4]:
            big_pill(text, "red" if sev == "hard_fail" else "amber")

     
    y += 12
    d.text((x0, y), "SUPPORTING DOCUMENTS", font=f_section, fill=MUTED)
    y += 34
    mandatory = set(policy["mandatory_documents"])
    col_w = (x1 - x0) // 2
    for i, (key, name) in enumerate(DOCS):
        col, r = divmod(i, 3)
        cx, cy = x0 + col * col_w, y + r * 34
        d.text((cx, cy), f"{name}:", font=f_doc, fill=INK)
        if to_bool(claim.get(f"has_{key}", False)):
            text, color = "YES", (33, 100, 45)
        elif key in mandatory:
            text, color = "MISSING", (183, 28, 28)
        else:
            text, color = "N/A", MUTED
        d.text((cx + 170, cy), text, font=f_stat, fill=color)
    y += 3 * 34 + 10

     
    missing = [name for key, name in DOCS
               if key in mandatory and not to_bool(claim.get(f"has_{key}", False))]
    if missing:
        text = "MISSING DOCUMENTS: " + ", ".join(missing)
        fill, fg = STYLES["amber"]
    else:
        text = "ALL MANDATORY DOCUMENTS PRESENT"
        fill, fg = STYLES["green"]
    size = 22
    while d.textlength(text, font=font(size, True)) > (x1 - x0 - 24) and size > 14:
        size -= 2
    d.rounded_rectangle([x0, y, x1, y + 52], radius=12, fill=fill)
    tw = d.textlength(text, font=font(size, True))
    d.text((x0 + (x1 - x0 - tw) / 2, y + 15), text, font=font(size, True), fill=fg)

    return img


def variant_style(rng):
    """Randomised visual style for training variation 2. Changes ONLY visual
    properties (SRS: layout, font size, background, spacing, image quality,
    date format) - claim information and class label stay identical."""
    return {
        "bg": rng.choice([(246, 248, 250), (250, 246, 238),
                          (240, 246, 242), (247, 243, 250)]),
        "pad": rng.choice([20, 32]),
        "bold_values": rng.random() < 0.5,
        "date_fmt": rng.choice(["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]),
        "scale": rng.choice([0.90, 0.96, 1.04, 1.08]),
    }


def read_split(split):
    with open(DATA / f"{split}_claims.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def generate():
    policies = load_policies()
    index_rows = []
    counts = {s: Counter() for s in ("train", "val", "test")}

    for split in ("train", "val", "test"):
        for claim in read_split(split):
            policy = policies[claim["product_category"]]
            outdir = CARDS / split / claim["label"]
            outdir.mkdir(parents=True, exist_ok=True)
            cid = claim["claim_id"]

     
     
            flags = factual_flags(claim, policy)
            if (claim["label"] == "Valid Claim") != (len(flags) == 0):
                raise SystemExit(
                    f"Card/label inconsistency for {cid}: label={claim['label']} "
                    f"but flags={flags}. factual_flags has drifted from "
                    "evaluate_claim - fix before training TM.")

     
            render_card(claim, policy).save(outdir / f"{cid}_v1.png")
            index_rows.append([cid, f"{cid}_v1.png", 1, split, claim["label"]])
            counts[split][claim["label"]] += 1

     
            if split == "train":
                rng = random.Random(f"{SEED}:{cid}")
                st = variant_style(rng)
                img = render_card(claim, policy, bg=st["bg"], pad=st["pad"],
                                  bold_values=st["bold_values"],
                                  date_fmt=st["date_fmt"])
                s = st["scale"]
                img = img.resize((int(BASE_W * s), int(BASE_H * s)), RESAMPLE)
                img.save(outdir / f"{cid}_v2.jpg", "JPEG", quality=88)
                index_rows.append([cid, f"{cid}_v2.jpg", 2, split, claim["label"]])
                counts[split][claim["label"]] += 1

    with open(DATA / "card_index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["claim_id", "filename", "variation", "split", "label"])
        w.writerows(index_rows)

    print("Claim Summary Cards (v2 design) written to data/cards/")
    for split in ("train", "val", "test"):
        total = sum(counts[split].values())
        per = ", ".join(f"{lbl} {n}" for lbl, n in sorted(counts[split].items()))
        print(f"  {split:5}: {total} images ({per})")
    print("Image index written to data/card_index.csv")
    print("\nSTEP 2A-v2 COMPLETE [OK]")


if __name__ == "__main__":
    generate()