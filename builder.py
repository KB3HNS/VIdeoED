#!/usr/bin/env python

import pygtk, gtk, os, sys, fcntl, gobject, time, re

import mplayer
from mplayer import s2hms

PROG_WIDTH, PROG_HEIGHT = 600, 15
STATUS_TIMEOUT=500
THREADS=2

#
# This is it...
# This is the whole point of the program:  Take a list of mark-in and mark-out points and build and output file.
# 

class Builder(mplayer.Mplayer):
    def __init__(self,sourcefile,framerate,flen):
        self.fname=sourcefile
        self.framerate=framerate
        self.valid=False
        self.segments=0
        self.array=[]
        self.io=[]
        self.flen=0
        self.paused=True
        self.fcnt=flen # Film total length in s!
        self.prog=[]

    def addSegment(self,start,stop):
        self.array.append([s2hms(self.getTime(start)),s2hms(self.getTime(stop-start))])
        self.segments=self.segments+1
        self.flen=self.flen+self.getTime(stop-start)
        self.prog.append(0)
        
    def generate(self,destfile):
        self.complete=0
        self.paused=False
        self.box=self._genUI(destfile)
        self.EoF=[ None for i in xrange(self.segments) ]
        self.IO=[ None for i in xrange(self.segments) ]
        self.n=0 #Counter used in tracking which thread is next
        for i in range(THREADS): self.spawnProc(destfile)
        
        ret=self.box.run()
        self.paused=True
        if not self.valid:
            self.close()

        return self.valid
    
    def spawnProc(self,destfile):
        if self.n==self.segments: return True
        i=self.array[self.n]
        cmd="mencoder -of mpeg -oac mp3lame -ovc lavc \
            -lavcopts vcodec=mpeg1video:vbitrate=2000 \
            -lameopts cbr:br=256 \
            -ss " + i[0] + " -endpos " + i[1] + " \
            -o /tmp/%02d.mpg " % (self.n)
        ioi, ioo = os.popen2(cmd + self.fname + " 2>/dev/null ")
        print "Spawning mencoder process cmd='" + cmd + self.fname + " 2>/dev/null' n=" + str(self.n) + "/" + str(self.segments-1)
        fcntl.fcntl(ioo, fcntl.F_SETFL, os.O_NONBLOCK)
        self.EoFWatch(ioo,self.n,destfile)
        self.io.append([ioi,ioo])
        self.IOWatch(self.n)
        self.n=self.n+1

    def close(self):
        # Abort processing, close active box, the class data is still valid
        self.box.destroy()
        for i in self.EoF:
            if i: gobject.source_remove(i)

        self.EoF=[]
        if self.mplayerIn and self.mplayerOut:
            self.cmd("quit")
            try:
                self.mplayerIn.close()
                self.mplayerOut.close()
            except:
                pass

        try:
            for i in self.io:
                if i[0]: i[0].close()
                if i[1]: i[1].close()
        except:
            pass

        self.io=[]
        self.valid=False
        self.paused=True
        
    def _genUI(self,dstfile):
       dialog=gtk.Dialog("Generating " + dstfile, None, 0, (gtk.STOCK_CANCEL, gtk.RESPONSE_CLOSE))
       vbox=dialog.get_content_area()
       self.progbar=gtk.ProgressBar()
       self.progbar.set_size_request(PROG_WIDTH, PROG_HEIGHT)
       self.progbar.set_text("0%")
       vbox.pack_start(self.progbar, True, False, 0)
       dialog.show_all()
       return dialog

    def EoFWatch(self,io,c,dstfile):
        self.EoF[c]=gobject.io_add_watch(io,gobject.IO_HUP,self.handleEof,c,dstfile)

    def handleEof(self,source,condition,c,dstfile):
        print "Received EoF callback: " + str(c) + " : " + dstfile
        gobject.source_remove(self.EoF[c])
        gobject.source_remove(self.IO[c])
        self.EoF[c]=None
        try:
            self.io[c][0].close()
            self.io[c][0] = None
            self.io[c][1].close()
            self.io[c][1] = None
        except:
            pass
        
        self.complete=self.complete+1        
        if self.complete == self.segments:
            cmd="mencoder -of mpeg -oac mp3lame -ovc lavc \
                -lavcopts vcodec=mpeg1video:vbitrate=2000 \
                -lameopts cbr:br=256 \
                -o " + dstfile
            for i in range(self.segments): cmd=cmd + " /tmp/%02d.mpg" % (i)
            self.mplayerIn,self.mplayerOut=os.popen2(cmd + " 2> /dev/null ")
            fcntl.fcntl(self.mplayerOut, fcntl.F_SETFL, os.O_NONBLOCK)
            print "Spawning mencoder stage2: '"+cmd+" 2> /dev/null'"
            self.EoF=[None]*2
            self.prog=[0]*2
            self.EoF[0]=gobject.io_add_watch(self.mplayerOut,gobject.IO_HUP,self.handleEof2)
            self.EoF[1]=gobject.io_add_watch(self.mplayerOut,gobject.IO_IN, self.dumpIO,self.segments)
        else:
            self.spawnProc(dstfile) #spawn a new encoder thread to replace this one.
        return True
    
    def handleEof2(self,source,condition):
        gobject.source_remove(self.EoF[0])
        gobject.source_remove(self.EoF[1])
        self.EoF[0]=None
        self.EoF[1]=None
        self.box.destroy()
        self.complete=self.complete+1
        self.valid=True
        return True
    
    def IOWatch(self,c):
        self.IO[c]=gobject.io_add_watch(self.io[c][1],gobject.IO_IN,self.dumpIO,c)

    def dumpIO(self,source,condition,c):
        #print "Enter IO loop:"
        #while True:
        try:
            data=source.read()
        except StandardError:
            print "Buffer underrun, try back later!"
            return True # We'll catch the next one!

        #print "Receive IO request : '" + data + "'"
        # This code is taken heavily from file2divx3pass by Rien Croonenborghs
        #Pos:  49.0s   1179f ( 1%) 232fps Trem:   8min  69mb  A-V:0.084 [0:115]
        #Pos:3439,7s  82468f (63%) 2401fps Trem:  0min 694mb  A-V:0,043 [929:135]
        #Pos:  17.2s    515f ( 2%) 117.82fps Trem:   2min 180mb  A-V:0.033 [1697:705]
        if re.match(r'^Pos:([ 0-9.,]+)s\s+([ 0-9.,]+)f \(([ 0-9.,]+)%\) ([ 0-9.,]+)fps',data):
            t=re.split(r'\s+',re.sub(r'[\(\)%]','',data))
            try:
		    pct=int(t[3])+1
        	    self._updateGraph(c,pct)
	    except:
	    	return True # Error with conversion, we'll get the next one
	    
        #print "Exit IO loop"        
        return True           
 
    def _updateGraph(self,num,pct):
        
        if num<self.segments:
            sp=100.0*(hms2s(self.array[num][0])/self.fcnt)
            se=100.0*(hms2s(self.array[num][1])/self.fcnt)
            #print "Percent: c="+str(c)+", sp="+str(sp)+", se="+str(se)+": "+str(pct)
            pct=int(100.0*(pct-sp)/se)
            if pct==self.prog[num]: return True
            self.prog[num]=100 if pct>100 else pct
            if pct>100: return True
            #print "Updating call " + str(num) + " - percentage: " + str(pct) + "%"
            pct=sum(self.prog)/(2*self.segments)
        else:
            if self.prog[0]==pct: return True
            if self.prog[0]>pct: self.prog[1]=self.prog[1]+1
            self.prog[0]=pct
            pct=50+(50*self.prog[1]/self.segments)+(pct/(2*self.segments))
            #pct=(pct/2)+50
            #print "Updating call - percentage: " + str(pct) + "% segment: " + str(self.prog[1])

        self.progbar.set_fraction(float(pct)/100)
        self.progbar.set_text(str(pct)+"%")
        
        return True

def hms2s(t):
    (h,m,s)=re.split(':',t)
    h=int(h)
    m=int(m)
    s=float(s)
    return (3600*h)+(60*m)+s
