# pulseScope
displays left and right channel audio as well as a spectrum of the sound frequencies.

written in python.

purpose for fun and games.

aditions are welcome.

it's not really a Scope but it does show wave forms.

currently the sampling rate is 44100 and the window width is 1024

so the minimum freq it can display is 44100 / 1024 = ~43Hz

the Spectrum displayed is streched and does not show the full spectrum

but only a part of it

from about 0 to ~8.8Khz

# requirements.
requires the following libraries in python:

<pre>
pygame
numpy
pyaudio
</pre>

# how to run
simply run the pulseScope.py script with python3.6

# Todo
[] implement adjusting the scaling of the spectrum

[] implement adjusting spectrum smoothing.

[] implement selecting a windowing function on the spectrum

[] implement adjusting windowing weight. (how much it adjusts a spectrum value)

[] implement displaying general information like avg. freq. and wave form power

   and other data like the timebase used to show the wave form.

[] possibly add a frequency scale under the spectrum.

[] implement adjusting time base on waveforms.

[] implement adjusting amplitude scaling.

[] make the background grid actually be time/div like on a real scope.

[] possibly add a function to subtract left and right channel from each other and show that as a wave form.

