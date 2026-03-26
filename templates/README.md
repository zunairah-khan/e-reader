# Overview
Custom e-reader built with a Raspberry Pi Zero 2W and Waveshare 5.83" e-ink display.

## Features
- E-ink display 
- WiFi book upload via browser interface
- Saves reading progress automatically
- Physical button controls


## Hardware
- Raspberry Pi Zero 2W
- Waveshare 5.83" e-ink HAT V2
- PiSugar 3 Plus battery board
- 4x tactile buttons

## Setup
Clone the repo and install dependencies:
```bash
pip install -r requirements.txt
```

## Usage
- Connect to the same WiFi as the device
- Visit `http://[device-ip]:5000` in your browser to upload EPUB files
- Use buttons to navigate: Prev / Next / Menu / Back

## Status
WIP — hardware not yet arrived.