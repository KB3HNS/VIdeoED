#!/usr/bin/env python

import pango, pygtk, gtk

PADDING = 2

class ControlButton:

	set, img1, img2, text1, text2=None, None, None, None, None
	ebox, vbox, img, text=None, None, None, None

	def __init__ (self, img1, text1, img2, text2, callbackPress, callbackRelease):
		vbox=gtk.VBox(False, 0)
		img=gtk.image_new_from_stock(img1, gtk.ICON_SIZE_MENU)
		text=gtk.Label(text1)
		img.set_padding(PADDING, PADDING)
		img.show()
		vbox.pack_start(img, True, False, 0)
		vbox.pack_start(text, True, False, 0)
		ebox=gtk.EventBox()
		ebox.add(vbox)

		if (callbackPress != None):
			ebox.connect("button-press-event", callbackPress)
                
		if (callbackRelease != None):
			ebox.connect("button-release-event", callbackRelease)

		self.img1=img1
		self.img2=img2
		self.text1=text1
		self.text2=text2

		self.ebox=ebox
		self.vbox=vbox
		self.img=img
		self.text=text

		set=True

	def switch(self, set):
		if (set == self.set):
			return

		img=gtk.image_new_from_stock((self.img1 if set else self.img2),  gtk.ICON_SIZE_MENU)
		img.set_padding(PADDING, PADDING)
		img.show()
		self.text.set_text(self.text1 if set else self.text2)
		#vbox=gtk.VBox(False, 0)
		#vbox.pack_start(img, True, False, 0)
		#vbox.pack_start(text, True, False, 0)

		#self.ebox.remove(self.vbox)
		#self.ebox.add(vbox)
		self.vbox.remove(self.img)
		self.vbox.pack_start(img, True, False, 0)
		self.vbox.reorder_child(img, 0)
		#self.vbox.remove(self.text)
		#self.vbox.pack_start(text, True, False, 0)

		self.set = set
		#self.vbox=vbox
		self.img=img
		#self.text=text

	def getObject(self):
		return self.ebox


