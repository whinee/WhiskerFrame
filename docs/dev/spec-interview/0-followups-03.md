### F-03.01 · re 3.03 · reason: vague
*You said:* "2 hours, side-to-side seating. Theft can be circumvented by having"
**Q: How will theft risk on transit be circumvented?**
(Your sentence cut off mid-thought. E.g., wrist lanyard/tether, low-profile carrying sleeve, or discreet chassis appearance?)
> A:

### F-03.02 · re 3.05 · reason: physics-check
*You said:* "Fanless operation, should be able to resist rain,"
**Q: Will you accept thermal throttling during sustained workloads, or add an external aluminum heatsink plate?**
(Pi Zero 2W draws ~2.0W at quad-core load; SSD draws ~1.5W; UPS DC-DC converter dissipates ~0.8W. Total internal heat is ~4.3W in a sealed box. In 35°C Philippine ambient with no airflow, internal air will exceed 75°C and throttle the SoC at 80°C.)
> A:

### F-03.03 · re 3.06 · reason: physics-check
*You said:* "Put the brightness of the screen at 100% by default, and change its contrast"
**Q: In outdoor sunlight, do you accept washed-out display visibility or require an inverted high-contrast mono theme?**
(The CYD's ILI9341 backlight outputs ~350 nits max. Tropical daylight is 10,000–30,000 lux indirect to 100,000 lux direct. Software contrast adjustment cannot boost LED nit output past 350 nits, which is physically washed out under direct sun.)
> A:

### F-03.04 · re 3.08 · reason: unstated-tradeoff
*You said:* "buzzer is acceptable, as long as there is a hardware/software toggle to turn it"
**Q: Should the silence profile toggle be a physical hardware switch or a software keyboard shortcut?**
(A physical toggle switch requires GPIO wiring and a case cutout, but guarantees silence before booting in a quiet classroom or library.)
> A:

### F-03.05 · re 3.10 · reason: unstated-tradeoff
*You said:* "ALL OF THEM!!!"
**Q: How should captive portals (requiring browser clicks/logins) be handled on a text-only terminal?**
(802.1X enterprise and WPA2-PSK work headless via iwd. Captive portals at cafes require executing JS or manual login redirects through w3m/lynx or curl scripts.)
> A:

### F-03.06 · re 3.11 · reason: physics-check
*You said:* "about 3 days should be fine :3"
**Q: Does 3-day offline tolerance mean running continuously for 72 hours on battery, or sleeping between uses?**
(3x 18650 cells = ~35Wh total energy. Pi Zero 2W + CYD + SSD idle draw is ~1.8W minimum: 35Wh / 1.8W = ~19.4 hours continuous battery life. Reaching 72 hours requires deep sleep / poweroff between sessions or recharging from wall/powerbank.)
> A:
