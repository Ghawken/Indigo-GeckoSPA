#! /usr/bin/env python2.6
# -*- coding: utf-8 -*-

"""
Gecko Spa Plugin
"""

import time as t
import datetime
import sys
import logging
import asyncio
from geckolib import GeckoAsyncSpaMan, GeckoSpaEvent, GeckoConstants
from geckolib.spa_state import GeckoSpaState
from config import Config
import threading
import builtins
from threading import Thread

try:
    import indigo
except:
    pass
# Pycharm debugging
try:
    import pydevd_pycharm
    pydevd_pycharm.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
except:
    pass
# Replace with your own UUID, see https://www.uuidgenerator.net/>
CLIENT_ID = "a2d936db-1123-eaed-82bc-b4225fa99739"
# Replace with your spa IP address if on a sub-net
SPA_ADDRESS = None

_LOGGER = logging.getLogger("Plugin.SpaMan")

class pluginSpa(GeckoAsyncSpaMan, Thread):
    """Sample spa man implementation"""
    def __init__(self, plugin):
        _LOGGER.debug("PluginSpa Class init called")
        threading.Thread.__init__(self)
        GeckoAsyncSpaMan.__init__(self, CLIENT_ID)
        self.plugin = plugin
        self._config = Config()
        self._can_use_facade = False
        self._last_update = t.monotonic()
        self._last_char = None
        self._commands = {}
        self.spa_thread = None
        self._watching_ping_sensor = False
        self.this_spa_is_alive = False
        self.loop = asyncio.new_event_loop()

    def run(self):
        _LOGGER.debug("Thread Running..")
        asyncio.set_event_loop(self.loop)
        asyncio.run(self.thread_connect())
        #self.thread_runforever()

    # def establish_connection(self):
    #     _LOGGER.info("Looking for spas on your network ...")
    #     _LOGGER.info('Nmber of Active Threads:' + str(threading.activeCount()))
    #     self.spa_thread = threading.Thread(target=self.thread_runforever, daemon=True)
    #     self.spa_thread.start()

    def thread_runforever(self):
        asyncio.run( self.thread_connect() )

    # async def thread_async(self, plugin):
    #      async with pluginSpa(plugin):
    #          await asyncio.sleep(GeckoConstants.ASYNCIO_SLEEP_TIMEOUT_FOR_YIELD)

    async def thread_connect(self):
        try:
            _LOGGER.debug("thread Connecting running")
            await GeckoAsyncSpaMan.__aenter__(self)
            #self.add_task(self._timer_loop(), "Timer", "SpaMan")
            await self.async_set_spa_info(
                self._config.spa_address, self._config.spa_id, self._config.spa_name
            )
            await self.wait_for_descriptors()
            if len(self.spa_descriptors) == 0:
                _LOGGER.info("**** There were no spas found on your network.")
                return False
            #self.plugin.spa_descriptors = self.spa_descriptors
            spa_descriptor = self.spa_descriptors[0]
            _LOGGER.info(f"Connecting to {spa_descriptor.name} at {spa_descriptor.ipaddress} ...")

            await self.async_set_spa_info(
                spa_descriptor.ipaddress,
                spa_descriptor.identifier_as_string,
                spa_descriptor.name,
            )
            # Wait for the facade to be ready
            await self.wait_for_facade()
            _LOGGER.info(f"Connected to {spa_descriptor.name}.")

            while True:
                await asyncio.sleep(5)
                #_LOGGER.debug(f"Thread reporting Spa state:{self.spa_state}")

        except:
            _LOGGER.exception("Exception")
        #self.logger.info(f"End of Connection:\n {spaman.facade.water_heater}")

    async def _select_next_watercare_mode(self) -> None:
        new_mode = (self.facade.water_care.active_mode + 1) % len(
            GeckoConstants.WATERCARE_MODE
        )
        await self.facade.water_care.async_set_mode(new_mode)

    async def increase_temp(self):
       self.facade.water_heater.set_target_temperature(
            self.facade.water_heater.target_temperature + 0.5
        )

    async def decrease_temp(self):
        self.facade.water_heater.set_target_temperature(
            self.facade.water_heater.target_temperature - 0.5
        )

    async def set_temp(self, temperature):
        self.facade.water_heater.set_target_temperature(
           temperature
        )

    async def spaAction(self, device, devicenumber,  action):
        ## move here to hopefully fix wreong event loop issue
        try:
            if device == "blower":
                if action=="ON":
                    self.facade.blowers[devicenumber].turn_on()
                    _LOGGER.info(f"Spa {device}, number {devicenumber+1} successfully turned on.")
                elif action == "OFF":
                    self.facade.blowers[devicenumber].turn_off()
                    _LOGGER.info(f"Spa {device}, number {devicenumber+1} successfully turned off.")
            elif device == "pump":
                    self.facade.pumps[devicenumber].set_mode(str(action))
                    _LOGGER.info(f"Spa {device}, number {devicenumber+1} set to {action}.")
            elif device == "light":
                if action=="ON":
                    self.facade.lights[devicenumber].turn_on()
                    _LOGGER.info(f"Spa {device}, number {devicenumber+1} successfully turned on.")
                elif action == "OFF":
                    self.facade.lights[devicenumber].turn_off()
                    _LOGGER.info(f"Spa {device}, number {devicenumber+1} successfully turned off.")
            elif device == "eco":
                if action=="ON":
                    self.facade.eco_mode.turn_on()
                    _LOGGER.info(f"{devicenumber} successfully turned on.")

                elif action == "OFF":
                    self.facade.eco_mode.turn_off()
                    _LOGGER.info(f"{devicenumber} successfully turned off.")
            return True

        except:
            _LOGGER.info("Error running command",exc_info=True)
            _LOGGER.debug("Exception in spa Action", exc_info=True)
            return False

    async def handle_event(self, event: GeckoSpaEvent, **kwargs) -> None:
        # Uncomment this line to see events generated
        if event == GeckoSpaEvent.CLIENT_FACADE_IS_READY:
            self._can_use_facade = True
        elif event in (
            GeckoSpaEvent.CLIENT_FACADE_TEARDOWN,
            GeckoSpaState.ERROR_NEEDS_ATTENTION,
        ):
            self._can_use_facade = False
        _LOGGER.debug(f"{event}: {kwargs}")

        pass

    async def __aenter__(self):
        await GeckoAsyncSpaMan.__aenter__(self)
        self.add_task(self._timer_loop(), "Timer", "SpaMan")
        await self.async_set_spa_info(
            self._config.spa_address, self._config.spa_id, self._config.spa_name
        )
        return self

    async def __aexit__(self, *exc_info):
        return await GeckoAsyncSpaMan.__aexit__(self, *exc_info)

    async def _timer_loop(self) -> None:
        while True:
            _LOGGER.debug("Timer Loop Run in SpaMan")
            await asyncio.sleep(1)

    def log_details(self):
        _LOGGER.info(self.facade)
        lines =  []
        lines.append(f"SpaPackStruct.xml revision {self.facade.spa.revision} \n" +
            f"intouch version EN {self.facade.spa.intouch_version_en}\n" +
            f"intouch version CO {self.facade.spa.intouch_version_co}\n" +
            f"Spa pack {self.facade.spa.pack} {self.facade.spa.version}\n" +
            f"Low level configuration # {self.facade.spa.config_number}\n" +
            f"Config version {self.facade.spa.config_version}\n" +
            f"Log version {self.facade.spa.log_version}\n" +
            f"Pack type {self.facade.spa.pack_type}\n" )

        lines.append(f"{self.facade.name} is ready")
        lines.append("")
        lines.append(f"{self.facade.water_heater}")
        for pump in self.facade.pumps:
            lines.append(f"{pump}")
        for blower in self.facade.blowers:
            lines.append(f"{blower}")
        for light in self.facade.lights:
            lines.append(f"{light}")
        for reminder in self.facade.reminders_manager.reminders:
            lines.append(f"{reminder}")
        lines.append(f"{self.facade.water_care}")
        for sensor in [
            *self.facade.sensors,
            *self.facade.binary_sensors,
        ]:
            lines.append(f"{sensor}")
        lines.append(f"{self.facade.eco_mode}")
        for line in lines:
            _LOGGER.info(line)



class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        builtins.status_data = {}
        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)
        try:
            self.logLevel = int(self.pluginPrefs["showDebugLevel"])
        except:
            self.logLevel = logging.DEBUG

        self.logger.debug(u"Initializing Gecko Spa plugin.")

        self.heater_timer = None
        self.myspa = pluginSpa(self)
        self.spa_descriptors = None
        self.spaFacade = None
        self.spa_list = []
        self.timeOutCount = 0
        self.debug = self.pluginPrefs.get('showDebugInfo', False)
        self.debugLevel = self.pluginPrefs.get('showDebugLevel', "1")
        self.deviceNeedsUpdated = ''
        self.prefServerTimeout = int(self.pluginPrefs.get('configMenuServerTimeout', "15"))
        self.configUpdaterInterval = self.pluginPrefs.get('configUpdaterInterval', 24)
        self.configUpdaterForceUpdate = self.pluginPrefs.get('configUpdaterForceUpdate', False)

        self.logger.info("{0:=^130}".format(" Initializing New Plugin Session "))
        self.logger.info("{0:<30} {1}".format("Plugin name:", pluginDisplayName))
        self.logger.info("{0:<30} {1}".format("Plugin version:", pluginVersion))
        self.logger.info("{0:<30} {1}".format("Plugin ID:", pluginId))
        self.logger.info("{0:<30} {1}".format("Indigo version:", indigo.server.version))
        self.logger.info("{0:<30} {1}".format("Python version:", sys.version.replace('\n', '')))
        self.logger.info("{0:<30} {1}".format("Python Directory:", sys.prefix.replace('\n', '')))
        self.logger.info("")
        self.pluginprefDirectory = '{}/Preferences/Plugins/com.GlennNZ.indigoplugin.HomeKitLink-Siri'.format(indigo.server.getInstallFolderPath())

    def validateDeviceConfigUi(self, values_dict, type_id, dev_id):
        return (True, values_dict)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")

        if not userCancelled:
            self.debug = valuesDict.get('showDebugInfo', False)
            self.debugLevel = self.pluginPrefs.get('showDebugLevel', "1")
            self.debugLog(u"User prefs saved.")

            self.debugLog(u"valuesDict: {0} ".format(valuesDict))

        return True

    # Start 'em up.
    def deviceStartComm(self, dev):
        self.debugLog(u"deviceStartComm() method called.  Connecting Spa.")

        dev.stateListOrDisplayStateIdChanged()  # update  from device.xml info if changed

        if dev.model == "Gecko Spa Device" or dev.model =="Gecko Main Spa Device":
            updatedStates = [
                {'key': 'deviceIsOnline', 'value': True},
                {'key': 'deviceStatus', 'value': "Starting Up"},
                {'key': 'Master_Heater', 'value': "OFF" },
                {'key': 'spa_in_use', 'value': False},
                {'key': 'master_heater_timeON', 'value': "unknown"}
             #   {'key': 'master_heater_timeON_timer', 'value': 0},

            ]
            dev.updateStatesOnServer(updatedStates)
            self.connectSpa()

    def createDevices(self, valuesDict, typeId, devId):
        #
        self.logger.info("Create Spa Linked Device Group if not already existing..")
        self.logger.debug(f"{valuesDict}\n  and {typeId}\n  and {devId}\n")

        if self.myspa == None:
            self.logger.info("Not connected.  Cannot create devices.... yet.... ")
            return
        if self.myspa.facade == None:
            self.logger.info("Not connected. Cannot create devices... yet....")
            return
        mainspadevice = indigo.devices[devId]
        newstates = []
        x = 1
        props_dict = dict()
        props_dict["member_of_device_group"] = True
        props_dict["linkedPrimaryIndigoDevice"] = mainspadevice.name

        for pump in self.myspa.facade.pumps:
            props_dict["device_number"] = x-1
            if x == 1:
                newpump = indigo.device.create(indigo.kProtocol.Plugin,
                                               deviceTypeId="geckoSpaPump",
                                               address = mainspadevice.address,
                                               #groupWithDevice=int(mainspadevice.id),
                                               name="Spa Pump "+str(x),
                                               folder=mainspadevice.folderId,
                                               description="Spa Pump",
                                               props = props_dict
                                               )

            else:
                first_device_id = newpump.id
                newpump = indigo.device.create(indigo.kProtocol.Plugin,
                                               deviceTypeId="geckoSpaPump",
                                               address = mainspadevice.address,
                                               groupWithDevice=int(first_device_id),
                                               name="Spa Pump "+str(x),
                                               folder=mainspadevice.folderId,
                                               description="Spa Pump",
                                               props = props_dict
                                               )
            secondary_dev_id = newpump.id
            secondary_dev = indigo.devices[secondary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed
            secondary_dev.subType = indigo.kRelayDeviceSubType.Switch + ",ui=Spa Pump "+str(x)
            secondary_dev.replaceOnServer()
            x = x +1
        x=1
        for blowers in self.myspa.facade.blowers:
            props_dict["device_number"] = x - 1
            newpump = indigo.device.create(indigo.kProtocol.Plugin,
                                           deviceTypeId="geckoSpaBlower",
                                           address=mainspadevice.address,
                                           groupWithDevice=int(first_device_id),
                                           name="Spa Blower " + str(x),
                                           folder=mainspadevice.folderId,
                                           description="Spa Blower",
                                           props=props_dict
                                           )
            secondary_dev_id = newpump.id
            secondary_dev = indigo.devices[secondary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed
            secondary_dev.subType = indigo.kRelayDeviceSubType.Switch + ",ui=Spa Blower " + str(x)
            secondary_dev.replaceOnServer()
            x = x + 1
        x=1
        for lights in self.myspa.facade.lights:
            props_dict["device_number"] = x - 1
            newpump = indigo.device.create(indigo.kProtocol.Plugin,
                                           deviceTypeId="geckoSpaLight",
                                           address=mainspadevice.address,
                                           groupWithDevice=int(first_device_id),
                                           name="Spa Light " + str(x),
                                           folder=mainspadevice.folderId,
                                           description="Spa Light",
                                           props=props_dict
                                           )
            secondary_dev_id = newpump.id
            secondary_dev = indigo.devices[secondary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed
            secondary_dev.subType = indigo.kRelayDeviceSubType.Switch + ",ui=Spa Light " + str(x)
            secondary_dev.replaceOnServer()
            x = x + 1

        x = 1
        props_dict["device_number"] = x - 1
        newpump = indigo.device.create(indigo.kProtocol.Plugin,
                                       deviceTypeId="geckoSpaEco",
                                       address=mainspadevice.address,
                                       groupWithDevice=int(first_device_id),
                                       name="Spa EcoMode " + str(x),
                                       folder=mainspadevice.folderId,
                                       description="Spa EcoMode",
                                       props=props_dict
                                       )
        secondary_dev_id = newpump.id
        secondary_dev = indigo.devices[secondary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed
        secondary_dev.subType = indigo.kRelayDeviceSubType.Switch + ",ui=Spa EcoMode"
        secondary_dev.replaceOnServer()
        x = x + 1


        dev_id_list = indigo.device.getGroupList(first_device_id)
        self.logger.debug(dev_id_list)

    # Shut 'em down.
    def deviceStopComm(self, dev):
        self.debugLog(u"deviceStopComm() method called.")
        indigo.server.log(u"Stopping Spa device: " + dev.name)

    def connectSpa(self):
        self.logger.info("Attempting to setup Library and connect to any compatible Spas...")
        self.logger.debug('Nmber of Active Threads:' + str(threading.activeCount()))
        #self.myspa = pluginSpa(self)
        if not self.myspa.is_alive():
            self.myspa.start()

        # self.spa_thread = threading.Thread(target=self.myspa.thread_runforever, daemon=True)
        # if not self.spa_thread.is_alive():
        #     self.spa_thread.start()

    def pumpON(self):
        self.logger.info("Temperature dwn test menu item")
        asyncio.run(self.myspa.decrease_temp())

    def runConcurrentThread(self):
        try:
            # this will create an infinite loop which exits via exception or you could
            # implement your own method/scheme to exit
            while True:
                self.sleep(10)
                #self.logger.info(f"Status:{builtins.status_data}")
                self.refreshData()

        except self.StopThread:
            # if needed, you could do any cleanup here, or could exit via another flag
            # or command from your plugin
            pass
        except:
            # this fall through will catch any other error that you were not expecting...
            # you may want to set the error state for the device(s) via a call to:
            #    [device].setErrorStateOnServer("Error")
            # you may also wish to schedule a re-connection attempt, if appropriate for the device
            self.exceptionLog()

    def shutdown(self):
        self.debugLog(u"shutdown() method called.")

    def startup(self):
        self.debugLog(u"Starting Gecko Spa Plugin. startup() method called.")

    def validatePrefsConfigUi(self, valuesDict):
        self.debugLog(u"validatePrefsConfigUi() method called.")

        error_msg_dict = indigo.Dict()
        return True, valuesDict
        ########################################
        # Relay / Dimmer Action callback
        ######################

    def actionControlDevice(self, action, dev):
        ###### TURN ON ######
        device_number = dev.ownerProps.get("device_number",99)
        send_success= False

        if device_number == 99:
            self.logger.info("Device Number is 99, odd error.  Ending now.")
            return
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            #self.logger.info(f"{action}\n{dev}")
            #self.logger.info(f"Device Number: {device_number}")
            #send_success = False  # Set to False if it failed.
            if dev.deviceTypeId == "geckoSpaPump":
                send_success = asyncio.run(self.myspa.spaAction("pump",device_number,self.myspa.facade.pumps[device_number].modes[-1]))  ### -1 == ON or HI, 0 ==OFF
            elif dev.deviceTypeId == "geckoSpaBlower":
                send_success = asyncio.run(self.myspa.spaAction("blower", device_number, "ON"))
            elif dev.deviceTypeId == "geckoSpaLight":
                send_success = asyncio.run(self.myspa.spaAction("light", device_number, "ON"))

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" on")
                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" on failed")

        ###### TURN OFF ######
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            # Command hardware module (dev) to turn OFF here:
            # ** IMPLEMENT ME **
            if dev.deviceTypeId == "geckoSpaPump":
                send_success = asyncio.run(self.myspa.spaAction("pump", device_number, self.myspa.facade.pumps[device_number].modes[0]))  ### -1 == ON or HI, 0 ==OFF
            elif dev.deviceTypeId == "geckoSpaBlower":
                send_success = asyncio.run(self.myspa.spaAction("blower", device_number, "OFF"))
            elif dev.deviceTypeId == "geckoSpaLight":
                send_success = asyncio.run(self.myspa.spaAction("light", device_number, "OFF"))

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" off")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", False)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" off failed")

        ###### LOCK ######
        if action.deviceAction == indigo.kDeviceAction.Lock:
            # Command hardware module (dev) to LOCK here:
            # ** IMPLEMENT ME **
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" lock")

                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" lock failed")

        ###### UNLOCK ######
        elif action.deviceAction == indigo.kDeviceAction.Unlock:
            # Command hardware module (dev) to turn UNLOCK here:
            # ** IMPLEMENT ME **
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" unlock")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", False)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" unlock failed")

        ###### TOGGLE ######
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            # Command hardware module (dev) to toggle here:
            # ** IMPLEMENT ME **
            new_on_state = not dev.onState
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" toggle")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", new_on_state)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" toggle failed")

        ###### SET BRIGHTNESS ######
        elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
            # Command hardware module (dev) to set brightness here:
            # ** IMPLEMENT ME **
            new_brightness = action.actionValue
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" set brightness to {new_brightness}")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("brightnessLevel", new_brightness)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" set brightness to {new_brightness} failed")

        ###### BRIGHTEN BY ######
        elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
            # Command hardware module (dev) to do a relative brighten here:
            # ** IMPLEMENT ME **
            new_brightness = min(dev.brightness + action.actionValue, 100)
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" brighten to {new_brightness}")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("brightnessLevel", new_brightness)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" brighten to {new_brightness} failed")

        ###### DIM BY ######
        elif action.deviceAction == indigo.kDeviceAction.DimBy:
            # Command hardware module (dev) to do a relative dim here:
            # ** IMPLEMENT ME **
            new_brightness = max(dev.brightness - action.actionValue, 0)
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" dim to {new_brightness}")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("brightnessLevel", new_brightness)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" dim to {new_brightness} failed")

        ###### SET COLOR LEVELS ######
        elif action.deviceAction == indigo.kDeviceAction.SetColorLevels:
            # action.actionValue is a dict containing the color channel key/value
            # pairs. All color channel keys (redLevel, greenLevel, etc.) are optional
            # so plugin should handle cases where some color values are not specified
            # in the action.
            action_color_vals = action.actionValue

            # Construct a list of channel keys that are possible for what this device
            # supports. It may not support RGB or may not support white levels, for
            # example, depending on how the device's properties (SupportsColor, SupportsRGB,
            # SupportsWhite, SupportsTwoWhiteLevels, SupportsWhiteTemperature) have
            # been specified.
            channel_keys = []
            using_white_channels = False
            if dev.supportsRGB:
                channel_keys.extend(['redLevel', 'greenLevel', 'blueLevel'])
            if dev.supportsWhite:
                channel_keys.extend(['whiteLevel'])
                using_white_channels = True
            if dev.supportsTwoWhiteLevels:
                channel_keys.extend(['whiteLevel2'])
            elif dev.supportsWhiteTemperature:
                channel_keys.extend(['whiteTemperature'])
            # Note having 2 white levels (cold and warm) takes precedence over
            # the use of a white temperature value. You cannot have both, although
            # you can have a single white level and a white temperature value.

            # Next enumerate through the possible color channels and extract that
            # value from the actionValue (action_color_vals).
            kv_list = []
            result_vals = []
            for channel in channel_keys:
                if channel in action_color_vals:
                    brightness = float(action_color_vals[channel])
                    brightness_byte = int(round(255.0 * (brightness / 100.0)))

                    # Command hardware module (dev) to change its color level here:
                    # ** IMPLEMENT ME **

                    if channel in dev.states:
                        kv_list.append({'key': channel, 'value': brightness})
                    result = str(int(round(brightness)))
                elif channel in dev.states:
                    # If the action doesn't specify a level that is needed (say the
                    # hardware API requires a full RGB triplet to be specified, but
                    # the action only contains green level), then the plugin could
                    # extract the currently cached red and blue values from the
                    # dev.states[] dictionary:
                    cached_brightness = float(dev.states[channel])
                    cached_brightness_byte = int(round(255.0 * (cached_brightness / 100.0)))
                    # Could show in the Event Log '--' to indicate this level wasn't
                    # passed in by the action:
                    result = '--'
                    # Or could show the current device state's cached level:
                    #    result = str(int(round(cached_brightness)))

                # Add a comma to separate the RGB values from the white values for logging.
                if channel == 'blueLevel' and using_white_channels:
                    result += ","
                elif channel == 'whiteTemperature' and result != '--':
                    result += " K"
                result_vals.append(result)
            # Set to False if it failed.
            send_success = True

            result_vals_str = ' '.join(result_vals)
            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" set color to {result_vals_str}")

                # And then tell the Indigo Server to update the color level states:
                if len(kv_list) > 0:
                    dev.updateStatesOnServer(kv_list)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" set color to {result_vals_str} failed")

        ########################################
        # General Action callback
        ######################

    def actionControlUniversal(self, action, dev):
        ###### BEEP ######
        if action.deviceAction == indigo.kUniversalAction.Beep:
            # Beep the hardware module (dev) here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" beep request")

        ###### ENERGY UPDATE ######
        elif action.deviceAction == indigo.kUniversalAction.EnergyUpdate:
            # Request hardware module (dev) for its most recent meter data here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" energy update request")

        ###### ENERGY RESET ######
        elif action.deviceAction == indigo.kUniversalAction.EnergyReset:
            # Request that the hardware module (dev) reset its accumulative energy usage data here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" energy reset request")

        ###### STATUS REQUEST ######
        elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
            # Query hardware module (dev) for its current status here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" status request")


    def refreshData(self):
        """
        The refreshData() method controls the updating of all plugin
        devices.
        """
        self.debugLog(u"refreshData() method called.")

        try:
            # Check to see if there have been any devices created.
            for device in indigo.devices.iter(filter="self"):
                if self.myspa !=None:
                    if self.myspa.facade !=None:
                        if device.model == "Gecko Spa Device" or device.model== "Gecko Main Spa Device":
                            self.debugLog(u"Updating data...")
                            if self.myspa != None:
                                pingstring = str(self.myspa.ping_sensor)
                                spaname = self.myspa.spa_name
                                spastate = str(self.myspa.spa_state)
                                radiosensor = str(self.myspa.radio_sensor)
                                statusstring = str(self.myspa.status_sensor)
                                if self.myspa.facade != None:
                                    pumps = self.myspa.facade.pumps
                                    blowers = self.myspa.facade.blowers
                                    lights = self.myspa.facade.lights
                                    water_care = str(self.myspa.facade.water_care)  #WaterCare: Standard
                                    waterheaterstring = str(self.myspa.facade.water_heater)  #Heater: Temperature 39.5°C, SetPoint 39.5°C, Real SetPoint 39.5°C, Operation Idle
                                    targettemperature = float(self.myspa.facade.water_heater.target_temperature)
                                    max_temp = float(self.myspa.facade.water_heater.max_temp)
                                    heater_currentoperation = str(self.myspa.facade.water_heater.current_operation)
                                        # print(self.myspa.facade.pumps[0].is_on)
                                        # print(self.myspa.facade.pumps[3].modes)
                                        # print(self.myspa.facade.pumps[2].mode)
                                    # lines.append(f"SpaPackStruct.xml revision {self.facade.spa.revision} \n" +
                                    #              f"intouch version EN {self.facade.spa.intouch_version_en}\n" +
                                    #              f"intouch version CO {self.facade.spa.intouch_version_co}\n" +
                                    #              f"Spa pack {self.facade.spa.pack} {self.facade.spa.version}\n" +
                                    #              f"Low level configuration # {self.facade.spa.config_number}\n" +
                                    #              f"Config version {self.facade.spa.config_version}\n" +
                                    #              f"Log version {self.facade.spa.log_version}\n" +
                                    #              f"Pack type {self.facade.spa.pack_type}\n")
                                    intouchversion = str(f"intouch version EN {self.myspa.facade.spa.intouch_version_en}")
                                    intouch_spapack = str(f"Spa pack {self.myspa.facade.spa.pack} {self.myspa.facade.spa.version}")
                                    spapacktype = str(f"Pack type {self.myspa.facade.spa.pack_type}")
                                    spa_config  =str( f"Config version {self.myspa.facade.spa.config_version}")
                                    spa_logversion = str( f"Log version {self.myspa.facade.spa.log_version}")
                                    economy_mode = str(self.myspa.facade.eco_mode.is_on)
                                    numpumps = len(self.myspa.facade.pumps)
                                    numblowers = len(self.myspa.facade.blowers)
                                    numlights = len(self.myspa.facade.lights)
                                    spaisinuse = True
                                    updatedStates = [
                                        {'key': 'deviceIsOnline', 'value': True},
                                        {'key': 'deviceStatus', 'value': statusstring},
                                        {'key': 'deviceLastUpdated', 'value': True},
                                        {'key': 'spa_in_use', 'value': spaisinuse},
                                        {'key': 'waterheater_target_temperature', 'value': targettemperature},
                                        {'key': 'ping_sensor', 'value': pingstring},
                                        {'key': 'spa_name', 'value': spaname},
                                        {'key': 'radio_sensor', 'value': radiosensor},
                                        {'key': 'Status', 'value': statusstring},
                                        {'key': 'watercare_mode', 'value': water_care},
                                        {'key': 'spa_state', 'value': spastate},
                                        {'key': 'waterheater', 'value': waterheaterstring},
                                        {'key': 'economy_mode', 'value': economy_mode},
                                        {'key': 'waterheater_current_operation', 'value': heater_currentoperation},
                                        {'key': 'num_pumps', 'value': int(numpumps)},
                                        {'key': 'num_blowers', 'value': int(numblowers)},
                                        {'key': 'num_lights', 'value': int(numlights)},
                                        {'key': 'intouch_version', 'value': intouchversion},
                                        {'key': 'intouch_spa_pack', 'value': intouch_spapack},
                                        {'key': 'intouch_spa_config', 'value': spa_config},
                                        {'key': 'intouch_spa_logversion', 'value': spa_logversion},
                                        {'key': 'intouch_spa_pack_type', 'value': spapacktype},
                                    ]
                                    device.updateStatesOnServer(updatedStates)

                                    try:
                                        x = 1
                                        newstates = []
                                        for pump in self.myspa.facade.pumps:
                                            key = "pump_"+str(x)+"_is_on"
                                            if pump.is_on:
                                                value = True
                                            else:
                                                value = False
                                            newstates.append({'key':key, 'value':value})
                                            x = x + 1
                                        x = 1
                                        for blower in self.myspa.facade.blowers:
                                            key = "blower_"+str(x)+"_is_on"
                                            if blower.is_on:
                                                value = True
                                            else:
                                                value = False
                                            newstates.append({'key':key, 'value':value})
                                            x =x +1
                                        x = 1
                                        for light in self.myspa.facade.lights:
                                            key = "light_"+str(x)+"_is_on"
                                            if light.is_on:
                                                value = True
                                            else:
                                                value = False
                                            newstates.append({'key':key, 'value':value})

                                        #self.logger.debug(f"New States of Devices \n {newstates}")
                                        device.updateStatesOnServer(newstates)
                                    except:
                                        self.logger.debug("Exception with status of pumps/blowers/lights",exc_info=True)

                                if builtins.status_data !=None:
                                    current_status = builtins.status_data
                                    newstates_again = []
                                    if "RhWaterTemp" in current_status:
                                        key = "current_temp"
                                        value = "{:.2f}".format(float(current_status['RhWaterTemp']))
                                        newstates_again.append({'key':key, 'value':value})
                                    if "MSTR_HEATER" in current_status:
                                        key = "Master_Heater"
                                        value = current_status['MSTR_HEATER']
                                        newstates_again.append({'key': key, 'value': value})
                                        if value == "ON":
                                            if str(device.states["Master_Heater"])=="OFF":
                                            ## start timer, just turned on
                                                self.heater_timer = t.time()
                                                self.current_heater = float(device.states['master_heater_timeON_timer'])
                                            else:
                                                ## if on add total time
                                                totaltime = t.time() - self.heater_timer  ## start heater time is being substracted so timedelta
                                                totaltime = totaltime + self.current_heater
                                                key = "master_heater_timeON"
                                                timedelta = str(datetime.timedelta(seconds=totaltime))
                                                value = str(timedelta)
                                                newstates_again.append({'key': key, 'value': value})
                                            ## If on add to time
                                        elif value == "OFF":
                                            if str(device.states["Master_Heater"])=="ON":
                                                key = "master_heater_timeON_timer"
                                                value = t.time() - self.heater_timer
                                                value = value + float(device.states['master_heater_timeON_timer'])
                                                newstates_again.append({'key': key, 'value': value})


                                    newstates_again.append({"key":"raw_states", "value":str(current_status)})
                                    device.updateStatesOnServer(newstates_again)

                        if device.deviceTypeId in ("geckoSpaPump","geckoSpaBlower", "geckoSpaEco", "geckSpaLight"):
                            device_number = device.ownerProps.get("device_number",99)
                            if device.deviceTypeId == "geckoSpaPump":
                                device.updateStateOnServer("onOffState", self.myspa.facade.pumps[device_number].is_on)
                            elif device.deviceTypeId == "geckoSpaBlower":
                                device.updateStateOnServer("onOffState", self.myspa.facade.blowers[device_number].is_on)
                            elif device.deviceTypeId == "geckoSpaEco":
                                device.updateStateOnServer("onOffState", self.myspa.facade.eco_mode.is_on)
                            elif device.deviceTypeId == "geckoSpaLight":
                                device.updateStateOnServer("onOffState", self.myspa.facade.lights[device_number].is_on)


            return True

        except Exception as error:
            self.logger.exception(u"Error refreshing devices. Please check settings.")
            return False

## ACtions

    def actionReturnPumps(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Pumps')
        myArray = []
        x = 0
        for pump in self.myspa.facade.pumps:
            myArray.append( (x,  "Pump : "+str(x+1)) )
            x= x +1
        return myArray

    def actionReturnPumpStates(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Pumps States')
        self.logger.debug(f"ValueDict:\n {valuesDict}")
        myArray = []
        pumpnum = 0
        for pump in self.myspa.facade.pumps:
            pumpnum = pumpnum + 1
            for modes in pump.modes:
                myArray.append( (modes,  "Pump "+str(pumpnum)+" State : "+str(modes) ))
        self.logger.debug(f"States:\n{myArray}")
        return myArray

    def actionReturnBlowers(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Blowers List')
        myArray = []
        x = 0
        for pump in self.myspa.facade.blowers:
            myArray.append( (x,  "Blower : "+str(x+1)) )
            x= x +1
        return myArray

    def actionReturnLights(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Lights')
        myArray = []
        x = 0
        for light in self.myspa.facade.lights:
            myArray.append( (x,  "Light : "+str(x+1)) )
            x= x +1
        return myArray

    def actionReturnTemp(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Temp')
        myArray = []
        starttemp = float(self.myspa.facade.water_heater.min_temp)
        maxtemp = float(self.myspa.facade.water_heater.max_temp)
        currenttemp = starttemp
        while currenttemp <maxtemp:
            myArray.append( (currenttemp,  "Temp : "+str(currenttemp)) )
            currenttemp = currenttemp + 0.5
        self.logger.debug(f"Temp myArray {myArray}")
        return myArray

    def sendPumpAction(self, pluginAction, device):
        self.logger.debug("pluginAction "+str(pluginAction))
        #asyncio.run(self.myspa.facade.pumps[0].async_set_mode()
        actionPump = int(pluginAction.props.get("actionPump"))
        statePump = str(pluginAction.props.get("statePump") )
        result = asyncio.run(self.myspa.spaAction("pump", actionPump, statePump))
        return result

    def sendBlowerOn(self, pluginAction, device):
        self.logger.debug("send Blower On Action "+str(pluginAction))
        actionBlower = int(pluginAction.props.get("actionBlower"))
        asyncio.run(self.myspa.spaAction("blower", actionBlower, "ON"))

        #asyncio.run(self.myspa.facade.blowers[actionBlower].async_turn_on())

    def sendBlowerOff(self, pluginAction, device):
        self.logger.debug("send Blower Off Action "+str(pluginAction))
        actionBlower = int(pluginAction.props.get("actionBlower"))
        asyncio.run(self.myspa.spaAction("blower", actionBlower, "OFF"))

        #asyncio.run(self.myspa.facade.blowers[actionBlower].async_turn_off())

    def sendLightOn(self, pluginAction, device):
        self.logger.debug("send Light On Action " + str(pluginAction))
        actionLight = int(pluginAction.props.get("actionLight"))
        asyncio.run(self.myspa.spaAction("light", actionLight, "OFF"))
        #asyncio.run(self.myspa.facade.lights[actionLight].async_turn_on())

    def sendLightOff(self, pluginAction, device):
        self.logger.debug("send Light Off Action " + str(pluginAction))
        actionLight = int(pluginAction.props.get("actionLight"))
        asyncio.run(self.myspa.spaAction("light", actionLight, "ON"))
        #asyncio.run(self.myspa.facade.lights[actionLight].async_turn_off())

    def sendEcoOff(self, pluginAction, device):
        self.logger.debug("send Eco Off Action " + str(pluginAction))
        asyncio.run(myspa.spaAction("eco", "Economy Mode", "OFF"))
        #asyncio.run(self.myspa.facade.eco_mode.async_turn_off())

    def sendEcoOn(self, pluginAction, device):
        self.logger.debug("send Eco On Action " + str(pluginAction))
        asyncio.run(self.myspa.spaAction("eco", "Economy Mode", "ON"))
        #asyncio.run(self.myspa.facade.eco_mode.async_turn_on())

    def increaseTemp(self, pluginAction, device):
        self.logger.debug("send increase temp Action " + str(pluginAction))
        asyncio.run(self.myspa.increase_temp())

        #asyncio.run(self.myspa.facade.water_heater.async_set_target_temperature(self.myspa.facade.water_heater.target_temperature + 0.5
        #))

    def decreaseTemp(self, pluginAction, device):
        self.logger.debug("send decrease temp Action " + str(pluginAction))
        asyncio.run(self.myspa.decrease_temp())

    def setTemp(self, pluginAction, device):
        self.logger.debug("send decrease temp Action " + str(pluginAction))
        actionTemp = float(pluginAction.props.get("actionTemp"))
        asyncio.run(self.myspa.set_temp(actionTemp))
       # asyncio.run(self.myspa.facade.water_heater.async_set_target_temperature(actionTemp    ))

    def resetTimer(self, pluginAction, device):
        self.logger.debug("reset Heater Timer " + str(pluginAction))
        updatedStates = [
            {'key': 'master_heater_timeON', 'value': ""},
            {'key': 'master_heater_timeON_timer', 'value': 0}]
        device.updateStatesOnServer(updatedStates)

####



    def toggleDebugEnabled(self):
        """
        Toggle debug on/off.
        """
        self.debugLog(u"toggleDebugEnabled() method called.")
        if not self.debug:
            self.debug = True
            self.pluginPrefs['showDebugInfo'] = True
            indigo.server.log(u"Debugging on.")
            self.debugLog(u"Debug level: {0}".format(self.debugLevel))

        else:
            self.debug = False
            self.pluginPrefs['showDebugInfo'] = False
            indigo.server.log(u"Debugging off.")
