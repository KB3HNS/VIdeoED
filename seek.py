#!/usr/bin/env python

import pygtk, gtk, os, sys, fcntl, gobject, time, threading
import y4m
import mplayer

# Default values
PIXEL_DECIMATION = 5 # Check every nth pixel
BLACK_THRESHOLD  = 60 # Range 0-255 (~20 - ~253)
MIN_SCENE_LENGTH = 1 # Minimum time in S to seek forward
PROG_WIDTH, PROG_HEIGHT = 600, 15
STATUS_TIMEOUT = 500

#
# Based on CBreak code by Nathan True "http://devices.natetrue.com/cbreak/"  Also makes heavy use of reference code from the y4m project:
# Start at a starting point of the file and search until the next nearly black frame.  CBreak used an AVIFile object from M$ VFW, we use
# a yuv4mpeg stream with similar properties.  
#

class Seeker(mplayer.Mplayer):
    box = None
    def __init__(self,sourcefile,framerate,flen):
        self.fname=sourcefile
        self.framerate=framerate
        self.valid=False
        self.paused=True
        self.flen=flen # Film total length in frames!

    def Initialize(self,start):
        self.fpos=start
        if (os.system("mkfifo /tmp/VIdeoED")): return False
        mpc="mplayer -slave -quiet -ss " + str(self.getTime(start)) + " -vo yuv4mpeg:file=/tmp/VIdeoED -ao null " + self.fname
        self.mplayerIn, self.mplayerOut = os.popen2(mpc + " 2> /dev/null")  #open pipe
        fcntl.fcntl(self.mplayerOut, fcntl.F_SETFL, os.O_NONBLOCK)
        self.ioo=open("/tmp/VIdeoED","r")
        print "Spawning mplayer process as: '"+mpc+" 2> /dev/null'.  Processing fifo: '/tmp/VIdeoED'"
        self.stream=y4m.Stream(self.ioo)

        try:
            #stream.readHeader()
            frame=self.stream.readFrame()
            self.h=frame.height
            self.w=frame.width
        except:
            print "Invalid file format error: Aborting!"
            self.close()
            return False

        if self.h == 0 or self.w == 0:
            print "Invalid file information error: Aborting!"
            self.close()
            return False

        self.startEofHandler()
        self.startIOHandler()
        #self.startStatusQuery(STATUS_TIMEOUT)
        gobject.threads_init()
        return True
        
    def seek(self):
        self.paused=False
        self.box=self._genUI(self.fname)
        self.fstart=self.fpos
        self.t=Scan(self)
        self.t.start()
        self.fpos=self.fpos+1
        gtk.gdk.threads_enter()
        self.box.run()
        gtk.gdk.threads_leave()
        self.paused=True
        self.close()

        return self.fpos
    
    def close(self,valid=False):
        # Abort processing, close active box, the class data is still valid
        if self.mplayerIn and self.mplayerOut:
            self.cmd("quit")

        try:
            self.stopStatusQuery()
            if self.box: self.box.destroy()
            self.stopEofHandler()
            self.stopIOHandler()
            #if self.y4IO: gobject.source_remove(self.y4IO)
            #if self.y4EoF: gobject.source_remove(self.y4EoF)
            if self.ioo: self.ioo.close()
            if self.mplayerIn: self.mplayerIn.close()
            if self.mplayerOut: self.mplayerOut.close()
            os.system("rm -f /tmp/VIdeoED")            
        except:
            pass

        self.paused=True
        self.valid=valid
        self.ioo, self.mplayerIn, self.mplayerOut, self.box = None, None, None, None
        
    def handleEof(self, source, condition):
        self.close()
        
    def _genUI(self,dstfile):
       dialog=gtk.Dialog("Seeking: " + dstfile, None, 0, (gtk.STOCK_CANCEL, gtk.RESPONSE_CLOSE))
       vbox=dialog.get_content_area()
       self.progbar=gtk.ProgressBar()
       self.progbar.set_size_request(PROG_WIDTH, PROG_HEIGHT)
       vbox.pack_start(self.progbar, True, False, 0)
       dialog.show_all()
       self._updateProgBar()
       return dialog
                
    def _updateProgBar(self):
        self.progbar.set_fraction(float(self.fpos)/float(self.flen))
        self.progbar.set_text(str(self.fpos))
        return True

    #Update the frame count.  Update the display only every 3rd frame to reduce display overhead.
    def incrfpos(self):
        self.fpos=self.fpos+1
        if self.fpos%3==0:
            self._updateProgBar()

    def _QstatusCb(self,resp):
	if not resp: return False

	seconds = float(resp.replace("ANS_TIME_POSITION=", ""))
		
	self.fpos=int(seconds*self.framerate)
        
	return True

class Scan (threading.Thread):
    def __init__(self,seek):
        super(Scan,self).__init__()
        self.seek=seek

        self.fstart=seek.fpos+1 # This makes a copy of the variable (not the pointer IAW python)
        self.msl=seek.getFrame(MIN_SCENE_LENGTH)
        
        #copy a few variables locally:
    # Attempt to receive and decode a video frame
    def run(self):
    	frame=None
        while True:
            try:
                frame=self.seek.stream.readFrame(frame)
            except StandardError:
                print "Caught an error.  Should I increment the frame counter anyways?"
                gtk.gdk.threads_enter()
                try:
                    self.seek.close(False)
                except:
                    print "I got an error!"
                    pass
                finally:
                    gtk.gdk.threads_leave()
                return True

            Y=frame.Y
            #Scan the middle fraction of the frame
            blackframe = True  #Assume it's black

            #Grab the frame data and skip the first 0x28 bytes (these are header crap)
            w=frame.width+0
            for i in xrange(0x28,frame.width*frame.height,PIXEL_DECIMATION):
            #for p in Y.pixels:
                #Grab that pixel pointer b/c we'll be using it
                #If any pixel is above the threshold, report non-black and break
                #print "Frame: "+str(self.seek.fpos)+" pixel val: "+str(p.val)
                if Y.getpixel(i%w,i/w) > BLACK_THRESHOLD:
                    blackframe = False
                    break

            #print "Frame done: " + str(self.seek.fpos+1) + " " + str(self.msl) + " " + str(blackframe)
            
            try:
                gtk.gdk.threads_enter()
                self.seek.incrfpos()
                if blackframe and self.seek.fpos-self.fstart>self.msl:
                    print "Found a black frame: " + str(self.seek.fpos) + " " + str(self.msl)
                    self.seek.close(True)
                    gtk.gdk.threads_leave()
                    return True
            except:
                print "I got an error!"
                pass
            finally:
                gtk.gdk.threads_leave()
                
