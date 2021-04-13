#!/usr/bin/env python

import pango, pygtk, gtk, sys, os
from xml.dom import minidom
from xml.dom.minidom import parse

from cbutton import ControlButton
from marker import Marker
from mplayer import Mplayer
from builder2 import Builder2
from seek import Seeker

PROG_WIDTH, PROG_HEIGHT = 1000, 55

SEEK_STEP = 30
VERSION = 1.0

#
#  Control is the brains.  Everything starts here.
#
class Control:
	
	vbox, progBar, window, draw, mark = None, None, None, None, None
	mplayer = None
	paused=False
	framecnt=100
	boxes=[]
	_curFolder, _filename = None, ""
	#
	#  Creates and returns a control group for pymp.
	#
	def __init__(self):
		window=gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.boxes.append(ControlButton(gtk.STOCK_MEDIA_REWIND, "Back", gtk.STOCK_MEDIA_REWIND, "Rew", self.seekRev, self.release))
		self.boxes.append(ControlButton(gtk.STOCK_MEDIA_PLAY, "Play", gtk.STOCK_MEDIA_PAUSE, "Pause", self.pause, None))
		self.boxes.append(ControlButton(gtk.STOCK_MEDIA_NEXT, "Frame Fwd", gtk.STOCK_MEDIA_NEXT, "Frame Adv", self.frameFwd, None))
		self.boxes.append(ControlButton(gtk.STOCK_MEDIA_FORWARD, "Forward", gtk.STOCK_MEDIA_FORWARD, "Fast Fwd", self.seekFwd, self.release))
		self.boxes.append(ControlButton(gtk.STOCK_JUMP_TO, "Seek Next", gtk.STOCK_JUMP_TO, "Seek Next", self.scanForward, None))
		self.boxes.append(ControlButton(gtk.STOCK_GOTO_TOP, "Mark In", gtk.STOCK_GOTO_TOP, "Mark In", self.markIn, None))
		self.boxes.append(ControlButton(gtk.STOCK_GOTO_BOTTOM, "Mark Out", gtk.STOCK_GOTO_BOTTOM, "Mark Out", self.markOut, None))

                self.adj=gtk.Adjustment(0,0,self.framecnt,1,self.framecnt/20,0)
		progBar = gtk.HScale(self.adj)
		progBar.set_draw_value(True)
		progBar.set_value_pos(gtk.POS_BOTTOM)
		progBar.set_size_request(PROG_WIDTH, PROG_HEIGHT)
		progBar.set_update_policy(gtk.UPDATE_DELAYED)
		progBar.connect("value_changed", self.seekPos)
		progBar.set_digits(0)
		
		draw=gtk.Fixed()
		draw.set_size_request(PROG_WIDTH, PROG_HEIGHT)

		vbox = gtk.VBox(False, 0)
		hbox = gtk.HBox(False, 0)
		hbox2= gtk.HBox(False, 0)

                hbox3= gtk.HBox(False, 0)
                self.projtext=gtk.Label("--Nothing Loaded--")
                self.filetext=gtk.Label("")
                self.timestamp=gtk.Label("T = --:--:--.--")
		hbox3.pack_start(gtk.VSeparator(), True, False, 0)
		hbox3.pack_start(self.projtext, True, False, 0)
		hbox3.pack_start(gtk.VSeparator(), True, False, 0)
		hbox3.pack_start(self.filetext, True, False, 0)
		hbox3.pack_start(gtk.VSeparator(), True, False, 0)
		hbox3.pack_start(self.timestamp, True, False, 0)
		hbox3.pack_start(gtk.VSeparator(), True, False, 0)
		
		self.progBar, self.vbox, self.window, self.draw = progBar, vbox, window, draw
		hbox.set_homogeneous(True)
		self.mark=Marker(draw, 0, 0)
		for i in self.boxes:
			hbox.pack_start(i.getObject(), True, False, 0)

		hbox2.pack_start(progBar, False, False, 0)
		vbox.pack_start(self.menu(), True, False, 0)
		vbox.pack_start(hbox, True, False, 0)
		vbox.pack_start(hbox2, True, False, 0)
		vbox.pack_start(draw, True, False, 0)
		vbox.pack_start(gtk.HSeparator(), True, False, 0)
                vbox.pack_start(hbox3, True, False, 0)
		vbox.pack_start(gtk.HSeparator(), True, False, 0)

		self.paused=True
		
		window.set_title("VIdeoED")
		window.add(vbox)
		window.connect("destroy", self.quit)
		window.show_all()

	def menu(self):
		menu=gtk.MenuBar()
		agr=gtk.AccelGroup()
		self.window.add_accel_group(agr)

		file=gtk.Menu()
		file_i=gtk.MenuItem("_File")
		new=gtk.ImageMenuItem(gtk.STOCK_NEW, agr)
		open=gtk.ImageMenuItem(gtk.STOCK_OPEN, agr)
		save=gtk.ImageMenuItem(gtk.STOCK_SAVE, agr)
		saveas=gtk.ImageMenuItem(gtk.STOCK_SAVE_AS, agr)
		export=gtk.MenuItem("_Export")
		close=gtk.ImageMenuItem(gtk.STOCK_QUIT, agr)

		new.connect_object("activate", self.fileBox, "file.new")
		key, mod=gtk.accelerator_parse("N")
		#new.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		open.connect_object("activate", self.fileBox, "file.open")
		key, mod=gtk.accelerator_parse("O")
		#open.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		save.connect_object("activate", self.save, "file.save")
		key, mod=gtk.accelerator_parse("S")
		#save.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		saveas.connect_object("activate", self.fileBox, "file.saveas")
		key, mod=gtk.accelerator_parse("<Control>A")
		saveas.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
                export.connect_object("activate", self.fileBox, "file.export")
		key, mod=gtk.accelerator_parse("<Control>E")
		export.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		close.connect_object("activate", self.quit, "file.close")
		key, mod=gtk.accelerator_parse("Q")
		#close.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)

		file.append(new)
		file.append(open)
		file.append(gtk.SeparatorMenuItem())
		file.append(save)
		file.append(saveas)
		file.append(export)
		file.append(gtk.SeparatorMenuItem())
		file.append(close)

		file_i.set_submenu(file)
		menu.append(file_i)
		
		edit=gtk.Menu()
		edit_i=gtk.MenuItem("_Edit")
		markin=gtk.ImageMenuItem("Mark _In", agr)
		markin.set_image(gtk.image_new_from_stock(gtk.STOCK_GOTO_TOP, gtk.ICON_SIZE_MENU))
		markout=gtk.ImageMenuItem("Mark _Out", agr)
		markout.set_image(gtk.image_new_from_stock(gtk.STOCK_GOTO_BOTTOM, gtk.ICON_SIZE_MENU))
		cLast=gtk.ImageMenuItem("_Remove Last Mark")
		cLast.set_image(gtk.image_new_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_MENU))
		cAll=gtk.ImageMenuItem("Clear _All Marks")
		cAll.set_image(gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU))
		execute=gtk.ImageMenuItem("_Execute", agr)
		execute.set_image(gtk.image_new_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU))
		
		markin.connect_object("activate", self.markIn, "edit.markin")
		key, mod=gtk.accelerator_parse("F2")
		markin.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		markout.connect_object("activate", self.markOut, "edit.markout")
		key, mod=gtk.accelerator_parse("F3")
		markout.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		cLast.connect_object("activate", self.mark.delete, self.draw)
		key, mod=gtk.accelerator_parse("Delete")
		cLast.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		cAll.connect_object("activate", self.mark.clear, self.draw)
		key, mod=gtk.accelerator_parse("<Control>X")
		cAll.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		execute.connect_object("activate", self.fileBox, "edit.execute")
		key, mod=gtk.accelerator_parse("F5")
		execute.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)

		edit.append(markin)
		edit.append(markout)
		edit.append(cLast)
		edit.append(cAll)
		edit.append(gtk.SeparatorMenuItem())
		edit.append(execute)

		edit_i.set_submenu(edit)
		menu.append(edit_i)

		nav=gtk.Menu()
		nav_i=gtk.MenuItem("_Navigate")
		seek=gtk.ImageMenuItem("_Seek Forward", agr)
		seek.set_image(gtk.image_new_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU))
		seek.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		frame=gtk.MenuItem("_Goto Frame", agr)
		
		seek.connect_object("activate", self.scanForward, "nav.seek")
		key, mod=gtk.accelerator_parse("F4")
		seek.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		frame.connect_object("activate", self.gotoBox, "nav.frame")
		key, mod=gtk.accelerator_parse("<Control>G")
		frame.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		
		nav.append(seek)
		nav.append(frame)

		nav_i.set_submenu(nav)
		menu.append(nav_i)

		help=gtk.Menu()
		help_i=gtk.MenuItem("_Help")
		contents=gtk.ImageMenuItem(gtk.STOCK_HELP, agr)
		key, mod=gtk.accelerator_parse("F1")
		contents.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
		about=gtk.ImageMenuItem(gtk.STOCK_ABOUT, agr)
		key, mod=gtk.accelerator_parse("<Control>H")
		contents.remove_accelerator(agr, key, mod)
		about.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)

		contents.connect_object("activate", self.helpDialog, "help.help")
		about.connect_object("activate", self.aboutbox, "help.about")

		help.append(contents)
		help.append(gtk.SeparatorMenuItem())
		help.append(about)

		help_i.set_submenu(help)
		menu.append(help_i)

		self._curFolder=None
		self._filename=""
		return menu


	#
	#  Seeks secs seconds in the current target.
	#
	def seekFwd(self, widget, event):
		secs=SEEK_STEP
		#print "Seek called: " + str(secs) + " seconds"
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False
                
                self.paused=self.mplayer.isPaused()
                if self.paused:
                        self.mplayer.seek(secs,0,True)
                else:
                        self.mplayer.FFwd()
                
		for i in self.boxes:
			i.switch(self.paused)
		
		return True

	def seekRev(self, widget, event):
		secs=SEEK_STEP * -1
		#print "Seek called: " + str(secs) + " seconds"
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False
                
                self.paused=self.mplayer.isPaused()
                if self.paused:
                        self.mplayer.seek(secs,0,True)
                else:
                        self.mplayer.Rew()
                
		for i in self.boxes:
			i.switch(self.paused)

		return True

	def release(self, widget, event):
		print "Seek release called:"
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False
                if self.paused:
                        return True

                self.mplayer.Play()
		return True
	
	def save(self, event):
		print "Save file called!"
		if not self.mplayer: return False
		if not self.mplayer.isvalid(): return False
		if (self._filename == ""):
			return self.fileBox("file.saveas")
                try:
                        fp=open(self._filename,"w")
                except:
                        print "Error saving file!"
                        self._filename=""
                        self.projtext.set_text("Untitled Project")
                        return False
                
                xml=minidom.Document()
                h=xml.createElement("videoed_project")
                h.setAttribute("version",str(VERSION))
                f=xml.createElement("filename")
                f.setAttribute("length",str(self.mplayer.getLength()))
                f.setAttribute("framerate",str(self.mplayer.getFramerate()))
                f.appendChild(xml.createTextNode(self.mplayer.getFilename()))
                h.appendChild(f)
                mark=self.mark
                while mark:
                        m=xml.createElement("marker")
                        i=xml.createElement("in")
                        i.appendChild(xml.createTextNode(str(mark.getIn())))
                        o=xml.createElement("out")
                        o.appendChild(xml.createTextNode(str(mark.getOut() if mark.getOut() > -1 else self.framecnt)))
                        m.appendChild(i)
                        m.appendChild(o)
                        h.appendChild(m)
                        mark=mark.getNext()

                xml.appendChild(h)
                xml.writexml(fp,""," ","\n","UTF-8")
                fp.close()
		return True

        def load(self,filename):
                if self._filename != "":
                        if self.confirm("Close existing project?") != gtk.RESPONSE_OK: raise FileFormatError("Invalid file format")

                self._filename=""
                if self.mplayer and self.mplayer.isvalid():
                        self.mplayer.close()

                self.mark.clear(self.draw)
                vidfile=""
                try:
                        xmldom=parse(filename)
                        root=xmldom.documentElement
                        if root.nodeName != "videoed_project" or float(root.getAttribute("version")) < VERSION: raise FileFormatError("Invalid file format")
                        for i in root.childNodes:
                                if i.nodeName == "filename":
                                        if vidfile != "": raise FileFormatError("Invalid file format")
                                        vidfile=i.childNodes[0].nodeValue
                                        fr=float(i.getAttribute("framerate"))
                                        ln=float(i.getAttribute("length"))
                                        fc=fr*ln
                                if i.nodeName == "marker":
                                        mkin=-1
                                        mkout=-1
                                        if vidfile == "": raise FileFormatError("Invalid file format")
                                        for j in i.childNodes:
                                                if j.nodeName == "in":
                                                        if mkout != -1: raise FileFormatError("Invalid file format")
                                                        mkin=int(j.childNodes[0].nodeValue)
                                                elif j.nodeName == "out":
                                                        if mkin == -1: raise FileFormatError("Invalid file format")
                                                        mkout=int(j.childNodes[0].nodeValue)
                                        if mkin == -1 or mkout == -1: raise FileFormatError("Invalid file format")
                                        #print "marker: in="+str(mkin)+", out="+str(mkout)
                                        self.mark.setIn(self.draw, mkin, int(mkin*PROG_WIDTH/fc))
                                        self.mark.setOut(self.draw, mkout, int(mkout*PROG_WIDTH/fc))
                except:
                        print "Error loading file!"
                        self.mark.clear(self.draw)
                        return False
                else:
                        self._filename=filename
                        #print "Spawning mplayer file="+vidfile.strip()
                        self.mplayer=Mplayer(vidfile.strip(), self.progBar.set_value, self.timestamp.set_text, self.replay)

                return True
        
 	#
	#  Pauses the current mplayer job.
	#
	def pause(self, widget=None, event=None):
		#print "Pause Called: current state is " + ("" if self.paused else "not ") + "paused."
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False

                self.paused=self.mplayer.pause()
		for i in self.boxes:
			i.switch(self.paused)
		
		return True
		
	
	def frameFwd(self, widget, event):
		#print "Frame Forward Called!"
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False

                self.mplayer.FrAdv()
                self.paused=self.mplayer.isPaused()
		for i in self.boxes:
			i.switch(self.paused)
		
		return True

	def scanForward(self, widget=None, event=None):
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False

                if not self.mplayer.isPaused(): self.pause()
		seek=Seeker(self.mplayer.getFilename(),self.mplayer.getFramerate(),self.framecnt)
		if not seek.Initialize(self.progBar.get_value()):
                        print "Error initializing the seek function!"
                        return False

                resp=seek.seek()
                if seek.isvalid():
                        print "Seek returned sucessfully"
                self.progBar.set_value(resp)
		
		return True

	def markIn(self, widget=None, event=None):
		loc=self.progBar.get_value()
		pix=loc*PROG_WIDTH/self.framecnt
		
		self.mark.setIn(self.draw, int(loc), int(pix))

		#print "Mark in at: " + str(loc) + "!"
		return True

	def markOut(self, widget=None, event=None):
		loc=self.progBar.get_value()
		pix=loc*PROG_WIDTH/self.framecnt
		
		self.mark.setOut(self.draw, int(loc), int(pix))

		#print "Mark out at: " + str(loc) + "!"
		return True
	
	#
	#  Seeks to an absolute frame in the current target.
	#
	def seekPos(self, hscale):
		
		#x, y = event.get_coords()  #resolve desired percent
		#percent = 100 * x / PROG_WIDTH
		secs = hscale.get_value()	
		#print "SeekPos called! " + str(secs) + " Frame"	
                if not self.mplayer:
                        return False

                if not self.mplayer.isvalid():
                        return False
                
                self.mplayer.seek(secs)
                self.paused=self.mplayer.isPaused()
		for i in self.boxes:
			i.switch(self.paused)

		return True
		
	def quit(self, event):
                if self.mplayer:
                        self.mplayer.close()
		print "Now Exit!"
		sys.exit(0)

	def pointlessCallback(self, dialog, pointless):
		print "Received a pointless call back! Response = " + str(pointless)
		dialog.destroy()

	def aboutbox(self, event):
		abt=gtk.AboutDialog()
		abt.set_name("VIdeoED")
		abt.set_version(".01a")
		abt.set_website("http://www.cletis.net/projects")
		abt.set_authors(["Andrew Buettner <leeloo at cletis dot net>"])
		abt.set_license("GNU Lesser General Public License\nSee http://www.gnu.org/copyleft/lesser.html for more details")
		abt.connect("response", self.pointlessCallback)
		abt.show()

	def fileBox(self, filetype="file.new"):
		ffilter=gtk.FileFilter()
		if (filetype=="file.new"):
			dialog="Open MPEG Source:"
			ffilter.add_mime_type("video/mpeg")
			ffilter.set_name("MPEG Video Files")
			act=gtk.FILE_CHOOSER_ACTION_OPEN
		elif (filetype=="file.open"):
			dialog="Open Previous VIdeoED Project:"
			ffilter.add_pattern("*.videoed")
			ffilter.set_name("VIdeoED Projects")
			act=gtk.FILE_CHOOSER_ACTION_OPEN
		elif (filetype=="file.saveas"):
			dialog="Save As:"
			ffilter.add_pattern("*.videoed")
			ffilter.set_name("VIdeoED Projects")
			act=gtk.FILE_CHOOSER_ACTION_SAVE
		elif (filetype=="edit.execute"):
			dialog="Output To:"
			ffilter.add_mime_type("video/mpeg")
			ffilter.set_name("MPEG Video Files")
			act=gtk.FILE_CHOOSER_ACTION_SAVE
		elif (filetype=="file.export"):
                        dialog="Export To:"
                        ffilter.add_pattern("*.edl")
                        ffilter.set_name("Edit Decision Lists")
                        act=gtk.FILE_CHOOSER_ACTION_SAVE
		else:
			print "Unknown Open, using default!"
			ffilter=None
			dialog="Open File:"
			act=gtk.FILE_CHOOSER_ACTION_SAVE

		dialog=gtk.FileChooserDialog(dialog, None, act,
			(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE, gtk.STOCK_OK, gtk.RESPONSE_OK))

		dialog.set_default_response(gtk.RESPONSE_OK)
		dialog.set_select_multiple(False)
		dialog.connect("response", self.fileopen, filetype)
		dialog.connect("close", self.pointlessCallback)
		if (self._curFolder):
			dialog.set_current_folder(self._curFolder)
		
		if (ffilter):
			dialog.add_filter(ffilter)

		ffilter=gtk.FileFilter()
		ffilter.add_pattern("*")
		ffilter.set_name("All Files")
		dialog.add_filter(ffilter)

		dialog.show()

	def fileopen(self, dialog, resp, filetype):
		
		folder=self._curFolder
		self._curFolder=dialog.get_current_folder()
		filen=dialog.get_filename()
		
		#print "Received OpenFile: Filename = " + str(filen) + ", Type = " + str(filetype) + ", Response = " + str(resp)
		dialog.destroy()
		if (resp != gtk.RESPONSE_OK):
			self._curFolder=folder
			return False

		if filetype == "file.new":
			self.mplayer_open(filen)
		elif filetype == "edit.execute":
                        fp,fn=os.path.split(filen)
                        fh,ext=os.path.split(fn)
                        if ext.find(".") == -1:
                                filen=filen + ".mpg"
                        self.generate(filen)
                elif filetype == "file.saveas":
                        fp,fn=os.path.split(filen)
                        fh,ext=os.path.split(fn)
                        if ext.find(".") == -1:
                                filen=filen+".videoed"
                        if os.path.isfile(filen) and filen != self._filename:
                                if self.confirm("Overwrite Existing file?") != gtk.RESPONSE_OK: return False
                        self._filename=filen
                        if self.save(None):
                                self.projtext.set_text(filen)
                elif filetype == "file.open":
                        self.load(filen)
                elif filetype == "file.export":
                        fp,fn=os.path.split(filen)
                        fh,ext=os.path.split(fn)
                        if ext.find(".") == -1:
                                filen=filen+".edl"
                        if os.path.isfile(filen):
                                if self.confirm("Overwrite Existing file?") != gtk.RESPONSE_OK: return False
                        return self.export(filen)
                
                else:
                        print "I received '"+filetype+"':'"+filen+"', but I don't know what to do with it!"
                        return False
                
		return True

	def gotoBox(self, arg):
		dialog=gtk.Dialog("Goto Frame:", None, 0, 
			(gtk.STOCK_CANCEL, gtk.RESPONSE_CLOSE, gtk.STOCK_APPLY, gtk.RESPONSE_OK))

		vbox=dialog.get_content_area()
		entry=gtk.Entry(7)
		entry.set_text(str(int(self.progBar.get_value())))
		entry.select_region(0, len(entry.get_text()))
		vbox.pack_start(entry, True, False, 0)
		entry.show()
		ag=gtk.AccelGroup()

		dialog.connect("response", self.gotoFrame, entry)
		dialog.connect("close", self.pointlessCallback)

		dialog.show()
		dialog.add_accel_group(ag)
		key, mod=gtk.accelerator_parse("Return")
		ag.connect_group(key, mod, 0, self.gotoFrameB)

	def gotoFrame(self, dialog, resp, entry):
		#print "Received gotoFrame callback! Response = " + str(resp) + " Text = " + entry.get_text()
		
		if (resp != gtk.RESPONSE_OK):
			dialog.destroy()
			return False
		
		try:
			frame=int(entry.get_text())
			if (frame > self.framecnt):
				print "Error! Frame value out of range!"
			else:
				self.progBar.set_value(frame)

		except:
			print "Error! No integer specified!"
		finally:
			dialog.destroy()
			

	def gotoFrameB(self, a, dialog, b, c):
		#print "Received gotoFrame callback B! a = " + str(a) + " b = " + str(b) + " c = " + str(c)

		vbox=dialog.get_content_area()
		children=vbox.get_children()

		self.gotoFrame(dialog, gtk.RESPONSE_OK, children[0])

	def helpDialog(self, arg):
		dialog=gtk.MessageDialog(None, 0, gtk.MESSAGE_QUESTION, gtk.BUTTONS_CLOSE, "Coming Soon!")
		dialog.connect("response", self.pointlessCallback)
		dialog.connect("close", self.pointlessCallback)
		dialog.show()

	def mplayer_open(self, filename):
		if self.mplayer:
			if self.confirm("Close existing project?") != gtk.RESPONSE_OK: return False

			self.mark.clear(self.draw)
			self.mplayer.close()
			self.mplayer=None
			self.progBar.set_range(0,0)
			self.framecnt=0
			self.paused=False
			self._filename=""

		self.mplayer=Mplayer(filename, self.progBar.set_value, self.timestamp.set_text, self.replay)
		
	#
	# Handles MPlayer validate/EoF callback. nEoF means weather or not the callback was because MPlayer was valid and hit EoF
	# to allow automatic respawn of the player when it hits the end of the file.
	# FIXME: Ugly, but it should work for my needs.  Someday some guy on sourceforge or whatever will fix this. :-)
	#
	def replay(self,mplayer,nEoF):
                if (not nEoF):
                        self.mplayer=Mplayer(mplayer.getFilename(), self.progBar.set_value, self.timestamp.set_text, self.replay)
                        return

               	self.mplayer.queryStatus()
                self.paused=self.mplayer.isPaused()
                v=self.progBar.get_value()
                self.framecnt=mplayer.getFrame(mplayer.getLength())
                self.adj.set_all(v,0,self.framecnt,1,self.framecnt/20,0)
                self.filetext.set_text(mplayer.getFilename())
       		self.projtext.set_text("Untitled Project" if self._filename == "" else self._filename)

		for i in self.boxes:
			i.switch(self.paused)

	def confirm(self, message):
		dialog=gtk.MessageDialog(None, 0, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, message)
		dialog.show()
		resp=dialog.run()
		dialog.destroy()
		return resp

	def generate(self,outfile):
                if not self.mplayer:
                        return False
                if not self.mplayer.isvalid():
                        return False
                if os.path.isfile(outfile):
                        if self.confirm("Overwrite Existing file?") != gtk.RESPONSE_OK: return False

                mark=self.mark
                build=Builder2(self.mplayer.getFilename(),self.mplayer.getFramerate(),self.mplayer.getLength())
                self.mplayer.seek(1) # Force pause! The mplayer object must remain valid.
                while mark:
                        build.addSegment(mark.getIn(), mark.getOut() if mark.getOut() > -1 else self.framecnt)
                        mark=mark.getNext()

                ret=build.generate(outfile)
                self.confirm("File created sucessfully!" if ret else "Error writing output file!")
                return ret

        def export(self,filen):
                if not self.mplayer: return False
                if not self.mplayer.isvalid(): return False

                try:
                        fp=open(filen,"w")
                except:
                        print "Error saving file!"
                        return False

                mark=self.mark
                lastout=0
                if mark.getIn() == 0:
                        lastout=self.mplayer.getTime(mark.getOut()) if mark.getOut() > 0 else self.mplayer.getLength()
                        mark=mark.getNext()

                while mark:
                        fp.write(str(lastout) + " " + str(self.mplayer.getTime(mark.getIn())) + " 0\n")
                        lastout=self.mplayer.getTime(mark.getOut()) if mark.getOut() > 0 else self.mplayer.getLength()
                        mark=mark.getNext()

                if lastout < self.mplayer.getLength():
                        fp.write(str(lastout) + " " + str(self.mplayer.getLength()+100) + " 0\n")
			# added to ensure the cut through the end.

                fp.close()
                self.confirm("Export: '" + filen + "' created successfully.")
                return True
                        
class FileFormatError(Exception): pass

#End of file
