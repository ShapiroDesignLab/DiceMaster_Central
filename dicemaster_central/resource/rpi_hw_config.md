# Raspberry Pi Hardware Configuration

## Ubuntu 22.04 Compatible Setup

**Note:** Ubuntu 22.04 for Raspberry Pi has limited overlay support compared to Raspberry Pi OS. The custom overlays (`spi3-2cs`, `spi6-2cs`, `i2c6`) are not available by default.

## Setup Instructions
0. Use raspi-flavor kernel modules because Ubuntu has issues with HW interfaces with generic kernel modules.
```bash
sudo apt install linux-raspi linux-modules-extra-raspi
sudo reboot
```

1. **Edit the config file:**
   ```bash
   sudo nano /boot/firmware/usercfg.txt   # Ubuntu 22.04 uses this file
   ```

2. **Add the configuration section below** at the end of the file

3. **Save and reboot:**
   ```bash
   sudo reboot
   ```

4. **Verify the buses are available:**
   ```bash
   ls /dev/i2c-1
   ls /dev/spidev0.*
   ```

Expected output for Ubuntu 22.04:
```
/dev/i2c-1
/dev/spidev0.0  /dev/spidev0.1
```

## Pin Reference Table (Ubuntu 22.04 Compatible)

| Bus   | Pins Used                        | GPIO Pins      | Physical Pins    | Device Files           |
|-------|----------------------------------|----------------|------------------|------------------------|
| I²C-1 | SDA=2, SCL=3                    | GPIO 2/3       | 3/5              | /dev/i2c-1             |
| SPI-0 | MISO=9, MOSI=10, SCLK=11, CS=7,8| GPIO 7-11      | 26-23-21-19-24   | /dev/spidev0.{0,1}     |

## Ubuntu 22.04 Configuration

```bash
############################################################
#  Extra I2C + three SPI buses (Ubuntu 22.04 Pi)
############################################################

# ---------- I2C -------------------------------------------------
# Create I²C-6 on GPIO 22/23 (pins 15/16)
dtoverlay=i2c6,pins_22_23         # → /dev/i2c-6  (BCM2711 only)   [oai_citation:4‡forums.raspberrypi.com](https://forums.raspberrypi.com/viewtopic.php?t=348458&utm_source=chatgpt.com)
dtparam=i2c_arm=off               # Disable the old I²C-1 so pins 2/3 become free

# ---------- SPI -------------------------------------------------
# 1) Classic SPI-0 (2 CS) on pins 7-11
dtparam=spi=on                    # → /dev/spidev0.0  /dev/spidev0.1   [oai_citation:5‡raspberrypi.com](https://www.raspberrypi.com/documentation/computers/config_txt.html?utm_source=chatgpt.com)

# 2) SPI-3 with two chip-selects
#    MISO=1 MOSI=2 SCLK=3  CE0=0  CE1=24
dtoverlay=spi3-2cs,cs1_pin=24     # → /dev/spidev3.{0,1}   [oai_citation:6‡raw.githubusercontent.com](https://raw.githubusercontent.com/raspberrypi/firmware/master/boot/overlays/README?utm_source=chatgpt.com)

# 3) SPI-6 with two chip-selects
#    MISO=19 MOSI=20 SCLK=21  CE0=18  CE1=27
dtoverlay=spi6-2cs,cs0_pin=18,cs1_pin=27  # → /dev/spidev6.{0,1}   [oai_citation:7‡raw.githubusercontent.com](https://raw.githubusercontent.com/raspberrypi/firmware/master/boot/overlays/README?utm_source=chatgpt.com)
```

## Troubleshooting

If buses don't appear after reboot:
1. Check `/boot/config.txt` for syntax errors
2. Verify no conflicting overlays are enabled
3. Check `dmesg | grep spi` and `dmesg | grep i2c` for error messages
4. Ensure your Pi model supports these overlays (Pi 4/5 recommended)