### F-04.01 · re 4.02 · reason: physics-check
*You said:* "hopefully, the agents can implement keychording in my cardkb tho..."
**Q: Will you accept sequential sticky modifier chords (press Fn then key) instead of simultaneous multi-key chords?**
(The CardKB's stock ATmega328P firmware only scans and transmits a single ASCII byte over I2C per keypress; it does not report key-down/up scancodes. True simultaneous chords like Ctrl+Shift+X are physically impossible without custom ISP-flashed keyboard firmware.)
> A:

### F-04.02 · re 4.04 · reason: unstated-tradeoff
*You said:* "i wanna design my own kind of card kb kinda thingy, where it has"
**Q: Should software development target stock CardKB v1.1 first as MVP, deferring the custom keyboard PCB to v2?**
(Designing and fabricating a custom PCB delays software testing. Stock CardKB is verified working on hardware today via `pi/cardkb/reader.py`.)
> A:

### F-04.03 · re 4.07 · reason: unstated-tradeoff
*You said:* "i was thinking to give it a very small OLED screen that says which"
**Q: Should the rotary encoder and its micro-OLED be wired to the Pi's GPIO/I2C or the ESP32 coprocessor?**
(Pi Zero 2W GPIO has spare pins, but running I2C screen refresh + GPIO interrupts in Python adds latency. ESP32 has hardware timers but very few free exposed pins on the CYD board.)
> A:

### F-04.04 · re 4.08 · reason: unstated-tradeoff
*You said:* "yeppers!!! maybe if we can implement full ncurses terminal in the CYD, we can"
**Q: Should resistive touch driver integration be deferred until after the keyboard-driven terminal contract is stable?**
(The XPT2046 resistive touch controller shares the SPI bus with the ILI9341 display. Polling it over serial wire protocol adds packet overhead to the 115200 baud link.)
> A:

### F-04.05 · re 4.09 · reason: physics-check
*You said:* "im planning to yet have another bigger oled screen which is really long and"
**Q: Where will you physically mount two extra OLED screens and a vibration motor within the <A5, <65mm case?**
(A primary 2.8" CYD, a CardKB, a trackball, rotary encoder, micro-OLED, and ribbon OLED compete for faceplate surface area. An A5 faceplate is 148 x 210 mm, leaving ~310 cm² of surface area.)
> A:

### F-04.06 · re 4.10 · reason: vague
*You said:* "truly important notifications!! like a call... but can it even receive calls right now?"
**Q: What specific system conditions should trigger the buzzer alert?**
(E.g., battery critical <5%, earlyoom process kill, root SSH login, or timer alarm?)
> A:

### F-04.07 · re 4.11 · reason: vague
*You said:* "lots of switches!!! lots of tactility!!! dont know where to use it tho :C"
**Q: What are the top two hardware switch functions you want physically wired on the chassis?**
(E.g., hard power cut, radio kill/airplane mode, audio/buzzer mute, or display backlight cut?)
> A:
