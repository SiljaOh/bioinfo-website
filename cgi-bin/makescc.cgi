#!/usr/bin/env python3

import sys
import cgi
import cgitb

cgitb.enable()
sys.path.insert(0, "/home/f/fiocco/public_html/cgi-bin")

from makescc import main

print("Content-Type: text/plain")
print()

form = cgi.FieldStorage()

class Args:
    pass

args = Args()
args.id = form.getfirst("id")
args.distance = float(form.getfirst("distance"))
args.atom_type = form.getfirst("type")
args.length = int(form.getfirst("length"))
args.contactmatrix = None

main(args)
