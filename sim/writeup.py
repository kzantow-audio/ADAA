# %%
import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt
import audio_dspy as adsp
from scipy.special import spence
from IPython.core.display import SVG, Image, display

# %% [markdown]
# # Practical Considerations for Antiderivative Anti-Aliasing
#
# In audio signal processing, it is often useful to use nonlinear
# functions for things like saturation, wavefolding, and more. While
# nonlinear functions can create interesting sounds, they often create
# difficulty in the world of signal processing, particularly by
# invalidating many of the handy mathematical theorems that hold up in the
# world of linear signal processing. One particularly nasty issue that
# arises when using nonlinear functions on digital audio is aliasing.
#
# In this article, we'll give a brief discussion of what aliasing is,
# and how it is typically dealt with. Then, we'll introduce a relatively
# new anti-aliasing technique called Antiderivative Anti-Aliasing (ADAA),
# and discuss some practical considerations for implementing various
# nonlinear systems with ADAA.
# %% [markdown]
# ## Aliasing
#
# First, what is aliasing? This question brings us to the heart of
# digital signal processing. A digital system with sample rate $f_s$
# can only faithfully reproduce signals up to the frequency $f_s/2$,
# often referred to as the Nyquist frequency, named after electrical
# engineer Harry Nyquist of Bell Labs. Any signal above the Nyquist
# frequency will be reflected back over it. For example, if digital
# system with sample rate $f_s = 48$ kHz attempts to reproduce a signal
# at 50 kHz, the signal will be reflected back to $48 - (50 - 48) = 46$
# kHz. This reflected signal is known as an "aliasing artifact" and
# is typically considered undesirable, particularly since the artifact
# is not harmonically related to the original signal. For a more
# in-depth explanation of aliasing, see [here](https://theproaudiofiles.com/digital-audio-aliasing/).
#
# Typically, digital systems use filters to supress any signal above
# the Nyquist frequency, so that aliasing artifacts don't occur. However,
# when using a nonlinear function, the digital system can create signal
# above the Nyquist frequency, thus creating aliasing artifacts. As an
# example let's look at a specific type of distortion known as
# "hard-clipping" distortion. A hard-clipper is a waveshaping distortion
# with a waveshaping curve that looks as follows:

# %%
adsp.plot_static_curve(adsp.hard_clipper, gain=5)
plt.grid()
plt.title('Hard Clipper Response')

# %% [markdown]
# If I now create a 1.2 kHz sine wave, and process it through a
# hard-clipping distortion with no aliasing, I would see the following
# frequency response:

# %%
def plot_fft(x, fs, sm=1.0/24.0):
    fft = 20 * np.log10(np.abs(np.fft.rfft(x) + 1.0e-9))
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    return freqs, fft

def process_nonlin(fc, FS, nonlin, gain=10):
    N = 200000
    sin = np.sin(2 * np.pi * fc / FS * np.arange(N))
    y = nonlin(gain * sin)
    freqs, fft = plot_fft(y, FS)
    return freqs, fft

FC = 1244.5
FS = 1920000

freqs_analog, fft_analog = process_nonlin(FC, FS, adsp.hard_clipper)
peak_idxs = signal.find_peaks(fft_analog, 65)[0]
plt.plot(freqs_analog, fft_analog)
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ No Aliasing')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()

# %% [markdown]
# The spike farthest to the left represents the original sine wave,
# while all the other spikes represent the higher order harmonics
# generated by the hard-clipper. Note that all of the harmonics are
# evenly spaced.
#
# Now, if we were to sample the sine wave at $f_s = 48$ kHz before
# processing it with the hard clipper, any generated harmonics above
# $f_s / 2 = 24$ kHz would be reflected back to produce aliasing
# artifacts. Let's see what that looks like:

# %%
FC = 1244.5
FS = 48000

freqs_alias, fft_alias = process_nonlin(FC, FS, adsp.hard_clipper)
plt.plot(freqs_alias, fft_alias)
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ Aliasing')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()
# %% [markdown]
# In this case, we see that all the blue spikes not marked with the red
# x's are aliasing artifacts. This level of aliasing will almost certainly
# be audible for people listening to signals that have been processed with
# this effect, and probably won't sound very pleasant.

# %% [markdown]
# ## Anti-Aliasing with Oversampling
#
# Now that we have some understanding of what aliasing is, and how
# nonlinear signal processing can create aliasing, let's look at the
# most common method for supressing aliasing artifacts: oversampling.
#
# The idea behind oversampling is very simple: if we run our nonlinear
# process at a higher sample rate, then any harmonics produced above the
# Nyquist frequency can be filtered out before the audio is downsampled
# back to its original sample rate. Let's see how well 4x oversampling
# works for out hard-clipping distortion:

# %%
freqs, fft = process_nonlin(FC, FS*4, adsp.hard_clipper)
plt.plot(freqs, fft)
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ 4x Oversampling')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()
# %% [markdown]
# The result is pretty good! While aliasing artifacts are still visible
# they are at a much lower magnitude than the original signal. More
# oversampling can be used to supress aliasing artifacts even further.
#
# However, using oversampling has some drawbacks, notably with performance.
# Specifically, the processing time for an effect will be multiplied by
# the oversampling factor. In other words, if a process is done with
# 4x oversampling, the oversampled process will be $1/4$th as efficient
# as the original process. With that in mind, let us look for other
# anti-aliasing methods, that hopefully introduce less performance
# overhead.

# %% [markdown]
# ## Antiderivative Antialiasing
#
# Antiderivative anti-aliasing (abbreviated as ADAA), was first introduced
# in a [2016 DAFx paper](http://dafx16.vutbr.cz/dafxpapers/20-DAFx-16_paper_41-PN.pdf)
# by Julian Parker, Vadim Zavalishin, and Efflam Le Bivic from Native
# Instruments. The technical background for ADAA is then further developed
# in an [IEEE paper](https://acris.aalto.fi/ws/portalfiles/portal/27135145/ELEC_bilbao_et_al_antiderivative_antialiasing_IEEESPL.pdf)
# by Stefan Bilbao, Fabián Esqueda, Parker, and Vesa Välimäki. I won't go
# to much into the mathematical details of ADAA, but the basic idea is
# that instead of applying a nonlinear function to a signal, we instead
# apply the anti-derivative of that function, and then use discrete-time
# differentiation resulting in a signal with supressed aliasing artifacts.
#
# ### 1st-order ADAA
#
# ADAA can be implemented as follows: Say we have a nonlinear function,
# $y[n] = f(x[n])$, with an antiderivative $F_1(x) = \int_0^x f(t) dt$. A first-order ADAA
# version of the function, can be written as follows:
# $$
# y[n] = \frac{F_1(x[n]) - F_1(x[n-1])}{x[n] - x[n-1]}
# $$
#
# Unfortunately, when $|x[n] - x[n-1]|$ is very small, this equation
# becomes ill-conditioned, similar to dividing by zero. To remedy this
# issue, we define a tolerance, below which $|x[n] - x[n-1]|$ is treated
# as if it were zero, and then use the following equation to express
# first-order ADAA:
# $$
# y[n] = \begin{cases}
# \frac{F_1(x[n]) - F_1(x[n-1])}{x[n] - x[n-1]}, & |x[n] - x[n-1]| > TOL \\
# f\left( \frac{x[n] + x[n-1]}{2} \right), & \text{else}
# \end{cases}
# $$
#
# For the hard-clipper, we can write the original nonlinear function
# as follows:
# $$
# f(x) = \begin{cases}
# x, & -1 \leq x \leq 1 \\
# \text{sgn}(x), & \text{else}
# \end{cases}
# $$
#
# And the first antiderivative as:
# $$
# F_1(x) = \begin{cases}
# \frac{1}{2}x^2, & -1 \leq x \leq 1 \\
# x \; \text{sgn}(x) - \frac{1}{2}, & \text{else}
# \end{cases}
# $$
#
# Let's see how the aliasing artifacts look using first-order ADAA:
# %%
class ADAA_1:
    def __init__(self, f, F1, TOL=1.0e-5):
        self.TOL = TOL
        self.f = f
        self.F1 = F1

    def process(self, x):
        y = np.copy(x)
        x1 = 0.0
        for n, _ in enumerate(x):
            if np.abs(x[n] - x1) < self.TOL: # fallback
                y[n] = self.f((x[n] + x1) / 2)
            else:
                y[n] = (self.F1(x[n]) - self.F1(x1)) / (x[n] - x1)
            x1 = x[n]
        return y

def signum(x):
    return int(0 < x) - int(x < 0)

def hardClip(x):
    return x if np.abs(x) < 1 else signum(x)

def hardClipAD1(x):
    return x * x / 2.0 if np.abs(x) < 1 else x * signum(x) - 0.5

hardClip_ADAA = ADAA_1(hardClip, hardClipAD1, 1.0e-5)
freqs, fft = process_nonlin(FC, FS, hardClip_ADAA.process)
plt.plot(freqs_alias, fft_alias, '--', c='orange', label='No ADAA')
plt.plot(freqs, fft, 'blue', label='ADAA1')
plt.legend()
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ 1st-order ADAA')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()
# %% [markdown]
# Clearly, the aliasing artifacts are significantly more supressed than
# with no anti-aliasing, however they are still of significant magnitude.
# One option would be to use first-order ADAA in tandem with a modest
# amount of oversampling, maybe 2x:

# %%
freqs_2x, fft_2x = process_nonlin(FC, FS*2, hardClip_ADAA.process)
plt.plot(freqs, fft, '--', c='orange', label='ADAA1')
plt.plot(freqs_2x, fft_2x, 'blue', label='ADAA1, 2x')
plt.legend()
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ 1st-order ADAA')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()

# %% [markdown]
# ### 2nd-order ADAA
#
# A second option is to use higher-order antiderivatives. Let's say that
# our nonlinear function $y[n] = f(x[n])$ has a second antiderivative,
# which we'll call $F_2(x)$. Then second-order ADAA can be written as:
# $$
# y[n] = \frac{2}{x[n] - x[n-2]} \left(\frac{F_2(x[n]) - F_2(x[n-1])}{x[n] - x[n-1]} - \frac{F_2(x[n-1]) - F_2(x[n-2])}{x[n-1] - x[n-2]} \right)
# $$
#
# Since this equation has more divisions where a divide-by-zero error is
# possible, several "fallback" computations are necessary. I won't go
# through them in detail here, but full derivations can be found in Stefan
# Bilbao's IEEE paper (linked above), and implementations can be seen in
# the attached code (see below). Finally, we need the second antiderivative
# of our hard clipping function:
# $$
# F_2(x) = \begin{cases}
# \frac{1}{6}x^3, & -1 \leq x \leq 1 \\
# \left(\frac{1}{2}x^2 + \frac{1}{6} \right) * \text{sgn}(x) - \frac{x}{2}, & \text{else}
# \end{cases}
# $$
#
# Now we can examine the response of second-order ADAA:

# %%
class ADAA_2:
    def __init__(self, f, F1, F2, TOL=1.0e-5):
        self.TOL = TOL
        self.f = f
        self.F1 = F1
        self.F2 = F2

    def process(self, x):
        y = np.copy(x)

        def calcD(x0, x1):
            if np.abs(x0 - x1) < self.TOL:
                return self.F1((x0 + x1) / 2.0)
            return (self.F2(x0) - self.F2(x1)) / (x0 - x1)

        def fallback(x0, x2):
            x_bar = (x0 + x2) / 2.0
            delta = x_bar - x0

            if delta < self.TOL:
                return self.f((x_bar + x0) / 2.0)
            return (2.0 / delta) * (self.F1(x_bar) + (self.F2(x0) - self.F2(x_bar)) / delta)

        x1 = 0.0
        x2 = 0.0
        for n, _ in enumerate(x):
            if np.abs(x[n] - x1) < self.TOL: # fallback
                y[n] = fallback(x[n], x2)
            else:
                y[n] = (2.0 / (x[n] - x2)) * (calcD(x[n], x1) - calcD(x1, x2))
            x2 = x1
            x1 = x[n]
        return y

def hardClipAD2(x):
    return x * x * x / 6.0 if np.abs(x) < 1 else ((x * x / 2.0) + (1.0 / 6.0)) * signum(x) - (x/2)

hardClip_ADAA2 = ADAA_2(hardClip, hardClipAD1, hardClipAD2, 1.0e-5)
freqs, fft = process_nonlin(FC, FS, hardClip_ADAA2.process)
plt.plot(freqs_alias, fft_alias, '--', c='orange', label='No ADAA')
plt.plot(freqs, fft, 'blue', label='ADAA2')
plt.legend()
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ 2nd-order ADAA')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()
# %% [markdown]
# Again, using a modest amount of oversampling in conjuntion with
# 2nd-order ADAA can help immensly. Below, we show the response
# using 2x oversampling:

# %%
freqs_2x, fft_2x = process_nonlin(FC, FS*2, hardClip_ADAA2.process)
plt.plot(freqs, fft, '--', c='orange', label='ADAA2')
plt.plot(freqs_2x, fft_2x, 'blue', label='ADAA2, 2x')
plt.legend()
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title('Hard Clipping Distortion w/ 2nd-order ADAA')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()

# %% [markdown]
# ## Tanh Distortion with ADAA
#
# So far, we've only looked at using ADAA with the hard-clipping
# nonlinearity. Let's move on to another nonlinear function commonly
# used for waveshaping distortion: the $\tanh$ function:
# %%
adsp.plot_static_curve(np.tanh, gain=5)
plt.grid()
plt.title(r'$\tanh$ Response')

# %% [markdown]
# Let's take a look at the frequency domain output of the $\tanh$ distortion,
# with and without aliasing:

# %%
FC = 1244.5
FS = 1920000

freqs_analog, fft_analog = process_nonlin(FC, FS, np.tanh)
peak_idxs = signal.find_peaks(fft_analog, 65)[0]
plt.plot(freqs_analog, fft_analog, label='no aliasing')
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')

FS = 48000
freqs_alias, fft_alias = process_nonlin(FC, FS, np.tanh)
plt.plot(freqs_alias, fft_alias, label='aliasing')

plt.legend()
plt.xlim(0, 20000)
plt.ylim(10)
plt.title(r'$\tanh$ Distortion')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()
# %% [markdown]
# In order to implement ADAA, we'll need to find the first and second
# antiderivatives of $f(x) = \tanh(x)$:
#
# $$
# F_1(x) = \log(\cosh(x))
# $$
# $$
# F_2(x) = \frac{1}{2} \left( \text{Li}_2\left(-e^{-2x}\right) - x \left(x + 2\log\left(e^{-2x} + 1\right) - 2\log(\cosh(x)) \right) \right) + \frac{\pi^2}{24}
# $$
#
# Note that $\log(x)$ refers to the natural logarithm, and $\text{Li}_2(x)$
# refers to the [dilogarithm function](https://en.wikipedia.org/wiki/Spence%27s_function).
# While the dilogarithm is a tricky function to implement by hand, there
# are decent open-source implementations available in Python's [Scipy library](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.spence.html),
# and for C/C++ in the [polylogarithm](https://github.com/Expander/polylogarithm)
# library on GitHub. Note that depending on the implementation of the
# dilogarithm function, it may need to be called in the form $\text{Li}_2(1-x)$.
#
# Let's take a look at how well first- and second-order ADAA supress
# aliasing artifacts for the $\tanh$ nonlinearity:

# %%
def tanh_AD1(x):
    return np.log(np.cosh(x))

def tanh_AD2(x):
    expval = np.exp(-2 * x)
    return 0.5 * (spence(1 + expval) - x * (x + 2 * np.log(expval + 1) - 2*np.log(np.cosh(x)))) + np.pi**2 / 24

plt.plot(freqs_alias, fft_alias, '--', c='orange', label='No ADAA')

tanh_ADAA1 = ADAA_1(np.tanh, tanh_AD1)
freqs, fft = process_nonlin(FC, FS, tanh_ADAA1.process)
plt.plot(freqs, fft, 'green', label='ADAA1')

tanh_ADAA2 = ADAA_2(np.tanh, tanh_AD1, tanh_AD2)
freqs, fft = process_nonlin(FC, FS, tanh_ADAA2.process)
plt.plot(freqs, fft, 'blue', label='ADAA2')

plt.legend()
plt.scatter(freqs_analog[peak_idxs], fft_analog[peak_idxs], c='r', marker='x')
plt.xlim(0, 20000)
plt.ylim(10)
plt.title(r'$\tanh$ Distortion w/ ADAA')
plt.ylabel('Magnitude [dB]')
plt.xlabel('Frequency [Hz]')
plt.grid()

# %% [markdown]
# ## ADAA with Stateful Systems
#
# You may have noticed that every nonlinear system examined thus far
# has been a "memoryless" system, i.e. the current output is dependent
# only on the current input, no memory of past input/output states
# is needed. In other systems, sometimes referred to as "stateful"
# systems, these past states are needed. For several years, ADAA was
# reputed to only work for memoryless systems, since first-order ADAA
# introduces 0.5 samples of group delay along the processing path.
# For an example of how this group delay can be problematic, let's
# examine a nonlinear waveguide resonator:

# %%
display(SVG('https://www.osar.fr/notes/waveguides/WG_Nonlinearities.svg'))
# %% [markdown]
# The resonant frequency of the nonlinear waveguide resonator is dependent
# on the round-trip delay around the nonlinear feedback loop. If we
# were to use first-order ADAA to implement the nonlinearity, then
# the resonant frequency would be skewed low due to the extra half
# sample added to the round-trip delay time by the ADAA process. While
# the error in frequency might be pretty minimal (especially for low-pitched
# resonators, or systems with high sample rates), it can be noticeable.
# For example, waveguide resonators are often used to model vibrating
# guitar strings, an error in the frequency of the waveguide could make
# a guitar string go out of tune!
#
# In this case, ADAA can be still be used, just with a small adjustment:
# after calculating the correct length of the delay line to use at the
# current sample rate, the user must subtract half a sample, to compensate
# for the delay added by the ADAA process.
#
# In general, using ADAA for stateful systems can be slightly more difficult,
# though it is possible. For more details, see Martin Holters' [2019 DAFx paper](http://dafx2019.bcu.ac.uk/papers/DAFx2019_paper_4.pdf)
# on the subject.

# %% [markdown]
# ## Implementation
#
# Thus far, we've seen how antiderivative anti-aliasing can be useful
# for supressing aliasing artifacts in nonlinear systems. However,
# when using ADAA in practice, it can often be difficult to determine
# what order of ADAA is neccesary, and how it compares to using oversampling
# in terms of aliasing supression and computational performance. To that
# end, I've developed an audio plugin using the JUCE/C++ framework, to
# demonstrate the capabilities of ADAA, and allow users to find the right
# balance for their applications. The plugin offers three processing modes:
# standard, first-order ADAA, and second-order ADAA, using both real-time
# computation and table-lookup, as well as variable oversampling options.
# The idea is that users can examine what combination of ADAA and
# oversampling work best for their application.
#
# %%
display(Image("../res/screenshot.png", width=500))

# %% [markdown]
# Currently, I've implemented the hard-clipper, and $\tanh$ distortion,
# as well as a nonlinear waveguide, using the $\tanh$ function as
# the nonlinearity in the feedback path. In the future, I hope to
# add more nonlinear systems, such as nonlinear filters, and wave
# digital filters (inspired by Davide Albertini's [recent paper](https://dafx2020.mdw.ac.at/proceedings/papers/DAFx2020_paper_35.pdf)).
# The project is open-source, so if you have a nonlinear system you'd like
# to see included, feel free to code it up for yourself!
#
# Source code and further documentation can be found on [GitHub](https://github.com/jatinchowdhury18/ADAA).

# %%[markdown]
# ## Acknowledgements
#
# Big thanks to Matt Nielsen for inspiring this project, and for some insightful conversations!
# %%
