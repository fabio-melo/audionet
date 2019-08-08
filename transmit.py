from pydub import AudioSegment
from pydub.generators import Sine,Square
from pydub.playback import play

with open('output.txt','r') as file:
  mt = file.read()

SLEEPTIME = 200
multitone = AudioSegment.empty()

for m in mt:
  if m == '0':
    tone1 =  AudioSegment.silent(duration=SLEEPTIME) 
    multitone = multitone.append(tone1, crossfade=0)
  elif m == '1':
    tone1 = Sine(15000).to_audio_segment(duration=SLEEPTIME)
    multitone = multitone.append(tone1, crossfade=0)
    


multitone.export("res.mp3", format="mp3")

