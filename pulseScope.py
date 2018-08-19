#!/usr/bin/env python
import struct
import math
import time
import traceback

import pyaudio
import pygame
import numpy
from operator import itemgetter

import utils
import audio
import artnet
from scope import Scope

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

        def __enter__(self):
            return self

        def __exit__(self, *args):
            print(">> args: ", args)
            etype, value, tb = args
            traceback.print_exception(etype, value, tb)
            self.quit()
            scope.quit()
            return False

        def quit(self):
            print(">> cleaning things up!")
            print(">> stopping stream")
            self.stream.stop_stream()
            print(">> closing stream.")
            self.stream.close()
            print(">> terminating pyaudio.")
            self.p.terminate()
            print(">> done cleaning up.")

        def audioCallback(self, in_data, frame_count, time_info, status):
            self.data = struct.unpack("%si" % int(len(in_data) / 4), in_data)
            self.new_data = True
            return (None, pyaudio.paContinue)

        def process(self):
            while self.stream.is_active():
                if scope != None:
                    if scope.process():
                        break # break loop to exit
                    if self.new_data:
                        self.new_data = False
                        scope.draw(self.data, self.rate)

    with AudioApp() as app:
        app.process()
    exit(0)