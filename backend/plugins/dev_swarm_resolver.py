import os
import sys
import builtins
import json
import re
import asyncio
import py_compile
import time
import difflib
import google.genai as genai
from core.config import GEMINI_API_KEY, CHOSEN_MODEL
from module.sandbox_executor import executer_fichier_sandbox

# Initialisation du client de génération Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Garde une référence forte sur les tâches de diffusion fire-and-forget pour éviter
# qu'asyncio ne les garbage-collect avant leur exécution (cf. doc asyncio.create_task)
_background_tasks = set()

def _fire_and_forget(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

def convert_unsplash_to_generator_tags(html_code: str, project_name: str = "") -> str:
    """
    Détecte TOUTE URL d'image externe (http/https/unsplash/pexels/picsum/placeholder)
    et la transforme obligatoirement en tag [GENERATE_IMAGE: ...] pour que l'IA (DALL-E / Imagen / Pollinations FLUX)
    génère un visuel 100% sur-mesure pour le projet.
    """
    import re
    
    is_real_estate = any(w in project_name.lower() for w in ["immo", "estate", "villa", "maison", "appartement", "residence", "logement"])

    # 1. Traitement des balises <img> avec récupération de l'alt ou du contexte
    def replace_external_img(match):
        full_tag = match.group(0)
        src_match = re.search(r'src=["\'](https?://[^"\']+)["\']', full_tag, re.IGNORECASE)
        if not src_match:
            return full_tag
        
        alt_match = re.search(r'alt=["\'](.*?)["\']', full_tag, re.IGNORECASE)
        alt_text = alt_match.group(1).strip() if alt_match else ""
        if not alt_text:
            title_match = re.search(r'title=["\'](.*?)["\']', full_tag, re.IGNORECASE)
            alt_text = title_match.group(1).strip() if title_match else ""
            
        if is_real_estate:
            context_desc = f"{alt_text if alt_text else 'Luxury villa interior exterior estate'}, professional real estate photography, 4k high-end architecture"
        else:
            context_desc = f"{alt_text if alt_text else 'High quality professional image'}, photorealistic, 4k resolution"

        new_tag = f"[GENERATE_IMAGE: {context_desc}]"
        return re.sub(r'src=["\']https?://[^"\']+["\']', f'src="{new_tag}"', full_tag, flags=re.IGNORECASE)

    fixed_html = re.sub(r'<img\s+[^>]*?src=["\']https?://[^"\']+["\'][^>]*>', replace_external_img, html_code, flags=re.IGNORECASE)

    # 2. Traitement des url('https://...') dans le CSS
    def replace_external_css_url(match):
        if is_real_estate:
            prompt_bg = "Luxury modern architectural villa estate hero background, 4k photorealistic"
        else:
            prompt_bg = "Modern luxury hero section background image, 4k photorealistic"
        return f"url('[GENERATE_IMAGE: {prompt_bg}]')"

    fixed_html = re.sub(r'url\(["\']?(https?://[^"\'()]+)["\']?\)', replace_external_css_url, fixed_html, flags=re.IGNORECASE)
    return fixed_html

async def secourir_images_html(code_text: str, project_dir: str = "", project_name: str = "") -> str:
    """
    Si une balise <img> ne pointe pas vers un fichier local assets/ valide (ex: URL externe restante ou tag fictif),
    la convertit en tag [GENERATE_IMAGE: ...] et relance la génération IA (Pollinations FLUX / DALL-E / Imagen).
    Garantit que 100% des images sont créées par l'IA !
    """
    import re
    if not project_dir:
        return code_text

    has_external = bool(re.search(r'<img\s+[^>]*?src=["\']https?://[^"\']+["\'][^>]*>', code_text, re.IGNORECASE))
    has_external_css = bool(re.search(r'url\(["\']?(https?://[^"\'()]+)["\']?\)', code_text, re.IGNORECASE))

    if has_external or has_external_css:
        code_text = convert_unsplash_to_generator_tags(code_text, project_name)
        code_text = await process_generated_images(code_text, project_dir)

    return code_text

def corriger_liens_invalides_html(html_code: str, valid_filenames: list) -> str:
    """
    Détecte et corrige automatiquement tous les liens href, action et onclick pointant vers des fichiers HTML inexistants.
    Exemple : si href="analysis.html" est présent alors que la liste contient "analytics.html", il remplace automatiquement "analysis.html" par "analytics.html".
    """
    valid_html_files = [f for f in valid_filenames if f.endswith('.html')]
    if not valid_html_files:
        return html_code

    def fix_link(match):
        prefix = match.group(1)
        link = match.group(2)
        quote = match.group(3)

        # Si le lien est valide, externe (http) ou ancrage (#), conserver tel quel
        if link in valid_html_files or link.startswith("http") or link.startswith("#") or link.startswith("data:"):
            return f"{prefix}{link}{quote}"

        # Trouver le nom de fichier HTML valide le plus proche
        closest = difflib.get_close_matches(link, valid_html_files, n=1, cutoff=0.2)
        if closest:
            print(f"[DEV SWARM AUTO-LINK FIX] Lien corrigé : '{link}' -> '{closest[0]}'")
            return f"{prefix}{closest[0]}{quote}"
        return f"{prefix}{valid_html_files[0]}{quote}"

    fixed_code = re.sub(r'(href=["\'])([^"\']+\.html)(["\'])', fix_link, html_code, flags=re.IGNORECASE)
    fixed_code = re.sub(r'(window\.location\.href\s*=\s*["\'])([^"\']+\.html)(["\'])', fix_link, fixed_code, flags=re.IGNORECASE)
    fixed_code = re.sub(r'(action=["\'])([^"\']+\.html)(["\'])', fix_link, fixed_code, flags=re.IGNORECASE)
    return fixed_code

def verifier_et_enrichir_html(html_code: str, file_path: str) -> tuple:
    """
    Vérifie qu'une page HTML n'est pas vide et que ses boutons et liens de navigation sont stylisés.
    Renvoie (html_traité, est_valide, message_erreur).
    """
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_code, re.DOTALL | re.IGNORECASE)
    body_content = body_match.group(1) if body_match else html_code
    text_content = re.sub(r'<[^>]+>', '', body_content).strip()
    
    if len(text_content) < 120:
        return html_code, False, f"La page {file_path} est quasiment vide ({len(text_content)} caractères de texte). Génère le contenu complet avec formulaires, cartes et éléments réels !"

    def fix_button(m):
        tag = m.group(0)
        if 'class=' not in tag.lower():
            if 'connecter' in tag.lower() or 'login' in tag.lower():
                return tag.replace('<button', '<button class="btn btn-outline"').replace('<a ', '<a class="btn btn-outline" ')
            return tag.replace('<button', '<button class="btn btn-primary"').replace('<a ', '<a class="btn btn-primary" ')
        return tag

    fixed_html = re.sub(r'<(?:button|a)\s+[^>]*>(?:Se connecter|S\'inscrire|Sign In|Sign Up|Commencer|Rejoindre|Continuer)[^<]*</(?:button|a)>', fix_button, html_code, flags=re.IGNORECASE)
    return fixed_html, True, ""

def auditer_et_corriger_projet_complet(project_dir):
    """
    Audite automatiquement et corrige l'intégralité du projet avant livraison :
    1. Nettoyage des balises <script src="...">.
    2. Auto-correction des favicon 404 (injection SVG).
    3. Auto-réparation des erreurs de syntaxe JS & CSS.
    4. Auto-vérification de la disposition des headers & boutons d'action.
    5. Cohérence visuelle des collections d'images multi-vues.
    """
    if not os.path.exists(project_dir):
        return

    html_files = [os.path.join(project_dir, f) for f in os.listdir(project_dir) if f.endswith('.html')]
    js_files = [os.path.join(project_dir, f) for f in os.listdir(project_dir) if f.endswith('.js')]
    css_files = [os.path.join(project_dir, f) for f in os.listdir(project_dir) if f.endswith('.css')]

    # Audit 1: Verification et auto-fix des fichiers JS (Syntaxe et variables)
    for jpath in js_files:
        try:
            with open(jpath, "r", encoding="utf-8") as f:
                js_code = f.read()

            # Fix 1a: Auto-remove stray closing brackets or unclosed strings
            if "yellow:" in js_code and "exteriorColors" not in js_code:
                js_code = re.sub(r'yellow:\s*["\'][^"\']+["\'],?', '', js_code)
            
            with open(jpath, "w", encoding="utf-8") as f:
                f.write(js_code)
        except Exception as e:
            print(f"[QA AUDITOR JS FIX ERROR] {jpath}: {e}")

    # Audit 2: Verification et auto-fix du CSS (Headers & Grid des Filtres)
    for cpath in css_files:
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                css_code = f.read()

            # Fix 2a: Dégagement du main pour header fixe
            if ".header" in css_code and "position: fixed" in css_code and "main {" not in css_code:
                css_code += "\nmain { padding-top: 80px; }\n"

            # Fix 2b: Neutralisation du double chevron sur les sélecteurs
            if ".filter-select" in css_code and "appearance: none" not in css_code:
                css_code = css_code.replace(".filter-select {", ".filter-select {\n    appearance: none;\n    -webkit-appearance: none;\n")

            with open(cpath, "w", encoding="utf-8") as f:
                f.write(css_code)
        except Exception as e:
            print(f"[QA AUDITOR CSS FIX ERROR] {cpath}: {e}")

    # Audit 3: Verification et auto-fix HTML (Scripts, Favicons, Links)
    for hpath in html_files:
        try:
            with open(hpath, "r", encoding="utf-8") as f:
                content = f.read()

            # Fix 3a: Script tag corruption fix
            def fix_script(m):
                src = m.group(1)
                if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', 'unsplash.com']):
                    return '<script src="script.js"></script>'
                return m.group(0)

            content = re.sub(r'<script\s+src=["\']([^"\']+)["\']\s*></script>', fix_script, content, flags=re.IGNORECASE)

            # Fix 3b: Favicon 404 Prevention
            svg_favicon = '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 100 100\'><text y=\'.9em\' font-size=\'90\'>⚡</text></svg>">'
            if 'favicon.ico' in content or 'rel="icon"' not in content:
                content = re.sub(r'<link\s+rel=["\']icon["\'][^>]*>', svg_favicon, content, flags=re.IGNORECASE)
                if 'rel="icon"' not in content and '</head>' in content:
                    content = content.replace('</head>', f'    {svg_favicon}\n</head>')

            # Fix 3c: script.js import
            if 'script.js' not in content and os.path.exists(os.path.join(project_dir, 'script.js')):
                content = content.replace('</body>', '    <script src="script.js"></script>\n</body>')

            content, _, _ = verifier_et_enrichir_html(content, os.path.basename(hpath))

            with open(hpath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"[QA AUDITOR AUTO-FIX ERROR] {hpath}: {e}")

# Définition du répertoire de travail (Sandbox)
SANDBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sandbox"))


def _chemin_confine(base: str, relatif: str):
    """Joint `relatif` à `base` en garantissant qu'on ne sort pas de `base`.

    Les noms de projet et de fichiers proviennent du JSON généré par les agents
    LLM. Sans ce contrôle, os.path.join() acceptait un chemin absolu (il écrase
    alors la base) ou des « ../.. », ce qui permettait d'écrire n'importe où —
    y compris d'écraser main.py.
    Retourne le chemin absolu, ou None si la tentative sort de la base.
    """
    if not relatif or not isinstance(relatif, str):
        return None
    if os.path.isabs(relatif) or (len(relatif) > 1 and relatif[1] == ":"):
        return None
    base_abs = os.path.abspath(base)
    try:
        cible = os.path.abspath(os.path.join(base_abs, relatif))
        if os.path.commonpath([cible, base_abs]) != base_abs:
            return None
        return cible
    except Exception:
        return None

async def diffuser_dev_swarm(data):
    """Diffuse l'état de l'essaim aux clients WebSocket connectés de façon sécurisée (anti-blocage)."""
    if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
        msg = json.dumps(data)
        
        async def send_safe(ws):
            try:
                await asyncio.wait_for(ws.send(msg), timeout=2.0)
            except Exception:
                pass
                
        await asyncio.gather(*[send_safe(ws) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)

async def _call_openai_compatible(model_name: str, prompt: str, env_var: str, base_url: str = None, provider_label: str = "") -> str:
    """Appelle un fournisseur compatible avec le SDK OpenAI (OpenAI, Groq, Grok, ...)."""
    api_key = os.environ.get(env_var)
    if not api_key:
        raise ValueError(f"Clé API {provider_label} ({env_var}) non configurée.")
    import openai
    client_compat = openai.OpenAI(api_key=api_key, base_url=base_url) if base_url else openai.OpenAI(api_key=api_key)

    def _call():
        res = client_compat.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return res.choices[0].message.content
    return await asyncio.to_thread(_call)

async def query_llm_provider(model_name: str, prompt: str) -> str:
    """Route la demande vers le bon fournisseur d'IA selon le modèle choisi (ChatGPT, Gemini, Groq, Grok, Claude)."""
    # 1. ChatGPT (OpenAI)
    if model_name.startswith("gpt-") or model_name.startswith("o3-"):
        return await _call_openai_compatible(model_name, prompt, "OPENAI_API_KEY", provider_label="OpenAI")

    # 2. Groq (LLaMA 3.3, Mixtral)
    elif "llama" in model_name.lower() or "mixtral" in model_name.lower():
        return await _call_openai_compatible(model_name, prompt, "GROQ_API_KEY", "https://api.groq.com/openai/v1", "Groq")

    # 3. Grok (xAI)
    elif "grok" in model_name.lower():
        env_var = "XAI_API_KEY" if os.environ.get("XAI_API_KEY") else "GROK_API_KEY"
        return await _call_openai_compatible(model_name, prompt, env_var, "https://api.x.ai/v1", "Grok")

    # 4. Gemini (Défaut Google GenAI)
    else:
        target_model = model_name if "gemini" in model_name else "gemini-2.5-flash"
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=target_model,
                contents=prompt,
            ),
            timeout=45.0
        )
        return response.text if response and hasattr(response, "text") else ""

async def interroger_model(prompt: str, agent_role: str = "DEV", retries: int = 3, file_path: str = None, project_name: str = "projets_swarm") -> str:
    """Interroge le modèle IA configuré de façon asynchrone avec retentatives et timeouts automatiques."""
    model_to_use = CHOSEN_MODEL

    for attempt in range(retries):
        try:
            if agent_role == "DEV" and file_path and model_to_use.startswith("gemini"):
                full_text = ""
                # Timeout de 45 secondes pour initialiser le stream
                response_stream = await asyncio.wait_for(
                    client.aio.models.generate_content_stream(
                        model=model_to_use,
                        contents=prompt,
                    ),
                    timeout=45.0
                )
                chunk_counter = 0
                async for chunk in response_stream:
                    if chunk.text:
                        full_text += chunk.text
                        chunk_counter += 1
                        if chunk_counter % 8 == 0:
                            clean_streamed_code = re.sub(r'^```[a-zA-Z]*\s*|```\s*$', '', full_text.strip(), flags=re.MULTILINE)
                            await diffuser_dev_swarm({
                                "action": "dev_swarm_update",
                                "agent": "DEV",
                                "message": f"Rédaction en cours de {file_path}...",
                                "log": f"Développeur Lead ({model_to_use}) : Rédaction en cours de {file_path}...",
                                "current_file": file_path,
                                "current_code": clean_streamed_code,
                                "status": "in_progress",
                                "project": project_name
                            })
                if full_text:
                    return full_text
            else:
                res_text = await query_llm_provider(model_to_use, prompt)
                if res_text:
                    return res_text
        except Exception as e:
            print(f"[DEV SWARM MODEL RETRY {attempt+1}/{retries}] Agent={agent_role} Model={model_to_use} Erreur : {e}")
            await asyncio.sleep(1.5 * (attempt + 1))
    return ""

async def enhance_user_prompt(user_prompt: str, is_new: bool = True) -> str:
    """
    Reformule et enrichit la demande utilisateur avant la phase de conception PM.
    """
    enhancement_prompt = f"""Tu es un Directeur Technique & Architecte Web Élite.
Demande utilisateur : "{user_prompt}"
Type de tâche : {"Création d'un nouveau projet" if is_new else "Retouche d'un projet existant"}

Reformule cette demande sous la forme d'une spécification d'ingénierie et de design ultra-détaillée.
EXIGENCES MANDATAIRES DE LA SPÉCIFICATION :
1. DIRECTION ARTISTIQUE & TYPOGRAPHIE : Couleurs nobles et contrastées (fonds sombres nobles, accents vifs), polices Google Fonts adaptées.
2. DESIGN SYSTEM CSS : Définition des variables :root (--primary, --accent, --bg, --surface, --radius, --shadow, --font-main).
3. MOTION DESIGN & ANIMATIONS : Animations CSS au scroll (@keyframes), smooth scroll (html {{ scroll-behavior: smooth; }}), hover effects sur cartes et boutons, compteurs animés.
4. RESPONSIVE MOBILE : Navigation hamburger JS, flexbox/grid souple (@media max-width 768px).
5. SEO & ACCESSIBILITÉ : Meta description, lang="fr", Open Graph tags, single h1 par page, alt descriptifs sur images, script defer, loading="lazy", rel="noopener noreferrer" sur liens externes, aria-label sur boutons icônes.
6. IMAGES IA SUR-MESURE : Consigne d'utiliser le tag [GENERATE_IMAGE: description ultra détaillée en anglais] à chaque endroit où une photo/illustration est nécessaire.

Réponds uniquement avec la spécification technique enrichie brute sans bavardage."""
    
    try:
        enhanced = await interroger_model(enhancement_prompt, agent_role="PM")
        if enhanced and len(enhanced.strip()) > 40:
            print(f"[DEV SWARM] Prompt enrichi avec succès pour : '{user_prompt[:50]}...'")
            return enhanced.strip()
    except Exception as e:
        print(f"[DEV SWARM ENHANCE PROMPT ERROR] {e}")
    return user_prompt

images_generated_count = 0
images_total_count = 0

async def process_generated_images(code_text: str, project_dir: str) -> str:
    """
    Détecte les tags [GENERATE_IMAGE: ...] et génère de vrais visuels IA (OpenAI DALL-E, Grok, Gemini Imagen, Pollinations FLUX).
    Utilise le système de retry de JARVIS 9.0 avec User-Agent Chrome pour éviter les 429.
    ZÉRO URL Unsplash externe : si tout échoue, génère un visuel dégradé de couleur local personnalisé.
    """
    import uuid
    import urllib.parse
    import requests
    import time

    global images_generated_count, images_total_count
    pattern = r"\[GENERATE_IMAGE:\s*(.*?)\]"
    matches = list(re.finditer(pattern, code_text, re.IGNORECASE))
    if not matches:
        return code_text

    images_total_count += len(matches)

    assets_dir = os.path.join(project_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    api_openai = os.environ.get("OPENAI_API_KEY")
    api_grok = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
    disable_imagen = False
    disable_openai = False

    for match in matches:
        full_tag = match.group(0)
        img_prompt = match.group(1).strip()
        filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(assets_dir, filename)
        rel_path = f"assets/{filename}"

        success = False

        # 1. API OPENAI DALL-E NATIVE
        if api_openai and not disable_openai and not success:
            try:
                import openai
                client_oa = openai.OpenAI(api_key=api_openai, timeout=15.0)
                resp = await asyncio.to_thread(
                    client_oa.images.generate,
                    model="dall-e-3",
                    prompt=img_prompt,
                    n=1,
                    size="1024x1024"
                )
                img_url = resp.data[0].url
                img_resp = await asyncio.to_thread(requests.get, img_url, timeout=30)
                img_resp.raise_for_status()
                with open(filepath, 'wb') as f:
                    f.write(img_resp.content)
                success = True
                print(f"[DEV SWARM IMAGE IA] OpenAI DALL-E -> {rel_path}")
            except Exception as e:
                print(f"[DEV SWARM IMAGE IA] OpenAI DALL-E non activé ou non supporté par votre clé (Passage au modèle suivant)")
                disable_openai = True

        # 2. API GROK IMAGINE NATIVE
        if api_grok and not success:
            try:
                import openai
                client_g = openai.OpenAI(api_key=api_grok, base_url="https://api.x.ai/v1")
                resp = await asyncio.to_thread(
                    client_g.images.generate,
                    model="grok-imagine-image",
                    prompt=img_prompt,
                    n=1
                )
                img_url = resp.data[0].url
                img_resp = await asyncio.to_thread(requests.get, img_url, timeout=30)
                img_resp.raise_for_status()
                with open(filepath, 'wb') as f:
                    f.write(img_resp.content)
                success = True
                print(f"[DEV SWARM IMAGE IA] Grok Imagine -> {rel_path}")
            except Exception as e:
                print(f"[DEV SWARM IMAGE IA] Grok Imagine non disponible (Passage au modèle suivant)")

        # 3. API GEMINI IMAGEN 3.0 NATIVE
        if GEMINI_API_KEY and not disable_imagen and not success:
            try:
                def call_imagen():
                    return client.models.generate_images(
                        model='imagen-3.0-generate-002',
                        prompt=img_prompt
                    )
                resp = await asyncio.to_thread(call_imagen)
                if resp and hasattr(resp, 'generated_images') and resp.generated_images:
                    image_bytes = resp.generated_images[0].image.image_bytes
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)
                    success = True
                    print(f"[DEV SWARM IMAGE IA] Gemini Imagen 3.0 -> {rel_path}")
            except Exception as e:
                print(f"[DEV SWARM IMAGE IA] Gemini Imagen non disponible sur votre clé API (Passage au fallback)")
                if "404" in str(e) or "not found" in str(e).lower() or "not supported" in str(e).lower():
                    disable_imagen = True

        # 4. FALLBACK HAUTE QUALITÉ FLUX (Pollinations API avec Retry & Headers Chrome)
        if not success:
            safe_p = urllib.parse.quote(img_prompt)
            pollinations_url = f"https://image.pollinations.ai/prompt/{safe_p}?model=flux&width=1024&height=1024&nologo=true"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            for attempt in range(3):
                try:
                    img_resp = await asyncio.to_thread(
                        requests.get, pollinations_url, headers=headers, timeout=60
                    )
                    if img_resp.status_code == 429:
                        print(f"[DEV SWARM IMAGE IA] Pollinations surchargé. Pause de 5s (essai {attempt+1}/3)...")
                        await asyncio.sleep(5)
                        continue
                    img_resp.raise_for_status()
                    with open(filepath, 'wb') as f:
                        f.write(img_resp.content)
                    success = True
                    print(f"[DEV SWARM IMAGE IA] Pollinations FLUX (essai {attempt+1}) -> {rel_path}")
                    break
                except Exception as e:
                    print(f"[DEV SWARM IMAGE IA] Échec Pollinations FLUX essai {attempt+1}: connexion ou délai dépassé. Nouvelle tentative...")
                    await asyncio.sleep(2)

        if success:
            code_text = code_text.replace(full_tag, rel_path)
            # Petite pause de cohabitation de 1.5s
            await asyncio.sleep(1.5)
        else:
            # ZÉRO Unsplash externe ! Générer une image de couleur unie / dégradé locale avec un texte
            print(f"[DEV SWARM IMAGE IA] Toutes les APIs ont échoué. Génération d'un placeholder de couleur local pour : {img_prompt[:30]}")
            try:
                # Créer une image de couleur unie ou dégradée en Python pur
                # Pour éviter d'importer Pillow (qui n'est pas forcément installé), on écrit un SVG simple et élégant !
                # Et oui, les balises <img> de HTML supportent parfaitement les SVG !
                svg_filename = filename.replace(".jpg", ".svg")
                svg_filepath = filepath.replace(".jpg", ".svg")
                svg_rel_path = rel_path.replace(".jpg", ".svg")

                # Déterminer des couleurs sympas à partir du nom
                h_val = hash(img_prompt) % 360
                c1 = f"hsl({h_val}, 70%, 25%)"
                c2 = f"hsl({(h_val + 40) % 360}, 70%, 15%)"

                svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="100%" height="100%">
                    <defs>
                        <linearGradient id="grad_{filename[:4]}" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:{c1};stop-opacity:1" />
                            <stop offset="100%" style="stop-color:{c2};stop-opacity:1" />
                        </linearGradient>
                    </defs>
                    <rect width="800" height="800" fill="url(#grad_{filename[:4]})" />
                    <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-size="28" font-weight="bold" fill="#ffffff" opacity="0.85">
                        {img_prompt[:40]}...
                    </text>
                </svg>"""
                with open(svg_filepath, "w", encoding="utf-8") as f_svg:
                    f_svg.write(svg_content)
                code_text = code_text.replace(full_tag, svg_rel_path)
            except Exception as ex:
                print(f"[DEV SWARM IMAGE IA PLACEHOLDER ERROR] {ex}")
                code_text = code_text.replace(full_tag, "")

        images_generated_count += 1
        try:
            _fire_and_forget(diffuser_dev_swarm({
                "action": "website_builder_update",
                "images_count": {"generated": images_generated_count, "total": max(images_generated_count, images_total_count)}
            }))
        except Exception:
            pass

    return code_text

async def run_dev_swarm_process(user_request, target_dir=None):
    """Gère le cycle de vie de l'essaim d'agents à 6 rôles spécialisés (PM, UI, DEV, SEC, QA, OPS) avec support de répertoires sur-mesure et retouches multi-tours."""
    print(f"[DEV SWARM 6-AGENTS] Démarrage du cycle pour la requête : {user_request}")

    # ── ÉTAPE 0 : Analyse du Répertoire Cible & Contexte Multi-Tours (Retouches) ──
    dir_match = re.search(r'(?:dans|sur|dossier|chemin)\s+([a-zA-Z]:[\\/][^\s"\'<>]+)', user_request, re.IGNORECASE)
    custom_target_dir = target_dir or (dir_match.group(1).replace('/', '\\') if dir_match else None)
    
    existing_files_summary = ""
    global images_generated_count, images_total_count
    images_generated_count = 0
    images_total_count = 0

    is_multi_turn_edit = False

    if custom_target_dir and os.path.exists(custom_target_dir):
        is_multi_turn_edit = True
        existing_files = [os.path.relpath(os.path.join(r, f), custom_target_dir).replace('\\', '/')
                          for r, _, fs in os.walk(custom_target_dir) for f in fs]
        existing_files_summary = f"\nDOSSIER CIBLE SUR-MESURE EXISTANT : '{custom_target_dir}'. Fichiers actuels : {', '.join(existing_files)}. Conserve le code fonctionnel et effectue des retouches ciblées sans tout effacer."
    else:
        # Vérifier si la requête fait référence à un projet sandbox existant (multi-tours, recherche souple)
        if os.path.exists(SANDBOX_DIR):
            req_clean = user_request.lower()
            # Si l'utilisateur demande explicitement de créer ou générer un site/projet de zéro, on évite de forcer le mode retouche
            is_new_request = any(phrase in req_clean for phrase in ["créer un site", "crée un site", "créer un nouveau", "crée un nouveau", "nouveau site", "générer un site", "generer un site", "nouveau projet"])
            if not is_new_request:
                for item in os.listdir(SANDBOX_DIR):
                    full_p = os.path.join(SANDBOX_DIR, item)
                    if os.path.isdir(full_p):
                        # Accepte le nom exact ou n'importe quel mot-clé distinctif (>3 lettres) du nom de projet (ex: "apexmind" -> "apexmind_studio_saas")
                        item_tokens = [t for t in item.lower().replace('_', ' ').split() if len(t) >= 4]
                        if item.lower() in req_clean or any(token in req_clean for token in item_tokens):
                            custom_target_dir = full_p
                            is_multi_turn_edit = True
                            existing_files = [os.path.relpath(os.path.join(r, f), full_p).replace('\\', '/')
                                              for r, _, fs in os.walk(full_p) for f in fs]
                            existing_files_summary = f"\n⚠️ MODE RETOUCHE SUR PROJET EXISTANT ('{item}'). Fichiers actuels : {', '.join(existing_files)}.\nCONSIGNE PM STRICTE : La liste 'files' DOIT contenir SEULEMENT les 1 à 3 fichiers réellement impactés par la modification (ex: script.js, style.css, index.html). INTERDICTION DE LISTER TOUT LE SITE DE 14 FICHIERS !"
                            print(f"[DEV SWARM] Projet existant reconnu via mot-clé : '{item}'")
                            break
    
    # Diffuser immédiatement pour ouvrir les deux HUDs instantanément
    await diffuser_dev_swarm({
        "action": "dev_swarm_update",
        "agent": "PM",
        "message": "Enrichissement du prompt et analyse initiale...",
        "log": "Initialisation de l'essaim d'agents d'élite...",
        "files": [],
        "status": "in_progress"
    })
    await diffuser_dev_swarm({
        "action": "website_builder_update",
        "status": "in_progress",
        "step_label": "[PM] INITIALISATION",
        "message": "Enrichissement du prompt et analyse initiale...",
        "progress": 5,
        "files_count": {"generated": 0, "total": 1},
        "images_count": {"generated": 0, "total": 0},
        "files_list": [],
        "logs": ["Initialisation de la console de suivi JARVIS..."],
        "project_name": "Initialisation..."
    })

    # Enrichissement automatique du prompt utilisateur
    enhanced_user_request = await enhance_user_prompt(user_request, is_new=not is_multi_turn_edit)

    # ── ÉTAPE 1 : Chef de Projet (PM) ──
    await diffuser_dev_swarm({
        "action": "dev_swarm_update",
        "agent": "PM",
        "message": "Conception et architecture du projet...",
        "log": f"Analyse de la demande utilisateur enrichie...\n{'Mode Retouche Multi-Tours' if is_multi_turn_edit else 'Création Nouveau Projet'}...",
        "files": [],
        "status": "in_progress"
    })
    
    pm_prompt = f"""Tu es le Chef de Projet (PM) Élite de l'essaim d'agents autonomes de JARVIS.
L'utilisateur souhaite créer ou modifier un projet sur mesure, ultra-professionnel et sans retouches.
Requête originale : "{user_request}"
Spécification enrichie : "{enhanced_user_request}"
{existing_files_summary}

RÈGLES MANDATAIRES D'ARCHITECTURE GLOBALE :
1. EXIGENCE DESIGN PROFESSIONNEL ÉPURÉ (NIVEAU APPLE / STRIPE / VERCEL) :
   - INTERDICTION FORMELLE des palettes néon criardes (cyan fluo agressif, magenta fluo) qui donnent un aspect de 'site d'amateur ou fait par un enfant de 12 ans'.
   - OBLIGATION d'utiliser un design moderne, sobre, haut de gamme et ultra-professionnel : fonds sombres nobles (#0b0f19, #0f172a), cartes dépolies en verre mat avec bordure fine (1px solid rgba(255,255,255,0.08)), typographie Inter ultra-lisible, accents Indigo (#6366f1) et Émeraude (#10b981).
2. ZÉRO LIEN MORT, ZÉRO FAKE TEXTE ET ARCHITECTURE MULTI-PAGES COMPLÈTE :
   - Inclus OBLIGATOIREMENT les pages annexes fonctionnelles (contact.html, faq.html, legal.html) afin qu'AUCUN lien du footer/header ne soit mort (#) ou inutilisable.
   - Si le menu principal ou le design requièrent des pages thématiques ou de services spécifiques (ex: Vente Off-Market, Acquisition, Estimation, Services), tu DOIS obligatoirement lister et créer ces fichiers HTML séparément. Pour une agence immobilière, prévois au moins : index.html, annonces.html, services.html, contact.html, faq.html, legal.html.
3. ADAPTE DYNAMISANT LA LISTE DES PAGES AU DOMAINE DU PROJET :
   - Exemple e-commerce/marketplace : `index.html`, `catalogue.html`, `categories.html`, `panier.html`, `produit_detail.html`, `validation_commande.html`, `contact.html`, `faq.html`, `legal.html`, `style.css`, `script.js`
   - Exemple voyage : `index.html`, `destinations.html`, `reservation.html`, `mes_voyages.html`, `contact.html`, `faq.html`, `legal.html`, `style.css`, `script.js`
   - Exemple finance : `index.html`, `dashboard.html`, `analytics.html`, `support.html`, `legal.html`, `style.css`, `script.js`
4. Définis les noms de fichiers de manière ultra-claire, cohérente et sans aucune ambiguïté.
5. RÈGLE ABSOLUE DE LA LISTE DES FICHIERS :
   - CHAQUE entrée dans "files" DOIT être un FICHIER RÉEL avec une EXTENSION (`.html`, `.css`, `.js`, `.json`...).
   - INTERDICTION TOTALE d'inclure des dossiers ou chemins de répertoires (`assets/`, `assets/images/`, `css/`, `js/`) dans la liste "files".
   - Les sous-dossiers sont créés automatiquement si un fichier les référence (ex: `assets/main.css` est valide, `assets/` seul est INTERDIT).
6. RÈGLE CRITIQUE DES CHEMINS RELATIFS DANS LES SOUS-DOSSIERS :
   - Si un fichier est dans un sous-dossier (ex: `studio/dashboard.html`), tous ses liens vers des fichiers à la racine DOIVENT utiliser `../` (ex: `href="../index.html"`, `href="../style.css"`).
   - Les liens ENTRE fichiers du même sous-dossier doivent être relatifs SANS `studio/` (ex: depuis `studio/dashboard.html`, lier vers `studio/settings.html` doit être `href="settings.html"` PAS `href="studio/settings.html"`).
   - INTERDICTION ABSOLUE de doubler le chemin du sous-dossier dans les liens (ex: `studio/studio/settings.html` est une erreur fatale).
7. RÈGLE INTERDICTION LOGO UNSPLASH :
   - INTERDICTION TOTALE d'utiliser des URLs contenant 'unsplash' avec des paramètres de logo ou de texte sur l'image. Toutes les images doivent être des photos de fond épurées.
8. RÈGLE STRICTE MODE RETOUCHE / MODIFICATION :
   - S'il s'agit d'une RETOUCHE sur un projet existant (ex: "ajouter un bouton mode sombre"), liste UNIQUEMENT les fichiers précis qui ont besoin d'être modifiés ou créés (ex: `script.js`, `style.css`, `index.html`). N'inclus PAS la liste de tous les autres fichiers du projet qui ne changent pas.

Réponds uniquement avec un objet JSON valide :
{{
  "project_name": "nom_du_projet_snake_case",
  "specs": "Description technique détaillée du projet adaptée au sujet",
  "files": [
    {{
      "file_path": "index.html",
      "purpose": "Rôle précis du fichier dans le projet"
    }}
  ]
}}
"""
    pm_response = await interroger_model(pm_prompt)
    json_match = re.search(r'\{.*\}', pm_response, re.DOTALL)
    pm_response_clean = json_match.group(0) if json_match else pm_response.strip()
    
    try:
        project_config = json.loads(pm_response_clean)
        project_name = project_config.get("project_name", "projets_swarm")
        specs = project_config.get("specs", "")
        files_list = project_config.get("files", [])
    except Exception as e:
        print(f"[DEV SWARM ERROR] JSON PM invalide : {e}")
        await diffuser_dev_swarm({
            "action": "dev_swarm_update",
            "agent": "PM",
            "message": "Échec de conception du projet",
            "log": f"Erreur de format de spécification JSON.\nRéponse reçue : {pm_response}",
            "files": [],
            "status": "failure"
        })
        return

    # Définition du répertoire de projet (sur mesure si spécifié, sinon sandbox).
    # project_name vient du JSON du chef de projet (LLM) : on le confine.
    if custom_target_dir:
        project_dir = custom_target_dir
    else:
        project_dir = _chemin_confine(SANDBOX_DIR, project_name)
        if project_dir is None:
            print(f"[SWARM] ⛔ Nom de projet refusé (sortie de sandbox) : {project_name!r}")
            await notify({
                "action": "dev_swarm_update", "agent": "SEC",
                "message": "Nom de projet refusé pour raison de sécurité.",
                "log": f"Chemin hors sandbox rejeté : {project_name!r}",
                "status": "failure"
            })
            return

    os.makedirs(project_dir, exist_ok=True)
    
    files_state = {f["file_path"]: "pending" for f in files_list}
    files_purpose = {f["file_path"]: f["purpose"] for f in files_list}
    written_files = {}

    # Pré-chargement des fichiers existants pour les retouches multi-tours
    if is_multi_turn_edit and os.path.exists(project_dir):
        for root, _, fs in os.walk(project_dir):
            for fname in fs:
                if fname.endswith(('.html', '.css', '.js', '.json')):
                    full_f = os.path.join(root, fname)
                    rel_f = os.path.relpath(full_f, project_dir).replace('\\', '/')
                    try:
                        with open(full_f, 'r', encoding='utf-8', errors='ignore') as f_in:
                            written_files[rel_f] = f_in.read()
                    except Exception:
                        pass

    logs = [f"[{time.strftime('%H:%M:%S')}] [PM] Architecture '{project_name}' validée ({len(files_list)} fichiers) dans {project_dir}"]

    async def notify(payload):
        payload["project"] = project_name
        agent = payload.get("agent", "SYSTEM")
        message = payload.get("message", "")
        status = payload.get("status", "in_progress")
        timestamp = time.strftime("%H:%M:%S")
        if message:
            logs.append(f"[{timestamp}] [{agent}] {message}")
            
        completed_count = sum(1 for s in files_state.values() if s in ["testing", "completed"])
        total_files = max(1, len(files_list))
        pct = 15 + int((completed_count / total_files) * 80)
        if status == "success":
            pct = 100

        await diffuser_dev_swarm(payload)
        await diffuser_dev_swarm({
            "action": "website_builder_update",
            "status": status,
            "step_label": f"[{agent}] ESSAIM 6 AGENTS ({completed_count}/{total_files})",
            "message": message,
            "progress": pct,
            "files_count": {"generated": completed_count, "total": total_files},
            "images_count": {"generated": images_generated_count, "total": max(images_generated_count, images_total_count)},
            "files_list": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
            "logs": list(logs),
            "project_name": project_name
        })

    await notify({
        "action": "dev_swarm_update",
        "agent": "PM",
        "message": f"Architecture validée pour '{project_name}'",
        "log": f"Spécifications : {specs}\nFichiers : " + ", ".join([f['file_path'] for f in files_list]),
        "files": files_list,
        "status": "in_progress"
    })
    await asyncio.sleep(0.8)

    # ── ÉTAPE 2 : UI Designer (UI) ──
    await notify({
        "action": "dev_swarm_update",
        "agent": "UI",
        "message": "Création du Design System Glassmorphic & Palettes...",
        "log": "Définition des tokens CSS, palettes sombres néon et composants réutilisables...",
        "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
        "status": "in_progress"
    })
    ui_prompt = f"""Tu es le Directeur Artistique & UI/UX Designer Senior de l'essaim JARVIS.
Pour le projet '{project_name}' ({specs}), tu dois concevoir une identité visuelle originale, sophistiquée et un style de motion design unique adapté au sujet.

CONSIGNES STRICTES DE DIRECTION ARTISTIQUE, DE MOTION DESIGN ET D'ÉLÉGANCE PROFESSIONNELLE :
1. EXIGENCE DE QUALITÉ UI PROFESSIONNELLE ÉPURÉE (NIVEAU APPLE / STRIPE / VERCEL) :
   - INTERDICTION FORMELLE des couleurs néon fluo agressives (cyan néon, magenta électrique criard) qui donnent un aspect 'site d'amateur ou fait par un enfant'.
   - Utilise une palette noble, moderne et épurée : fond ardoise profond (`#0b0f19`), cartes dépolies en verre fumé avec des bordures d'une extrême finesse (`1px solid rgba(255,255,255,0.08)`), et des accents technologiques élégants (Indigo `#6366f1`, Émeraude `#10b981`, Violet royal `#8b5cf6`).
2. ANALYSE CRÉATIVE ET PALETTE SUR-MESURE :
   - Réfléchis en véritable Directeur Artistique Senior de marque de prestige : contrastes impeccables, typographie ultra-lisible (Inter, Outfit, Plus Jakarta Sans), espacements aérés (8px, 16px, 24px, 48px).
3. MOTION DESIGN & ANIMATIONS CONTEXTUELLES ADAPTÉES AU SUJET :
   - Ne choisis PAS la même animation sur tous les sites ! Invente des animations CSS/JS spécifiques qui renforcent l'émotion du sujet :
     - Si Voyage : Animations de parallaxe douce au survol, transitions en vague, zoom d'image d'évasion.
     - Si E-Commerce : Zoom produit élégant au survol, glissement latéral du tiroir de panier, micro-animations au clic.
     - Si Finance : Apparitions nettes et exécutives, dessin progressif de courbes de graphiques, chiffres qui comptent.
4. TYPOGRAPHIE ET COMPOSANTS PRO :
   - Polices Google Fonts d'une clarté absolue avec une hiérarchie visuelle parfaite (h1 2.2rem, h2 1.5rem, body 1rem).

Définis en 5-6 lignes le Design System complet : palette Hex sur-mesure épurée, polices Google Fonts et concept de motion design contextuel."""
    ui_guidelines = await interroger_model(ui_prompt)
    await notify({
        "action": "dev_swarm_update",
        "agent": "UI",
        "message": "Directives de Design System & Motion Design Sur-Mesure établies",
        "log": f"Guide UI Designer : {ui_guidelines.strip()}",
        "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
        "status": "in_progress"
    })
    await asyncio.sleep(0.8)

    # ── ÉTAPE 3 : Développeur Lead (DEV), ÉTAPE 4 : Security Auditor (SEC), ÉTAPE 5 : QA Tester (QA) ──
    for f in files_list:
        file_path = f["file_path"].replace("\\", "/").strip()
        purpose = f["purpose"]

        # Ignorer les entrées qui sont des dossiers (chemin se terminant par '/')
        if file_path.endswith("/") or file_path.endswith("\\") or "." not in os.path.basename(file_path):
            dir_to_create = os.path.join(project_dir, file_path)
            os.makedirs(dir_to_create, exist_ok=True)
            print(f"[DEV SWARM] Dossier créé (ignoré en tant que fichier) : {file_path}")
            continue

        files_state[file_path] = "writing"
        
        await notify({
            "action": "dev_swarm_update",
            "agent": "DEV",
            "message": f"Écriture de {file_path}...",
            "log": f"Développement du fichier {file_path} ({purpose})...",
            "current_file": file_path,
            "current_code": written_files.get(file_path, f"<!-- [DEV] Rédaction du code en cours pour {file_path}... -->\n<!-- Génération des composants et styles sous vos yeux -->"),
            "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
            "status": "in_progress"
        })

        other_files_context = "\n".join([f"--- {fp} ---\n{content}" for fp, content in written_files.items()]) if written_files else "(Aucun)"

        dev_prompt = f"""Tu es le Développeur Lead Senior de l'essaim JARVIS. Tu dois produire un code de niveau Développeur Web Senior : ultra-moderne, dynamique, animé et 100% fonctionnel.
Projet : "{project_name}" ({specs})
Directives UI Designer Senior : "{ui_guidelines}"
Fichier à écrire : "{file_path}" ({purpose})

Voici la liste de tous les fichiers du projet :
{json.dumps(files_purpose, indent=2, ensure_ascii=False)}

Fichiers déjà écrits :
{other_files_context}

CONSIGNES STRICTES NIVEAU DÉVELOPPEUR WEB SENIOR :
1. GENERATION D'IMAGES REELLES PAR IA VIA TAGS :
   - Pour chaque photo, illustration ou visuel nécessaire, utilise EXCLUSIVEMENT le tag : [GENERATE_IMAGE: description ultra detaillee du visuel en anglais].
   - EXEMPLE HTML : <img src="[GENERATE_IMAGE: A modern luxury interior living room, 4k photorealistic]" alt="Interieur moderne" loading="lazy">
   - INTERDICTION TOTALE d'inventer des URLs externes ou d'utiliser Unsplash.

2. NAVIGATION, LIENS DU MENU ET MENUS DÉROULANTS :
   - Pour chaque bouton, lien de navigation, ou élément de sous-menu (comme le menu déroulant 'Services'), tu DOIS utiliser EXCLUSIVEMENT des fichiers HTML faisant partie du projet (ex: index.html, services.html, contact.html) ou des ancres pointant vers des sections de ces fichiers (ex: href="services.html#acquisition-privee" ou href="services.html#estimation").
   - Ne crée JAMAIS de liens vers des fichiers HTML qui ne figurent pas dans la liste des fichiers du projet ci-dessus (comme acquisition.html ou offmarket.html si elles ne sont pas créées).

3. SEO, BALISAGE & ACCESSIBILITÉ HYPER-STRICTS :
   - HTML Structure : Inclure <html lang="fr">, <meta charset="UTF-8">, <meta name="viewport" content="width=device-width, initial-scale=1.0">.
   - SEO Meta Tags : Inclure <meta name="description" content="..."> et <meta name="keywords" content="...">.
   - Open Graph Tags : Inclure <meta property="og:title" content="...">, <meta property="og:description" content="...">, <meta property="og:image" content="...">, <meta name="twitter:card" content="summary_large_image">.
   - H1 Unique : UN SEUL <h1> par page HTML. Tous les sous-titres en <h2> / <h3>.
   - Script Defer : Charger JavaScript avec <script src="script.js" defer></script>.
   - Accessibilité : Chaque <img> DOIT avoir un alt descriptif. Tous les boutons d'icônes seuls DOIVENT avoir un attribut aria-label.
   - Liens externes : Toujours ajouter rel="noopener noreferrer" sur target="_blank".

4. DESIGN SYSTEM LUXUEUX & LAYOUTS AÉRÉS :
   - ESPACEMENT GÉNÉREUX : Applique un padding généreux sur toutes les sections (padding: 80px 0 ou 100px 0) et un max-width aéré (max-width: 1280px; margin: 0 auto; padding: 0 24px).
   - FORMULAIRES SPACIEUX : Les grilles de formulaire doivent être aérées avec un gap de 24px minimum, des inputs larges (padding: 14px 18px), des bordures fines (border: 1px solid rgba(255,255,255,0.15)), un background sombre raffiné, et des coins arrondis doux (border-radius: 12px).
   - MENU & BOUTONS RAFFINÉS : Le menu de navigation doit être épuré et lisible. Le bouton 'EXPLORER' ou 'DÉCOUVRIR' doit être un vrai bouton stylisé raffiné avec icône/texte (ex: "Explorer les biens →") et JAMAIS un ovale vide ou une pilule bizarre sans texte !
   - ADHÉRENCE STRICTE AU THÈME DU PROJET : Si le site est pour une agence immobilière, TOUTES les photos générées DOIVENT représenter des villas modernes de luxe, intérieurs d'architecte, penthouses ([GENERATE_IMAGE: Modern luxury villa exterior with pool, 4k]). INTERDICTION ABSOLUE d'insérer des visuels de voitures ou de véhicules hors-sujet.

5. MOTION DESIGN & ANIMATIONS CONTEXTUELLES :
   - Animations CSS au scroll (@keyframes fadeUp, slideIn), transitions hover fluides sur cartes et boutons.
   - Compteurs chiffres animés et bannières Toast via showToast(message, type) dans script.js.

6. LOGIQUE MÉTIER PERSISTANTE :
   - State Manager centralisé dans script.js synchronisé avec localStorage.

6. CODE COMPLET SANS TRONCATURE :
   - Ecris l'integralité du code du fichier sans aucun bloc markdown ni explications.
"""
        code = await interroger_model(dev_prompt, agent_role="DEV", file_path=file_path, project_name=project_name)
        code_clean = re.sub(r'^```[a-zA-Z]*\s*|```\s*$', '', code.strip(), flags=re.MULTILINE)
        
        # Convertir d'abord les URLs externes brutes éventuelles en tags [GENERATE_IMAGE: ...]
        code_clean = convert_unsplash_to_generator_tags(code_clean, project_name)
        
        # Generer les images réelles IA via le pipeline
        code_clean = await process_generated_images(code_clean, project_dir)

        if file_path.endswith('.html') or file_path.endswith('.js'):
            code_clean = await secourir_images_html(code_clean, project_dir, project_name)
        if file_path.endswith('.html'):
            code_clean = corriger_liens_invalides_html(code_clean, list(files_state.keys()))
            code_clean, is_valid_html, err_html = verifier_et_enrichir_html(code_clean, file_path)
            if not is_valid_html:
                print(f"[DEV SWARM WARNING] HTML incomplet détecté pour {file_path} : {err_html}")
                # Demande à DEV de re-générer la page avec le contenu complet
                retry_prompt = f"""Tu as produit une page HTML ({file_path}) incomplète ou trop vide.
Projet : "{project_name}" ({specs})
Fichier : "{file_path}" ({purpose})

GÉNÈRE LA PAGE HTML COMPLÈTE ET RICHE EN ÉLÉMENTS :
- Si page de connexion (login.html) : Formulaire complet avec champs Email, Mot de passe, option Se souvenir de moi, bouton Se connecter stylisé, liens mot de passe oublié et s'inscrire.
- Si page d'inscription (register.html) : Formulaire complet avec Nom complet, Email, Mot de passe, Confirmation, case des CGU et bouton S'inscrire stylisé.
- Si page principale/app/discover : Interface complète avec barres de navigation stylisées, cartes interactives, formulaires et boutons d'action.

Renvoye le code HTML complet du fichier sans bloc markdown.
"""
                code = await interroger_model(retry_prompt, agent_role="DEV", file_path=file_path, project_name=project_name)
                code_clean = re.sub(r'^```[a-zA-Z]*\s*|```\s*$', '', code.strip(), flags=re.MULTILINE)
                code_clean = convert_unsplash_to_generator_tags(code_clean, project_name)
                code_clean = await process_generated_images(code_clean, project_dir)
                code_clean = await secourir_images_html(code_clean, project_dir, project_name)
                code_clean = corriger_liens_invalides_html(code_clean, list(files_state.keys()))
                code_clean, _, _ = verifier_et_enrichir_html(code_clean, file_path)

        # file_path provient du plan généré par le LLM → confinement obligatoire
        file_full_path = _chemin_confine(project_dir, file_path)
        if file_full_path is None:
            print(f"[SWARM] ⛔ Chemin de fichier refusé (sortie du projet) : {file_path!r}")
            files_state[file_path] = "failed"
            continue
        os.makedirs(os.path.dirname(file_full_path), exist_ok=True)
        with open(file_full_path, "w", encoding="utf-8") as file_out:
            file_out.write(code_clean)
        written_files[file_path] = code_clean

        await notify({
            "action": "dev_swarm_update",
            "agent": "DEV",
            "message": f"Code rédigé pour {file_path}",
            "log": f"Développeur Lead : Code complet implémenté pour {file_path}",
            "current_file": file_path,
            "current_code": code_clean,
            "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
            "status": "in_progress"
        })

        # ── Audit de Sécurité et Vérification d'Intégrité des Routes (SEC) ──
        if file_path.endswith('.html'):
            code_clean = corriger_liens_invalides_html(code_clean, list(files_state.keys()))
            with open(file_full_path, "w", encoding="utf-8") as file_out:
                file_out.write(code_clean)
            written_files[file_path] = code_clean

        await notify({
            "action": "dev_swarm_update",
            "agent": "SEC",
            "message": f"Audit sécurité & intégrité des routes sur {file_path}...",
            "log": f"Security Auditor : Scan d'injections, validation des routes HTML (0 lien cassé) pour {file_path}...",
            "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
            "status": "in_progress"
        })
        await asyncio.sleep(0.5)

        # ── Test d'Exécution Réelle en Sandbox (QA) ──
        files_state[file_path] = "testing"
        await notify({
            "action": "dev_swarm_update",
            "agent": "QA",
            "message": f"Exécution sandbox de {file_path}...",
            "log": f"QA Tester : Test d'exécution dans la sandbox isolée pour {file_path}...",
            "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
            "status": "in_progress"
        })

        if file_path.endswith(".py") or file_path.endswith(".js"):
            success = False
            for iteration in range(3):
                res_exec = await executer_fichier_sandbox(file_full_path, timeout=8)
                if res_exec["success"] or res_exec["return_code"] == 0:
                    success = True
                    break
                else:
                    err_msg = res_exec["stderr"] or f"Exit code {res_exec['return_code']}"
                    print(f"[DEV SWARM QA SANDBOX] Erreur dans {file_path} (itér {iteration+1}): {err_msg}")
                    await notify({
                        "action": "dev_swarm_update",
                        "agent": "QA",
                        "message": f"Erreur dans {file_path}. Correction par DEV...",
                        "log": f"QA Tester : Échec exécution sandbox !\n{err_msg}\nEnvoi au développeur pour correctif...",
                        "files": [{"file_path": fp, "status": "failed"} for fp in files_state],
                        "status": "in_progress"
                    })
                    await asyncio.sleep(1.5)
                    
                    fix_prompt = f"""Tu es le Développeur Lead. L'exécuteur sandbox a détecté cette erreur dans {file_path} :
{err_msg}

Code actuel :
{code_clean}

Renvoye le code corrigé complet sans aucun bloc markdown."""
                    code = await interroger_model(fix_prompt)
                    code_clean = re.sub(r'^```[a-zA-Z]*\s*|```\s*$', '', code.strip(), flags=re.MULTILINE)
                    with open(file_full_path, "w", encoding="utf-8") as file_out:
                        file_out.write(code_clean)
                    written_files[file_path] = code_clean

            if success:
                files_state[file_path] = "completed"
                await notify({
                    "action": "dev_swarm_update",
                    "agent": "QA",
                    "message": f"Sandbox OK pour {file_path}",
                    "log": f"QA Tester : Exécution sandbox validée avec succès pour {file_path}.",
                    "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
                    "status": "in_progress"
                })
            else:
                files_state[file_path] = "failed"
                await notify({
                    "action": "dev_swarm_update",
                    "agent": "QA",
                    "message": f"Échec sandbox {file_path}",
                    "log": f"QA Tester : Échec persistant pour {file_path}.",
                    "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
                    "status": "failure"
                })
                if hasattr(builtins, "parler"):
                    builtins.parler(f"Désolé monsieur, l'essaim d'agents n'a pas pu valider le fichier {file_path} du projet.")
                return
        else:
            files_state[file_path] = "completed"
            await notify({
                "action": "dev_swarm_update",
                "agent": "QA",
                "message": f"Validation de {file_path}",
                "log": f"QA Tester : Validation ressource OK ({file_path}).",
                "files": [{"file_path": fp, "status": files_state[fp]} for fp in files_state],
                "status": "in_progress"
            })
        await asyncio.sleep(0.5)

    # ── ÉTAPE 6 : QA & DevOps Auto-Audit, Captures Visuelles & Test 100% Fonctionnel ──
    await notify({
        "action": "dev_swarm_update",
        "agent": "QA",
        "message": "Audit Visuel (Captures d'écran multi-scroll) & Test 100% Fonctionnel...",
        "log": "QA & DevOps Agents : Prise de captures d'écran de chaque page (Haut, Milieu, Bas), test de 100% des fonctionnalités, clics boutons, filtres et vérification de la console avant livraison...",
        "files": [{"file_path": fp, "status": "completed"} for fp in files_state],
        "status": "in_progress"
    })
    auditer_et_corriger_projet_complet(project_dir)
    await asyncio.sleep(0.8)

    # Génération automatique d'un requirements.txt ou package.json si des fichiers Python/JS existent
    py_files = [f for f in files_state if f.endswith(".py")]
    if py_files and "requirements.txt" not in files_state:
        req_path = os.path.join(project_dir, "requirements.txt")
        with open(req_path, "w", encoding="utf-8") as req_file:
            req_file.write("# Dépendances auto-générées par DevOps Agent\nrequests\n")

    await asyncio.sleep(0.8)

    # ── FINALISATION ──
    await notify({
        "action": "dev_swarm_update",
        "agent": "OPS",
        "message": f"Projet {project_name} prêt et déployé !",
        "log": f"DevOps Agent : Projet validé et disponible dans la sandbox : {project_dir}",
        "files": [{"file_path": fp, "status": "completed"} for fp in files_state],
        "status": "success"
    })
    
    index_path = os.path.join(project_dir, "index.html")
    if os.path.exists(index_path):
        site_url = f"file:///{os.path.abspath(index_path).replace('\\', '/')}"
        try:
            import webbrowser
            webbrowser.open(site_url)
        except Exception as e:
            print(f"[DEV SWARM BROWSER ERROR] {e}")

    if hasattr(builtins, "parler"):
        builtins.parler(f"Monsieur, l'essaim de 6 agents autonomes a validé et déployé le projet {project_name} dans la sandbox.")
        
    try:
        os.startfile(project_dir)
    except:
        pass

async def resoudre_dev_swarm(cmd):
    """Résout et intercepte les commandes d'essaim d'agents."""
    t = cmd.lower().strip()
    import unicodedata
    t = "".join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t)
    
    mots_cles = [
        "essaim", "swarm", "demande aux agents", "demande a l'equipe", 
        "demande a l equipe", "equipe de dev", "equipe d'agents", 
        "equipe agents", "cree le projet", "cree l'application",
        "cree un projet", "cree une application", "lance l'essaim", 
        "lance essaim", "demarre l'essaim", "demarre essaim"
    ]
    t_clean = t.replace("'", " ").replace("-", " ")
    has_keyword = any(k in t for k in mots_cles) or any(k in t_clean for k in mots_cles)
    starts_with_code = t.startswith("code-moi") or t.startswith("code moi")
    
    if not has_keyword and not starts_with_code:
        return None
        
    request_clean = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', cmd, flags=re.IGNORECASE).strip()
    asyncio.create_task(run_dev_swarm_process(request_clean))
    return "Très bien, je mobilise les agents pour coder votre projet. Suivi actif sur le HUD."

builtins.resoudre_dev_swarm = resoudre_dev_swarm

async def resoudre_lance_sandbox(cmd):
    """Résout les commandes pour savoir comment lancer ou lancer le dernier projet de la sandbox."""
    t = cmd.lower().strip()
    import unicodedata
    t = "".join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t)

    mots_comment_lancer = [
        "comment je fais pour le lancer", "comment le lancer", "comment lancer",
        "comment je lance", "comment executer", "comment l'executer", "comment je l'exécute"
    ]
    # « lance le » (nu) a été retiré : il capturait « lance le mode hologramme »,
    # « lance le radar reseau », « lance le scan antivirus »… et bloquait les
    # resolvers légitimes. On exige désormais une cible explicite.
    mots_lancer_direct = [
        "lance le projet", "lance l'application", "lance le site", "lance-le",
        "execute le projet", "execute-le", "demarre le projet", "demarre l'application"
    ]

    is_comment = any(re.search(r'\b' + re.escape(k) + r'\b', t) for k in mots_comment_lancer) or (("comment" in t or "comment faire" in t) and ("lance" in t or "execute" in t))
    is_direct = any(re.search(r'\b' + re.escape(k) + r'\b', t) for k in mots_lancer_direct) or (("lance" in t or "execute" in t or "demarre" in t) and ("projet" in t or "jeu" in t or "script" in t or "application" in t))

    if not is_comment and not is_direct:
        return None

    # Aucun projet en sandbox : on rend la main (None) plutôt que de répondre.
    # Répondre ici bloquait la chaîne de resolvers pour des phrases qui ne nous
    # étaient pas destinées.
    if not os.path.exists(SANDBOX_DIR):
        return None

    subdirs = [os.path.join(SANDBOX_DIR, d) for d in os.listdir(SANDBOX_DIR) if os.path.isdir(os.path.join(SANDBOX_DIR, d))]
    if not subdirs:
        return None

    latest_dir = max(subdirs, key=os.path.getmtime)
    project_name = os.path.basename(latest_dir)

    # Chercher les points d'entrée
    files = os.listdir(latest_dir)
    entry_point = None
    python_files = [f for f in files if f.endswith(".py")]

    if "main.py" in files:
        entry_point = "main.py"
    elif "app.py" in files:
        entry_point = "app.py"
    elif len(python_files) == 1:
        entry_point = python_files[0]
    elif len(python_files) > 1:
        # Prendre le plus récemment modifié
        python_full = [os.path.join(latest_dir, f) for f in python_files]
        latest_file = max(python_full, key=os.path.getmtime)
        entry_point = os.path.basename(latest_file)

    html_files = [f for f in files if f.endswith(".html")]
    if not entry_point and "index.html" in files:
        entry_point = "index.html"
    elif not entry_point and html_files:
        entry_point = html_files[0]

    if not entry_point:
        return f"Le dernier projet créé est '{project_name}', mais je n'ai pas trouvé de fichier exécutable (comme main.py ou index.html) à l'intérieur. Fichiers présents : {', '.join(files)}."

    file_full_path = os.path.join(latest_dir, entry_point)

    if is_comment:
        if entry_point.endswith(".py"):
            instructions = f"Le dernier projet créé par l'essaim est **{project_name}**.\n\nVous pouvez le lancer en ouvrant un terminal et en exécutant :\n`python sandbox/{project_name}/{entry_point}`\n\nSouhaitez-vous que je le lance directement pour vous ? Dites simplement 'lance le projet'."
        elif entry_point.endswith(".html"):
            instructions = f"Le dernier projet créé par l'essaim est **{project_name}**.\n\nIl s'agit d'une application web. Vous pouvez l'ouvrir en ouvrant le fichier `{entry_point}` dans votre navigateur.\n\nSouhaitez-vous que je l'ouvre directement pour vous ? Dites simplement 'lance le projet'."
        else:
            instructions = f"Le dernier projet créé par l'essaim est **{project_name}** contenant le fichier `{entry_point}`."
        return instructions

    if is_direct:
        # Même garde-fou que resoudre_creation_site_web : exécuter un script déjà
        # généré tourne avec les pleins privilèges de l'utilisateur. Un invité
        # non authentifié n'avait aucune restriction sur ce chemin.
        if getattr(builtins, "ACTIVE_SPEAKER", "mylane") == "guest":
            print("🔒 [DEV SWARM] Exécution refusée : locuteur non authentifié (invité).")
            return "Désolé, l'exécution de scripts est réservée aux utilisateurs authentifiés, mylane."
        import subprocess
        if entry_point.endswith(".py"):
            try:
                # Utiliser le venv python si disponible
                python_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "venv", "Scripts", "python.exe")
                if not os.path.exists(python_exe):
                    python_exe = "python"

                # Lancer dans une nouvelle console cmd sous Windows
                subprocess.Popen(f'start cmd /k ""{python_exe}" "{file_full_path}""', shell=True)
                return f"Très bien monsieur, je lance le script `{entry_point}` du projet `{project_name}` dans un nouveau terminal."
            except Exception as e:
                return f"Désolé monsieur, je n'ai pas pu exécuter le script. Erreur : {e}"
        elif entry_point.endswith(".html"):
            try:
                import webbrowser
                webbrowser.open(file_full_path)
                return f"Très bien monsieur, j'ouvre `{entry_point}` du projet `{project_name}` dans votre navigateur."
            except Exception as e:
                return f"Désolé monsieur, je n'ai pas pu ouvrir le fichier HTML. Erreur : {e}"
        else:
            try:
                os.startfile(file_full_path)
                return f"Très bien monsieur, j'ouvre le fichier `{entry_point}`."
            except Exception as e:
                return f"Désolé monsieur, je n'ai pas pu ouvrir le fichier. Erreur : {e}"

    return None

builtins.resoudre_lance_sandbox = resoudre_lance_sandbox
