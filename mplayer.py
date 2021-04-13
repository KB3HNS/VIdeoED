#!/usr/bin/env python

import sys, os, fcntl, gobject, time

STATUS_TIMEOUT = 100

#
#  Provides simple piped I/O to an mplayer process.
# Since VIdeoED uses frame count to track everything, this class must translate frame count to
# MPlayer's native time format.  NB, this means that it will not work with older MPlayers which
# only support percentage as we need the granularity.
# FIXME: Is there a native frame count interface to MPlayer? I didn't see one in the docs.
# Also, this class must be completely responsible for handling MPlayer's play/pause
#
class Mplayer:
	
	mplayerIn, mplayerOut = None, None
	eofHandler, statusQuery = None, None
	paused, valid, _qst = False, False, False
	setProgress, EoFCall, setText, rev = None, None, None, None
	framerate, flen, fname, mult = 0, 0, "", 1
	callque = []
	#
	#  Initializes this Mplayer with the specified data.
	#
	def __init__(self, filename, progressbar, progresstext, statusCb):
		
		mpc = "mplayer -slave -quiet \"" + filename + "\" 2>/dev/null"
		
		self.mplayerIn, self.mplayerOut = os.popen2(mpc)  #open pipe
		fcntl.fcntl(self.mplayerOut, fcntl.F_SETFL, os.O_NONBLOCK)
		
		self.paused=False
		self.valid=False
		self.callque=[]
		self._statusCb  = statusCb
		self.startIOHandler()
		self.startEofHandler()
		self.startStatusQuery(1000)
		self.fname = filename
		self.setProgress=progressbar
		self.setText=progresstext
	
        def _validateCb(self,resp):
                if resp.find("ANS_LENGTH=") > -1:
                        self.flen=float(resp.replace("ANS_LENGTH=",""))
                elif resp.find("ANS_fps") > -1:
                        self.framerate=float(resp.replace("ANS_fps=",""))
                else:
                        print "Unknown response : " + resp
                        return False

                if (self.framerate > 0 and self.flen > 0):
                        self.valid=True
                        self.pause()
                        self._statusCb(self,True)
                print "_validateCb called! resp=" + resp + ". flen=" + str(self.flen) + ", fr=" + str(self.framerate)
                return True
        
	#
	#  Issues command to mplayer. (Internal use only!)
	#
	def cmd(self, command, resp="", callback=None):
		if (resp != ""):
        		cq=[resp,callback]
                        self.callque.append(cq)
		#print "Sending command: " + command  + " awaiting response: " + resp
		try:
			self.mplayerIn.write(command + "\n")
			self.mplayerIn.flush()  #flush pipe
		except StandardError:
			self.valid=False
			return None

		return True
	
	#
	#  Toggles pausing of the current mplayer job and status query.
	# Unlike other calls, this one returns the status of paused, not isvalid()!
	#
	def pause(self):
		
		if not self.isvalid():
			return False
			
		if self.paused:  #unpause
                        self.stopStatusQuery()
			self.startStatusQuery()
			self.paused = False
			
		else:  #pause
			self.stopStatusQuery()
			self.startStatusQuery(10000)
			self.paused = True
			
		self.cmd("pause")
		self.queryStatus()
		return self.paused
		
	#
	#  Seeks to a frame using the specified mode.  See mplayer docs.
	# Mode: 0 = Seek to a relative frame, 2 = Seek to an absolute frame, 1 (unused)
	# If, for some reason we want to seek time instead, set time to True!
	def seek(self, frame, mode=2, time=False):
		if self._qst: return True

		if not self.isvalid(): return False
		
		amount = frame if time else frame / self.framerate
		self.cmd("pausing seek " + str(amount) + " " + str(mode))
		self.paused=True
		#self.pause()
		self.FrAdv()
		return self.queryStatus()
	
	def FrAdv(self):
		if not self.isvalid(): return False

		self.paused=True
		self.cmd("frame_step")
		self.queryStatus()
		return True

	def FFwd(self, mult=4):
		if not self.isvalid(): return False

		self.paused=False
                self.mult=mult
                return self.cmd("speed_mult " + str(mult))


	def Rew(self, mult=4):
		if not self.isvalid(): return False

		# FIXME - No way to rewind, just reverse
		#print "Function not implemented!"
		self.rev=gobject.timeout_add(1000/mult, self._rev)
		self.mult=1
		#pass
		return True

        # Internal call: Rewind by 1 second.  Called at a rate of [mult] times/s will in effect "rewind" the file.
        def _rev(self):
                if not self.isvalid(): return False

                self.cmd("seek -1 0")
                self.paused=False
                
	# Forces to play... Unlike Pause which toggles.
	def Play(self):
		if not self.isvalid(): return False

                if self.rev:
                        gobject.source_remove(self.rev)
                        self.rev=None
                
		self.paused=False
		mult=1.0000/self.mult
                self.mult=1
		print "Mplayer playing..." + str(mult) + " " + str(self.mult)
		return self.cmd("speed_mult " + str(mult))

	#
	#  Cleanly closes any IPC resources to mplayer.
	#
	def close(self):
		
		if self.paused:  #untoggle pause to cleanly quit
			self.pause()
		self.framerate,self.flen=0,0 # Invalidate the class so statusCb will not get called.
		self.stopStatusQuery()  #cancel query
		self.stopEofHandler()  #cancel eof monitor
		self.stopIOHandler()

		self.cmd("quit")  #ask mplayer to quit
		self.valid=False
		
		try:			
			self.mplayerIn.close()	 #close pipes
			self.mplayerOut.close()
		except StandardError:
			pass
			
		self.mplayerIn, self.mplayerOut = None, None
		self.framerate, self.flen = 0, 0
		self.setProgress(0) #reset bar
		
	#
	#  Triggered when mplayer's stdout reaches EOF.
	#
	def handleEof(self, source, condition):
		
		self.stopStatusQuery()  #cancel queries
		self.stopEofHandler()
		self.stopIOHandler()
		self.mplayerIn, self.mplayerOut = None, None
		self.valid=False
		
		if (self.flen > 0 and self.framerate > 0): return self._statusCb(self,False)
		self.framerate, self.flen = 0, 0

		return False
	
	#
	#  Triggered when mplayer has stdout
	#
	def handleIO(self, source, condition):
                #print "Enter IO loop:"
                data=""
                while data == "":
                        try:
                                data=self.mplayerOut.readline().strip()
                        except StandardError:
                                print "Read error...  trying again!"
                                time.sleep(.1)

                #print "Receive IO request : '" + data + "'"
                if len(self.callque) < 1:
                        return True

                n=0
                for i in self.callque:
                        #print "Comparing: " + i[0] + " : " + str(i[1]) + " to " + data + " " + str(data.find(i[0]))
                        if (data.find(i[0]) > -1):
                                #print "Found CB: " + i[0] + " index=" + str(n) + " - jumping : " + str(i[1])
                                i[1](data)
                                del self.callque[n]
                                return True
                        n=n+1

                return True

	#
	#  Queries mplayer's playback status and upates the progress bar.
	#
	def queryStatus(self):

                if (self.flen == 0):
                        self.cmd("pausing_keep get_time_length","ANS_LENGTH",self._validateCb)
                        return True
                
		if (self.framerate == 0):
                        self.cmd("pausing_keep get_property fps","ANS_fps",self._validateCb)
                        return True
		
		self.cmd("pausing_keep_force get_time_pos", "ANS_TIME_POSITION",self._QstatusCb)
		return True
	
	def _QstatusCb(self,resp):
		seconds = 0
		if not resp: return False

		seconds = float(resp.replace("ANS_TIME_POSITION=", ""))
		
		frame=int(seconds*self.framerate)

		# We will get a callback when we update the status bar, ignore it
		self._qst=True
		if self.setProgress: self.setProgress(frame)
		self._qst=False
                if self.setText: self.setText("T = " + s2hms(seconds))
		return True
		
	#
	#  Inserts the status query monitor.
	#
	def startStatusQuery(self,timeout=STATUS_TIMEOUT):
		self.statusQuery = gobject.timeout_add(timeout, self.queryStatus)
		
	#
	#  Removes the status query monitor.
	#
	def stopStatusQuery(self):
		if self.statusQuery:
			gobject.source_remove(self.statusQuery)
		self.statusQuery = None
		
	#
	#  Inserts the EOF monitor.
	#
	def startEofHandler(self):
		self.eofHandler = gobject.io_add_watch(self.mplayerOut, gobject.IO_HUP, self.handleEof)
	
	#
	#  Removes the EOF monitor.
	#
	def stopEofHandler(self):
		if self.eofHandler:
			gobject.source_remove(self.eofHandler)
		self.eofHandler = None
	#
	#  Inserts the IO monitor.
	#
	def startIOHandler(self):
		self.ioHandler = gobject.io_add_watch(self.mplayerOut, gobject.IO_IN, self.handleIO)
	
	#
	#  Removes the IO monitor.
	#
	def stopIOHandler(self):
		if self.ioHandler:
			gobject.source_remove(self.ioHandler)
		self.ioHandler = None

	# Get Attribute functions:
	def getFramerate(self):
		return self.framerate

	def getLength(self):
		return self.flen

	def isPaused(self):
		return self.paused

	def isvalid(self):
		if not self.mplayerIn:
			self.valid=False

		return self.valid
	
	def getTime(self, frame):
		return frame / self.framerate

	def getFrame(self, time):
		return int(time * self.framerate)
	
	def getFilename(self):
		return self.fname

# A few helper functions:
# Converts a float (t: seconds) to "HH:MM:SS.ss" format
def s2hms(t):
        frac=t-int(t)
        m,s=divmod(int(t), 60)
        s=s+frac
        h,m=divmod(m, 60)

        hms="%d:%02d:%05.2f" % (h,m,s)
        return hms
        
#End of file

