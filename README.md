![scrshot_saver_plus](https://user-images.githubusercontent.com/31065180/167504126-4ea81863-f93c-4481-9f52-a67bce1ac62e.png)


# ScreenshotSaver Introduction
ScreenshotSaver is a Blender tool for easily rendering screenshots of your WIPs without the manual setup hassle. 


# Feature Set

![screenshot_1_0003](https://user-images.githubusercontent.com/31065180/167505799-8a3fa5e0-e5e9-4f5e-b917-51c100a6c030.gif)
<p align="center">
    <em>Quick example gif I put together using purely Screenshot Saver, will replace with a more final piece later on</em>
</p>

<br />

- Efficiently add and manipulate screenshot cameras
    - Per camera resolution control
    - Per camera custom Workbench & EEVEE shading setups
    - Per camera specific frame rendering
    - Copy camera settings between different screenshot items
    - Quick preview & selection toggles for each screenshot camera
- Screenshots respect render visibility
- Take screenshots in EXR, PNG, or JPEG
- Automatic folder creation for neat, reliable and organized file structure
- Option to automatically render screenshots on file save for a hands-off approach to collecting progress shots
- Built-in FFMPEG encoding support to convert your screenshots into an MP4 or GIF in one click!
  - Set a framerate to control the playback speed  
  - Add buffer frames at the start/end to "hold" on results
  - Downscale encoded GIFs for smaller sizes to accomodate web uses
  - Automatically converts EXRs to the sRGB color space
- ...And more!


# Installation Guide

1. Click the **Code** button in the top right of the repo & click **Download ZIP** in the dropdown (Do not unpack the ZIP file)
2. Follow this video for the rest of the simple instructions

https://user-images.githubusercontent.com/31065180/137642217-d51470d3-a243-438f-8c49-1e367a8972ab.mp4


# TODO / Future Update Paths

- [ ] Support more image formats
- [ ] Support animation rendering (will likely be very slow, maybe out of scope)


# Known Issues

- In some very specific cases, GIF may fail to encode JPEGs due to an internal FFMPEG error. Sometimes finding and removing the "bad" image fixes this.
