"""Render the original Bug Tracker icon; Pillow is a build-time dependency."""
from pathlib import Path
from PIL import Image, ImageDraw

size = 1024
image = Image.new('RGBA', (size, size), (15, 23, 42, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((42, 42, 982, 982), radius=180, fill='#17263f', outline='#334b68', width=8)
teal, amber = '#46ddc0', '#ffbd59'
for y in (370, 480, 590):
    draw.line([(360, y), (235, y - 50), (190, y - 105)], fill=teal, width=32)
    draw.line([(655, y), (780, y - 50), (825, y - 105)], fill=teal, width=32)
draw.line([(450, 285), (390, 205)], fill=teal, width=25)
draw.line([(565, 285), (625, 205)], fill=teal, width=25)
draw.ellipse((398, 245, 618, 425), fill=teal)
draw.rounded_rectangle((350, 340, 665, 690), radius=155, fill=teal)
draw.line([(510, 360), (510, 650)], fill='#17263f', width=15)
draw.ellipse((620, 475, 875, 730), fill='#17263f', outline=amber, width=30)
draw.line([(835, 695), (918, 780)], fill=amber, width=38)
draw.line([(135, 820), (270, 820), (310, 755), (355, 875), (410, 795), (460, 820), (760, 820)],
          fill='#8fa9c5', width=14)
image = image.resize((512, 512), Image.Resampling.LANCZOS)
output = Path(__file__).with_name('icon.png')
image.save(output)
print(output)
