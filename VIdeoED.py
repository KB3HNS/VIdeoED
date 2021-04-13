#!/usr/bin/env python

import pygtk, gtk

import control

try:
    import psyco
    psyco.full()
except ImportError:
    print "Missing Psyco.  Continuing without optimization"
    pass

control=control.Control()
#vbox=gtk.VBox(False,0)
#vbox.pack_start(control.hbox,False,False,0)
gtk.main()

