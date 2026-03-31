#!/usr/bin/python3
import cgi
import cgitb
import sys

# Fehler im Browser anzeigen
cgitb.enable()

class Form:
    def __init__(self):
        # FieldStorage initialisieren
        self.form = cgi.FieldStorage()

    def getvalue(self, key, default=None):
        # Wert holen (z.B. für pattern oder d)
        return self.form.getvalue(key, default)

    def __contains__(self, key):
        # Prüfen ob key existiert (z.B. 'if "file" in form')
        return key in self.form

    def __getitem__(self, key):
        # Zugriff wie Dictionary (z.B. form['file'])
        return self.form[key]
