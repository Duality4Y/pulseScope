import math

A4 = 440
C0 = A4 * pow(2, -4.75)
keyname = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def pitch(freq):
    if freq:
        h = round(12 * math.log2(freq / C0))
        octave = h // 12
        n = h % 12
        return keyname[n] + str(octave)
    else:
        return ""