import requests
import urllib.parse
import time
import base64
import io
import textwrap

def generer_image_ia(prompt):
    """
    Génère une image via l'API Pollinations.ai.
    Retourne l'URL de l'image générée.
    """
    try:
        print(f"[IMAGE] Génération pour : {prompt}")
        
        # Encodage du prompt pour l'URL
        prompt_enc = urllib.parse.quote(prompt)
        
        # Nouvelle API Pollinations
        seed = int(time.time())
        image_url = f"https://image.pollinations.ai/prompt/{prompt_enc}?seed={seed}&nologo=true"
        
        # On déguise la requête en navigateur web pour ne pas être bloqué/ralenti
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/jpeg, image/png, image/*"
        }
        
        # On télécharge l'image directement depuis le serveur Python (Timeout allongé à 45s)
        response = requests.get(image_url, headers=headers, timeout=45)
        if response.status_code == 200:
            # On convertit l'image en base64 pour l'envoyer au WebSocket sans problème de CORS
            img_b64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{img_b64}"
        else:
            print(f"[IMAGE ERROR] Status {response.status_code}")
            return None

    except Exception as e:
        print(f"[IMAGE ERROR] {e}")
        return None


def generer_affiche_ia(prompt_visuel, lignes_texte=None, titre=None):
    """
    Génère une affiche : visuel produit par l'IA en fond, texte superposé
    proprement avec Pillow. Les modèles de génération d'image ne savent pas
    écrire du texte lisible (dates, phrases) à l'intérieur de l'image, donc
    on sépare volontairement le visuel (IA) du texte (rendu vectoriel).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        img_data_uri = generer_image_ia(prompt_visuel)
        if not img_data_uri:
            return None

        _, b64data = img_data_uri.split(",", 1)
        img = Image.open(io.BytesIO(base64.b64decode(b64data))).convert("RGBA")
        w, h = img.size

        lignes = ([titre] if titre else []) + (lignes_texte or [])
        if not lignes:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=90)
            return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

        # Bandeau semi-transparent en bas de l'image pour la lisibilité du texte
        bandeau_h = int(h * 0.24)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle([0, h - bandeau_h, w, h], fill=(0, 0, 0, 175))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        try:
            font_titre = ImageFont.truetype("arialbd.ttf", int(h * 0.045))
            font_texte = ImageFont.truetype("arial.ttf", int(h * 0.03))
        except Exception:
            font_titre = ImageFont.load_default()
            font_texte = ImageFont.load_default()

        y = h - bandeau_h + int(bandeau_h * 0.10)
        for i, ligne in enumerate(lignes):
            font = font_titre if (titre and i == 0) else font_texte
            largeur_car = max(15, int(w / max(1, font.size * 0.55)))
            sous_lignes = textwrap.wrap(ligne, width=largeur_car) or [""]
            for sous_ligne in sous_lignes:
                bbox = draw.textbbox((0, 0), sous_ligne, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(((w - tw) / 2, y), sous_ligne, font=font, fill=(255, 255, 255, 255))
                y += th + int(h * 0.012)
            y += int(h * 0.01)

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_b64}"

    except Exception as e:
        print(f"[AFFICHE ERROR] {e}")
        return None


def modifier_image_ia(chemin_image, instruction):
    """
    Modifie une image locale du PC selon une instruction en langage naturel, via le
    modèle d'édition d'image Gemini (image + instruction en entrée, image éditée en sortie).
    """
    try:
        from PIL import Image
        import google.genai as genai
        from core.config import GEMINI_API_KEY

        client = genai.Client(api_key=GEMINI_API_KEY)
        img = Image.open(chemin_image)

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[img, instruction],
        )

        if not response.candidates:
            return None

        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) is not None:
                mime = part.inline_data.mime_type or "image/png"
                img_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                return f"data:{mime};base64,{img_b64}"
        return None

    except Exception as e:
        print(f"[IMAGE EDIT ERROR] {e}")
        return None
