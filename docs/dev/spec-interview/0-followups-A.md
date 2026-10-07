# Follow-ups for Section A

F-A.01 (parent: A.02)
> A: Configureable everything. From color themes, font family and style, terminal size, and splash screen, everything should be customizeable.
Why: Vague user-facing capabilities limit. Customizability is a trait, not a capability. If I hand you this customized deck, what do you DO with it? (e.g. read Wikipedia offline, SSH into servers, take notes, scan networks).
> A: 

F-A.02 (parent: A.03)
> A: dev-time only.
Why: Physics check. A dev-time agent implies the deck operates completely autonomously without an LLM when deployed, acting simply as a programmable sysadmin terminal. Does the terminal runtime need local completion/linting at all?
> A: 

F-A.03 (parent: A.07)
> A: Size should be ideally less than A5.
Why: Missing number. A5 is 148 x 210 mm. Can you give a hard maximum bounding box (L x W x H in mm) that it must fit inside when fully assembled (e.g., to fit in a specific bag or pocket)?
> A: 

F-A.04 (parent: A.09)
> A: Developer can add RTC module if need be. Developer has one on hand.
Why: Unstated tradeoff. Adding an RTC takes up I2C bus pins and physical space, and requires systemd-timesyncd configuration to read from it. Should we add the `DS3231` RTC to the wiring spec now, or wait until log timestamps drift too much in the field?
> A: 
