import re
import builtins

# On importe les fonctions de memory_manager et vector_memory
from module.memory_manager import ajouter_memoire, charger_memoire, supprimer_memoire
from module.vector_memory import supprimer_souvenir_semantique, rechercher_souvenir_semantique
from core.interlocuteur import nom_espace, nom_virgule

async def resoudre_memoire_locale(texte):
    """Gère l'enregistrement et la récupération d'informations en mémoire locale."""
    t = texte.lower().strip()
    if "google" in t or "tasks" in t:
        return None
        
    # ── CONSOLIDATION DE LA MÉMOIRE IA (ex: "consolide ma mémoire")
    if "consolide" in t or "synthetise" in t:
        if "memoire" in t or "conversation" in t or "notes" in t:
            builtins.parler(f"Très bien{nom_espace()}, je lance le protocole de consolidation de votre mémoire...")
            from module.memory_manager import consolider_memoire_ia
            success = await consolider_memoire_ia()
            if success:
                return "Consolidation de la mémoire terminée. J'ai extrait les faits récents importants et mis à jour vos notes."
            else:
                return "J'ai analysé nos échanges récents, mais aucune nouvelle information significative n'a été trouvée pour enrichir vos notes."
    
    # ── ENREGISTREMENT (ex: "enregistre que mon code est 1234")
    _triggers_save = ["enregistre que", "mémorise que", "note que", "rappelle-toi que", "retiens que", "retiens de", "retiens "]
    if any(m in t for m in _triggers_save):
        for trig in _triggers_save:
            if trig in t:
                content = t.split(trig)[-1].strip()
                if not content: continue
                # Tentative de découpage Sujet / Valeur
                seps = [" est ", " sont ", " s'appelle ", " se trouve ", " se trouvent ", " à "]
                for sep in seps:
                    if sep in content:
                        parties = content.split(sep)
                        sujet = parties[0].strip()
                        valeur = " ".join(parties[1:]).strip()
                        if len(sujet) > 2 and len(valeur) > 1:
                            ajouter_memoire(sujet, valeur)
                            def _a_la_deuxieme_personne(texte_a_corriger):
                                # "mon/ma/mes" (1re personne, côté utilisateur) doivent devenir
                                # "votre/vos" une fois répétés par JARVIS (2e personne). Avant ce
                                # correctif, seul le sujet était corrigé : "mémorise que clara est
                                # ma copine" faisait dire à JARVIS "j'ai enregistré que ... ma
                                # copine", comme si c'était SA copine à lui.
                                return re.sub(r'\bmon\b', 'votre', re.sub(r'\bma\b', 'votre', re.sub(r'\bmes\b', 'vos', texte_a_corriger)))
                            sujet_poli = _a_la_deuxieme_personne(sujet)
                            valeur_polie = _a_la_deuxieme_personne(valeur)
                            return f"C'est fait{nom_espace()}, j'ai enregistré que {sujet_poli} {sep.strip()} {valeur_polie}."
                
                ajouter_memoire("note_rapide", content)
                return f"C'est noté{nom_espace()}, j'ai mis cela en mémoire : {content}."
    # ── SUPPRESSION / OUBLI (ex: "oublie le code du portail", "oublie mon code", "supprime le code du garage")
    _triggers_forget = [
        "oublie que", "oublie le", "oublie la", "oublie les", "oublie mon", "oublie ma", "oublie mes", "oublie",
        "supprime le", "supprime la", "supprime les", "supprime mon", "supprime ma", "supprime mes", "supprime",
        "efface le", "efface la", "efface les", "efface mon", "efface ma", "efface mes", "efface"
    ]
    if any(m in t for m in _triggers_forget):
        for trig in _triggers_forget:
            if trig in t:
                sujet = t.split(trig)[-1].strip()
                if not sujet: continue
                # Enlever la ponctuation de fin
                sujet = re.sub(r'[?!\.]', '', sujet).strip()
                
                success_kv = False
                
                # Essayer de trouver la clé correspondante dans la mémoire clé-valeur
                mem = charger_memoire()
                cle_exacte = None
                
                # 1. Recherche par correspondance exacte (ignorant la casse/les espaces/les accents)
                for cle in mem.keys():
                    cle_clean = cle.replace("_", " ").lower().strip()
                    if cle_clean == sujet.lower():
                        cle_exacte = cle
                        break
                
                # 2. Recherche par inclusion si pas de correspondance exacte
                if not cle_exacte:
                    for cle in mem.keys():
                        cle_clean = cle.replace("_", " ").lower().strip()
                        if cle_clean in sujet.lower() or sujet.lower() in cle_clean:
                            cle_exacte = cle
                            break
                            
                if cle_exacte:
                    success_kv = supprimer_memoire(cle_exacte)
                
                # Supprimer également de la base vectorielle ChromaDB
                success_vect = False
                try:
                    success_vect = supprimer_souvenir_semantique(sujet)
                except Exception as e:
                    print(f"[MEMOIRE LOCALE] Erreur suppression vectorielle : {e}")
                
                if success_kv or success_vect:
                    return f"Information oubliée{nom_virgule()}."
                # Rien trouvé en mémoire : on rend la main (None) au lieu de
                # répondre. Les déclencheurs incluent les verbes nus « supprime »,
                # « efface », « oublie » : répondre ici interceptait des phrases
                # comme « supprime le rendez-vous de demain » ou « efface l'écran »
                # et empêchait tous les resolvers suivants — et l'IA — de les voir.
                return None

    # ── RÉCUPÉRATION (ex: "quel est mon code ?", "code du portail ?")
    _triggers_get = ["comment s'appelle", "quel est le nom de", "où se trouve", "où est", "quelle est ma", "quel est mon", "quel est le", "quelle est la", "qu'est-ce que", "qui est", "qu'est ce que"]
    is_get_query = any(m in t for m in _triggers_get)
    t_clean = re.sub(r'[?!\.]', '', t).strip()
    
    mem = charger_memoire()
    if mem:
        for cle, data in mem.items():
            cle_clean = cle.replace("_", " ").lower().strip()
            # Correspondance exacte, déclencheur de recherche, ou sous-chaîne significative (ex: "code du portail" pour "le code du portail")
            if t_clean == cle_clean or (is_get_query and cle_clean in t) or (len(t_clean) >= 4 and t_clean in cle_clean):
                valeur = data.get('valeur', 'inconnue')
                cle_polie = cle_clean.replace("mon ", "votre ").replace("ma ", "votre ").replace("mes ", "vos ")
                if "où" in t:
                    return f"D'après mes notes, {cle_polie} se trouve : {valeur}."
                elif "qui" in t or "s'appelle" in t:
                    return f"D'après mes notes, {cle_polie} est {valeur}."
                else:
                    return f"D'après mes notes, {cle_polie} est : {valeur}."
            
    # ── RÉSOLUTION SÉMANTIQUE DE SOUS-SEUIL (Vector Memory fallback local)
    try:
        reponse_semantique = rechercher_souvenir_semantique(texte)
        if reponse_semantique:
            return reponse_semantique
    except Exception as e:
        print(f"[MEMOIRE LOCALE] Erreur import ou resolution sémantique : {e}")

    return None

# Injection builtins
builtins.resoudre_memoire_locale = resoudre_memoire_locale
