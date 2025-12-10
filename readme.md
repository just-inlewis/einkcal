## EinkCal Setup
1. Raspberry Pi Zero 2 Setup (32-bit)
2. **Enable SPI:** Open a terminal and run the following command to launch the Raspberry Pi Software Configuration Tool:

    ```sh
    sudo raspi-config
    ```

    Navigate to `Interfacing Options > SPI` and enable SPI.

3. **Enable Network at Boot:** Navigate to `System Options > Network at Boot` and enable network connectivity at boot.

4. **Install PiSugar:**
    ```sh
    wget https://cdn.pisugar.com/release/pisugar-power-manager.sh
    bash pisugar-power-manager.sh -c release
    ```

5. **Install Python3 and Dependencies:**
    ```sh
    sudo apt-get update
    sudo apt-get install git
    sudo apt-get install wkhtmltopdf
    sudo apt-get install python3-pip
    sudo apt-get install python3-tz
    sudo apt-get install python3-icalendar
    sudo apt-get install python3-recurring-ical-events
    sudo apt-get install python3-flask

    sudo apt-get install python3-rpi-lgpio # (Zero 2+)
    sudo apt-get install python3-rpi.gpio
    
    sudo python3 -m pip install --break-system-packages pisugar
    ```
    If `wiringpi` fails, try:
    ```sh
    git clone https://github.com/WiringPi/WiringPi
    cd WiringPi
    ./build
    gpio -v
    ```

6. **Clone einkcal and Install Dependencies:**
    ```sh
    git clone https://github.com/just-inlewis/einkcal.git
    ```

7. **Install Service to Run Calendar Script on Launch:**
    a) Create a systemd service to run the script on launch:
    ```sh
    sudo nano /lib/systemd/system/einkcal.service
    ```

    b) Add the following service details:
    ```ini
    [Unit]
    Description=einkcal
    After=multi-user.target network-online.target systemd-time-wait-sync.service
    Wants=network-online.target systemd-time-wait-sync.service
    
    [Service]
    Type=idle
    User=calendar
    WorkingDirectory=/home/calendar/einkcal/
    ExecStart=/usr/bin/python3 /home/calendar/einkcal/main.py
    StandardOutput=syslog
    StandardError=syslog
    SyslogIdentifier=einkcal
    
    [Install]
    WantedBy=multi-user.target
    ```

    c) Set the correct permissions and reload systemd:
    ```sh
    sudo chmod 644 /lib/systemd/system/einkcal.service
    sudo systemctl daemon-reload
    sudo systemctl enable einkcal.service
    ```


8. **Install Service to Run WiFi Script on Launch:**
    a) Create a systemd service to run the script on launch:
    ```sh
    sudo nano /lib/systemd/system/wifi.service
    ```

    b) Add the following service details:
    ```ini
    [Unit]
    Description=einkcal config
    After=network.target
    
    [Service]
    ExecStart=/usr/bin/python3 /home/calendar/einkcal/wifi.py
    WorkingDirectory=/home/calendar
    StandardOutput=inherit
    StandardError=inherit
    Restart=always
    User=root
    
    [Install]
    WantedBy=multi-user.target
    ```

    c) Set the correct permissions and reload systemd:
    ```sh
    sudo chmod 644 /lib/systemd/system/wifi.service
    sudo systemctl daemon-reload
    sudo systemctl enable wifi.service
    ```

9. **Schedule wakeups:**
    ```sh
    http://calendar.local
    http://x.x.x.x:8421
    ```
    Set Schedule Wake Up to 00:30 and Safe Shutdown to <= 10%
    
10. **Reboot:**
    After completing the steps above, reboot the Raspberry Pi Zero 2:
    ```sh
    sudo reboot
    ```
