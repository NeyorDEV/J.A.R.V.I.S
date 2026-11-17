"""Découpage des enregistrements d'enrôlement en extraits courts (profil vocal)."""
import math
import struct

from core.voix_extraits import extraits_courts

RATE = 16000


def son(secondes, amplitude=6000):
    """Un ton de `secondes` secondes (PCM 16 bits mono)."""
    return b"".join(struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 300 * i / RATE))) for i in range(int(secondes * RATE)))


def silence(secondes):
    return b"\x00\x00" * int(secondes * RATE)


def test_fenetres_d_une_seconde_tous_les_0_4_s():
    ex = extraits_courts(son(4.2), RATE, maximum=100)
    assert ex and all(len(e) == RATE * 2 for e in ex)   # 1 s = 16 000 échantillons de 2 octets
    assert len(ex) == 8                                  # départs à 0,3 ; 0,7 ; 1,1 ; … ; 3,1 s : 8 fenêtres de 1 s tiennent dans 4,2 s


def test_les_passages_silencieux_sont_ecartes():
    ex = extraits_courts(silence(2.0) + son(2.0) + silence(2.0), RATE, maximum=100)
    assert ex and len(ex) < 10                           # moins de fenêtres que sur 6 s de son continu
    assert all(max(struct.unpack("<%dh" % (len(e) // 2), e)) > 1000 for e in ex)   # aucune fenêtre vide


def test_plafond_avec_fenetres_reparties_sur_toute_la_phrase():
    long = son(12.0)
    ex = extraits_courts(long, RATE, maximum=4)
    assert len(ex) == 4
    tout = extraits_courts(long, RATE, maximum=1000)
    assert ex[0] == tout[0] and ex[-1] == tout[-1]       # la première et la dernière sont conservées : pas seulement le début


def test_audio_trop_court_ou_vide():
    assert extraits_courts(son(0.8), RATE) == []
    assert extraits_courts(b"", RATE) == []
    assert extraits_courts(b"\x01", RATE) == []          # octet isolé


def test_un_seul_extrait_demande():
    ex = extraits_courts(son(5.0), RATE, maximum=1)
    assert len(ex) == 1
