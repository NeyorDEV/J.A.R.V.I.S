"""Les tests importent le code du backend tel quel (sans lancer JARVIS) : core.*, module.*, plugins.*."""
import os
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "backend"))
