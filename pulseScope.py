import struct
import math
import time

import pyaudio
import pygame
import numpy

def chunks(l, n):
    """ Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

""" point volume calculators. like averaging and just taking the first point """
def pointVolumeAvg(chunk):
    return sum(chunk) / len(chunk)

def pointVolumeFirst(chunk):
    return chunk[0]

def mean(a):
    return sum(a) / len(a)

def average_lists(lists):
    return map(mean, zip(*lists))

class Scope(object):
    def __init__(self, size=(), pointcalc=pointVolumeFirst):
        pygame.init()
        self.screen_size = 1024, 800
        self.surface = pygame.display.set_mode(self.screen_size)
        pygame.display.set_caption("pulseScope")
        self.pointcalc = pointcalc

        self.spectra = []
        self.window = None
        # self.window = numpy.hanning(self.screen_size[0])
        # self.window = numpy.bartlett(self.screen_size[0])
        # self.window = numpy.blackman(self.screen_size[0])
        # self.window = numpy.hamming(self.screen_size[0])
        # self.window = numpy.kaiser(self.screen_size[0], 2.5)

        self.spectra_smooth = 3
        self.waves = []

    def drawSpectrum(self, data, samplerate):
        spectrum = numpy.fft.fft(data, n=5*len(data))
        real_spectrum = numpy.absolute(spectrum)
        # print(numpy.fft.fftfreq(n=44100))
        width, height = self.screen_size


        self.spectra.append(real_spectrum)
        if len(self.spectra) > self.spectra_smooth:
            del self.spectra[0]

        avg_spectra = average_lists(self.spectra)

        points = []
        for x, value in enumerate(avg_spectra):
            if x >= width:
                break
            if math.isnan(value):
                value = 0
            if self.window is not None:
                y = height - int(value / (2**31) * self.window[x]) - 1
            else:
                y = height - int(value / (2**31)) - 1
            point = (x, y)
            points.append(point)


        # prototype of function that might be applied to the spectrum?
        # line = []
        # for x in range(0, int(len(data) / 2)):
        #     if x >= width:
        #         break
        #     y = height - 200 * (1 - (1.012 ** (-x)))
        #     point = (x, y)
        #     line.append(point)

        return points, None

    def drawWaveForm(self, data, samplerate):
        lchannel_data = list(data[0::2])
        rchannel_data = list(data[1::2])
        # turn data into a list of points
        width,  height = self.screen_size

        lpoints = []
        for x, chunk in enumerate(chunks(lchannel_data, round(len(lchannel_data) / width))):
            value = self.pointcalc(chunk)
            y = height * 0.20 - int((value / (2**31)) * (height / 2))
            point = (x, y)
            lpoints.append(point)

        rpoints = []
        for x, chunk in enumerate(chunks(rchannel_data, round(len(rchannel_data) / width))):
            value = self.pointcalc(chunk)
            y = height * 0.50 - int((value / (2**31)) * (height / 2))
            point = (x, y)
            rpoints.append(point)

        points = lpoints, rpoints
        return points

    def draw(self, data, samplerate):
        # clear screen
        self.surface.fill((0, 0, 0))

        # draw a grid but don't draw the first lines
        width, height = self.screen_size
        for x in range(32, width, 32):
            pygame.draw.line(self.surface, (0x40, 0x40, 0x00), (x, 0), (x, height), 1)
        for y in range(32, height, 32):
            pygame.draw.line(self.surface, (0x40, 0x40, 0x00), (0, y), (width, y), 1)

        # draw a audio waveform time is at samplerate / len(data)
        shapes = self.drawWaveForm(data, samplerate)
        for shape in shapes:
            if shape:
                pygame.draw.lines(self.surface, (0, 0xff, 0), False, shape, 1)

        # draw a spectrum
        shapes = self.drawSpectrum(data, samplerate)
        for shape in shapes:
            if shape:
                pygame.draw.lines(self.surface, (0, 0xff, 0xFF), False, shape, 1)

        pygame.display.update()


    def process(self):
        # handle for ctrl-c
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            elif event.type == pygame.KEYDOWN:
                mods = event.mod
                key_mod = pygame.KMOD_LCTRL
                lctrlpressed = (mods & key_mod) == key_mod
                if event.key == pygame.K_c and lctrlpressed:
                    raise KeyboardInterrupt
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    raise KeyboardInterrupt

if __name__ == "__main__":
    scope = Scope()

    class TestAudio(object):
        def __init__(self):
            self.audioChannels = 2
            self.rate = 44100
            self.chunksize = 1024

            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(format=pyaudio.paInt32,
                                      channels=self.audioChannels,
                                      rate=self.rate,
                                      input=True,
                                      output=False,
                                      frames_per_buffer=self.chunksize,
                                      stream_callback=self.audioCallback)

            self.stream.start_stream()
            self.data = None
            self.new_data = False

        def __enter__(self): 
            return self

        def __exit__(self, *args, **kwargs):
            print("clearing things up!")
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()

        def audioCallback(self, in_data, frame_count, time_info, status):
            self.data = struct.unpack("%si" % int(len(in_data) / 4), in_data)
            self.new_data = True
            return (None, pyaudio.paContinue)

        def process(self):
            while self.stream.is_active():
                if self.new_data and self.data != None:
                    if scope != None:
                        scope.process()
                        scope.draw(self.data, self.rate)
                    self.new_data = False
                    time.sleep(1. / 30)
    with TestAudio() as ta:
        ta.process()

"""
WIDTH = 2
CHANNELS = 2
RATE = 44100

p = pyaudio.PyAudio()

def callback(in_data, frame_count, time_info, status):
    print(in_data)
    print(frame_count)
    print(time_info)
    print(status)

    return (in_data, pyaudio.paContinue)

stream = p.open(format=p.get_format_from_width(WIDTH),
                channels=CHANNELS,
                rate=RATE,
                input=True,
                output=True,
                stream_callback=callback)

stream.start_stream()

try:
    while stream.is_active():
        pass
        # time.sleep(0.1)
except Exception as e:
    stream.stop_stream()
    stream.close()

    p.terminate()
"""
