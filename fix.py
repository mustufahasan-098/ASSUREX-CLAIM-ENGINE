"""QR decode test - proves the test images are valid and OpenCV can read them."""
from pathlib import Path

from src.smart_lookup import decode_qr

for f in sorted(Path(".").glob("test_qr_*.png")):
    decoded = decode_qr(f.read_bytes())
    print(f"{f.name:28s} -> {decoded!r}")