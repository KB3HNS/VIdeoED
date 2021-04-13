#!/usr/bin/env python

import gtk

SCALEPIX=.97

#
# This class is to help in keeping track of the in and out markers
# Be aware of some number fudging with the pix value, it won't hold water if the gtk theme changes!
# The mark-in and mark-out wigdets are entirely stored here so the control class doesn't have to
# worry about them.  All it really needs is a blank window area of type Fixed for free-style widget
# placement.
#
class Marker:
	imgIn, imgOut = None, None
	next = None
	markIn,markOut=-1,-1
	def __init__(self, draw, markIn, pix):
		self._init(draw, markIn, pix)
	
	# Get properties
	def getIn(self):
		return self.markIn

	def getOut(self):
		return self.markOut

	def getNext(self):
		return self.next
	
	# Dont use these function!
	def In(self, draw, markIn, pix):
		draw.remove(self.imgIn)
		self._init(draw, markIn, pix)
	
	def _init(self, draw, markIn, pix):
		img=gtk.image_new_from_stock(gtk.STOCK_GOTO_TOP, gtk.ICON_SIZE_MENU)
		img.show()
		text=gtk.Label(str(markIn))
		text.show()
		self.imgIn=gtk.VBox(False, 0)
		self.imgIn.pack_start(img, True, False, 0)
		self.imgIn.pack_start(text, True, False, 0)
		self.imgIn.show()
		self.markIn=markIn
		draw.put(self.imgIn, int(SCALEPIX*pix), 0)

	def Out(self, draw, markOut, pix):
		if (self.imgOut):
			draw.remove(self.imgOut)
			self.imgOut=None

		img=gtk.image_new_from_stock(gtk.STOCK_GOTO_BOTTOM, gtk.ICON_SIZE_MENU)
		img.show()
		text=gtk.Label(str(markOut))
		text.show()
		self.imgOut=gtk.VBox(False, 0)
		self.imgOut.pack_start(img, True, False, 0)
		self.imgOut.pack_start(text, True, False, 0)
		self.imgOut.show()
		self.markOut=markOut
		draw.put(self.imgOut, int(SCALEPIX*pix), 0)

	def setNext(self, draw, markIn, pix):
		self.next=Marker(draw, markIn, pix)
		return self.next
	
	
	def remove(self, draw):
		draw.remove(self.imgIn)
		if (self.imgOut):
			draw.remove(self.imgOut)
			self.imgOut=None

		self.markIn=-1
		self.markOut=-1
		self.next=None

	# Use these functions! (added bonus, ready for callbacks)
	def setIn(self, draw, markIn, pix):
		if (self.markOut == -1 or markIn < self.markOut):
			self.In(draw, markIn, pix)
			return True

		if (markIn == self.markOut):
			if (self.next):
				print "Error, Cannot clear markOut when there is another marker!"
				return False

			draw.remove(self.imgOut)
			self.markOut=-1
			self.imgOut=None
			self.In(draw, markIn, pix)
			return True

		if (self.next):
			return self.next.setIn(draw, markIn, pix)
			
		return self.setNext(draw, markIn, pix)

	def setOut(self, draw, markOut, pix):
		if (markOut <= self.markIn):
			print "Error! Cannot set markOut before markIn!"
			return False		
		
		if (self.markOut == -1):
			self.Out(draw, markOut, pix)
			return True

		if (markOut < self.markOut and markOut > self.markIn):
			self.Out(draw, markOut, pix)
			return True

		if (self.next == None):
			self.Out(draw, markOut, pix)
			return True

		this=self.next
		if (markOut < this.getIn()):
			self.Out(draw, markOut, pix)
			return True
		
		return this.setOut(draw, markOut, pix)

	def delete(self,draw,prev=None):
		if (self.next):
			return self.next.delete(draw,self)

		if (prev):
			self.remove(draw)
			prev.next=None
			return True

		self.clear(draw)
		return True

	def clear(self,draw):
		while(self.next):
			self.next.delete(draw,self)

		if (self.imgOut):
			draw.remove(self.imgOut)
			self.imgOut=None

		self.In(draw, 0, 0)
		self.markOut=-1

