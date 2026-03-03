from django.core.management.base import BaseCommand
from django.conf import settings
import os, json, math, random, base64
from PIL import Image
from openai import OpenAI

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        base_dir = os.path.join(settings.MEDIA_ROOT, "datasets", "contractor")
        manifest_path = os.path.join(base_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            self.stdout.write(self.style.ERROR("Manifest not found"))
            return
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        rng = random.Random(9876)
        rng.shuffle(items)
        split = int(len(items)*0.7)
        train = items[:split]
        test = items[split:]
        api_key = os.environ.get("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key) if api_key else None
        def score_image(path):
            try:
                if client:
                    with open(path, "rb") as fh:
                        b64 = base64.b64encode(fh.read()).decode("ascii")
                    msg = [
                        {"role": "system", "content": "Assess authenticity of Ethiopian contractor application document image, return likelihood 0..1 and short reason."},
                        {"role": "user", "content": [{"type":"input_text","text":"Analyze authenticity and return score and reason."},{"type":"input_image","image_data":b64}]},
                    ]
                    r = client.chat.completions.create(model="gpt-4.1-mini", messages=msg)
                    txt = r.choices[0].message.content or ""
                    import re
                    m = re.search(r'([01](?:\.\d+)?)', txt)
                    if m:
                        return float(m.group(1))
                    return 0.5
                img = Image.open(path).convert("L")
                arr = img.resize((64, 64))
                xs = list(arr.getdata())
                mean = sum(xs)/len(xs)
                var = sum((x-mean)*(x-mean) for x in xs)/len(xs)
                s = 1.0/(1.0+math.exp(-0.01*(var-500)))
                return float(s)
            except Exception:
                return 0.5
        train_scores = []
        for it in train:
            s = score_image(it["path"])
            train_scores.append((s, 1 if it["label"]=="true" else 0))
        best_t = 0.7
        best_f1 = -1.0
        for t in [i/100 for i in range(30, 91, 1)]:
            tp=fp=fn=tn=0
            for s,y in train_scores:
                pred = 1 if s>=t else 0
                if pred==1 and y==1: tp+=1
                elif pred==1 and y==0: fp+=1
                elif pred==0 and y==1: fn+=1
                else: tn+=1
            prec = tp/(tp+fp) if tp+fp>0 else 0.0
            rec = tp/(tp+fn) if tp+fn>0 else 0.0
            f1 = 2*prec*rec/(prec+rec) if prec+rec>0 else 0.0
            if f1>best_f1:
                best_f1=f1
                best_t=t
        model_path = os.path.join(base_dir, "model.json")
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump({"true_threshold": best_t, "f1": best_f1}, f)
        self.stdout.write(self.style.SUCCESS(f"Trained threshold {best_t:.2f} (F1={best_f1:.3f}) saved to {model_path}"))
