# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

import random
import time

from adafruit_matrixportal.matrixportal import MatrixPortal
import adafruit_imageload.bmp
import audiobusio
import audiocore
import audiomp3
import audiomixer
import board
import displayio
import digitalio
import framebufferio
import rgbmatrix
#from adafruit_displayio_layout.widgets.animated_gif import AnimatedGif



displayio.release_displays()

matrix = MatrixPortal(
    width=64,
    height=32,
    bit_depth=4,
    serpentine=True,
    debug=False
)
display = matrix.display
display.rotation = 180

# Each wheel can be in one of three states:
STOPPED, RUNNING, BRAKING = range(3)

#def play_win_gif(filename):
#    gif = AnimatedGif(display, filename)
#    gif.play(loop=False)

# Return a duplicate of the input list in a random (shuffled) order.
def shuffled(seq):
    return sorted(seq, key=lambda _: random.random())


# The Wheel class manages the state of one wheel. "pos" is a position in
# floating point coordinates, with one 1 pixel being 1 position.
# The wheel also has a velocity (in positions
# per tick) and a state (one of the above constants)
class Wheel(displayio.TileGrid):
    def __init__(self, bitmap, palette):
        # Portions of up to 3 tiles are visible.
        super().__init__(
            bitmap=bitmap,
            pixel_shader=palette,
            width=1,
            height=3,
            tile_width=20,
            tile_height=24,
        )
        self.order = shuffled(range(6))
        self.state = STOPPED
        self.pos = 0
        self.vel = 0
        self.termvel = 2
        self.y = 0
        self.x = 0
        self.stop_time = time.monotonic_ns()
        self.step()

    def step(self):
        # Update each wheel for one time step
        if self.state == RUNNING:
            # Slowly lose speed when running, but go at least terminal velocity
            self.vel = max(self.vel * 0.99, self.termvel)
            if time.monotonic_ns() > self.stop_time:
                self.state = BRAKING
        elif self.state == BRAKING:
            # More quickly lose speed when baking, down to speed 0.4
            self.vel = max(self.vel * 0.85, 0.4)

        # Advance the wheel according to the velocity, and wrap it around
        # after 24*20 positions
        self.pos = (self.pos + self.vel) % (20 * 24)

        # Compute the rounded Y coordinate
        yy = round(self.pos)
        # Compute the offset of the tile (tiles are 24 pixels tall)
        yyy = yy % 24
        # Find out which tile is the top tile
        off = yy // 24

        # If we're braking and a tile is close to midscreen,
        # then stop and make sure that tile is exactly centered
        if self.state == BRAKING and self.vel <= 2 and yyy < 8:
            self.pos = off * 24
            self.vel = 0
            yyy = 0
            self.state = STOPPED

        # Move the displayed tiles to the correct height and make sure the
        # correct tiles are displayed.
        self.y = yyy - 20
        for i in range(3):
            self[i] = self.order[(19 - i + off) % 6]

    # Set the wheel running again, using a slight bit of randomness.
    # The 'i' value makes sure the first wheel brakes first, the second
    # brakes second, and the third brakes third.
    def kick(self, i):
        self.state = RUNNING
        self.vel = random.uniform(8, 10)
        self.termvel = random.uniform(1.8, 4.2)
        self.stop_time = time.monotonic_ns() + 3000000000 + i * 350000000

def logoDisplay():
    logobitmap, logoPalette = adafruit_imageload.load(
        "/images/BW_Logo6.bmp",
        bitmap=displayio.Bitmap,
        palette=displayio.Palette)

    logo_grid = displayio.TileGrid(bitmap=logobitmap, pixel_shader=logoPalette)
    logo_group = displayio.Group()
    logo_group.append(logo_grid)
    display.root_group = logo_group
    time.sleep(3)

# This bitmap contains the emoji we're going to use. It is assumed
# to contain 20 icons, each 20x24 pixels. This fits nicely on the 64x32
# RGB matrix display.
the_bitmap, the_palette = adafruit_imageload.load(
    "/images/halloween7.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
)

# Our fruit machine has 3 wheels, let's create them with a correct horizontal
# (x) offset and arbitrary vertical (y) offset.
g = displayio.Group()
wheels = []

def mainDisplay():
    for idx in range(3):
        wheel = Wheel(the_bitmap, the_palette)
        wheel.x = idx * 22
        wheel.y = -20
        g.append(wheel)
        wheels.append(wheel)
    display.root_group = g


###############################################
####            BUTTONS
###############################################
# We want a digital input to trigger the fruit machin
button = digitalio.DigitalInOut(board.A4)
button.switch_to_input(pull=digitalio.Pull.UP)

volUpButton = digitalio.DigitalInOut(board.BUTTON_UP)
volUpButton.switch_to_input(pull=digitalio.Pull.UP)

volDownButton = digitalio.DigitalInOut(board.BUTTON_DOWN)
volDownButton.switch_to_input(pull=digitalio.Pull.UP)
###############################################
####            AUDIO FEATURES
###############################################
i2s = audiobusio.I2SOut(bit_clock=board.A1, word_select=board.A2, data=board.A3)

# Create mixer with one voice
mixer = audiomixer.Mixer(voice_count=1, sample_rate=22050, channel_count=2, bits_per_sample=16, samples_signed=True)

def volChange():
    print("Checking for volume change")
    #check if we need to decrease the volume
    if not volDownButton.value:
        if (mixer.voice[0].level != 0):
            mixer.voice[0].level -= volStep
        else:
            print("VOLUME MUTED")
        print(mixer.voice[0].level)
        print("volume decreased")
    #check if we need to increase the volume
    if not volUpButton.value:
        if (mixer.voice[0].level != 1):
            mixer.voice[0].level += volStep
        else:
            print("Volume Max!")
        print("volume increased")
        print(mixer.voice[0].level)
    time.sleep(0.3)

#get the decoded audio file
def getSound(soundFilePath):

    mp3file = open(str(soundFilePath), "rb")
    sample = audiomp3.MP3Decoder(mp3file)
    mixer.sample_rate = sample.sample_rate
    return sample

###############################################
####            MAIN LOOP
###############################################
def main():
    currVol = volume
    while True:
        print("Starting Main Loop")
        # Refresh the dislpay (doing this manually ensures the wheels move
        # together, not at different times)
        display.refresh(minimum_frames_per_second=0, target_frames_per_second=60)

        all_stopped = all(si.state == STOPPED for si in wheels)
        if all_stopped:
            #play_win_gif("/images/firework.gif")
            # Once everything comes to a stop, wait until the lever is pulled and
            # start everything over again.  Maybe you want to check if the
            # combination is a "winner" and add a light show or something.

            while button.value:
                volChange()
                pass
            for idx, si in enumerate(wheels):
                si.kick(idx)

        # Otherwise, let the wheels keep spinning...
        for idx, si in enumerate(wheels):
            si.step()



###############################################
####            ENTRY/STARTUP
###############################################
#Startup Sequence
logoDisplay()

mainDisplay()
mainTrack = getSound("/music/GothicGroove.mp3")

#set intial volume to 50%
volume = 0.2
volStep = 0.1


i2s.play(mixer)
mixer.voice[0].play(mainTrack, loop=True)
mixer.voice[0].level = volume
main()
while(mixer.playing):
    main()


