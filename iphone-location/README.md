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

## Control it from your iPhone

You can run the app from the iPhone itself, with no need to touch the computer after setup:

1. Keep the computer on and the app running, with the iPhone **plugged into it** and both on the same Wi-Fi.
2. On the computer page, find **📱 Control from your iPhone** and scan the QR code with the iPhone camera.
3. In Safari tap **Share → Add to Home Screen**. You now have a "Location" app icon that opens
   full screen.

The link contains a secret key, so other people on your Wi-Fi can't use it. Keep it private.
To get a new key, delete `access_key.txt` and restart the app.
Start with `python app.py --local-only` if you don't want it reachable over Wi-Fi.

> Why the computer is still needed: Apple doesn't let any iPhone app (App Store or sideloaded)
> change the system GPS without a jailbreak. The computer does the actual change through
> Apple's developer tools; the iPhone is just the remote control.

## Phone-only mode (no computer afterwards)

Community apps can change the location from the iPhone itself, with no computer, by using
a loopback VPN (**LocalDevVPN**) plus a **pairing file**. Examples:
[Locus](https://github.com/Drj0/Locus) and [WaypointApp](https://github.com/ykondury/WaypointApp).
They are third-party projects that weren't checked as part of this app, so review them before you trust them.

This app makes the pairing file for you:

1. Connect the iPhone, select it, and click **🔑 Create pairing file** (tap Trust on the phone if asked).
   This also enables Wi-Fi connections for that pairing, which those apps need.
2. Get the `.plist` file onto the iPhone: AirDrop it (Mac), save it to iCloud Drive, or click the
   button from the iPhone remote page so it downloads straight into **Files → Downloads**.
3. Install LocalDevVPN and the location app (via SideStore), turn on the VPN, and import the
   pairing file in the location app.

**Keep the pairing file private.** Anyone who has it can fully access your iPhone. If it leaks,
reset trust on the iPhone: Settings → General → Transfer or Reset iPhone → Reset → Reset Location & Privacy.

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
