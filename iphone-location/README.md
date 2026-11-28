# iPhone Location Changer

A desktop app that changes your iPhone's GPS location. Maps, **Find My**, Weather and every
other app on the phone see the location you pick. Includes teleport, walk/drive along a route,
place search and saved places.

It runs on your computer (Windows, Mac or Linux) and controls the iPhone over USB, using
Apple's developer location simulation (the same feature Xcode uses). No jailbreak needed.

## Setup (once)

1. Install **Python 3.10+** from python.org (on Windows tick "Add Python to PATH").
2. **Windows only:** install **Apple Devices** (or iTunes) from the Microsoft Store so the PC can
   talk to the iPhone. **Linux:** `sudo apt install usbmuxd`.
3. Plug in the iPhone with a cable, unlock it and tap **Trust This Computer**.
4. Start the app:
   - Windows: double-click `start-windows.bat`
   - Mac/Linux: `./start-mac-linux.sh`

   Your browser opens at http://127.0.0.1:8765.
5. Click **Prepare iPhone**. The first time, it tells you to turn on
   **Settings → Privacy & Security → Developer Mode** and restart the phone. After the restart
   click **Prepare iPhone** again. It mounts Apple's developer image (download on the first run).

## Use

- **Teleport:** search a place (or paste `lat, lon`, or click the map), then press
  **Set this location on iPhone**.
- **Walk / Drive:** click several points on the map, pick a speed, press **Start moving**.
- **Stop · Use real GPS** puts the phone back on its real location.
- **★ Save current pin** keeps places you use often.

## Find My

Find My on the iPhone reports whatever location the phone reports, so friends and family
see the location you set. Give it a few minutes to update. To keep it there:

- keep the iPhone **connected** and the app **running** (on iOS 17+ the fake location ends when
  the connection closes);
- closing the app or unplugging the phone brings back the real location.

## Troubleshooting

| Problem | Fix |
|---|---|
| "No iPhone found" | Use a data cable, unlock the phone, tap Trust, press Refresh. Windows: install Apple Devices. |
| Developer Mode toggle missing | Press **Prepare iPhone**, then look again under Privacy & Security. |
| "image"/"mount" error | Press **Prepare iPhone** (needs internet the first time). |
| Status shows "iPhone disconnected" | Cable came loose or the phone was asleep too long: press Set again. |

Built on [pymobiledevice3](https://github.com/doronz88/pymobiledevice3).
