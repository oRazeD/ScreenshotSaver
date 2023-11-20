![scrshot_saver_plus](https://user-images.githubusercontent.com/31065180/167504126-4ea81863-f93c-4481-9f52-a67bce1ac62e.png)

# ScreenshotSaver Introduction
ScreenshotSaver is a Blender 3.0+ tool for easily rendering high-quality viewport screenshots of your WIPs without any of the setup hassle and with more reliability overall.

# Feature Set
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

Below is an example clip of a Cryobed model I worked on for a private project.

https://github.com/oRazeD/ScreenshotSaver/assets/31065180/5bb05faa-1e75-4622-8149-42ffaa06f3ed

# Installation Guide
1. Click the **Code** button in the top right of the repo & click **Download ZIP** in the dropdown (Do not unpack the ZIP file)
2. Follow this video for the rest of the simple instructions

This video guide is for a different project, but the same principles apply.

https://user-images.githubusercontent.com/31065180/137642217-d51470d3-a243-438f-8c49-1e367a8972ab.mp4

# Known Issues

- In some very specific cases, GIF may fail to encode JPEGs due to an internal FFMPEG error. Sometimes finding and removing the bad image fixes this.
