import builtins
import json
import unicodedata
import re
import asyncio
from google.genai import types
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

def extraire_nombre(texte):
    # Cherche un nombre en chiffres
    match = re.search(r'\d+', texte)
    if match:
        return int(match.group(0))
    # Cherche des mots-clés de nombres en français
    mots_nombres = {
        "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
        "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "douze": 12
    }
    for mot, val in mots_nombres.items():
        if re.search(rf"\b{mot}\b", texte):
            return val
    return None

def extraire_personnes_proactif(texte):
    # Cherche strictement "pour X personnes" ou "pour X"
    # où X est un chiffre ou un mot-nombre
    pattern = r"\bpour\s+(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|douze)\b"
    match = re.search(pattern, texte, flags=re.IGNORECASE)
    if match:
        valeur = match.group(1).lower()
        if valeur.isdigit():
            return int(valeur)
        mots_nombres = {
            "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
            "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "douze": 12
        }
        return mots_nombres.get(valeur)
    return None

async def resoudre_recipe(cmd):
    t = nettoyer_accent(cmd.lower().strip())

    # 1. SI ON ATTEND LE NOMBRE DE PERSONNES (CONTEXTE ACTIF - DEUXIÈME TOUR)
    if hasattr(builtins, "recipe_context") and builtins.recipe_context:
        ctx = builtins.recipe_context
        if ctx.get("awaiting_people_count"):
            recipe_name = ctx.get("recipe_name")
            # Seule une réponse qui ressemble à un nombre de personnes est prise comme
            # telle : n'importe quelle commande contenant un nombre (« baisse le son de
            # la télé de 5 ») était consommée comme réponse.
            if len(t.split()) > 6 and not re.search(r"\b(personnes?|pers|couverts?|convives?|gens)\b", t):
                builtins.recipe_context = None
                return None
            nb_personnes = extraire_nombre(t)

            # Le contexte expire au bout de 2 minutes : sans cela il restait actif
            # indéfiniment et détournait la commande suivante, quelle qu'elle soit.
            import time as _t_rec
            _pose_a = ctx.get("_pose_a", 0)
            if _pose_a and (_t_rec.time() - _pose_a) > 120:
                builtins.recipe_context = None
                return None

            # Si la phrase ne contient AUCUN nombre, c'est que l'utilisateur est
            # passé à autre chose (« allume la télé ») : on abandonne le contexte
            # et on rend la main, au lieu de servir une recette pour 4 personnes.
            if not nb_personnes:
                builtins.recipe_context = None
                print("[Recipe Resolver] Pas de nombre détecté : contexte recette abandonné.")
                return None

            print(f"[Recipe Resolver] Contexte actif pour {recipe_name}. Nombre de personnes choisi : {nb_personnes}")
            
            # Réinitialiser le contexte immédiatement
            builtins.recipe_context = None
            
            # Appel à Gemini pour générer la recette adaptée
            prompt = (
                f"Génère une recette de cuisine pour \"{recipe_name}\", spécifiquement adaptée et dosée pour {nb_personnes} personnes. "
                "Le résultat doit être un objet JSON STRICTEMENT du format suivant :\n"
                "```json\n{\n  \"recipe_title\": \"Nom de la recette\",\n  \"ingredients\": [\"Ingrédient 1\", \"Ingrédient 2\"],\n  \"instructions\": [\"Étape 1\", \"Étape 2\"]\n}\n```\n"
                "Assure-toi que les valeurs des tableaux `ingredients` et `instructions` sont des chaînes de caractères simples avec les proportions exactes recalculées pour "
                f"{nb_personnes} personnes. Ne rajoute aucun texte avant ou après le JSON. Si tu ne trouves pas la recette, réponds avec un JSON vide comme ceci : {{}}."
            )
            
            try:
                print("[Recipe Resolver] Appel à Gemini pour générer la recette adaptée...")
                def call_gemini():
                    return builtins.client.models.generate_content(
                        model=builtins.CHOSEN_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                
                response = await asyncio.to_thread(call_gemini)
                recipe_data = json.loads(response.text)
                
                if recipe_data and isinstance(recipe_data, dict) and recipe_data.get("recipe_title"):
                    title = recipe_data.get("recipe_title", "")
                    ingredients = recipe_data.get("ingredients", [])
                    instructions = recipe_data.get("instructions", [])
                    
                    print(f"[Recipe Resolver] Recette générée : {title}")
                    
                    # Envoi au HUD
                    await builtins.send_action_to_frontend({
                        "type": "show_recipe",
                        "recipe_title": title,
                        "ingredients": ingredients,
                        "instructions": instructions,
                    })
                    
                    # Construction de la lecture complète
                    ingredients_text = ", ".join(ingredients)
                    instructions_text = " ".join([f"Étape {i+1} : {inst}" for i, inst in enumerate(instructions)])
                    
                    # Correction de répétition dans le titre
                    vocal_response = (
                        f"J'ai affiché la recette de {title} sur l'hud{nom_virgule()}. "
                        f"Voici la liste des ingrédients requis : {ingredients_text}. "
                        f"Concernant les étapes de préparation : {instructions_text}. Bon appétit !"
                    )
                    return vocal_response
                else:
                    print("[Recipe Resolver] Aucune recette valide générée.")
                    return "Désolé, je n'ai pas pu trouver de recette pour cela."
                    
            except Exception as e:
                print(f"[Recipe Resolver] Erreur de traitement : {e}")
                return "Désolé, une erreur est survenue lors de la recherche de la recette."

    # 2. PREMIÈRE DEMANDE DE RECETTE (DETECTION PAR MOTS CLÉS)
    recipe_patterns = [
        r"donne moi la recette de (.*)",
        r"quelle est la recette de (.*)",
        r"je voudrais la recette de (.*)",
        r"trouve moi une recette de (.*)",
        r"montre moi la recette de (.*)",
        r"recette de (.*)",
        r"recette pour faire des (.*)",
        r"recette pour faire de la (.*)",
        r"recette pour faire du (.*)",
        r"recette pour faire un (.*)",
        r"recette pour faire une (.*)",
        r"recette (.*)"
    ]

    recipe_name = None
    for pattern in recipe_patterns:
        match = re.search(pattern, t)
        if match:
            recipe_name = match.group(1).strip()
            if recipe_name.endswith("."):
                recipe_name = recipe_name[:-1].strip()
            break

    if recipe_name:
        print(f"[Recipe Resolver] Première demande de recette détectée pour : {recipe_name}")
        
        # DÉTECTION PROACTIVE STRICTE (Nécessite le mot "pour" en amont)
        nb_personnes = extraire_personnes_proactif(t)
        if nb_personnes:
            print(f"[Recipe Resolver] Détection proactive stricte du nombre de personnes : {nb_personnes}")
            # Nettoyer le nom de la recette pour retirer "pour X personnes"
            recipe_name_clean = re.sub(r"\bpour\s+\d+\s+personnes?\b", "", recipe_name, flags=re.IGNORECASE)
            recipe_name_clean = re.sub(r"\bpour\s+(un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|douze)\s+personnes?\b", "", recipe_name_clean, flags=re.IGNORECASE)
            recipe_name_clean = recipe_name_clean.strip()
            if not recipe_name_clean:
                recipe_name_clean = recipe_name

            prompt = (
                f"Génère une recette de cuisine pour \"{recipe_name_clean}\", spécifiquement adaptée et dosée pour {nb_personnes} personnes. "
                "Le résultat doit être un objet JSON STRICTEMENT du format suivant :\n"
                "```json\n{\n  \"recipe_title\": \"Nom de la recette\",\n  \"ingredients\": [\"Ingrédient 1\", \"Ingrédient 2\"],\n  \"instructions\": [\"Étape 1\", \"Étape 2\"]\n}\n```\n"
                "Assure-toi que les valeurs des tableaux `ingredients` et `instructions` sont des chaînes de caractères simples avec les proportions exactes recalculées pour "
                f"{nb_personnes} personnes. Ne rajoute aucun texte avant ou après le JSON. Si tu ne trouves pas la recette, réponds avec un JSON vide comme ceci : {{}}."
            )
            
            try:
                print("[Recipe Resolver] Appel à Gemini pour générer la recette adaptée...")
                def call_gemini():
                    return builtins.client.models.generate_content(
                        model=builtins.CHOSEN_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                
                response = await asyncio.to_thread(call_gemini)
                recipe_data = json.loads(response.text)
                
                if recipe_data and isinstance(recipe_data, dict) and recipe_data.get("recipe_title"):
                    title = recipe_data.get("recipe_title", "")
                    ingredients = recipe_data.get("ingredients", [])
                    instructions = recipe_data.get("instructions", [])
                    
                    print(f"[Recipe Resolver] Recette générée : {title}")
                    
                    # Envoi au HUD
                    await builtins.send_action_to_frontend({
                        "type": "show_recipe",
                        "recipe_title": title,
                        "ingredients": ingredients,
                        "instructions": instructions,
                    })
                    
                    ingredients_text = ", ".join(ingredients)
                    instructions_text = " ".join([f"Étape {i+1} : {inst}" for i, inst in enumerate(instructions)])
                    
                    # Correction de répétition dans le titre
                    return (
                        f"J'ai affiché la recette de {title} sur l'hud{nom_virgule()}. "
                        f"Voici la liste des ingrédients requis : {ingredients_text}. "
                        f"Concernant les étapes de préparation : {instructions_text}. Bon appétit !"
                    )
                else:
                    return "Désolé, je n'ai pas pu trouver de recette pour cela."
            except Exception as e:
                print(f"[Recipe Resolver] Erreur de traitement : {e}")
                return "Désolé, une erreur est survenue lors de la recherche de la recette."

        # SINON : Enregistrer le contexte et poser la question du nombre de personnes
        import time as _t_ctx
        builtins.recipe_context = {
            "recipe_name": recipe_name,
            "awaiting_people_count": True,
            "_pose_a": _t_ctx.time(),   # horodatage : le contexte expire après 2 min
        }
        
        # Formatage grammatical naturel en français
        nom_propre = recipe_name
        if nom_propre.startswith("des "):
            phrase_nom = nom_propre
        elif nom_propre.startswith("de la "):
            phrase_nom = nom_propre
        elif nom_propre.startswith("du "):
            phrase_nom = nom_propre
        elif nom_propre.startswith("d'"):
            phrase_nom = nom_propre
        else:
            phrase_nom = f"de {nom_propre}"
            
        return f"Pour combien de personnes souhaitez-vous préparer cette recette {phrase_nom} ?"

    return None

builtins.resoudre_recipe = resoudre_recipe
