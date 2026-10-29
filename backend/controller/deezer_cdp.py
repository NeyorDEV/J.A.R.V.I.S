"""Pilotage de l'appli Deezer par son port de débogage local (Chrome DevTools Protocol).

Pourquoi : l'accessibilité Windows (UIA) n'agit sur Deezer que si sa fenêtre est
restaurée, et certains états internes de l'appli la bloquent (erreur 0x80040200). Les
liens deezer:// affichent Deezer et lui donnent le focus. Ici, le JavaScript s'exécute
directement dans la page deezer.com de l'appli : rien n'est affiché, aucun focus n'est
pris, et cela marche Deezer réduit, caché dans la zone de notification ou sous un jeu
plein écran.

Deezer doit avoir été lancé avec ARG_PORT (deezer_controller s'en charge). Le port
n'écoute que sur 127.0.0.1.

Les attentes se font côté Python, par des évaluations courtes et répétées : dans une page
cachée depuis plus de 5 minutes, Chromium ne réveille plus les minuteurs JavaScript
qu'une fois par minute, une boucle d'attente en JavaScript serait donc inutilisable.
"""

import asyncio
import json
import os

import requests
import websockets

PORT = int(os.getenv("DEEZER_CDP_PORT", "9339"))
ARG_PORT = f"--remote-debugging-port={PORT}"

# Fonctions communes injectées dans chaque évaluation
_JS_COMMUN = r"""
const norm = s => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
const langue = () => {
  const a = document.querySelector('a[href^="#/"][href*="/album/"], a[href^="#/"][href*="/artist/"]');
  const m = a && a.getAttribute('href').match(/^#\/([a-z]{2})\//);
  return m ? m[1] : 'fr';
};
"""


def port_actif():
    """Vrai si le port de pilotage de Deezer répond."""
    try:
        return requests.get(f"http://127.0.0.1:{PORT}/json", timeout=1).ok
    except Exception:
        return False


def _url_page():
    cibles = requests.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json()
    for t in cibles:
        if t.get("type") == "page" and t.get("url", "").startswith("https://www.deezer.com"):
            return t["webSocketDebuggerUrl"]
    return None


async def evaluer(corps_js, params=None, timeout=10):
    """Exécute `corps_js` (corps d'une fonction recevant `p`) dans la page deezer.com et
    renvoie sa valeur de retour (JSON). Lève une exception si la page est injoignable."""
    url = await asyncio.to_thread(_url_page)
    if not url:
        raise RuntimeError("page deezer.com introuvable")
    expr = f"((p) => {{ {_JS_COMMUN}\n{corps_js} }})({json.dumps(params or {})})"
    async with websockets.connect(url, max_size=None, open_timeout=timeout) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": expr, "returnByValue": True}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            if msg.get("id") == 1:
                res = msg.get("result", {})
                if "exceptionDetails" in res:
                    raise RuntimeError(json.dumps(res["exceptionDetails"])[:300])
                return res.get("result", {}).get("value")


async def _attendre(corps_js, params=None, timeout=10, intervalle=0.3):
    """Répète l'évaluation jusqu'à une valeur non nulle, ou None après `timeout`."""
    fin = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < fin:
        try:
            v = await evaluer(corps_js, params)
            if v:
                return v
        except Exception:
            pass
        await asyncio.sleep(intervalle)
    return None


async def pret(timeout=5):
    """Vrai quand la page Deezer et son lecteur (dzPlayer) sont prêts."""
    if not await asyncio.to_thread(port_actif):
        return False
    return bool(await _attendre(
        "return typeof dzPlayer !== 'undefined' && !!document.querySelector('#topbar-search');",
        timeout=timeout, intervalle=0.5))


# ── État et commandes du lecteur ──────────────────────────────────────────────

_JS_ETAT = """
return { joue: dzPlayer.isPlaying(), titre: dzPlayer.getSongTitle() || '', artiste: dzPlayer.getArtistName() || '',
         album: dzPlayer.getAlbumTitle() || '' };
"""


async def etat():
    """{joue, titre, artiste, album} du lecteur, ou None si injoignable."""
    try:
        return await evaluer(_JS_ETAT)
    except Exception:
        return None


# Position et durée en secondes quand le lecteur les expose (sinon null)
_JS_LECTURE = """
const f = (n) => (typeof dzPlayer[n] === 'function') ? dzPlayer[n]() : null;
return { joue: dzPlayer.isPlaying(), titre: dzPlayer.getSongTitle() || '', artiste: dzPlayer.getArtistName() || '',
         position: f('getPosition'), duree: f('getDuration') };
"""


async def lecture_en_cours():
    """Morceau affiché par le lecteur (titre, artiste, lecture/pause, position/durée).
    Source exacte et immédiate, contrairement au titre de fenêtre ou à l'historique d'écoute
    (qui a toujours un morceau de retard). None si la page n'est pas joignable."""
    # (hors de la boucle : port_actif() attend jusqu'à 1 s quand Deezer est fermé, et ceci est
    #  appelé toutes les 2 s par weather_music_service)
    if not await asyncio.to_thread(port_actif):
        return None
    try:
        return await evaluer(_JS_LECTURE, timeout=3)
    except Exception:
        return None


async def controle(action):
    """pause / lecture / suivant / precedent. Renvoie l'état avant l'action, ou None."""
    js = {
        "pause": "dzPlayer.control.pause();",
        "lecture": "dzPlayer.control.play();",
        "bascule": "dzPlayer.control.togglePause();",
        "suivant": "dzPlayer.control.nextSong();",
        "precedent": "dzPlayer.control.prevSong();",
    }[action]
    try:
        return await evaluer(f"const avant = {{ joue: dzPlayer.isPlaying() }}; {js} return avant;")
    except Exception as e:
        print(f"[DEEZER CDP] Échec commande {action} : {e}")
        return None


async def _verifier(titre=None, artiste=None, album=None, morceau_id=None, contexte_id=None, timeout=8):
    """Attend que le lecteur joue et que ce qui joue correspond : identifiant du morceau,
    identifiant du contexte de lecture (album, playlist, artiste : getContext().ID), et/ou
    titre, artiste, album. Un simple « ça joue » ne suffit pas : la musique précédente
    pourrait encore tourner."""
    ok = await _attendre("""
      if (!dzPlayer.isPlaying()) return null;
      if (p.morceau_id && String(dzPlayer.getSongId()) !== String(p.morceau_id)) return null;
      if (p.contexte_id && String((dzPlayer.getContext() || {}).ID) !== String(p.contexte_id)) return null;
      const t = norm(dzPlayer.getSongTitle()), a = norm(dzPlayer.getArtistName()), al = norm(dzPlayer.getAlbumTitle());
      if (p.titre && !t.startsWith(norm(p.titre))) return null;
      if (p.artiste && !a.includes(norm(p.artiste))) return null;
      if (p.album && al !== norm(p.album)) return null;
      return true;
    """, {"titre": titre, "artiste": artiste, "album": album, "morceau_id": morceau_id,
          "contexte_id": contexte_id}, timeout=timeout)
    if not ok:
        print(f"[DEEZER CDP] Lecture non confirmée : {await etat()}")
    return bool(ok)


# ── Lancements ────────────────────────────────────────────────────────────────

async def lancer_titre(titre, artiste, album_id=None, titre_court=None, morceau_id=None):
    """Recherche « titre artiste » et lance le morceau depuis la liste des résultats : la
    file de lecture devient cette liste, Deezer enchaîne ensuite sur les titres suivants.
    La ligne visée a exactement ce titre et, si connu, un lien vers son album (pour ne
    pas lancer une version karaoké ou une reprise qui porte les mêmes mots)."""
    await evaluer("location.hash = '#/search/' + encodeURIComponent(p.requete); return true;",
                  {"requete": f"{titre} {artiste}"})
    clic = await _attendre("""
      const titres = [norm(p.titre), norm(p.titre_court)].filter(Boolean);
      const lignes = [...document.querySelectorAll('button[aria-label^="Écouter "]')].map(b => {
        const m = b.getAttribute('aria-label').match(/^Écouter (.*) par (.*)$/);
        return m && titres.includes(norm(m[1])) ? { b, artiste: norm(m[2]) } : null;
      }).filter(Boolean);
      const dansAlbum = l => {
        let c = l.b;
        for (let i = 0; i < 7 && c; i++) {
          c = c.parentElement;
          if (c && c.querySelector('a[href*="/album/"]')) return !!c.querySelector(`a[href$="/album/${p.album_id}"]`);
        }
        return false;
      };
      const cible = (p.album_id && lignes.find(dansAlbum)) || lignes.find(l => l.artiste.includes(norm(p.artiste)));
      if (!cible) return null;
      const label = cible.b.getAttribute('aria-label');
      cible.b.click();
      return label;
    """, {"titre": titre, "titre_court": titre_court, "artiste": artiste, "album_id": album_id}, timeout=10)
    if not clic:
        print(f"[DEEZER CDP] Morceau « {titre} » introuvable dans les résultats de recherche")
        return False
    print(f"[DEEZER CDP] Clic : {clic}")
    if morceau_id:
        return await _verifier(morceau_id=morceau_id)
    return await _verifier(titre=titre_court or titre, artiste=artiste)


_JS_SIGNATURE_PAGE = """
const signature = () => [...document.querySelectorAll('[data-testid="masthead-subtitle"], [data-testid="title"]')]
  .slice(0, 3).map(e => e.innerText).join('|');
"""


_JS_SENS_TRI = r"""
if (!location.hash.endsWith(`/playlist/${p.id}`) || !document.querySelector('[data-testid="masthead"]')) return null;
const dates = [...document.querySelectorAll('[role="row"]')].map(l => (l.innerText || '').match(/\b(\d{2})\/(\d{2})\/(\d{4})\b/))
  .filter(Boolean).map(m => Number(m[3] + m[2] + m[1]));
if (dates.length < 2 || dates[0] === dates[dates.length - 1]) return 'plat';
return dates[0] > dates[dates.length - 1] ? 'recent' : 'ancien';
"""


async def trier_recent_en_premier(ident):
    """Trie la playlist affichée par date d'ajout, les titres ajoutés le plus récemment en premier : Deezer joue
    dans l'ordre affiché. Un clic sur « AJOUTÉ » alterne ancien/récent en premier ; Deezer retient le dernier tri.
    La direction se lit sur les dates des lignes affichées (deux lectures identiques : la page a fini de charger).
    Sans colonne de dates (playlist éditoriale, un seul titre), rien n'est fait."""
    for _ in range(4):
        sens = await _attendre(_JS_SENS_TRI, {"id": str(ident)}, timeout=10)
        await asyncio.sleep(0.5)
        try:
            controle = await evaluer(_JS_SENS_TRI, {"id": str(ident)})
        except Exception:
            controle = None
        if not sens or sens != controle:
            continue
        if sens in ("recent", "plat"):
            return True
        clic = await evaluer("""
          const b = [...document.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'AJOUTÉ');
          if (!b) return false;
          b.click();
          return true;
        """)
        if not clic:
            return False
        print("[DEEZER CDP] Playlist triée : titres ajoutés le plus récemment en premier")
        await asyncio.sleep(1.2)
    return False


async def lancer_page(genre, ident, titre, artiste=None):
    """Ouvre la page album / playlist / artiste par son identifiant et clique son bouton
    de lecture (album-play_small-button, playlist-play_small-button, artist-play-button ;
    « play_button_play » est celui du lecteur en bas, présent sur toutes les pages).

    Pour ne jamais cliquer le bouton de la page précédente pendant le chargement (la page
    peut être réutilisée d'un album à l'autre), on attend que le contenu affiché (en-tête
    et premiers titres) ait changé, sauf si la page demandée était déjà affichée."""
    params = {"genre": genre, "id": str(ident)}
    params["avant"] = await evaluer(_JS_SIGNATURE_PAGE + """
      const deja = location.hash.endsWith(`/${p.genre}/${p.id}`);
      const avant = deja ? null : signature();
      location.hash = `#/${langue()}/${p.genre}/${p.id}`;
      return avant;
    """, params)
    if genre == "playlist":
        await trier_recent_en_premier(ident)
        # Lecture depuis la première ligne de la liste triée : la playlist repart toujours du titre ajouté le plus
        # récemment (le bouton de la page, lui, reprendrait la file en cours, ancien ordre compris). Si elle joue
        # déjà, on n'y touche pas.
        ligne = await _attendre("""
          if (!location.hash.endsWith(`/playlist/${p.id}`)) return null;
          if (dzPlayer.isPlaying() && String((dzPlayer.getContext() || {}).ID) === String(p.id)) return 'déjà en cours';
          const b = document.querySelector('#page_content [role="row"] button[aria-label^="Écouter "]');
          if (!b) return null;
          const nom = b.getAttribute('aria-label');
          b.click();
          return nom;
        """, {"id": str(ident)}, timeout=6)
        if ligne:
            print(f"[DEEZER CDP] Playlist « {titre} » : {ligne}")
            return await _verifier(contexte_id=ident)
    clic = await _attendre(_JS_SIGNATURE_PAGE + """
      if (!location.hash.endsWith(`/${p.genre}/${p.id}`)) return null;
      const sig = signature();
      if (!sig || (p.avant !== null && sig === p.avant)) return null;
      // Le bouton de la page est celui qui suit son en-tête (masthead), absent des pages
      // d'artiste : on ne clique pas une playlist suggérée de la page précédente.
      const tete = document.querySelector('[data-testid="masthead"]');
      if (!tete) return null;
      const b = [...document.querySelectorAll(`[data-testid="${p.genre}-play_small-button"], [data-testid="${p.genre}-play-button"]`)]
        .find(x => tete.compareDocumentPosition(x) & Node.DOCUMENT_POSITION_FOLLOWING);
      if (!b) return null;
      // Déjà en cours de lecture : le bouton de la page est alors un bouton « pause », le cliquer couperait la musique
      if (dzPlayer.isPlaying() && String((dzPlayer.getContext() || {}).ID) === String(p.id)) return 'déjà en cours';
      b.click();
      return b.getAttribute('aria-label') || 'lecture';
    """, params, timeout=12)
    if not clic:
        print(f"[DEEZER CDP] Bouton de lecture introuvable sur la page {genre}/{ident}")
        return False
    print(f"[DEEZER CDP] Clic « {clic} » sur la page {genre} « {titre} »")
    return await _verifier(contexte_id=ident)


async def lancer_artiste(nom, ident, mix=False):
    """Lance les « Top titres » (ou le « Mix artiste ») d'un artiste depuis sa carte
    « Meilleur résultat » de la recherche. (Le bouton principal de la page d'artiste,
    lui, lance un mix.)"""
    await evaluer("location.hash = '#/search/' + encodeURIComponent(p.nom); return true;", {"nom": nom})
    clic = await _attendre("""
      const bloc = [...document.querySelectorAll('[data-testid="artist_top_result_block"]')]
        .find(x => x.querySelector(`a[href$="/artist/${p.id}"]`));
      if (!bloc) return null;
      const motif = p.mix ? /^Mix/ : /^Top titres/;
      const b = [...bloc.querySelectorAll('button')].find(x => motif.test(x.getAttribute('aria-label') || x.innerText || ''));
      if (!b) return null;
      b.click();
      return b.getAttribute('aria-label') || b.innerText;
    """, {"nom": nom, "id": str(ident), "mix": mix}, timeout=10)
    if not clic:
        print(f"[DEEZER CDP] Carte de l'artiste « {nom} » introuvable dans la recherche")
        return False
    print(f"[DEEZER CDP] Clic « {clic} » sur la carte de l'artiste « {nom} »")
    return await _verifier(contexte_id=ident)


async def trouver_playlist_bibliotheque(requete):
    """(identifiant, nom) d'une playlist de la bibliothèque de l'utilisateur dont le nom correspond à
    `requete` (égalité d'abord, sinon inclusion, sinon tous les mots), ou None.

    Les playlists sont lues sur la page « Bibliothèque > Playlists » : la barre latérale et l'accueil
    mélangent les playlists de l'utilisateur et des suggestions de Deezer."""
    try:
        await evaluer("location.hash = '#/' + langue() + '/library/playlists'; return true;")
        res = await _attendre("""
          const zone = document.querySelector('#page_content');
          if (!zone || !document.querySelector('[data-testid="open_history_thumbnail"]')) return null;
          const pl = [...zone.querySelectorAll('a[href*="/playlist/"]')].map(a => ({
            id: (a.getAttribute('href').match(/\\/playlist\\/(\\d+)/) || [])[1],
            nom: (a.innerText || '').split('\\n')[0].trim(),
          })).filter(x => x.id && x.nom);
          if (!pl.length || !location.hash.includes('/library/playlists')) return null;
          const q = norm(p.requete);
          const mots = (p.requete || '').split(/\\s+/).map(norm).filter(m => m.length > 1);
          const t = pl.find(x => norm(x.nom) === q) || pl.find(x => norm(x.nom).includes(q))
            || (mots.length ? pl.find(x => mots.every(m => norm(x.nom).includes(m))) : null);
          return { trouve: t ? [t.id, t.nom] : null, noms: pl.map(x => x.nom) };
        """, {"requete": requete}, timeout=10)
        if res and res.get("trouve"):
            return tuple(res["trouve"])
        if res:
            print(f"[DEEZER CDP] Aucune de vos playlists ne correspond à « {requete} » : {res.get('noms')}")
        return None
    except Exception:
        return None


# ── Volume, Flow ──────────────────────────────────────────────────────────────

async def volume():
    """Volume du lecteur Deezer (0 à 1), ou None si injoignable."""
    try:
        return await evaluer("return dzPlayer.getVolume();")
    except Exception:
        return None


async def regler_volume(valeur):
    """Règle le volume du lecteur Deezer (0 à 1) sans toucher au volume de Windows. Renvoie le volume appliqué."""
    valeur = max(0.0, min(1.0, float(valeur)))
    try:
        return await evaluer("dzPlayer.control.setVolume(p.v); return dzPlayer.getVolume();", {"v": valeur})
    except Exception as e:
        print(f"[DEEZER CDP] Échec réglage du volume : {e}")
        return None


async def lancer_flow():
    """Lance le Flow (bouton de lecture de la section Flow de l'accueil)."""
    await evaluer("location.hash = '#/' + langue() + '/'; return true;")
    clic = await _attendre("""
      if (location.hash.replace(/\\/$/, '').split('/').length > 3) return null;
      const b = document.querySelector('[data-testid="flow-config-default"] button[aria-label="Écouter"]');
      if (!b) return null;
      b.click();
      return 'Flow';
    """, timeout=15)
    if not clic:
        print("[DEEZER CDP] Bouton du Flow introuvable sur l'accueil")
        return False
    print("[DEEZER CDP] Clic sur le Flow")
    ok = await _attendre("return dzPlayer.isPlaying() && dzPlayer.isRadio && dzPlayer.isRadio() ? true : null;", timeout=10)
    if not ok:
        print(f"[DEEZER CDP] Flow non confirmé : {await etat()}")
    return bool(ok)


async def appliquer_lecture(joue, tentatives=3):
    """Met le lecteur en lecture (joue=True) ou en pause (joue=False) et vérifie. Juste après le lancement d'un
    morceau, le lecteur peut relancer la lecture tout seul en finissant de charger : on réessaie."""
    for _ in range(tentatives):
        await controle("lecture" if joue else "pause")
        await asyncio.sleep(0.6)
        e = await etat()
        if e is not None and bool(e.get("joue")) == bool(joue):
            return True
    return False


async def position():
    """Position de lecture en secondes, ou None."""
    try:
        return await evaluer("return typeof dzPlayer.getPosition === 'function' ? dzPlayer.getPosition() : null;")
    except Exception:
        return None
