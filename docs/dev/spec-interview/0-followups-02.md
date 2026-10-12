### F-02.01 · re 2.02 · reason: vague
*You said:* "I am commuting... I connect my phone to the Cyberdeck and stream my downloaded songs from there"
**Q: How does your phone connect to the deck to stream music?**
(The Zero 2W's Wi-Fi is occupied acting as a client or AP, and Bluetooth A2DP audio sinking is notoriously CPU-heavy. Are you hosting a local icecast/mpd server over Wi-Fi AP, or a USB tether?)
> A: the cyberdeck connects to my phone via my phone's hotspot. after which, the cyberdeck's services is now available to be accessed in my phone. maybe its just a simple SMB... in any case, the SMB is only activated in trusted networks, not in public Wi-Fi, where it can be sniffed by other people... unless said connection is going thru netbird, in which case, its allowed :3 :3 :3 in any case, a music player will play from the SMB connection. hmm... NFS can also work :3 whatever can be mounted in an android phone with an external app... SAYYYY!!! what if we make an android app for connecting to the cyberdeck, which manages the cyberdeck, can program it from the get go, connect to its services and mount its shit like SMB so that it can stream music from my cyberdeck to my phone... using [expo.dev](http://expo.dev) :3 :3 :3

### F-02.02 · re 2.06 · reason: physics-check
*You said:* "might be able to use discord bot with a custom discord client... that Agents will develop."
**Q: Are you aware that Discord actively bans accounts and IPs operating self-bots or 3rd-party clients?**
(Discord's TOS explicitly bans 3rd-party text mode clients (like `cordless`) and self-botting on user accounts. Is an official web-hook based channel poster enough, or do you accept the ban risk?)
> A: oh no no... not that... i just need to talk with my gf, and if i use an actual discord bot, with legitimate bot tokens, just to talk to my gf, then its fine, isnt it??? i can also interact with my server which i administrate and own myself. it wouldnt be against TOS, right?!!?!

### F-02.03 · re 2.11 · reason: unstated-tradeoff
*You said:* "Yes, sure sureee!!!"
**Q: Does the audio requirement mean 11.5 KB/s UART terminal text should take priority over audio processing, or can the terminal freeze/stutter while decoding MP3s?**
(The single core Pi Zero 2W is already pinned maintaining the terminal bridge. Adding ALSA/PulseAudio to decode music over the USB-C adapter will steal CPU cycles and power from the 1.5A budget).
> A: oh wait... the UART is thru USB from the USB hub... will that eat a lot of bandwidth tho... is there a lighter solution for this that can use the usb hub to play music with my USB C IEMs with a DSP, which is then connected to the USB hub with a USB C female to USB A male adapter... is there a way around that??

### F-02.04 · re 2.17 · reason: physics-check
*You said:* "Yea, sure!!"
**Q: How do you plan to play games at 150 KB per frame over a 11.5 KB/s serial UART link?**
(The Pi sits behind the ESP32. The ESP32 clears text fine, but pumping raw framebuffers for retro games across UART would result in less than 0.1 frames per second. Does this mean text-based games only (like zork or nethack)?)
> A: i was thinking more like snake... or a man pushing boxes around stone obstacles, in order to push all of the boxes in a narrow space... hmm... like those very old fashioned games in those cheapo knockoff of a knockoff of a gameboy that u can buy in 2010s PH palengkes of which, there are lots of arcade games!!!