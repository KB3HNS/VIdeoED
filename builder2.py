#!/usr/bin/env python

import pygtk, gtk, os, sys, fcntl, gobject, time, re

import mplayer, builder
from mplayer import s2hms

PROG_WIDTH, PROG_HEIGHT = builder.PROG_WIDTH, builder.PROG_HEIGHT

#
# This is it...
# This is the whole point of the program:  Take a list of mark-in and mark-out points and build and output file.
# 

# Overloaded version of original builder class: this version produces an EDL file and uses that to transcode the video
class Builder2(builder.Builder):
    def __init__(self,sourcefile,framerate,flen):
        self.fname=sourcefile
        self.framerate=framerate
        self.valid=False
        self.segments=0
        self.array=[]
        self.paused=True
        self.flen=flen # Film total length in s!
        self.prog=[]
        self.lastout=0
        
    def addSegment(self,start,stop):
        lastout=self.lastout
        self.lastout=self.getTime(stop)
        if self.getTime(start) <= lastout:
            return None
        
        # Follow the EDL format (skip_start(last mark out) skip_end(mark_in) 0)        
        self.array.append([lastout,self.getTime(start)])
        self.segments=self.segments+1
        
    def generate(self,destfile):
        self.complete=0
        self.box=self._genUI(destfile)
        if self.lastout<self.flen: self.array.append([self.lastout,self.flen+100])
        # Add 1 minute to guarantee that the last few secods are chopped off as well.  Experimental
        cmd="mencoder -of mpeg -oac lavc -ovc lavc \
            -lavcopts vcodec=mpeg1video:vbitrate=2000:acodec=libmp3lame:abitrate=256:threads=2 \
            -edl /tmp/VIdeoED.edl -hr-edl-seek \
            -o " + destfile + " "
        
        self._writeEDL("/tmp/VIdeoED.edl")
        self.paused=False
        self.mplayerIn, self.mplayerOut = os.popen2(cmd + self.fname + " 2>/dev/null ")
        fcntl.fcntl(self.mplayerOut, fcntl.F_SETFL, os.O_NONBLOCK)
        print "Spawning mencoder process cmd='" + cmd + self.fname + " 2>/dev/null'"
        self.startEofHandler()
        self.startIOHandler()

        ret=self.box.run()
        self.paused=True
        if not self.valid:
            self.close()

        return self.valid
    
    def close(self, valid=False):
        # Abort processing, close active box, the class data is still valid
        
        self.box.destroy()
        self.stopEofHandler()
        self.stopIOHandler()
        try:
                self.mplayerIn.close()
                self.mplayerOut.close()
        except:
            pass

        os.system("rm -f /tmp/VIdeoED.edl")
        self.valid=valid
        self.paused=True
        
    def handleEof(self,source,condition):
        print "Received EoF callback."
        self.close(True)
        return True
    

    def handleIO(self,source,condition):
        return self.dumpIO(source,condition,None)

    def _updateGraph(self,c,pct):
        self.progbar.set_fraction(float(pct)/100)
        self.progbar.set_text(str(pct)+"%")

    def _writeEDL(self,fname):
        fp=open(fname,'w')
        for i in self.array: fp.write(str(i[0]) + " " + str(i[1]) + " 0\n")

        fp.close()
        
