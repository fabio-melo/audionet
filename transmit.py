from pydub import AudioSegment
from pydub.generators import Sine,Square
from pydub.playback import play
import sys


def string2bits(s=''):
  return ''.join([bin(ord(x))[2:].zfill(8) for x in s])

  print(sys.argv)

mt = '00001101' + string2bits(sys.argv[1])

SLEEPTIME = 200
multitone = AudioSegment.empty()

for m in mt:
  if m == '0':
    tone1 =  AudioSegment.silent(duration=SLEEPTIME) 
    multitone = multitone.append(tone1, crossfade=0)
  elif m == '1':
    tone1 = Sine(15000).to_audio_segment(duration=SLEEPTIME)
    multitone = multitone.append(tone1, crossfade=0)
    


play(multitone)
  