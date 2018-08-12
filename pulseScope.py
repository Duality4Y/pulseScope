#!/usr/bin/env python
import struct
import math
import time

import pyaudio
import pygame
import numpy
from operator import itemgetter

def chunks(l, n):
    """ Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

""" point volume calculators. like averaging and just taking the first point """
def pointVolumeAvg(chunk):
    return float(sum(chunk)) / float(len(chunk))

def pointVolumeFirst(chunk):
    return chunk[0]

def mean(a):
    return float(sum(a)) / float(len(a))

def average_lists(lists):
    return map(mean, zip(*lists))

# if data is interlaced audio then return a tuple with left and right data
def channels(data):
    return (data[0::2], data[1::2])

def toLinear(data, logScale=20):
    value = logScale * numpy.log10(value)

from math import log2, pow

A4 = 440
C0 = A4 * pow(2, -4.75)
keyname = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def pitch(freq):
    if freq:
        h = round(12 * log2(freq / C0))
        octave = h // 12
        n = h % 12
        return keyname[n] + str(octave)
    else:
        return ""


# object for doing averages on lists of numbers.
class Average(object):
    def __init__(self, size=20):
        self.size = size
        self.lists = []

    def averageLists(self, lists):
        return list(map(mean, zip(*lists)))

    def getSize(self):
        return self.size

    def setSize(self, value):
        self.size = value

    def average(self, values):
        self.lists.append(values)
        if len(self.lists) > self.size:
            del self.lists[0]
        return self.averageLists(self.lists)

class Buffer(object):
    def __init__(self, length=10, chunksize=1024):
        self.data = []
        self.length = length
        self.chunksize = chunksize
        self.dataslice = slice(self.chunksize, -1, 1)

    def add(self, inputData):
        """
            This function adds data to a buffered list of data.
            Assumes that the inputData is a list of fixed length.
        """
        # remove the first one if the length is indicates it's full
        if len(self.data) == self.chunksize * self.length:
            self.data = self.data[self.chunksize::1]

        self.data.extend(inputData)

    @property
    def size(self):
        return len(self.data)

    @property
    def buffer(self):
        return self.data

    @property
    def filled(self):
        return self.size == (self.length * self.chunksize)

class FramedBuffer(Buffer):
    def __init__(self, *args, **kwargs):
        super(FramedBuffer, self).__init__(*args, **kwargs)

    @property
    def buffer(self):
        return self.data[math.floor(self.chunksize / 2):self.size - math.floor(self.chunksize / 2):1]


class Scope(object):
    def __init__(self, samplerate, chunksize, rect=(0, 0, 1024, 1024), pointcalc=pointVolumeFirst):
        pygame.init()
        pygame.font.init()

        self.rect = rect
        self.surface = pygame.display.set_mode(self.windowSize)
        pygame.display.set_caption("pulseScope")

        self.chunksize = chunksize
        self.samplerate = samplerate
        
        self.font = pygame.font.SysFont('Times New Roman', 28)

        self.pointcalc = pointcalc
        self.xyEnabled = False

        # fft scale to window, so fftscale = 2 = max height half the window height (height / 2)
        self.fftscale = 1024 / (13 * 32) # i want it to go to the 13'th bar.
        self.fft_stretch = 2

        self.leftcolor = (0, 0xff, 0xff)
        self.rightcolor = (0xff, 0, 0xff)


        self.average = 2
        self.avgLeft = Average(size=self.average)
        self.avgRight = Average(size=self.average)

        self.leftBuffer = FramedBuffer(length=3, chunksize=self.chunksize)
        self.rightBuffer = FramedBuffer(length=3, chunksize=self.chunksize)

        self.bufferedLine = Buffer(length=3, chunksize=self.chunksize)
        self.maxDistance = 0

        width, height = self.windowSize
        self.window = None
        # self.window = numpy.bartlett(width)
        # self.window = numpy.blackman(width)
        # self.window = numpy.hamming(width)
        # self.window = numpy.kaiser(width * 2, 5.0)

        self.windowpoints = []
        if self.window is not None:
            for x, value in enumerate(self.window):
                point = (x, int(height - (value * height)))
                self.windowpoints.append(point)

    @property
    def windowSize(self):
        return self.rect[2:4:1]

    # prints text on the screen on line
    # line is in increments of font height.
    def printText(self, text, line, color):
        self.textsurface = self.font.render(text, True, color)
        x, y, width, height = self.textsurface.get_rect()
        self.surface.blit(self.textsurface, (0, line * height))

    # build a specturm (list of values) from data.
    # (fft spectrum)
    def buildSpectrum(self, data):
        # n is simpy how many points are returned. if bigger its padded with zero's
        # if smaller then len(data) it is cropped.
        width, height = self.windowSize
        spectrum = numpy.fft.fft(data, n=self.fft_stretch * width)
        real_spectrum = numpy.absolute(spectrum)
        width, height = self.windowSize

        return real_spectrum

    def logFun(self, value, a):
        return value / (a + value)

    def calcSpectrumHeight(self, x, value):
        _ , height = self.windowSize
        # apply a non linear function to value.
        value = self.logFun(value, ((1 << 32) - 1))
        # then scale it nicely
        y = (height - height * (value / self.fftscale))

        return x, y


    def drawSpectrum(self, data):
        points = []
        width, height = self.windowSize
        for x, value in enumerate(data):
            if x >= width:
                break
            point = self.calcSpectrumHeight(x, value)
            points.append(point)

        return points

    def calcFreq(self, spectrum, samplerate):
        freqs = numpy.fft.fftfreq(len(spectrum))
        idx = numpy.argmax(numpy.abs(spectrum))
        freq = freqs[idx]
        return abs(freq * samplerate)

    def drawSpectra(self, data, samplerate):
        leftData, rightData = channels(data)
        leftPoints, rightPoints = [], []

        # buffer left data
        self.leftBuffer.add(leftData)
        if(self.leftBuffer.filled):
            # sufficient data to do things with.
            leftSpectrum = self.buildSpectrum(self.leftBuffer.data)
            leftPoints = self.drawSpectrum(leftSpectrum)

        self.rightBuffer.add(rightData)
        if(self.rightBuffer.filled):
            rightSpectrum = self.buildSpectrum(self.rightBuffer.data)
            rightPoints = self.drawSpectrum(rightSpectrum)

        return leftPoints, rightPoints


    def _drawSpectra(self, data, samplerate):
        width, height = self.windowSize
        leftData, rightData = channels(data)
        # self.leftBuffer.buffer(leftData)
        # self.rightBuffer.buffer(rightData)
        
        # process the left side and draw.
        # leftData = [item for sublist in self.leftBuffer.lists for item in sublist]
        leftSpectrum = self.buildSpectrum(leftData)
        leftSpectrum = self.avgLeft.average(leftSpectrum)
        freq = self.calcFreq(leftSpectrum, samplerate)
        self.printText("L Freq: %dHz %s" % (freq, pitch(freq)), 0, self.leftcolor)
        leftPoints = self.drawSpectrum(leftSpectrum)

        # process the right side and draw it.
        # rightData = [item for sublist in self.rightBuffer.lists for item in sublist]
        rightSpectrum = self.buildSpectrum(rightData)
        rightSpectrum = self.avgRight.average(rightSpectrum)
        freq = self.calcFreq(rightSpectrum, samplerate)
        self.printText("R Freq: %dHz %s" % (freq, pitch(freq)), 1, self.rightcolor)
        rightPoints = self.drawSpectrum(rightSpectrum)


        # get the value that is in the view that is the max value and return a index + a 
        # step, value = max(enumerate(leftSpectrum), key=itemgetter(1))
        # if step < width:
        #     pass

        # freqs = numpy.fft.fftfreq(len(rightSpectrum))
        # idx = numpy.argmax(numpy.abs(rightSpectrum), axis=0)
        # freq = freqs[idx]
        # freqhz = abs(freq * samplerate)

        return leftPoints, rightPoints

    def drawWaveForm(self, data, samplerate):
        lchannel_data = list(data[0::2])
        rchannel_data = list(data[1::2])
        # turn data into a list of points
        width,  height = self.windowSize

        lpoints = []
        for x, chunk in enumerate(chunks(lchannel_data, round(len(lchannel_data) / width))):
            value = self.pointcalc(chunk)
            if numpy.isnan(value) or numpy.isinf(value):
                value = 0
            y = int(height * 0.20 - (value / ((1 << 32) - 1) * (height / 2.0)))
            point = (x, y)
            lpoints.append(point)

        rpoints = []
        for x, chunk in enumerate(chunks(rchannel_data, round(len(rchannel_data) / width))):
            value = self.pointcalc(chunk)
            y = int(height * 0.50 - (value / ((1 << 32) - 1) * (height / 2.0)))
            point = (x, y)
            rpoints.append(point)

        points = lpoints, rpoints
        return points

    def drawXY(self, data, scale=5):
        width, height = self.windowSize
        lcvalues, rcvalues = channels(data)

        lcvalues = list(map(lambda x: (width / 2) + (x / ((1 << 32) - 1) * width * scale), lcvalues))
        rcvalues = list(map(lambda y: height - ((height / 2) + (y / ((1 << 32) - 1) * height * scale)), rcvalues))

        return list(zip(lcvalues, rcvalues))

    def draw(self, data, samplerate):
        if data == None:
            return

        self.surface.fill((0, 0, 0))

        # draw a grid but don't draw the first lines
        width, height = self.windowSize
        for x in range(32, width, 32):
            pygame.draw.line(self.surface, (0x40, 0x40, 0x00), (x, 0), (x, height), 1)
        for y in range(32, height, 32):
            pygame.draw.line(self.surface, (0x40, 0x40, 0x00), (0, y), (width, y), 1)

        # draw a representation of the wave form shape.
        # time is samplerate / 1024
        leftshape, rightshape = self.drawWaveForm(data, samplerate)
        if leftshape:
            pygame.draw.lines(self.surface, self.leftcolor, False, leftshape, 1)
        if rightshape:
            pygame.draw.lines(self.surface, self.rightcolor, False, rightshape, 1)

        # draw freq spectra
        leftshape, rightshape = self.drawSpectra(data, samplerate)
        if leftshape:
            pygame.draw.lines(self.surface, self.leftcolor, False, leftshape, 1)
        if rightshape:
            pygame.draw.lines(self.surface, self.rightcolor, False, rightshape, 1)


        # draw the windowing function.
        if self.window is not None:
            pygame.draw.lines(self.surface, (0xff, 0, 0), False, self.windowpoints, 1)

        

        if self.xyEnabled:
            shape = self.drawXY(data)
            self.bufferedLine.add(shape)
            shape = self.bufferedLine.data
            if shape is not None:
                # pygame.draw.aalines(self.surface, (0, 0xff, 0), False, shape, 1)
                for p1, p2 in zip(shape[0:-1], shape[1::]):
                    pygame.draw.line(self.surface, (0, 0xff, 0), p1, p2, 1)

        pygame.display.update()

    def process(self):
        # handle for ctrl-c
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            elif event.type == pygame.KEYDOWN:
                mods = event.mod
                key_mod = pygame.KMOD_LCTRL
                lctrlpressed = (mods & key_mod) == key_mod
                if event.key == pygame.K_c and lctrlpressed:
                    return True
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return True
        return False

    def quit(self):
        print("exiting scope.")
        pygame.display.quit()
        pygame.quit()

if __name__ == "__main__":
    samplerate = 44800
    chunksize = (1 << 10)
    scope = Scope(samplerate, chunksize)

    class AudioApp(object):
        def __init__(self):
            self.audioChannels = 2
            self.rate = samplerate
            self.chunksize = chunksize

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

        def quit(self):
            print("cleaning things up!")
            print("stopping stream")
            self.stream.stop_stream()
            print("closing stream.")
            self.stream.close()
            print("terminating pyaudio.")
            self.p.terminate()
            print("done cleaning up.")

        def audioCallback(self, in_data, frame_count, time_info, status):
            self.data = struct.unpack("%si" % int(len(in_data) / 4), in_data)
            self.new_data = True
            return (None, pyaudio.paContinue)

        def process(self):
            while self.stream.is_active():
                if scope != None:
                    if scope.process():
                        break # break loop to exit
                    scope.draw(self.data, self.rate)
                time.sleep(1. / 30.)

    ap = AudioApp()
    ap.process()
    ap.quit()
    scope.quit()