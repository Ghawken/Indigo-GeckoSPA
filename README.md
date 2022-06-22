# inTouch Gecko Spa indigoPlugin

![](https://github.com/Ghawken/Indigo-GeckoSPA/blob/master/geckoSpa.indigoPlugin/Resources/icon.png?raw=true)

This is a Indigo plugin for all Gecko Spa Controllers. (intouch 2 Wifi controllers)

[https://geckointouch.com/](https://geckointouch.com)

It allows creation of a Spa master device, and all accessory devices (pumps, blowers, lights) and control, triggering based on these values.

It is made possible by the python3 Geckolib here: http://github.com/gazoodle

Steps:

1. Install indigoplugin Bundle
2. Create Indigo new Device - Gecko Spa Main Spa Device:
   1. Wait for Plugin to find and connect to your Spa.....
   2. Wait until successfully connected - then click edit devices and create Devices..
      
      ![](https://github.com/Ghawken/Indigo-GeckoSPA/blob/master/geckoSpa.indigoPlugin/Resources/MainDeviceEdit.png?raw=true)
      
      Plugin will create all Pumps/lights/Blowers/and Eco_mode switch in same Folder as Main Spa Device.
      
      ![](https://github.com/Ghawken/Indigo-GeckoSPA/blob/master/geckoSpa.indigoPlugin/Resources/SpaDevices.png?raw=true)

Control Spa items.. On/Off usual triggers

The Main Spa Device has a number, quite a number of states it reports.  Most are updated every 60 seconds or so.
(Temperature units... mmm.. not sure ... hopefully these change with your spa settings...)

![](https://github.com/Ghawken/Indigo-GeckoSPA/blob/master/geckoSpa.indigoPlugin/Resources/MainStates.png?raw=true)

There are a number of Raw States that the plugin reports - these are added to as received, some may be of use...

## Actions:

A number of Actions are possible including Setting temperature and changing Water Care Modes..
![](https://github.com/Ghawken/Indigo-GeckoSPA/blob/master/geckoSpa.indigoPlugin/Resources/Actions.png?raw=true)

## Issues:

Only 1 Spa in total can be controlled with the approach I have taken.  *Didn't think there would be too many households with x2 spas....*
May be able to refactor - but asyncio adds a few complexities would rather avoid.You can create more than one Main Spa Device - but will only connect to first spa found.


Device controls:
On / Off - at times there can be a refusal to action the command.  This means very occasionally your device won't turn on as expected. (😕 )
The device state will quickly reflect the actual devices states and you will need to try again.  (I may be able to fine tune this further - but is fairly infrequent)



