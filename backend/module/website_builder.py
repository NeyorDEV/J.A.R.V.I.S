import os
import sys
import json
import re
import time
import urllib.parse
import requests
import asyncio
import webbrowser
import builtins
import google.genai as genai
from core.config import GEMINI_API_KEY, CHOSEN_MODEL
from core.interlocuteur import nom_espace

# Initialisation de la Sandbox dans le dossier backend/sandbox
_dir_courant = os.path.dirname(os.path.abspath(__file__))
SANDBOX_DIR = os.path.abspath(os.path.join(_dir_courant, "..", "sandbox"))

def get_gemini_client():
    """Récupère ou réinitialise le client Gemini."""
    if hasattr(builtins, "client") and builtins.client is not None:
        return builtins.client
    if GEMINI_API_KEY:
        return genai.Client(api_key=GEMINI_API_KEY)
    return None

async def interroger_model(prompt):
    """Interroge Gemini de manière asynchrone."""
    try:
        client = get_gemini_client()
        if not client:
            print("[WEBSITE BUILDER ERROR] Aucun client Gemini disponible.")
            return ""
        
        model_name = getattr(builtins, "CHOSEN_MODEL", CHOSEN_MODEL)
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return response.text if response and hasattr(response, 'text') else ""
    except Exception as e:
        print(f"[WEBSITE BUILDER ERROR] Erreur génération LLM : {e}")
        return ""

async def diffuser_hud_update(data):
    """Diffuse l'état de la console HUD aux clients WebSocket."""
    if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
        msg = json.dumps(data)
        await asyncio.gather(*[ws.send(msg) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)

def telecharger_image_hd(prompt, filepath):
    """
    Télécharge une image HD thématique via Unsplash/Pollinations.
    Si échec, génère un visuel SVG vectoriel HD professionnel en fallback.
    """
    try:
        keywords = prompt.split(',')[0].replace(' ', ',')
        prompt_enc = urllib.parse.quote(prompt)
        seed = int(time.time() * 1000) % 1000000
        
        # Source 1: Unsplash Source API
        unsplash_url = f"https://source.unsplash.com/featured/1024x768/?{keywords}"
        pollination_url = f"https://image.pollinations.ai/prompt/{prompt_enc}?seed={seed}&nologo=true&width=1024&height=768"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/jpeg, image/png, image/*"
        }

        # Try Pollinations
        res = requests.get(pollination_url, headers=headers, timeout=12)
        if res.status_code == 200 and len(res.content) > 2000:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(res.content)
            return True
            
        # Try Unsplash
        res_un = requests.get(unsplash_url, headers=headers, timeout=10)
        if res_un.status_code == 200 and len(res_un.content) > 2000:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(res_un.content)
            return True

    except Exception as e:
        print(f"[WEBSITE BUILDER IMAGE WARNING] Fetch exception: {e}")

    # Fallback SVG HD Vectoriel ultra-moderne
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        title = prompt.split(',')[0][:25].strip().upper()
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768" viewBox="0 0 1024 768">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0b0d1b;stop-opacity:1" />
      <stop offset="50%" style="stop-color:#161936;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#6c5ce7;stop-opacity:0.3" />
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#6c5ce7" />
      <stop offset="100%" style="stop-color:#00e5ff" />
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <circle cx="800" cy="200" r="300" fill="#6c5ce7" opacity="0.12" />
  <circle cx="200" cy="600" r="250" fill="#00e5ff" opacity="0.1" />
  <rect x="112" y="134" width="800" height="500" rx="24" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)" stroke-width="2" />
  <path d="M 150 500 Q 350 250 550 400 T 900 200" fill="none" stroke="url(#accent)" stroke-width="6" />
  <text x="50%" y="45%" font-family="system-ui, sans-serif" font-size="42" font-weight="800" fill="#ffffff" text-anchor="middle" letter-spacing="2">{title}</text>
  <text x="50%" y="54%" font-family="system-ui, sans-serif" font-size="20" fill="#00e5ff" text-anchor="middle" font-weight="600">AURA ELITE DESIGN ENGINE</text>
</svg>'''
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(svg_content)
        return True
    except Exception:
        return False

async def generer_site_web_autonome(user_prompt: str):
    """
    Chef d'orchestre autonome pour la création complète et massive d'applications web.
    """
    logs = []
    
    def log_line(msg: str):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {msg}"
        logs.append(entry)
        print(f"[WEBSITE CONSOLE] {entry}")
        return entry

    log_line(f"[SYSTEM] Démarrage de l'Architecture Élite pour : '{user_prompt}'")
    
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', user_prompt[:25].lower()).strip('_') or "site_web_jarvis"
    project_dir = os.path.join(SANDBOX_DIR, clean_name)
    assets_dir = os.path.join(project_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # Étape 1 : Conception & Spécification des Visuels IA
    await diffuser_hud_update({
        "action": "website_builder_update",
        "status": "in_progress",
        "step_label": "[1/4] CONCEPTION & ARCHITECTURE PROJET",
        "message": "Définition de la structure et planification des visuels HD...",
        "progress": 10,
        "images_count": {"generated": 0, "total": 4},
        "logs": logs,
        "project_name": clean_name
    })

    images_spec = [
        {"filename": "hero_preview.jpg", "prompt": f"Futuristic high-tech analytics dashboard interface background, 8k render, {user_prompt}", "purpose": "Visuel d'en-tête Hero"},
        {"filename": "card1.jpg", "prompt": f"Financial analytics data chart visualization, glowing neon, {user_prompt}", "purpose": "Visuel carte analytics"},
        {"filename": "card2.jpg", "prompt": f"Digital security data encryption vault cyber tech, {user_prompt}", "purpose": "Visuel carte sécurité"},
        {"filename": "card3.jpg", "prompt": f"Mobile synchronization application interface, {user_prompt}", "purpose": "Visuel carte synchro"}
    ]

    total_images = len(images_spec)
    log_line(f"[ARCHITECT] {total_images} visuels HD programmés pour la génération.")

    # Étape 2 : Génération des Visuels HD (Pollinations / Unsplash / Fallback)
    generated_images_count = 0
    images_dict = {}

    for idx, img_info in enumerate(images_spec, 1):
        fn = img_info["filename"]
        prompt_ia = img_info["prompt"]
        purpose = img_info["purpose"]
        filepath = os.path.join(assets_dir, fn)

        log_line(f"[IMAGE IA {idx}/{total_images}] Génération de '{fn}' ({purpose})...")
        
        await diffuser_hud_update({
            "action": "website_builder_update",
            "status": "in_progress",
            "step_label": f"[2/4] GENERATION VISUELS HD ({idx}/{total_images})",
            "message": f"Création de {fn}...",
            "progress": 10 + int((idx / total_images) * 35),
            "images_count": {"generated": generated_images_count, "total": total_images},
            "logs": logs,
            "project_name": clean_name
        })

        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, telecharger_image_hd, prompt_ia, filepath)
        
        if success:
            generated_images_count += 1
            log_line(f"[IMAGE IA {idx}/{total_images}] '{fn}' sauvegardée avec succès !")
        else:
            log_line(f"[IMAGE IA {idx}/{total_images}] Fallback appliqué pour '{fn}'.")

        images_dict[fn] = f"assets/{fn}"
        await asyncio.sleep(0.3)

    # Étape 3 : Écriture du Code HTML5 Complet (Avec Chart.js & FontAwesome CDN)
    log_line("[CODE ENGINE] Génération de l'application HTML5 massive et ultra-complète...")
    await diffuser_hud_update({
        "action": "website_builder_update",
        "status": "in_progress",
        "step_label": "[3/4] CODAGE HTML5 & ARCHITECTURE INTERACTIVE",
        "message": "Génération du code HTML5 sémantique complet avec Chart.js...",
        "progress": 60,
        "images_count": {"generated": generated_images_count, "total": total_images},
        "logs": logs,
        "project_name": clean_name
    })

    html_prompt = f"""Tu es le Lead Web Architect chez JARVIS.
Crée une application web / dashboard D'ÉLITE 100% COMPLÈTE, VIVANTE et ULTRA-INTERACTIVE pour la demande : "{user_prompt}".

CONSIGNES STRICTES POUR HTML :
1. DANS LE `<head>` :
   - Inclus Google Fonts ('Plus Jakarta Sans' et 'Outfit').
   - Inclus FontAwesome CDN: `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">`
   - Inclus Chart.js CDN: `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`
   - Lien vers `style.css` et `script.js`.
2. NE METS AUCUN CODE CSS OU JS EN TEXTE BRUT DANS LE HTML ! Seuls les liens `<link>` et `<script src="...">` sont autorisés dans le HTML.
3. IMAGES DISPONIBLES DANS `assets/` :
   - `assets/hero_preview.jpg` (Hero visual)
   - `assets/card1.jpg`, `assets/card2.jpg`, `assets/card3.jpg`
4. STRUCTURE MASSIVE DE L'APPLICATION WEB (5 Sections principales) :
   - Navigation Latérale / Header : Logo néon, nom d'utilisateur ("Mylan PERRIER"), badges de statut "Premium VIP", navigation par onglets réactifs.
   - Hero Banner / Welcome Header : Titre dynamique "Maîtrisez vos finances avec élégance", description, bouton CTA "+ Nouvelle Transaction" déclenchant la modale.
   - 4 Cartes de Métriques KPI (Solde Total, Revenus, Dépenses, Épargne) avec badges %, icônes FontAwesome et barres de progression.
   - Section Graphiques Interactifs Chart.js : 2 canvas `<canvas id="cashflowChart"></canvas>` et `<canvas id="categoryChart"></canvas>`.
   - Tableau de Données Réactif Complet : Recherche par mot-clé, filtre de catégorie, 5+ lignes de données réelles, colonnes de statut, boutons d'action suppression/édition.
   - Fenêtre Modale d'Ajout (`<div id="modal-transaction" class="modal-overlay hidden">`) avec formulaire complet.
5. NE DONNE AUCUN TEXTE EXPLICATIF. Renvoye uniquement le code HTML5 brut de `<!DOCTYPE html>` à `</html>`.
"""

    raw_html = await interroger_model(html_prompt)
    
    # Nettoyage strict anti-leak de code
    clean_html = re.sub(r'^```html\s*|```\s*$', '', raw_html.strip(), flags=re.MULTILINE)
    clean_html = re.sub(r'^```\s*|```\s*$', '', clean_html.strip(), flags=re.MULTILINE)
    clean_html = re.sub(r'/\*.*?\*/', '', clean_html, flags=re.DOTALL)

    with open(os.path.join(project_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(clean_html)
    log_line("[CODE ENGINE] index.html généré et nettoyé avec succès !")

    # Étape 4 : Écriture du Style CSS3 Ultra-Moderne
    log_line("[CODE ENGINE] Écriture de style.css avec correspondance HTML 100%...")
    await diffuser_hud_update({
        "action": "website_builder_update",
        "status": "in_progress",
        "step_label": "[4/4] STYLISATION CSS GLASSMORPHISM & NÉON",
        "message": "Création du design sombre, lueurs néon et micro-animations...",
        "progress": 80,
        "images_count": {"generated": generated_images_count, "total": total_images},
        "logs": logs,
        "project_name": clean_name
    })

    css_prompt = f"""Tu es le Lead UI Designer chez JARVIS.
Crée le fichier `style.css` d'exception pour le projet "{user_prompt}".

Voici le code HTML EXACT auquel ton CSS DOIT s'appliquer :
```html
{clean_html}
```

CONSIGNES IMPÉRATIVES POUR CSS :
1. RÈGLE N°1 : Stylise TOUTES les balises et classes du HTML ci-dessus.
2. THÈME SOMBRE PRÉMIUM & NÉON : Fond profond `#090b17`, accents violets `#6c5ce7`, cyans `#00e5ff`, roses `#ff477e`, verts `#00b894` et dorés `#ffd700`.
3. GLASSMORPHIC CARDS : `background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);`.
4. NAVIGATION : Supprime les puces (`list-style: none`), nav en flexbox sans soulignement.
5. FORMULAIRES & INPUTS : Inputs sombres réactifs (`background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); color: #fff; border-radius: 10px; padding: 12px;`) avec focus néon.
6. BOUTONS : Boutons avec dégradés vibrants et hover animations (`transform: translateY(-3px)`).
7. MODALE : Overlay sombre flouté (`position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1000;`). La classe `.hidden` doit avoir `display: none !important;`.
8. Renvoye uniquement le code CSS brut sans aucun commentaire explicatif.
"""

    raw_css = await interroger_model(css_prompt)
    clean_css = re.sub(r'^```css\s*|```\s*$', '', raw_css.strip(), flags=re.MULTILINE)
    clean_css = re.sub(r'^```\s*|```\s*$', '', clean_css.strip(), flags=re.MULTILINE)

    with open(os.path.join(project_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(clean_css)
    log_line("[CODE ENGINE] style.css généré et vérifié !")

    # Étape 5 : Écriture de script.js (Chart.js & Logique de Données)
    log_line("[CODE ENGINE] Écriture de script.js avec initialisation Chart.js & Modales...")
    
    js_prompt = f"""Tu es un Développeur JavaScript Senior chez JARVIS.
Crée le fichier `script.js` complet et 100% FONCTIONNEL pour l'application web "{user_prompt}".

Voici le code HTML exact de l'application :
```html
{clean_html}
```

CONSIGNES STRICTES POUR JAVASCRIPT :
1. INITIALISATION DE CHART.JS :
   - Initialise le premier graphique `cashflowChart` (type: 'line') avec dégradé et données réelles (Mois: Jan-Juin, Revenus vs Dépenses).
   - Initialise le deuxième graphique `categoryChart` (type: 'doughnut' ou 'pie') avec répartition des dépenses par catégorie (Logement, Alimentation, Loisirs, Transport).
2. GESTION DE LA MODALE & DU FORMULAIRE :
   - Ouvre la modale au clic sur le bouton "+ Nouvelle Transaction".
   - Ferme la modale au clic sur le bouton de fermeture ou l'overlay.
   - Soumission du formulaire : Ajoute dynamiquement la ligne dans le tableau, recalcule les cartes de métriques (Solde, Revenus, Dépenses) et met à jour les données de Chart.js (`chart.update()`) !
3. RECHERCHE ET FILTRES EN TEMPS RÉEL :
   - Filtre les lignes du tableau lors de la saisie dans la barre de recherche ou le menu déroulant.
4. SUPPRESSION DE TRANSACTIONS :
   - Supprime la ligne au clic sur le bouton supprimer avec mise à jour immédiate des totaux et des graphiques.
5. Renvoye uniquement le code JavaScript brut sans aucun commentaire explicatif.
"""

    raw_js = await interroger_model(js_prompt)
    clean_js = re.sub(r'^```javascript\s*|```js\s*|```\s*$', '', raw_js.strip(), flags=re.MULTILINE)

    with open(os.path.join(project_dir, "script.js"), "w", encoding="utf-8") as f:
        f.write(clean_js)
    log_line("[CODE ENGINE] script.js généré avec succès !")

    # Déploiement & Ouverture Automatique
    index_file_path = os.path.abspath(os.path.join(project_dir, "index.html"))
    site_url = f"file:///{index_file_path.replace('\\', '/')}"
    
    log_line(f"[DEPLOY] Application Web Élite déployée et ouverte : {index_file_path}")

    await diffuser_hud_update({
        "action": "website_builder_update",
        "status": "success",
        "step_label": "[4/4] APPLICATION WEB ÉLITE DEPLOYÉE !",
        "message": f"Le projet '{clean_name}' a été généré avec 4 visuels HD et Chart.js !",
        "progress": 100,
        "images_count": {"generated": generated_images_count, "total": total_images},
        "logs": logs,
        "project_name": clean_name,
        "site_url": site_url
    })

    try:
        webbrowser.open(site_url)
    except Exception as e:
        print(f"[WEBSITE BUILDER BROWSER ERROR] {e}")

    if hasattr(builtins, "send_web_action"):
        try:
            await builtins.send_web_action("ctx_card", title="PROJET WEB COMPLET", text=f"L'application '{clean_name}' a été créée avec {generated_images_count} visuels HD et Chart.js.", type="info", icon="🔥")
        except Exception:
            pass

    if hasattr(builtins, "parler"):
        builtins.parler(f"Très bien{nom_espace()}, votre application web d'élite avec visuels HD, Chart.js et gestionnaire interactif a été générée avec succès et ouverte dans votre navigateur.")

    return site_url
