"""Accès synchronisés à l'état du moteur de parole (core/speech.py), utilisés par le VAD."""

import core.speech as speech


# Synchronisation dynamique des états (important pour le VAD)
def get_is_speaking(): return speech.is_speaking


def get_stop_parler(): return speech.STOP_PARLER


def set_stop_parler(val): speech.STOP_PARLER = val


def get_dernier_parle_time(): return speech.dernier_parle_time
