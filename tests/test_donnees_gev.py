"""Données françaises de la Vue de Dieu (module/gev_donnees_fr.py) : conversions testées sur de petits exemples fabriqués, sans réseau."""
import pytest

from module import gev_donnees_fr as g


def test_tous_les_jeux_sont_declares_et_appelables():
    # garde-fou : un nettoyage qui supprimerait par erreur une fonction de mise à jour casserait aussi le démarrage de JARVIS
    attendus = {"vigilance", "seismes", "crues", "air", "recharge", "avalanche", "electricite", "secheresse", "trafic", "seveso", "baignade", "parkings"}
    assert attendus <= set(g.JEUX)
    for nom, (maj, validite) in g.JEUX.items():
        assert callable(maj) and validite > 0, nom


def test_electricite_derniere_valeur_complete_par_region():
    lignes = [
        {"code_insee_region": "84", "libelle_region": "Auvergne-Rhône-Alpes", "date_heure": "2026-11-16T22:45:00+00:00", "consommation": None, "nucleaire": None},   # créneau pas encore rempli
        {"code_insee_region": "84", "libelle_region": "Auvergne-Rhône-Alpes", "date_heure": "2026-11-16T11:45:00+00:00", "consommation": 7995, "nucleaire": 10638, "eolien": 194, "solaire": 835,
         "hydraulique": 2161, "thermique": 461, "bioenergies": 80, "ech_physiques": -6055},
        {"code_insee_region": "84", "libelle_region": "Auvergne-Rhône-Alpes", "date_heure": "2026-11-16T11:30:00+00:00", "consommation": 1, "nucleaire": 1, "eolien": 1, "solaire": 1, "hydraulique": 1, "thermique": 1, "bioenergies": 1},
        {"code_insee_region": "99", "libelle_region": "Inconnue", "consommation": 1, "nucleaire": 1, "eolien": 1, "solaire": 1, "hydraulique": 1, "thermique": 1, "bioenergies": 1},
    ]
    r = g.convertir_electricite(lignes)
    assert len(r) == 1 and r[0][0] == "84" and r[0][5:] == [7995, 10638, 194, 835, 2161, 461, 80, -6055]


def test_secheresse_niveaux_par_usage():
    r = g.convertir_secheresse([{"code": "42", "niveauGraviteMax": "crise", "niveauGraviteSupMax": "alerte", "niveauGraviteSouMax": None, "niveauGraviteAepMax": "vigilance"}, {"code": "75"}, {"nom": "sans code"}])
    assert r == {"42": [4, 2, 0, 1], "75": [0, 0, 0, 0]}


XML_TRAFIC = """<?xml version="1.0"?><d2LogicalModel xmlns="http://datex2.eu/schema/2/2_0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<payloadPublication><situation id="a"><overallSeverity>high</overallSeverity>
<situationRecord xsi:type="Accident" id="a1"><validity><validityTimeSpecification><overallStartTime>2026-11-16T06:00:00+01:00</overallStartTime></validityTimeSpecification></validity>
<generalPublicComment><comment><values><value lang="fr">Accident
 sur la N7</value></values></comment></generalPublicComment>
<groupOfLocations><point><pointCoordinates><latitude>45.5</latitude><longitude>4.5</longitude></pointCoordinates></point></groupOfLocations></situationRecord>
<situationRecord xsi:type="Accident" id="a2"><validity><validityTimeSpecification><overallStartTime>2026-11-16T06:00:00+01:00</overallStartTime><overallEndTime>2026-11-16T07:00:00+01:00</overallEndTime></validityTimeSpecification></validity>
<groupOfLocations><point><pointCoordinates><latitude>45.6</latitude><longitude>4.6</longitude></pointCoordinates></point></groupOfLocations></situationRecord>
<situationRecord xsi:type="MaintenanceWorks" id="a3"><validity><validityTimeSpecification><overallStartTime>2027-01-01T08:00:00+01:00</overallStartTime></validityTimeSpecification></validity>
<groupOfLocations><point><pointCoordinates><latitude>45.7</latitude><longitude>4.7</longitude></pointCoordinates></point></groupOfLocations></situationRecord>
<situationRecord xsi:type="TypeInconnu" id="a4"><groupOfLocations><point><pointCoordinates><latitude>45.8</latitude><longitude>4.8</longitude></pointCoordinates></point></groupOfLocations></situationRecord>
</situation></payloadPublication></d2LogicalModel>"""


def test_trafic_ne_garde_que_les_evenements_en_cours():
    from datetime import datetime, timezone
    ev = g.convertir_trafic(XML_TRAFIC, maintenant=datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc))
    assert len(ev) == 1   # a2 est terminé, a3 n'a pas commencé, a4 est d'un type inconnu
    cat, libelle, lat, lon, texte, gravite = ev[0][:6]
    assert (cat, libelle, lat, lon, gravite) == ("incident", "Accident", 45.5, 4.5, "high") and texte == "Accident sur la N7"   # sauts de ligne aplatis


def test_seveso_conversion_et_champs():
    r = g.convertir_seveso([
        {"raisonSociale": " BASF ", "commune": "Roussillon", "latitude": 45.36, "longitude": 4.79, "statutSeveso": "Seveso seuil haut", "regime": "Autorisation", "adresse1": "Plateforme chimique", "codePostal": "38150",
         "codeNaf": "20", "prioriteNationale": True, "ied": False, "serviceAIOT": "DREAL AURA", "codeAIOT": "0003205117", "etatActivite": "En exploitation avec titre",
         "inspections": [{"dateInspection": "2022-12-01"}, {"dateInspection": "2026-07-22"}]},
        {"raisonSociale": "X", "latitude": 45, "longitude": 4, "statutSeveso": "Non Seveso"},
        {"raisonSociale": "Fermé", "latitude": 45, "longitude": 4, "statutSeveso": "Seveso seuil bas", "etatActivite": "Cessation d'activité"},
        {"raisonSociale": "Sans position", "statutSeveso": "Seveso seuil bas"},
    ])
    assert len(r) == 1
    s = r[0]
    assert len(s) == 15 and s[0] == "BASF" and s[4] == 2 and s[7] == "Industrie chimique" and s[8] == 1 and s[10] == 2 and s[11] == "2026-07-22" and s[13] == "0003205117" and s[14] == []


def test_seveso_rubriques_substances_d_abord():
    rubriques = [{"numeroRubrique": "2552", "nature": "Fonderie", "quantiteTotale": "1900.000", "unite": "kg/j"},
                 {"numeroRubrique": "4711", "nature": "Composés de nickel", "quantiteTotale": None, "unite": None},
                 {"numeroRubrique": "4711", "nature": "doublon"}, {"nature": "sans numéro"}]
    assert g.resumer_rubriques(rubriques) == [["4711", "Composés de nickel", ""], ["2552", "Fonderie", "1900 kg/j"]]


def test_baignade_csv():
    csv = ("index;nom_site;libelle_geographique;libelle_departement;latitude;longitude;type_eau_norm;qualite\n"
           "0;PLAGE DU PORT;Nice;Alpes-Maritimes;43.69;7.28;COTIERE;Excellent\n1;SANS POSITION;X;Y;;;INTERIEURE;Bon\n2;HORS FRANCE;X;Y;10.0;100.0;INTERIEURE;Bon\n")
    r = g.convertir_baignade(csv)
    assert r == [["Plage Du Port", "Nice", "Alpes-Maritimes", 43.69, 7.28, 1, "Excellent"]]


XML_BRA = """<?xml version="1.0"?><BULLETINS_NEIGE_AVALANCHE MASSIF="Aravis" DATEBULLETIN="2026-11-14T16:00:00" DATEECHEANCE="2026-11-15T18:00:00">
<CARTOUCHERISQUE><RISQUE RISQUE1="1" ALTITUDE="2500" RISQUE2="3" RISQUEMAXI="3" RISQUEMAXIJ2="2" COMMENTAIRE="Au-dessus de 2500 m, marqué"/>
<RESUME><![CDATA[Départs spontanés : RAS
Déclenchements skieurs : plaques à vent]]></RESUME></CARTOUCHERISQUE></BULLETINS_NEIGE_AVALANCHE>"""


def test_avalanche_bulletin():
    b = g._extraire_bulletin(XML_BRA)
    assert (b["r"], b["r2"], b["r1"], b["hautr"], b["alt"]) == (3, 2, 1, 3, "2500") and "plaques à vent" in b["resume"] and b["date"] == "2026-11-14T16:00:00"


def test_avalanche_noms_embrunais_et_accents():
    assert g._nom_cle("Embrunnais Parpaillon") == g._nom_cle("Embrunais-Parpaillon")
    assert g._nom_cle("Haute-Ariège") == g._nom_cle("Haute-Ariege")


def test_massifs_geojson_simplifie():
    geo = {"features": [{"properties": {"code": 1, "title": "Chablais", "mountain": "Alpes du Nord"},
                         "geometry": {"type": "Polygon", "coordinates": [[[6.0, 46.0], [6.1, 46.0], [6.1, 46.1], [6.0, 46.1], [6.0, 46.0]]]}},
                        {"properties": {"title": "Sans géométrie"}, "geometry": {"type": "Polygon", "coordinates": []}}]}
    r = g.convertir_massifs(geo)
    assert len(r) == 1 and r[0][1] == "Chablais" and r[0][2] == "Alpes du Nord" and len(r[0][3]) == 1


def test_vigilance_conversion():
    carte = {"product": {"periods": [{"echeance": "J", "begin_validity_time": "b", "end_validity_time": "e", "timelaps": {"domain_ids": [
        {"domain_id": "FRA", "max_color_id": 3, "phenomenon_items": []},
        {"domain_id": "2A", "max_color_id": 2, "phenomenon_items": [{"phenomenon_id": 1, "phenomenon_max_color_id": 2}, {"phenomenon_id": 9, "phenomenon_max_color_id": 1}]}]}}, {"echeance": "J1", "timelaps": {"domain_ids": []}}]}}
    assert g.convertir_vigilance(carte) == [{"e": "J", "d": "b", "f": "e", "z": {"2A": [2, {"1": 2, "9": 1}]}}]


@pytest.mark.parametrize("x,y,lat,lon", [(652469.0, 6862047.0, 48.857, 2.352)])
def test_lambert93_paris(x, y, lat, lon):
    # la conversion de coordonnées n'est plus utilisée par un jeu, mais gardée : vérifiée si elle existe
    if not hasattr(g, "lambert93_vers_wgs84"):
        pytest.skip("conversion retirée avec les ralentissements mesurés")
    la, lo = g.lambert93_vers_wgs84(x, y)
    assert abs(la - lat) < 0.01 and abs(lo - lon) < 0.01


def test_parkings_bnls_champ_multiligne_et_hors_france():
    # le CSV de Saemes a un champ entre guillemets avec retour à la ligne : un découpage ligne à ligne le casserait
    texte = ('id;nom;insee;adresse;url;type_usagers;gratuit;nb_places;nb_pr;nb_pmr;nb_voitures_electriques;nb_velo;nb_2r_el;nb_autopartage;nb_2_rm;nb_covoit;hauteur_max;num_siret;Xlong;Ylat;tarif_pmr;tarif_1h;tarif_2h;tarif_3h;tarif_4h;tarif_24h\n'
             '75107-P-042;BAC MONTALEMBERT;75107;39 rue du Bac;https://x;tous;0;425;0;8;191;79;0;0;57;0;190;"\t\n31 703";2.32699912;48.8566579;;5.1;10.2;15.3;20.4;45.9\n'
             '99999-P-001;Ailleurs;99999;nulle part;;tous;1;10;0;0;0;0;0;0;0;0;0;1;120.0;0.0;;;;;;\n')
    r = g.convertir_parkings_bnls(texte, "BNLS")
    assert len(r) == 1 and r[0][:6] == ["Bac Montalembert", "39 rue du Bac", 48.85666, 2.327, 425, 0] and r[0][8:11] == [190, 5.1, 45.9] and r[0][11] == "BNLS"


def test_parkings_indigo_position_latitude_d_abord():
    doc = {"places": [{"name": [{"language": "fr", "string": "GARE DE LYON"}], "indicativePointLocation": {"type": "Point", "coordinates": [45.76, 4.85]}, "characteristics": {"spacesTotal": 300}},
                     {"name": [{"string": "Sans position"}]}, {"name": [{"string": "Hors de France"}], "indicativePointLocation": {"coordinates": [10.0, 100.0]}}]}
    r = g.convertir_parkings_indigo(doc)
    assert len(r) == 1 and r[0][0] == "Gare De Lyon" and r[0][2:5] == [45.76, 4.85, 300] and r[0][11] == "Indigo"


def test_parkings_fusion_garde_le_premier_a_moins_de_60_m():
    a = ["BNLS", "", 48.8566, 2.3270, 100, 0, 0, 0, 0, None, None, "BNLS", ""]
    proche = ["Indigo", "", 48.85663, 2.32703, 0, 0, 0, 0, 0, None, None, "Indigo", ""]   # ~4 m : même parking
    loin = ["Indigo", "", 48.8576, 2.3270, 0, 0, 0, 0, 0, None, None, "Indigo", ""]       # ~110 m : un autre
    r = g.fusionner_parkings([a], [proche, loin])
    assert [p[0] for p in r] == ["BNLS", "Indigo"] and r[1][2] == 48.8576


def test_demarrer_ne_plante_pas_et_ne_masque_pas_l_etat_interne(monkeypatch):
    # régression : une fonction nommée « _etat » avait remplacé le dictionnaire _etat du module et fait échouer demarrer() (donc toute la vue de Dieu)
    monkeypatch.setattr(g, "JEUX", {})
    assert isinstance(g._etat, dict)
    assert "JARVIS_DONNEES_DIR" in g.demarrer()
    g.arreter()


def test_parkings_nantes_statuts_et_donnees_perimees():
    from datetime import datetime, timezone
    maintenant = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    base = {"grp_nom": "FEYDEAU", "adresse": "Parvis Neptune", "grp_exploitation": 490, "grp_complet": 10, "location": {"lon": -1.55, "lat": 47.21}}
    def un(**kw):
        return g.convertir_nantes([{**base, "grp_horodatage": "2026-11-19T08:50:00+00:00", **kw}], maintenant=maintenant)[0]
    ouvert = un(grp_statut=5, grp_disponible=328)
    assert ouvert[13] == 328 and ouvert[15] == "ouvert" and ouvert[4] == 490 and ouvert[0] == "Feydeau"
    assert un(grp_statut=5, grp_disponible=8)[15] == "complet"        # sous le seuil « complet » du parking
    assert un(grp_statut=1, grp_disponible=300)[13:] [0] is None and un(grp_statut=1, grp_disponible=300)[15] == "ferme"   # fermé : pas de places affichées
    assert un(grp_statut=2, grp_disponible=300)[15] == "abonnes"
    assert un(grp_statut=0, grp_disponible=300)[13] is None and un(grp_statut=0, grp_disponible=300)[15] is None           # comptage hors service
    perime = g.convertir_nantes([{**base, "grp_statut": 5, "grp_disponible": 300, "grp_horodatage": "2026-11-19T07:00:00+00:00"}], maintenant=maintenant)[0]
    assert perime[13] is None and perime[15] is None                    # plus de 30 minutes : une valeur périmée est pire qu'une valeur absente


def test_parkings_aix_tours_clermont():
    aix = g.convertir_aix([{"nom": "Cours Julien", "voitureplacescapacite": 250.0, "voitureplacesdisponibles": 40.0, "tempsreel": "True", "adresse": "58 Cours Julien", "commune": "MARSEILLE",
                            "latitude": 43.29, "longitude": 5.38, "datemajpy": "2026-11-19 09:05:04", "producteur": "MAMP"},
                           {"nom": "Sans direct", "voitureplacescapacite": 100.0, "voitureplacesdisponibles": 100.0, "tempsreel": "False", "latitude": 43.3, "longitude": 5.4}])
    assert aix[0][13] == 40 and aix[0][15] == "ouvert" and aix[0][14] == "2026-11-19T09:05:04" and aix[1][13] is None and aix[1][15] is None
    tours = g.convertir_tours([{"libelle_parking": "Parc Halles", "adresse": "36 Place X", "commune": "Tours", "geo_point": {"lon": 0.68, "lat": 47.39}, "capacite": 670, "free_spots": 0, "hauteur_max_premier_niveau": "2,5 m"}])
    assert tours[0][13] == 0 and tours[0][15] == "complet" and tours[0][8] == 250
    clermont = g.convertir_clermont([{"nom": "Vercingetorix", "latitude": 45.77, "longitude": 3.08, "places_libres": 173, "capacite_maximale": 262, "etat": "Valide"},
                                     {"nom": "Panne", "latitude": 45.78, "longitude": 3.09, "places_libres": 5, "capacite_maximale": 50, "etat": "Hors service"}])
    assert clermont[0][13] == 173 and clermont[1][13] is None


def test_fusion_le_direct_l_emporte_mais_deux_voisins_d_une_meme_liste_restent():
    direct = [["A", "", 48.8566, 2.3270, 100, 0, 0, 0, 0, None, None, "X", "", 10, "", "ouvert"], ["B", "", 48.85662, 2.32702, 50, 0, 0, 0, 0, None, None, "X", "", 5, "", "ouvert"]]
    statique = [["A statique", "", 48.85661, 2.32701, 100, 0, 0, 0, 0, None, None, "BNLS", "", None, "", None]]
    r = g.fusionner_parkings(direct, statique)
    assert [p[0] for p in r] == ["A", "B"]
