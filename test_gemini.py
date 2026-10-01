"""Milestone 1.3 - verify your Gemini API key (text-only and text+image).

Usage (from the project root, venv active):
    python scripts/test_gemini.py
    python scripts/test_gemini.py path/to/outfit.jpg     # also tests image + text
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services.gemini_utils import _models_to_try  # noqa: E402


def main() -> int:
    if not settings.GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY is missing. Copy .env.example to .env and paste your key.")
        return 1

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    working = None
    for model in _models_to_try():
        try:
            r = client.models.generate_content(model=model, contents="Reply with the single word: ready")
            print(f"✅ Text test passed with model '{model}': {r.text.strip()}")
            working = model
            break
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  Model '{model}' failed: {str(exc)[:160]}")
    if not working:
        print("❌ No model worked. Check the key and the model list at https://ai.google.dev/gemini-api/docs/models")
        return 1

    if len(sys.argv) > 1:
        img = Path(sys.argv[1])
        mime = "image/png" if img.suffix.lower() == ".png" else "image/jpeg"
        r = client.models.generate_content(
            model=working,
            contents=["Describe the main colours in this image in one sentence.",
                      types.Part.from_bytes(data=img.read_bytes(), mime_type=mime)],
        )
        print("✅ Image + text test passed:", r.text.strip())
    else:
        print("ℹ️  Skipped image test (pass an image path as an argument to run it).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
