"""Cortex neuronal 3D : messages WebSocket de la mémoire et diffusion des nouveaux souvenirs."""

import asyncio
import builtins
import json
import os
import time
from datetime import datetime

import core.shared as shared
from core.web_bridge import _safe_ws_send


async def handle_cortex_ws(data, websocket):
    """Gère les messages WebSocket spatial_action du Cortex Neuronal."""
    action = data.get("action")
    if action == "cortex_list":
        import module.vector_memory as vector_memory
        souvenirs_vecteurs = []
        
        # 1. Souvenirs vectoriels ChromaDB
        for s in vector_memory.lister_souvenirs_complets():
            doc_text = s.get("document", "")
            entry_id = s.get("id", "")
            user_text = doc_text
            model_text = ""
            timestamp = s.get("metadata", {}).get("timestamp", "Date inconnue")
            
            try:
                lines = doc_text.split("\n")
                for line in lines:
                    if line.startswith("Date: "):
                        timestamp = line[6:].strip()
                    elif line.startswith("User: "):
                        user_text = line[6:].strip()
                    elif line.startswith("Assistant: "):
                        model_text = line[11:].strip()
            except Exception:
                pass
                
            souvenirs_vecteurs.append({
                "id": entry_id,
                "type": "vector",
                "user": user_text,
                "assistant": model_text,
                "timestamp": timestamp
            })

        # 2. Souvenirs locaux clé-valeur
        souvenirs_kv = []
        mem_path = os.path.join(shared.RACINE_PROJET, "data", "jarvis_memoire.json")
        if os.path.exists(mem_path):
            try:
                with open(mem_path, "r", encoding="utf-8") as f:
                    kv_data = json.load(f)
                    for key, val_obj in kv_data.items():
                        val = val_obj.get("valeur", "")
                        t_stamp = val_obj.get("timestamp", "Date inconnue")
                        souvenirs_kv.append({
                            "id": f"kv_{key}",
                            "type": "key_value",
                            "user": f"Fait retenu : {key}",
                            "assistant": f"Valeur mémorisée : {val}",
                            "timestamp": t_stamp
                        })
            except Exception as err:
                print(f"[CORTEX] Erreur lecture jarvis_memoire.json : {err}")
                
        # Charger les synapses personnalisées créées par Drag-and-Link
        synapses_path = os.path.join(shared.RACINE_PROJET, "data", "jarvis_synapses.json")
        custom_links = []
        if os.path.exists(synapses_path):
            try:
                with open(synapses_path, "r", encoding="utf-8") as f:
                    custom_links = json.load(f)
            except Exception as err:
                print(f"[CORTEX] Erreur lecture jarvis_synapses.json : {err}")

        # Envoi au client
        msg = json.dumps({
            "action": "cortex_list",
            "nodes": souvenirs_vecteurs + souvenirs_kv,
            "links": custom_links
        })
        await websocket.send(msg)


    elif action == "cortex_edit_memory":
        souvenir_id = data.get("entity_id")
        user_txt = data.get("user", "")
        assistant_txt = data.get("assistant", "")
        if not souvenir_id:
            return
            
        edited_ok = False
        if souvenir_id.startswith("kv_"):
            # Édition clé-valeur locale (Fait)
            key = souvenir_id[3:]
            new_key = user_txt.replace("Fait retenu : ", "").strip()
            new_val = assistant_txt.replace("Valeur mémorisée : ", "").strip()
            
            mem_path = os.path.join(shared.RACINE_PROJET, "data", "jarvis_memoire.json")
            if os.path.exists(mem_path):
                try:
                    with open(mem_path, "r", encoding="utf-8") as f:
                        kv_data = json.load(f)
                    
                    if key in kv_data:
                        t_stamp = kv_data[key].get("timestamp", datetime.now().strftime("%d/%m/%Y %H:%M"))
                        if key != new_key:
                            del kv_data[key]
                        kv_data[new_key] = {
                            "valeur": new_val,
                            "timestamp": t_stamp
                        }
                        with open(mem_path, "w", encoding="utf-8") as f:
                            json.dump(kv_data, f, ensure_ascii=False, indent=2)
                        edited_ok = True
                        print(f"[CORTEX] Modifié fait local : {key} -> {new_key} = {new_val}")
                except Exception as err:
                    print(f"[CORTEX] Erreur édition fait local : {err}")
        else:
            # Édition vectorielle ChromaDB
            try:
                import module.vector_memory as vector_memory
                coll = vector_memory._get_collection()
                if coll:
                    res = coll.get(ids=[souvenir_id])
                    t_stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
                    if res and res.get('documents') and res['documents'][0]:
                        doc_text = res['documents'][0][0]
                        for line in doc_text.split("\n"):
                            if line.startswith("Date: "):
                                t_stamp = line[6:].strip()
                                break
                    
                    new_doc = f"Date: {t_stamp}\nUser: {user_txt}\nAssistant: {assistant_txt}"
                    coll.update(ids=[souvenir_id], documents=[new_doc])
                    edited_ok = True
                    print(f"[CORTEX] Modifié souvenir vectoriel : {souvenir_id}")
            except Exception as err:
                print(f"[CORTEX] Erreur édition souvenir vectoriel : {err}")
                
        if edited_ok:
            # Diffuser la mise à jour à tous les clients connectés
            msg = json.dumps({
                "action": "cortex_edit_success",
                "entity_id": souvenir_id,
                "user": user_txt,
                "assistant": assistant_txt
            })
            await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)


    elif action == "cortex_delete":
        souvenir_id = data.get("entity_id")
        if not souvenir_id:
            return
            
        deleted_ok = False
        if souvenir_id.startswith("kv_"):
            # Suppression clé-valeur locale
            key_to_delete = souvenir_id[3:]
            mem_path = os.path.join(shared.RACINE_PROJET, "data", "jarvis_memoire.json")
            if os.path.exists(mem_path):
                try:
                    with open(mem_path, "r", encoding="utf-8") as f:
                        kv_data = json.load(f)
                    if key_to_delete in kv_data:
                        del kv_data[key_to_delete]
                        with open(mem_path, "w", encoding="utf-8") as f:
                            json.dump(kv_data, f, ensure_ascii=False, indent=2)
                        deleted_ok = True
                        print(f"[CORTEX] Supprimé clé locale : {key_to_delete}")
                except Exception as err:
                    print(f"[CORTEX] Erreur suppression clé locale : {err}")
        else:
            # Suppression vectorielle ChromaDB
            try:
                import module.vector_memory as vector_memory
                coll = vector_memory._get_collection()
                if coll:
                    coll.delete(ids=[souvenir_id])
                    deleted_ok = True
                    print(f"[CORTEX] Supprimé souvenir vectoriel : {souvenir_id}")
            except Exception as err:
                print(f"[CORTEX] Erreur suppression souvenir vectoriel : {err}")
                
        if deleted_ok:
            # Diffuser le signal de mise à jour à tous les clients connectés
            msg = json.dumps({
                "action": "cortex_update",
                "deleted_id": souvenir_id
            })
            await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)

    elif action == "cortex_speak":
        souvenir_id = data.get("entity_id")
        if not souvenir_id:
            return
            
        phrase = ""
        if souvenir_id.startswith("kv_"):
            # Fait local clé-valeur
            key = souvenir_id[3:]
            mem_path = os.path.join(shared.RACINE_PROJET, "data", "jarvis_memoire.json")
            if os.path.exists(mem_path):
                try:
                    with open(mem_path, "r", encoding="utf-8") as f:
                        kv_data = json.load(f)
                    if key in kv_data:
                        valeur = kv_data[key].get("valeur", "")
                        timestamp = kv_data[key].get("timestamp", "Date inconnue")
                        phrase = f"Fait mémorisé le {timestamp}. Pour la clé : {key}. La valeur enregistrée est : {valeur}."
                except Exception as err:
                    print(f"[CORTEX] Erreur lecture fait local pour parler : {err}")
        else:
            # Souvenir vectoriel ChromaDB
            try:
                import module.vector_memory as vector_memory
                coll = vector_memory._get_collection()
                if coll:
                    res = coll.get(ids=[souvenir_id])
                    if res and res.get('documents') and res['documents'][0]:
                        doc_text = res['documents'][0][0]
                        timestamp = "Date inconnue"
                        user_text = doc_text
                        model_text = ""
                        
                        lines = doc_text.split("\n")
                        for line in lines:
                            if line.startswith("Date: "):
                                timestamp = line[6:].strip()
                            elif line.startswith("User: "):
                                user_text = line[6:].strip()
                            elif line.startswith("Assistant: "):
                                model_text = line[11:].strip()
                        
                        if model_text:
                            phrase = f"Souvenir conversationnel du {timestamp}. Vous m'avez dit : {user_text}. Et je vous ai répondu : {model_text}."
                        else:
                            phrase = f"Souvenir conversationnel du {timestamp}. Échange mémorisé : {user_text}."
            except Exception as err:
                print(f"[CORTEX] Erreur lecture souvenir vectoriel pour parler : {err}")
                
        if phrase:
            builtins.parler(phrase, print_console=True)

    elif action == "cortex_link":
        from_id = data.get("from_id")
        to_id = data.get("to_id")
        if from_id and to_id:
            synapses_path = os.path.join(shared.RACINE_PROJET, "data", "jarvis_synapses.json")
            custom_links = []
            if os.path.exists(synapses_path):
                try:
                    with open(synapses_path, "r", encoding="utf-8") as f:
                        custom_links = json.load(f)
                except:
                    pass
            # Éviter les doublons de liaison
            exists = any(
                (l.get("from") == from_id and l.get("to") == to_id) or 
                (l.get("from") == to_id and l.get("to") == from_id) 
                for l in custom_links
            )
            if not exists:
                custom_links.append({"from": from_id, "to": to_id})
                try:
                    with open(synapses_path, "w", encoding="utf-8") as f:
                        json.dump(custom_links, f, ensure_ascii=False, indent=2)
                    print(f"[CORTEX] Liaison synaptique créée : {from_id} <-> {to_id}")
                    # Diffuser la liaison à tous les clients connectés
                    msg = json.dumps({
                        "action": "cortex_link_created",
                        "from": from_id,
                        "to": to_id
                    })
                    await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
                except Exception as err:
                    print(f"[CORTEX] Erreur écriture jarvis_synapses.json : {err}")
            else:
                # Supprimer la liaison existante !
                custom_links = [
                    l for l in custom_links 
                    if not ((l.get("from") == from_id and l.get("to") == to_id) or 
                            (l.get("from") == to_id and l.get("to") == from_id))
                ]
                try:
                    with open(synapses_path, "w", encoding="utf-8") as f:
                        json.dump(custom_links, f, ensure_ascii=False, indent=2)
                    print(f"[CORTEX] Liaison synaptique supprimée : {from_id} <-> {to_id}")
                    # Diffuser la suppression à tous les clients
                    msg = json.dumps({
                        "action": "cortex_link_removed",
                        "from": from_id,
                        "to": to_id
                    })
                    await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
                except Exception as err:
                    print(f"[CORTEX] Erreur écriture jarvis_synapses.json : {err}")


async def broadcast_cortex_new_memory(user_text, model_text):
    """Diffuse la création d'un souvenir en direct pour animer le Cortex."""
    timestamp = time.strftime("%d/%m/%Y %H:%M")
    entry_id = f"msg_{int(time.time())}"
    msg = json.dumps({
        "action": "cortex_new_memory",
        "node": {
            "id": entry_id,
            "type": "vector",
            "user": user_text,
            "assistant": model_text,
            "timestamp": timestamp
        }
    })
    if shared.CONNECTED_CLIENTS:
        await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)


# Callback hook synchrone -> asynchrone vers le WebSocket
def _notify_cortex_new_memory(user_text, model_text):
    if shared.WS_LOOP and shared.CONNECTED_CLIENTS:
        asyncio.run_coroutine_threadsafe(
            broadcast_cortex_new_memory(user_text, model_text),
            shared.WS_LOOP
        )


def _notify_factual_memory_added(cle, valeur):
    """Diffuse la création d'un fait mémorisé en direct au Cortex."""
    timestamp = time.strftime("%d/%m/%Y %H:%M")
    node = {
        "id": f"kv_{cle}",
        "type": "key_value",
        "user": f"Fait retenu : {cle}",
        "assistant": f"Valeur mémorisée : {valeur}",
        "timestamp": timestamp
    }
    msg = json.dumps({
        "action": "cortex_new_memory",
        "node": node
    })
    _safe_ws_send(msg)


builtins._notify_factual_memory_added = _notify_factual_memory_added


import module.vector_memory as _vm
_vm.on_souvenir_added.append(_notify_cortex_new_memory)
