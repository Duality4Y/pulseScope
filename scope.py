import pygame
import numpy

import artnet
import utils
import audio

class Scope(object):
    def __init__(self, samplerate, chunksize, rect=(0, 0, 1024, 1024), pointcalc=utils.chunkFirstPoint):
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
        self.tracingEnabled = False
        self.fftEnabled = True
        self.candyMachineEnabled = False

        # fft scale to window, so fftHeightScale = 2 = max height half the window height (height / 2)
        # self.fftHeightScale = 1024 / (13 * 32) # i want it to go to the 13'th bar.
        self.fftHeightScale = 0.5
        self.fftBinScale = 6
        # self.fftBinScale = 2

        self.leftcolor = (0, 0xff, 0xff)
        self.rightcolor = (0xff, 0, 0xff)


        self.fftAverage = 4
        self.avgLeft = utils.Average(size=self.fftAverage)
        self.avgRight = utils.Average(size=self.fftAverage)

        fftFrameSize = 1
        self.leftBuffer = utils.Buffer(length=fftFrameSize, chunksize=self.chunksize)
        self.rightBuffer = utils.Buffer(length=fftFrameSize, chunksize=self.chunksize)

        self.bufferedLine = utils.Buffer(length=1, chunksize=self.chunksize)
        self.maxDistance = 0

        width, height = self.windowSize
        self.window = None
        # self.window = ["barlett", numpy.bartlett(width)]
        # self.window = ["blackman", numpy.blackman(width)]
        # self.window = ["hamming", numpy.hamming(width)]
        self.window = ["kaiser", numpy.kaiser(width * 2, 5.0)]
        self.drawWindowShape = True

        self.windowpoints = []
        if self.window is not None:
            for x, value in enumerate(self.window[1]):
                point = (x, int(height - (value * height)))
                self.windowpoints.append(point)
        
        self.waveFormScale = 10 * 2

        self.numberFftBars = 6 * 2 + 20
        # self.numberFftBars = 6
        """
        self.artnet = artnet.Artnet()
        self.candy = artnet.CandyMachine()
        """
        self.artnet = None
        self.candy = None
        self.candyHeightScale = 1

        self.displayInfo = False
        self.drawTheFftBlocks = True

    @property
    def windowSize(self):
        return self.rect[2:4:1]

    # prints text on the screen on line
    # line is in increments of font height.
    def printText(self, text, line, color=(0xff, 0xff, 0xff), x_offset=0, y_offset=0):
        self.textsurface = self.font.render(text, True, color)
        x, y, width, height = self.textsurface.get_rect()
        self.surface.blit(self.textsurface, (x + x_offset, line * height + y_offset))

    # build a specturm (list of values) from data.
    # (fft spectrum)
    def buildSpectrum(self, data):
        # n is simpy how many points are returned. if bigger its padded with zero's
        # if smaller then len(data) it is cropped.
        width, height = self.windowSize
        spectrum = numpy.fft.fft(data, n=self.fftBinScale * width)
        real_spectrum = numpy.absolute(spectrum)
        if self.window is not None:
            for x, scaler in enumerate(self.window[1]):
                real_spectrum[x] = real_spectrum[x] * scaler

        return real_spectrum

    def logFun(self, value, a):
        return value / (a + value)

    def calcSpectrumHeight(self, x, value):
        _ , height = self.windowSize
        # if self.window is not None:
        #     value *= self.window[x]

        # apply a non linear function to value.
        value = self.logFun(value, ((1 << 32) - 1))
        # then scale it nicely
        y = (height - height * (value / self.fftHeightScale))

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
        leftData, rightData = utils.channels(data)
        leftPoints, rightPoints = [], []
        width, _ = self.windowSize

        # buffer left/right data
        self.leftBuffer.add(leftData)
        if(self.leftBuffer.filled):
            leftSpectrum = self.buildSpectrum(self.leftBuffer.data)
            # slicing the data breaks pitch dection outside of the window.
            # (full range of the fft bins. doesn't have to fall inside the window.)
            leftSpectrum = self.avgLeft.average(leftSpectrum)
            leftPoints = self.drawSpectrum(leftSpectrum)
            freq = self.calcFreq(leftSpectrum, samplerate)
            self.printText("L Freq: {0:.2f}Hz {1}".format(freq, audio.pitch(freq)), 0, self.leftcolor)

        self.rightBuffer.add(rightData)
        if(self.rightBuffer.filled):
            rightSpectrum = self.buildSpectrum(self.rightBuffer.data)
            rightSpectrum = self.avgRight.average(rightSpectrum)
            rightPoints = self.drawSpectrum(rightSpectrum)
            freq = self.calcFreq(rightSpectrum, samplerate)
            self.printText("R Freq: {0:.2f}Hz {1}".format(freq, audio.pitch(freq)), 1, self.rightcolor)

        return leftPoints, rightPoints

    def drawWaveForm(self, data, samplerate):
        """ Draw the shape of the wave in data set."""
        lchannel_data, rchannel_data = utils.channels(data)
        # turn data into a list of points
        width, height = self.windowSize

        """ Simply loop through all the points of data scale them right, and plot them. """
        lpoints = []
        if(len(lchannel_data) < width):
            for x in range(0, len(lchannel_data), 1):
                value = self.pointcalc([lchannel_data[x]])
                y = int(height * 0.20 - (value / ((1 << 32) - 1) * (height / 2.0)))
                point = (x, y)
                lpoints.append(point)
        else:
            for x, chunk in enumerate(utils.chunks(lchannel_data, round(len(lchannel_data) / width))):
                value = self.pointcalc(chunk) * self.waveFormScale
                if numpy.isnan(value) or numpy.isinf(value):
                    value = 0
                y = int(height * 0.20 - (value / ((1 << 32) - 1) * (height / 2.0)))
                point = (x, y)
                lpoints.append(point)

        rpoints = []
        if(len(rchannel_data) < width):
            for x in range(0, len(rchannel_data), 1):
                value = rchannel_data[x]
                y = int(height * 0.50 - (value / ((1 << 32) - 1) * (height / 2.0)))
                point = (x, y)
                rpoints.append(point)
        else:
            for x, chunk in enumerate(utils.chunks(rchannel_data, round(len(rchannel_data) / width))):
                value = self.pointcalc(chunk) * self.waveFormScale
                y = int(height * 0.50 - (value / ((1 << 32) - 1) * (height / 2.0)))
                point = (x, y)
                rpoints.append(point)

        points = lpoints, rpoints
        return points

    def drawFftBlocks(self, points, color, numbars, chunkfun=utils.chunkMean):
        shape = []
        width, height = self.windowSize
        barWidth = width / numbars
        values = [height - value[1] for value in points]

        barHeightOffset = 512
        
        if self.candy != None:
            self.candy.fill((0, 0, 0))
        
        for x, chunk in enumerate(utils.chunks(values, int(barWidth))):
            barHeight = chunkfun(chunk)
            pos = (x * barWidth, barHeightOffset - barHeight)
            size = (barWidth, barHeight)

            bar = pygame.Surface(size)
            bar.set_alpha(int(0xff * 0.3))
            bar.fill(color)
            pygame.draw.rect(bar, (0, 0, 0), (0, 0, *size), 2)
            self.surface.blit(bar, pos)

            if self.candy != None:
                candyBarHeight = (barHeight / height) * self.candy.width * self.candyHeightScale
                self.candy.drawHLine(0, x, candyBarHeight, (0, 0xFF, 0))

        if self.artnet != None:
            self.artnet.transmit(bytes(self.candy))
        
        return shape

    def drawXY(self, data, scale=5):
        width, height = self.windowSize
        lcvalues, rcvalues = utils.channels(data)

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
        if self.tracingEnabled:
            leftshape, rightshape = self.drawWaveForm(data, samplerate)
            if leftshape:
                pygame.draw.lines(self.surface, self.leftcolor, False, leftshape, 1)
            if rightshape:
                pygame.draw.lines(self.surface, self.rightcolor, False, rightshape, 1)

        # draw freq spectra
        if self.fftEnabled:
            leftshape, rightshape = self.drawSpectra(data, samplerate)
            if leftshape:
                pygame.draw.lines(self.surface, self.leftcolor, False, leftshape, 1)
                if self.drawTheFftBlocks:
                    self.drawFftBlocks(leftshape, (0, 0xff, 0), self.numberFftBars, chunkfun=utils.chunkMean)
            if rightshape:
                pygame.draw.lines(self.surface, self.rightcolor, False, rightshape, 1)
                if self.drawTheFftBlocks:
                    self.drawFftBlocks(rightshape, (0xff, 0, 0), self.numberFftBars, chunkfun=utils.chunkMean)


        # draw the windowing function.
        if self.drawWindowShape and self.window is not None:
            pygame.draw.lines(self.surface, (0xff, 0, 0), False, self.windowpoints, 1)

        
        # tries to emulate XY mode on scope.
        if self.xyEnabled:
            shape = self.drawXY(data)
            # self.bufferedLine.add(shape)
            # shape = self.bufferedLine.data
            if shape is not None:
                # pygame.draw.aalines(self.surface, (0, 0xff, 0), False, shape, 1)
                for p1, p2 in zip(shape[0:-1], shape[1::]):
                    pygame.draw.line(self.surface, (0, 0xff, 0), p1, p2, 1)

        # Display some info.
        # if self.displayInfo:
        #     self.printText(str.format("Windowing function: {0}", self.window[0]), 0, (0xff, 0xff, 0xff), x_offset=200)

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
                if event.key == pygame.K_w:
                    self.tracingEnabled = not self.tracingEnabled
                if event.key == pygame.K_f:
                    self.fftEnabled = not self.fftEnabled
                if event.key == pygame.K_s:
                    self.candyMachineEnabled = not self.candyMachineEnabled
                    self.drawTheFftBlocks = not self.drawTheFftBlocks
                if event.key == pygame.K_x:
                    self.xyEnabled = not self.xyEnabled
                    print(self.xyEnabled)
                if event.key == pygame.K_c and lctrlpressed:
                    return True
                elif event.key == pygame.K_c:
                    self.drawTheFftBlocks = not self.drawTheFftBlocks
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return True
                if event.key == pygame.K_i:
                    self.displayInfo = not self.displayInfo
        return False

    def quit(self):
        print(">> exiting scope.")
        pygame.display.quit()
        pygame.quit()

if __name__ == "__main__":
    from pulseScope import AudioApp

    with AudioApp() as audioapp:
        audioapp.process()