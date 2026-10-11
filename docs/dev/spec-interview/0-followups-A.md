### F-A.01 · re A.02 · reason: vague
*You said:* "Configureable everything. From color themes, font family and style..."
**Q: If I handed you this fully customized deck tomorrow, what is the *primary* thing you'd do with it?**
(Customizability is a trait, not a capability. Choose: read offline, SSH/pentest, code locally, run agents?)
> A: Change the color scheme! Oh, right... the question is asking me if the spec should start with user capabilities instead of the hardware contracts. In which case, sure! Having a massive offline repository of articles for reading Wikipedia articles on the go, as well as having an offline repository of Python, Bash manuals and whatnot. I should be able to code locally in it as well, albeit the spec should state that the user is massively limited by a small screen and  

### F-A.02 · re A.03 · reason: physics-check
*You said:* "dev-time only."
**Q: Should the deck's terminal runtime include basic local auto-completion and syntax highlighting, or strictly act as a dumb serial pipe?**
(A dev-time-only agent implies the deck operates completely autonomously without an LLM when deployed, acting simply as a programmable sysadmin terminal. Does the terminal runtime need local completion/linting at all?)
> A: No LLM at the deck AT ALL due to memory constraints.

### F-A.03 · re A.07 · reason: missing-number
*You said:* "Size should be ideally less than A5."
**Q: What is your absolute hard maximum bounding box limit (Length x Width x Height in mm) when fully assembled?**
(A5 is 148 x 210 mm, but your acrylic plate BOM says 203 x 203 mm, which is wider than A5. Does it need to fit a specific bag?)
> A: Less than A5 size. Thickness is unspecified, but must be as thin as can be without compromising on features.

### F-A.04 · re A.09 · reason: unstated-tradeoff
*You said:* "Developer can add RTC module if need be. Developer has one on hand."
**Q: Should we add the DS3231 RTC module to the spec now, or wait until log/TLS timestamps drift in the field?**
(Adding an RTC now uses I2C bus pins and physical space in the case, but fixes TLS/git sync issues when off-grid.)
> A: I can easily add one and fit it in there. The cyberdeck has too much nooks and crannies to add it to.

### F-A.05 · re A.13 · reason: physics-check
*You said:* "Power is unconnected. OTG to the hub. Remove OTG, and connect RPI directly to programmer PC..."
**Q: Are you okay with the deck losing all its storage (SSD) and networking (LTE) while plugged into a PC for debugging?**
(OTG to hub feeds both the hub and powers the SSD/Modem. If you unplug the hub to connect to a PC via OTG, the PC powers the Pi but the hub is disconnected, meaning you lose the SSD and modem.)
> A: Of course not! But how would I debug the Raspberry Pi when I cannot connect it to the internet? UART to USB?!?!?!?! absurd! Literally primitive technology. Anyways, maybe we can resort to that if it really comes to that... But yeah, the only use case for that is when I am in a new network, and I need to connect it to the Wi-Fi, since I don't know how to make it connect to the new network LMFAOOOOO.

