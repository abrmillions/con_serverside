from django.core.management.base import BaseCommand
from django.conf import settings
import os, json, random, uuid
from PIL import Image, ImageDraw, ImageFont, ImageFilter

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        base_dir = os.path.join(settings.MEDIA_ROOT, "datasets", "contractor")
        os.makedirs(base_dir, exist_ok=True)
        images_dir = os.path.join(base_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        manifest_path = os.path.join(base_dir, "manifest.json")
        types = ["national_id", "tax_certificate", "experience_certificate", "financial_statement"]
        rng = random.Random(12345)
        items = []
        def gen_text():
            return f"{rng.randint(100000,999999)}"
        def draw_stamp(d, x, y, r, col):
            d.ellipse((x-r, y-r, x+r, y+r), outline=col, width=3)
            d.line((x-r, y, x+r, y), fill=col, width=2)
            d.line((x, y-r, x, y+r), fill=col, width=2)
        def make_image(doc_type, label):
            w, h = 1200, 800
            img = Image.new("RGB", (w, h), (245, 245, 245))
            d = ImageDraw.Draw(img)
            title = {
                "national_id": "National ID",
                "tax_certificate": "Tax Registration Certificate",
                "experience_certificate": "Experience Certificate",
                "financial_statement": "Financial Statement",
            }[doc_type]
            d.rectangle((50, 50, w-50, h-50), outline=(60, 60, 60), width=4)
            d.text((80, 80), title, fill=(20, 20, 20))
            d.text((80, 140), f"Name: {rng.choice(['Abebe','Kebede','Alem','Sara'])} {rng.choice(['Bekele','Teshome','Desta','Tadese'])}", fill=(30, 30, 30))
            d.text((80, 180), f"ID/TIN: {gen_text()}", fill=(30, 30, 30))
            d.text((80, 220), f"Company: {rng.choice(['Addis Build Co','Oromia Infra','Nile Works','Axum Plc'])}", fill=(30, 30, 30))
            d.text((80, 260), f"Issue: 20{rng.randint(20,25)}-0{rng.randint(1,9)}-{rng.randint(10,28)}", fill=(30, 30, 30))
            draw_stamp(d, w-180, h-180, 60, (180, 0, 0))
            d.text((w-240, h-120), "Official", fill=(180, 0, 0))
            if label == "fake":
                img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.5, 2.5)))
                d = ImageDraw.Draw(img)
                x0 = rng.randint(100, 300)
                y0 = rng.randint(150, 350)
                x1 = rng.randint(500, 700)
                y1 = rng.randint(300, 550)
                if x1 < x0: x0, x1 = x1, x0
                if y1 < y0: y0, y1 = y1, y0
                d.rectangle((x0, y0, x1, y1), outline=(255, 0, 0), width=3)
                d.line((rng.randint(100,600), rng.randint(100,600), rng.randint(600,1100), rng.randint(100,600)), fill=(255, 0, 0), width=2)
            noise_pixels = int(w*h*0.0015)
            for _ in range(noise_pixels):
                x = rng.randint(0, w-1); y = rng.randint(0, h-1)
                img.putpixel((x,y), (rng.randint(200,255), rng.randint(200,255), rng.randint(200,255)))
            return img
        total = 40
        for doc_type in types:
            for i in range(total):
                label = "true" if i < total//2 else "fake"
                img = make_image(doc_type, label)
                fname = f"{uuid.uuid4().hex}_{doc_type}_{label}.png"
                fpath = os.path.join(images_dir, fname)
                img.save(fpath, format="PNG", optimize=True)
                items.append({
                    "path": fpath,
                    "type": doc_type,
                    "label": label,
                })
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=2)
        try:
            if not items:
                items2 = []
                for name in os.listdir(images_dir):
                    if not name.lower().endswith(".png"):
                        continue
                    parts = name.split("_")
                    if len(parts) < 3:
                        continue
                    doc_type = "_".join(parts[1:-1])
                    label = parts[-1].split(".")[0]
                    items2.append({"path": os.path.join(images_dir, name), "type": doc_type, "label": label})
                with open(manifest_path, "w", encoding="utf-8") as f2:
                    json.dump({"items": items2}, f2, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self.stdout.write(self.style.SUCCESS(f"Dataset created: {len(items)} images at {images_dir}"))
