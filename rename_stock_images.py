import os
import base64
from pathlib import Path
from slugify import slugify
from tqdm import tqdm
from openai import OpenAI

# ===== CONFIG =====
FOLDER = Path("/Users/kevinlin/Downloads/Stock Image")
MAX_LEN = 50
MODEL = "gpt-5.2"
# ==================

client = OpenAI()

def describe_image(image_path):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    response = client.responses.create(
        model=MODEL,
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Provide a short 4-8 word meaningful phrase describing this image. No punctuation. No quotes."
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{b64}",
                },
            ],
        }],
        max_output_tokens=40,
    )

    return response.output_text.strip()

def safe_rename(path, new_stem):
    new_stem = slugify(new_stem)[:MAX_LEN]
    new_path = path.with_name(f"{new_stem}{path.suffix.lower()}")

    counter = 1
    while new_path.exists():
        new_path = path.with_name(f"{new_stem}-{counter}{path.suffix.lower()}")
        counter += 1

    path.rename(new_path)
    return new_path.name

def main():
    images = [p for p in FOLDER.iterdir() if p.suffix.lower() in [".jpg", ".jpeg", ".png"]]

    print(f"Found {len(images)} images")

    for img in tqdm(images):
        try:
            phrase = describe_image(img)
            new_name = safe_rename(img, phrase)
            print(f"Renamed: {img.name} → {new_name}")
        except Exception as e:
            print(f"Skipped {img.name}: {e}")

if __name__ == "__main__":
    main()