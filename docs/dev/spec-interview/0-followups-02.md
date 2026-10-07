### F-02.01 · re 2.02 · reason: vague
*You said:* "I am commuting... I connect my phone to the Cyberdeck and stream my downloaded songs from there"
**Q: How does your phone connect to the deck to stream music?**
(The Zero 2W's Wi-Fi is occupied acting as a client or AP, and Bluetooth A2DP audio sinking is notoriously CPU-heavy. Are you hosting a local icecast/mpd server over Wi-Fi AP, or a USB tether?)
> A:

### F-02.02 · re 2.06 · reason: physics-check
*You said:* "might be able to use discord bot with a custom discord client... that Agents will develop."
**Q: Are you aware that Discord actively bans accounts and IPs operating self-bots or 3rd-party clients?**
(Discord's TOS explicitly bans 3rd-party text mode clients (like `cordless`) and self-botting on user accounts. Is an official web-hook based channel poster enough, or do you accept the ban risk?)
> A:

### F-02.03 · re 2.11 · reason: unstated-tradeoff
*You said:* "Yes, sure sureee!!!"
**Q: Does the audio requirement mean 11.5 KB/s UART terminal text should take priority over audio processing, or can the terminal freeze/stutter while decoding MP3s?**
(The single core Pi Zero 2W is already pinned maintaining the terminal bridge. Adding ALSA/PulseAudio to decode music over the USB-C adapter will steal CPU cycles and power from the 1.5A budget).
> A:

### F-02.04 · re 2.17 · reason: physics-check
*You said:* "Yea, sure!!"
**Q: How do you plan to play games at 150 KB per frame over a 11.5 KB/s serial UART link?**
(The Pi sits behind the ESP32. The ESP32 clears text fine, but pumping raw framebuffers for retro games across UART would result in less than 0.1 frames per second. Does this mean text-based games only (like zork or nethack)?)
> A:
