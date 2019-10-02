
import pyaudio
import numpy as np
import math
import os
import random
from time import sleep
from collections import deque
from threading import Thread
import sys
import warnings
from ctypes import *
from contextlib import contextmanager
import logging
import curses
from pydub import AudioSegment
from pydub.generators import Sine,Square
from pydub.playback import play


# boilerplate error handling -----------------------------------------------------
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt): pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)


if not sys.warnoptions: warnings.simplefilter("ignore")
#----------------------------------------------------------------




# CONFIG --------------------------------------

SLEEPTIME=.5

SLEEPTIME_MS = int(SLEEPTIME * 1000)
START_PATTERN = [1,0,1,1,0,1]
ACK_PATTERN = [1,0,0,1,1,0]
paused_monitor = False

# ------------------------------------

signal_dq = deque('',maxlen=100)
send_dq = deque()
tx = deque([],maxlen=50)

exit_threads = False

class AudioCaptureThread(Thread):
  def __init__(self, logger):
    Thread.__init__(self)
    self._logger = logger

  def run(self):
    global signal_dq
    global exit_threads

    RATE = 44100
    BUFFER = 882
    with noalsaerr():
      p = pyaudio.PyAudio()

    stream = p.open(
        format = pyaudio.paFloat32,
        channels = 1,
        rate = RATE,
        input = True,
        output = False,
        frames_per_buffer = BUFFER)

    r = range(0,int(RATE/2+1),int(RATE/BUFFER))
    l = len(r)
    self._logger.info("Audio Capture Start")

    while (not exit_threads):
      try:
        data = np.fft.rfft(np.frombuffer(
            stream.read(BUFFER), dtype=np.float32))
      except IOError: pass

      data = np.log10(np.sqrt(np.real(data)**2+np.imag(data)**2) / BUFFER) * 10
      signal_dq.append(1 if data[300] > -20.0 else 0)
    self._logger.info("Audio Capture Stop")

class ReceiverThread(Thread):
  def __init__(self, logger):
    Thread.__init__(self)
    self._logger = logger

  def run(self):
    global signal_dq
    global SLEEPTIME
    global exit_threads
    global paused_monitor

    self._logger.info("Waiting for Start Signal")

    startup = deque([0 for _ in range(len(START_PATTERN))], maxlen=len(START_PATTERN))

    while (not exit_threads):
      while ((not paused_monitor) and (not exit_threads)):
        sleep(SLEEPTIME)
        #self._logger.info(f"WAIT: {list(startup)}")
        startup.append(signal_dq.pop())
        if list(startup) == START_PATTERN:
          startup.append(2) #delay
          self._logger.info("START Signal found: Reading")
          #self._logger.info(f"FOUND {START_PATTERN}: Start Reader")
          msg = self.reader()
          acn = self.ack(msg)
          play(acn)
          
    self._logger.info("Receiver Thread Stop")

  def reader(self):
    global signal_dq
    global SLEEPTIME

    self._logger.info("START Capture")
    silence = 0
    suc, err = 0,0
    msg = []
    while True:
      bit_queue = []
      
      if silence == 1: 
        self._logger.info("END Capture")
        break

      for x in range(9):
        sleep(SLEEPTIME)
        bit_queue.append(signal_dq.pop())
      
      silence = silence+1 if bit_queue == [0, 0, 0, 0, 0, 0, 0, 0, 0] else 0

      if sum(bit_queue) % 2 == 0: 
        suc += 1; r = "OK"
      else:
        err += 1; r = "FAIL"

      res = chr(int("".join(map(str,bit_queue[:8])),2))
      msg.append(res)
      self._logger.info(f'{res} - {bit_queue} {r}')
    self._logger.info(f"RECEIVED: {''.join(msg)}")
    return msg

  def ack(self,msg):
    self._logger.info(f'Sending ACK - {len(msg)}')
    response = "".join([str(x) for x in ACK_PATTERN])
    bits = bin(len(msg))[2:]
    bits = '00000000'[len(bits):] + bits
    aud = generate_audio(response + bits)
    return aud

class TransmitThread(Thread):
  def __init__(self, logger):
    Thread.__init__(self)
    self._logger = logger

  def run(self):
    global send_dq
    global exit_threads
    self._logger.info("Starting Transmit")
    while (not exit_threads):
      while send_dq:
        msg = send_dq.pop()
        aud = self.generate_message(msg)
        self.check_for_noise()
        play(aud)
        self.check_ack(msg)
    
    self._logger.info("Transmit Thread Stop")

  def check_for_noise(self):
    global signal_dq
    global SLEEPTIME
    can_transmit = False

    self._logger.info('Checking if Carrier is OPEN')
    silence = 0
    while (not can_transmit):
      bit_queue = []
      byte_size = 9
      for x in range(byte_size):
        sleep(SLEEPTIME)
        bit_queue.append(signal_dq.pop())
      
      silence = True if bit_queue == [0 for x in range(byte_size)] else False

      if silence:
        self._logger.info('CARRIER OPEN - SEND')
        can_transmit = True

      else:
        tts = round(random.uniform(0.5,5.0),2)
        self._logger.info(f"CARRIER BUSY - wait for {tts} seconds")
        sleep(tts)
  
  def check_ack(self,msg):
    global SLEEPTIME


    res = []
    self._logger.info("Waiting for ACK")

    waiting = deque([0 for _ in range(len(ACK_PATTERN))], maxlen=len(ACK_PATTERN))

    while True:
      sleep(SLEEPTIME)
      waiting.append(signal_dq.pop())
      if list(waiting) == ACK_PATTERN:
        self._logger.info("ACK START Signal found: Reading")
        for x in range(8):
          sleep(SLEEPTIME)
          res.append(str(signal_dq.pop()))
        val = int(''.join(res),2)
        self._logger.info(f'ACK RECEIVED {val}')
        if val == len(msg):
          self._logger.info(f'ACK MATCH / SENT: {len(msg)} RECEIVED: {val} ')
        else:
          self._logger.info(f'ACK MISMATCH / SENT: {len(msg)} RECEIVED: {val} ')
        break

  def generate_message(self, s, start=START_PATTERN, sleeptime=SLEEPTIME_MS):
      #max 32 chars
      self._logger.info(f"Sending: {s}")
      silence = '' # '0000000'
      result = ""
      for c in s:
          bits = bin(ord(c))[2:]
          bits = '00000000'[len(bits):] + bits
          # paridade
          if sum([int(b) for b in bits]) %2 == 0: 
            bits += '0'
          else:
            bits += '1'
          result += bits
          
      #checksum 8 bits
      checksum = bin(sum([int(b) for b in result]))[2:]
      checksum = '00000000'[len(checksum):] + checksum
  
      start = "".join([str(x) for x in start])
      result = silence + start + result
      
      return generate_audio(result, sleeptime=sleeptime)
      

      

def generate_audio(msg, sleeptime=SLEEPTIME_MS):
  # recebe string, transforma em audio
  tones = AudioSegment.empty()
  for b in msg:
    if b == '0':
      tone =  AudioSegment.silent(duration=sleeptime) 
      tones = tones.append(tone, crossfade=0)
    elif b == '1':
      tone = Sine(15000).to_audio_segment(duration=sleeptime)
      tones = tones.append(tone, crossfade=0)
  return tones



def main():
  global paused_monitor
  global exit_threads

  running = True
  logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

  #logging.basicConfig(format='%(asctime)-6s: %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG,
  #          )

  prc = AudioCaptureThread(logging)
  rec = ReceiverThread(logging)
  trn = TransmitThread(logging)

  threads = [prc,rec,trn]

  for t in threads:
    t.setDaemon(True)
    t.start()
  
  while (not exit_threads):
    x = input('>')
    try:
      if x == 'exit':
        logging.info("Exiting")
        exit_threads = True
      elif x == 'stop':
        paused_monitor = True
        logging.info("Paused Reader Mode")
      elif x == 'start':
        paused_monitor = False
        logging.info("Restarted Reader Mode")
      elif x[:4] == 'send':
        msg = x[5:]
        if msg:
        #msg = input("String to Send: ")
          send_dq.append(msg)
        else:
          logging.info("missing message")
    except: pass

  for t in threads:
    t.join()

main()