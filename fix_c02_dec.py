with open("docs/dev/ai-decisions.md", 'r') as f:
    text = f.read()

# Make sure DEC-W15 records the physical impossibility of B
# "How would (b) work? It is already what I am doing right now. How do you think I will be able to connect the device to the programmer PC if the device is already acting as a host? (c) it is then..."
text = text.replace("Since separating the OTG hub destroys the running BTRFS mount.",
                    "Since USB Gadget mode conflicts with USB Host mode (needed for the OTG hub), and a powered hub doesn't solve the host/gadget pin negotiation. Separation destroys the running BTRFS mount.")
with open("docs/dev/ai-decisions.md", 'w') as f:
    f.write(text)

