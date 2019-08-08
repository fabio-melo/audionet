from pydub import AudioSegment
from pydub.generators import Sine
from pydub.playback import play
import pyaudio
import numpy as np
import math
from time import sleep
from collections import deque
from threading import Thread
import sys
import warnings

if not sys.warnoptions:
    warnings.simplefilter("ignore")

HELLO = "00001101 01101000 01100101 01101100 01101100 01101111"
HOLLA = "00001101 01101000 01101111 01101100 01101100 01100001"

q = deque('',maxlen=1000)
tx = deque([],maxlen=50)

SLEEPTIME=.5
SOUNDDURR = 500

def processor():
  RATE = 44100
  BUFFER = 882
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
  print("Audio Processing Start")

  while True:
    try:
      data = np.fft.rfft(np.frombuffer(
          stream.read(BUFFER), dtype=np.float32))
    except IOError: pass

    data = np.log10(np.sqrt(
      np.real(data)**2+np.imag(data)**2) / BUFFER) * 10
      
    q.append(1 if data[300] > -20.0 else 0)
    

def reader(msg):
  print("Reader Start",flush=True)
  rq = deque([0,0,0,0], maxlen=4)
  while True:
    sleep(SLEEPTIME)
    print(f"Waiting for Pattern - Buffer: {list(rq)}", flush=True)
    rq.append(q.pop())
    if list(rq) == [1,1,0,1]:
      rq.append(255)
      print("Pattern Found - Reading Bytes",flush=True)
      if proc_str() == msg:
        return True
      

def proc_str():
  print("---> Message START",flush=True)
  silence = 0
  msg = []
  while True:
    bq = []
    
    if silence == 2: 
      print("---> Message END")
      break

    for x in range(8):
      sleep(SLEEPTIME)
      bq.append(q.pop())
    if bq == [0, 0, 0, 0, 0, 0, 0, 0]:
      silence += 1
    else:
      msg.append(chr(int("".join(map(str,bq)),2)))
      silence = 0

    res = chr(int("".join(map(str,bq)),2))
    print(f'{res} - {bq}',flush=True)
  return "".join(msg)


def play_sound(mt):
  multitone = AudioSegment.empty()

  for m in mt:
    if m == '0':
      tone1 =  AudioSegment.silent(duration=SOUNDDURR) 
      multitone = multitone.append(tone1, crossfade=0)
    elif m == '1':
      tone1 = Sine(15000).to_audio_segment(duration=SOUNDDURR)
      multitone = multitone.append(tone1, crossfade=0)
  
  play(multitone)

def client1():
  while True:
    play_sound(HELLO)
    reader('holla')

def server1():
  while True:
    reader('hello')
    sleep(1)
    play_sound(HOLLA)
    

if __name__ == '__main__':

  proc = Thread(target=processor)
  proc.start()
  if 'server' in sys.argv:
    srvr = Thread(target=server1)
    srvr.start()
  elif 'client' in sys.argv:
    clin = Thread(target=client1)
    clin.start()

