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
import traceback
import geckolib
from os import path
from geckolib import GeckoAsyncSpaMan, GeckoSpaEvent, GeckoConstants
from geckolib.spa_state import GeckoSpaState
from config import Config
import threading
import builtins
from threading import Thread
import human_readable
import platform

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

# class UniqueQueue(asyncio.Queue):
#     def put(self, item, block=False, timeout=None):
#         if item not in self.queue:  # fix join bug
#             Queue.put(self, item, block, timeout)
#
#     def _init(self, maxsize):
#         self.queue = set()
#
#     def _put(self, item):
#         self.queue.add(item)
#
#     def _get(self):
#         return self.queue.pop()

CLIENT_ID = "a2d936db-1123-eaed-82bc-b4225fa99739"
# Replace with your spa IP address if on a sub-net
SPA_ADDRESS = None

#commandQue = UniqueQueue()
commandQue = asyncio.Queue()

_LOGGER = logging.getLogger("Plugin.SpaMan")

################################################################################
class IndigoLogHandler(logging.Handler):
    def __init__(self, display_name, level=logging.NOTSET):
        super().__init__(level)
        self.displayName = display_name

    def emit(self, record):
        """ not used by this class; must be called independently by indigo """
        logmessage = ""
        try:
            levelno = int(record.levelno)
            is_error = False
            is_exception = False
            if self.level <= levelno:  ## should display this..
                if record.exc_info !=None:
                    is_exception = True
                if levelno == 5:	# 5
                    logmessage = '({}:{}:{}): {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                elif levelno == logging.DEBUG:	# 10
                    logmessage = '({}:{}:{}): {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                elif levelno == logging.INFO:		# 20
                    logmessage = record.getMessage()
                elif levelno == logging.WARNING:	# 30
                    logmessage = record.getMessage()
                elif levelno == logging.ERROR:		# 40
                    logmessage = '({}: Function: {}  line: {}):    Error :  Message : {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                    is_error = True
                if is_exception:
                    logmessage = '({}: Function: {}  line: {}):    Exception :  Message : {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                    indigo.server.log(message=logmessage, type=self.displayName, isError=is_error, level=levelno)
                    if record.exc_info !=None:
                        etype,value,tb = record.exc_info
                        tb_string = "".join(traceback.format_tb(tb))
                        indigo.server.log(f"Traceback:\n{tb_string}", type=self.displayName, isError=is_error, level=levelno)
                        indigo.server.log(f"Error in plugin execution:\n\n{traceback.format_exc(30)}", type=self.displayName, isError=is_error, level=levelno)
                    indigo.server.log(f"\nExc_info: {record.exc_info} \nExc_Text: {record.exc_text} \nStack_info: {record.stack_info}",type=self.displayName, isError=is_error, level=levelno)
                    return
                indigo.server.log(message=logmessage, type=self.displayName, isError=is_error, level=levelno)
        except Exception as ex:
            indigo.server.log(f"Error in Logging: {ex}",type=self.displayName, isError=is_error, level=levelno)

################################################################################
class pluginSpa(GeckoAsyncSpaMan, Thread):
    """Sample spa man implementation"""
    def __init__(self, plugin):
        global commandQue
        _LOGGER.debug("PluginSpa Class init called")
        threading.Thread.__init__(self)
        GeckoAsyncSpaMan.__init__(self, CLIENT_ID)
        self.plugin = plugin
        self._config = Config()
        self._can_use_facade = False
        self._last_update = t.monotonic()
        self._last_char = None
        self._commands = {}
        self.shared_data = {}
        self._watching_ping_sensor = False
        self.this_spa_is_alive = False
        self.loop = asyncio.new_event_loop()
        self.data_lock = threading.Lock()

    def run(self):
        _LOGGER.debug("Thread Running..")
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.thread_connect(self.loop))
        #asyncio.run_coroutine_threadsafe(self.thread_connect(), self.loop)


    async def thread_connect(self, loop):
        global commandQue
        asyncio.set_event_loop(loop)
        while True:
            await asyncio.sleep(0.5)
            try:
                _LOGGER.debug("Thread for  Connectingrunning.  Attempting to connect.")
                await GeckoAsyncSpaMan.__aenter__(self)

                await self.async_set_spa_info(
                    self._config.spa_address, self._config.spa_id, self._config.spa_name
                )
                await self.wait_for_descriptors()

                if len(self.spa_descriptors) == 0:
                    _LOGGER.info("There were no spas found on your network currently. Sleeping for a bit.")
                    await asyncio.sleep(10)
                    continue
                else:
                    _LOGGER.info("Spa has been found.  Setting up connection.... ")
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
                await asyncio.sleep(1)
                while True:
                    await asyncio.sleep(0.1)
                    cmd = await commandQue.get()
                    _LOGGER.debug(f"Actioning Command {cmd}")
                    try:
                        if self.facade !=None:
                            await cmd
                    except:
                        _LOGGER.exception("Exception with the cmd.  Skipping.")

            except:
                _LOGGER.exception("Exception in main Thread connection Spa.  Restarting.")


    async def _select_next_watercare_mode(self) -> None:
        new_mode = (self.facade.water_care.active_mode + 1) % len(
            GeckoConstants.WATERCARE_MODE
        )
        await self.facade.water_care.async_set_mode(new_mode)

    async def handle_event(self, event: GeckoSpaEvent, **kwargs) -> None:
        # Uncomment this line to see events generated
        if event == GeckoSpaEvent.CLIENT_FACADE_IS_READY:
            self._can_use_facade = True
            _LOGGER.info("Facade is ready. Waiting for devices to be initialized.")
            await self.wait_for_devices()
            _LOGGER.info("Devices are initialized. Setting up observers.")
            self.setup_observers()
        elif event in (
            GeckoSpaEvent.CLIENT_FACADE_TEARDOWN,
            GeckoSpaState.ERROR_NEEDS_ATTENTION,
        ):
            self._can_use_facade = False
        _LOGGER.debug(f"{event}: {kwargs}")

    async def wait_for_devices(self):
        # Wait until pumps are available
        while not self.facade.pumps:
            _LOGGER.debug("Waiting for pumps to be initialized...")
            await asyncio.sleep(0.1)

    def setup_observers(self):
        try:
            _LOGGER.debug("Starting setup_observers")
            # Register observers for pumps
            _LOGGER.debug("Setting up observers for pumps")
            for pump in self.facade.pumps:
                _LOGGER.debug(f"Registering observer for Pump: {pump}")
                pump.watch(self.on_pump_changed)

            _LOGGER.debug("Completed setting up observers for pumps")

            # Register observers for blowers
            _LOGGER.debug("Setting up observers for blowers")
            for blower in self.facade.blowers:
                _LOGGER.debug(f"Registering observer for Blower: {blower}")
                blower.watch(self.on_blower_changed)

            _LOGGER.debug("Completed setting up observers for blowers")

            # Register observers for lights
            _LOGGER.debug("Setting up observers for lights")
            for light in self.facade.lights:
                _LOGGER.debug(f"Registering observer for Light: {light}")
                light.watch(self.on_light_changed)

            _LOGGER.debug("Completed setting up observers for lights")

            # Register observers for sensors
            _LOGGER.debug("Setting up observers for sensors")
            for sensor in self.facade.sensors:
                _LOGGER.debug(f"Registering observer for Sensor: {sensor}")
                sensor.watch(self.on_sensor_changed)

            _LOGGER.debug("Completed setting up observers for sensors")

            # Register observers for binary sensors
            _LOGGER.debug("Setting up observers for binary sensors")
            for binary_sensor in self.facade.binary_sensors:
                _LOGGER.debug(f"Registering observer for Binary Sensor: {binary_sensor}")
                binary_sensor.watch(self.on_binary_sensor_changed)

            _LOGGER.debug("Completed setting up observers for binary sensors")

            # Register observer for water heater
            _LOGGER.debug("Setting up observer for water heater")
            if self.facade.water_heater:
                _LOGGER.debug("Registering observer for Water Heater")
                self.facade.water_heater.watch(self.on_water_heater_changed)

            _LOGGER.debug("Completed setting up observer for water heater")

            # Register observer for water care
            _LOGGER.debug("Setting up observer for water care")
            if self.facade.water_care:
                _LOGGER.debug("Registering observer for Water Care")
                self.facade.water_care.watch(self.on_water_care_changed)

            _LOGGER.debug("Completed setting up observer for water care")

            # Register observer for keypad
            _LOGGER.debug("Setting up observer for keypad")
            if self.facade.keypad:
                _LOGGER.debug("Registering observer for Keypad")
                self.facade.keypad.watch(self.on_keypad_changed)


            _LOGGER.debug("Completed setting up observer for keypad")

            # Register observer for error sensor
            _LOGGER.debug("Setting up observer for error sensor")
            if self.facade.error_sensor:
                _LOGGER.debug("Registering observer for Error Sensor")
                self.facade.error_sensor.watch(self.on_error_sensor_changed)

            _LOGGER.debug("Completed setting up observer for error sensor")

            # Register observer for eco mode
            _LOGGER.debug("Setting up observer for eco mode")
            if self.facade.eco_mode:
                _LOGGER.debug("Registering observer for Eco Mode")
                self.facade.eco_mode.watch(self.on_eco_mode_changed)

            _LOGGER.debug("Completed setting up observer for eco mode")

        except:
            _LOGGER.exception("Exception Caught")
        _LOGGER.info("All observers have been set up.")

    def on_pump_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Pump {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"Pump.{sender.tag}"
            self.shared_data[key] = new_value

    def on_blower_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Blower {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"Blower.{sender.tag}"
            self.shared_data[key] = new_value

    def on_light_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Light {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"Light.{sender.tag}"
            self.shared_data[key] = new_value

    def on_sensor_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Sensor {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"Sensor.{sender.tag}"
            self.shared_data[key] = new_value

    def on_binary_sensor_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Binary Sensor {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"BinarySensor.{sender.tag}"
            self.shared_data[key] = new_value

    def on_water_heater_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Water Heater {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"WaterHeater.{sender.tag}"
            self.shared_data[key] = new_value

    def on_water_care_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Water Care {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"WaterCare.{sender.tag}"
            self.shared_data[key] = new_value

    def on_keypad_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Keypad {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"Keypad.{sender.tag}"
            self.shared_data[key] = new_value

    def on_error_sensor_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Error Sensor {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"ErrorSensor.{sender.tag}"
            self.shared_data[key] = new_value

    def on_eco_mode_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Eco Mode {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"EcoMode.{sender.tag}"
            self.shared_data[key] = new_value

    def on_reminder_changed(self, sender, old_value, new_value):
        _LOGGER.info(f"Reminder {sender.tag} changed from {old_value} to {new_value}")
        with self.data_lock:
            key = f"Reminder.{sender.tag}"
            self.shared_data[key] = new_value

    def get_shared_data(self):
        with self.data_lock:
            return self.shared_data.copy()

    async def __aenter__(self):
        await GeckoAsyncSpaMan.__aenter__(self)
        #self.add_task(self._timer_loop(), "Timer", "SpaMan")
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
        global commandQue
        self.logger.setLevel(logging.DEBUG)
        try:
            self.logLevel = int(self.pluginPrefs["showDebugLevel"])
            self.fileloglevel = int(self.pluginPrefs["showDebugFileLevel"])
        except:
            self.logLevel = logging.INFO
            self.fileloglevel = logging.DEBUG

        self.logger.removeHandler(self.indigo_log_handler)

        self.indigo_log_handler = IndigoLogHandler(pluginDisplayName, logging.INFO)
        ifmt = logging.Formatter("%(message)s")
        self.indigo_log_handler.setFormatter(ifmt)
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.addHandler(self.indigo_log_handler)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)s\t%(name)s.%(funcName)s:\t%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)
        self.plugin_file_handler.setLevel(self.fileloglevel)
        logging.getLogger("geckolib").addHandler(self.plugin_file_handler)

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
        system_version, product_version, longer_name = self.get_macos_version()
        self.logger.info("{0:=^130}".format(" Initializing New Plugin Session "))
        self.logger.info("{0:<30} {1}".format("Plugin name:", pluginDisplayName))
        self.logger.info("{0:<30} {1}".format("Plugin version:", pluginVersion))
        self.logger.info("{0:<30} {1}".format("Plugin ID:", pluginId))
        self.logger.info("{0:<30} {1}".format("Indigo version:", indigo.server.version))
        self.logger.info("{0:<30} {1}".format("System version:", f"{system_version} {longer_name}" ))
        self.logger.info("{0:<30} {1}".format("Product version:", product_version))
        self.logger.info("{0:<30} {1}".format("Silicon version:", str(platform.machine()) ))
        self.logger.info("{0:<30} {1}".format("Geckolib Library version:", str(geckolib.__version__)))
        self.logger.info("{0:<30} {1}".format("Python version:", sys.version.replace('\n', '')))
        self.logger.info("{0:<30} {1}".format("Python Directory:", sys.prefix.replace('\n', '')))
        self.logger.info("{0:=^130}".format(" Plugin Session Initialized "))
        self.logger.info("")
        self.pluginprefDirectory = '{}/Preferences/Plugins/com.GlennNZ.indigoplugin.geckoSpa'.format(indigo.server.getInstallFolderPath())
    def get_macos_version(self):
        try:
            version, _, _ = platform.mac_ver()
            longer_version = platform.platform()
            self.logger.info(f"{version}")
            longer_name = self.get_macos_marketing_name(version)
            return version, longer_version, longer_name
        except:
            self.logger.debug("Exception:",exc_info=True)
            return "","",""

    def get_macos_marketing_name(self, version: str) -> str:
        """Return the marketing name for a given macOS version number."""
        versions = {
            "10.0": "Cheetah",
            "10.1": "Puma",
            "10.2": "Jaguar",
            "10.3": "Panther",
            "10.4": "Tiger",
            "10.5": "Leopard",
            "10.6": "Snow Leopard",
            "10.7": "Lion",
            "10.8": "Mountain Lion",
            "10.9": "Mavericks",
            "10.10": "Yosemite",
            "10.11": "El Capitan",
            "10.12": "Sierra",
            "10.13": "High Sierra",
            "10.14": "Mojave",
            "10.15": "Catalina",
            "11": "Big Sur",  # Just use the major version number for macOS 11+
            "12": "Monterey",
            "13": "Ventura",
            "14": "Sonoma",
            "15": "Sequoia"
        }
        major_version_parts = version.split(".")
        # If the version is "11" or later, use only the first number as the key
        if int(major_version_parts[0]) >= 11:
            major_version = major_version_parts[0]
        # For macOS "10.x" versions, use the first two numbers as the key
        else:
            major_version = ".".join(major_version_parts[:2])
        self.logger.debug(f"Major Version== {major_version}")
        return versions.get(major_version, f"Unknown macOS version for {version}")
    def validateDeviceConfigUi(self, values_dict, type_id, dev_id):
        return (True, values_dict)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")

        if not userCancelled:
            self.debugLevel = valuesDict.get('showDebugLevel', "10")
            self.debugLog(u"User prefs saved.")

            #self.logger.error(str(valuesDict))

            try:
                self.logLevel = int(valuesDict[u"showDebugLevel"])
            except:
                self.logLevel = logging.INFO

            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(u"logLevel = " + str(self.logLevel))
            self.logger.debug(u"User prefs saved.")
            self.logger.debug(u"Debugging on (Level: {0})".format(self.debugLevel))

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
            x = 0
            last_day  = datetime.datetime.now().day
            self.sleep(15)
            self.refreshData()
            while True:
                x = x + 1
                self.refreshOnOffState()  ## refresh device on/off state regularly.
                if x >12:
                    self.refreshData()
                    x = 0
                    ## check in here no rush
                    day = datetime.datetime.now().day
                    if day != last_day:  #Next day
                        last_day = day
                        self.updateTimers()
                self.sleep(5)

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
        global commandQue
        device_number = dev.ownerProps.get("device_number",99)
        send_success= False

        if device_number == 99:
            self.logger.info("Device Number is 99, odd error.  Ending now.")
            return
        tryloop = 0
        while send_success==False:
            tryloop = tryloop +1
            if action.deviceAction == indigo.kDeviceAction.Toggle:
                if dev.deviceTypeId == "geckoSpaPump":
                    if self.myspa.facade.pumps[device_number].is_on:
                        action.deviceAction = indigo.kDeviceAction.TurnOff
                    else:
                        action.deviceAction = indigo.kDeviceAction.TurnOn
                elif dev.deviceTypeId == "geckoSpaBlower":
                    if self.myspa.facade.blowers[device_number].is_on:
                        action.deviceAction = indigo.kDeviceAction.TurnOff
                    else:
                        action.deviceAction = indigo.kDeviceAction.TurnOn
                elif dev.deviceTypeId == "geckoSpaLight":
                    if self.myspa.facade.lights[device_number].is_on:
                        action.deviceAction = indigo.kDeviceAction.TurnOff
                    else:
                        action.deviceAction = indigo.kDeviceAction.TurnOn
                elif dev.deviceTypeId == "geckoEco":
                    if self.myspa.facade.eco_mode.is_on:
                        action.deviceAction = indigo.kDeviceAction.TurnOff
                    else:
                        action.deviceAction = indigo.kDeviceAction.TurnOn

            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                if dev.deviceTypeId == "geckoSpaPump":
                    #send_success = asyncio.run(self.myspa.spaAction("pump",device_number,self.myspa.facade.pumps[device_number].modes[-1]))
                    commandQue.put_nowait( self.myspa.facade.pumps[device_number].async_set_mode(self.myspa.facade.pumps[device_number].modes[-1]) )
                    send_success = True
                    ### -1 == ON or HI, 0 ==OFF
                elif dev.deviceTypeId == "geckoSpaBlower":
                    commandQue.put_nowait(self.myspa.facade.blowers[device_number].async_turn_on())
                    send_success = True
                   # send_success = asyncio.run(self.myspa.spaAction("blower", device_number, "ON"))
                elif dev.deviceTypeId == "geckoSpaLight":
                    commandQue.put_nowait( self.myspa.facade.lights[device_number].async_turn_on() )
                    send_success = True
                    #send_success = asyncio.run(self.myspa.spaAction("light", device_number, "ON"))
                elif dev.deviceTypeId == "geckoEco":
                    commandQue.put_nowait( self.myspa.facade.eco_mode.async_turn_on())
                    send_success = True

                if send_success:
                    # If success then log that the command was successfully sent.
                    self.logger.info(f"sent \"{dev.name}\" on")
                    # And then tell the Indigo Server to update the state.
                    dev.updateStateOnServer("onOffState", True)
                    return
                else:
                    # Else log failure but do NOT update state on Indigo Server.
                    self.logger.debug(f"send \"{dev.name}\" on failed")

        ###### TURN OFF ######
            elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                # Command hardware module (dev) to turn OFF here:
                # ** IMPLEMENT ME **
                if dev.deviceTypeId == "geckoSpaPump":
                    #send_success = asyncio.run(self.myspa.spaAction("pump", device_number, self.myspa.facade.pumps[device_number].modes[0]))
                    commandQue.put_nowait(self.myspa.facade.pumps[device_number].async_set_mode(self.myspa.facade.pumps[device_number].modes[0] ) )
                    send_success = True
                    ### -1 == ON or HI, 0 ==OFF
                elif dev.deviceTypeId == "geckoSpaBlower":
                   # send_success = asyncio.run(self.myspa.spaAction("blower", device_number, "OFF"))
                    commandQue.put_nowait( self.myspa.facade.blowers[device_number].async_turn_off() )
                    send_success = True
                elif dev.deviceTypeId == "geckoSpaLight":
                    commandQue.put_nowait( self.myspa.facade.lights[device_number].async_turn_off())
                    send_success = True
                    #send_success = asyncio.run(self.myspa.spaAction("light", device_number, "OFF"))
                elif dev.deviceTypeId == "geckoEco":
                    commandQue.put_nowait( self.myspa.facade.eco_mode.async_turn_off())
                    send_success = True
                    #send_success = asyncio.run(self.myspa.spaAction("light", device_number, "OFF"))
                if send_success:
                    # If success then log that the command was successfully sent.
                    self.logger.info(f"sent \"{dev.name}\" off")
                    # And then tell the Indigo Server to update the state:
                    dev.updateStateOnServer("onOffState", False)
                    return
                else:
                    # Else log failure but do NOT update state on Indigo Server.
                    self.logger.info(f"send \"{dev.name}\" off failed")

            self.sleep(5)
            self.logger.debug("Trying command again given seemed to fail")

            if tryloop>=3:
                self.logger.error("3 Errors trying to send command.  Giving up sadly")
                return


        ###### TOGGLE ######




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


    def refreshOnOffState(self):
        try:
            # Check to see if there have been any devices created.
            for device in indigo.devices.iter(filter="self"):
                if self.myspa !=None:
                    if self.myspa.facade !=None:
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

        except Exception as error:
            self.logger.exception(u"Error refreshing devices. Please check settings.")
            return False

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
                                    #pumps = self.myspa.facade.pumps
                                    #blowers = self.myspa.facade.blowers
                                    #lights = self.myspa.facade.lights
                                    #reminders = self.myspa.facade.reminders_manager.reminders
                                    water_care = str(self.myspa.facade.water_care)  #WaterCare: Standard
                                    waterheaterstring = str(self.myspa.facade.water_heater)  #Heater: Temperature 39.5°C, SetPoint 39.5°C, Real SetPoint 39.5°C, Operation Idle
                                    targettemperature = float(self.myspa.facade.water_heater.target_temperature)
                                    max_temp = float(self.myspa.facade.water_heater.max_temp)
                                    currenttemp = float(self.myspa.facade.water_heater.current_temperature)
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
                                    now = datetime.datetime.now()

                                    # Format the datetime using %c
                                    formatted_date = now.strftime("%c")
                                    updatedStates = [
                                        {'key': 'deviceIsOnline', 'value': True},
                                        {'key': 'deviceStatus', 'value': statusstring},
                                        {'key': 'deviceLastUpdated', 'value': formatted_date},
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
                                        x = 1
                                        for reminder in self.myspa.facade.reminders_manager.reminders:
                                            key = "reminder"+str(x)
                                            value = str(reminder)
                                            newstates.append({'key':key, 'value':value})
                                            x = x +1
                                            if x == 6:  # only 6 reminder fields in devices.
                                                break
                                        #self.logger.debug(f"New States of Devices \n {newstates}")
                                        device.updateStatesOnServer(newstates)
                                    except:
                                        self.logger.debug("Exception with status of pumps/blowers/lights",exc_info=True)

                                try:
                                    # Update the current heater state
                                    newstates_again = []
                                    key = "Master_Heater"
                                    result_Heating = heater_currentoperation
                                    newstates_again.append({'key': key, 'value': result_Heating})

                                    # Retrieve the previous heater state, defaulting to "Off" if not set
                                    prev_heater_state = device.states.get("Master_Heater", "Off")

                                    # Determine current and previous heater status
                                    heater_now_on = (result_Heating == "Heating")
                                    heater_was_on = (prev_heater_state == "Heating")

                                    # Ensure self.current_heater is initialized
                                    if not hasattr(self, 'current_heater'):
                                        self.current_heater = float(device.states.get('master_heater_timeON_timer', 0))
                                    # Initialize self.heater_timer if it doesn't exist
                                    if not hasattr(self, 'heater_timer'):
                                        self.heater_timer = None

                                    # Heater just turned on
                                    if not heater_was_on and heater_now_on:
                                        self.heater_timer = t.time()
                                        _LOGGER.debug("Heater just turned ON, timer started.")

                                    # Heater is on
                                    if heater_now_on:
                                        if self.heater_timer is None:
                                            # Heater was on when the program started; start timer
                                            self.heater_timer = t.time()
                                            _LOGGER.debug("Heater is ON, but timer was None; timer started.")

                                        current_session_time = t.time() - self.heater_timer
                                        total_time = self.current_heater + current_session_time
                                        # Update the readable total time
                                        key = "master_heater_timeON"
                                        timedelta_obj = datetime.timedelta(seconds=total_time)
                                        stringtimedelta = human_readable.precise_delta(timedelta_obj, minimum_unit="minutes")
                                        value = str(stringtimedelta)
                                        newstates_again.append({'key': key, 'value': value})
                                        _LOGGER.debug(f"Heater is ON, total time updated: {value}")

                                    # Heater just turned off
                                    if heater_was_on and not heater_now_on:
                                        if self.heater_timer is not None:
                                            session_time = t.time() - self.heater_timer
                                            self.current_heater += session_time
                                            # Update the cumulative timer
                                            key = "master_heater_timeON_timer"
                                            value = self.current_heater
                                            newstates_again.append({'key': key, 'value': value})
                                            # Update the all-time total if needed
                                            key = "master_heater_timeON_timer_alltime"
                                            total_all_time = float(device.states.get('master_heater_timeON_timer_alltime', 0))
                                            total_all_time += session_time
                                            newstates_again.append({'key': key, 'value': total_all_time})

                                            # Reset the timer
                                            self.heater_timer = None
                                            _LOGGER.debug("Heater just turned OFF, session time added.")

                                    # Update the readable total time when heater is off
                                    if not heater_now_on:
                                        key = "master_heater_timeON"
                                        total_time = self.current_heater
                                        timedelta_obj = datetime.timedelta(seconds=total_time)
                                        stringtimedelta = human_readable.precise_delta(timedelta_obj, minimum_unit="minutes")
                                        value = str(stringtimedelta)
                                        newstates_again.append({'key': key, 'value': value})
                                        _LOGGER.debug(f"Heater is OFF, total time: {value}")

                                except Exception:
                                    self.logger.debug("Exception", exc_info=True)

                                if self.myspa.get_shared_data() != None:
                                    current_status = self.myspa.get_shared_data()
                                    self.logger.debug(f"Raw States = shared data:{current_status}")
                                    if "RhWaterTemp" in current_status:
                                        key = "current_temp"
                                        value = "{:.2f}".format(float(current_status['RhWaterTemp']))
                                        newstates_again.append({'key':key, 'value':value})
                                    else:  ## use sensitive above, until available use current temp from water heater
                                        key = "current_temp"
                                        value = "{:.2f}".format(float(currenttemp))
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

    def updateTimers(self):
        self.logger.debug("24 hours gone by updating states")
        for device in indigo.devices.iter(filter="self"):
            if device.model == "Gecko Spa Device" or device.model == "Gecko Main Spa Device":
                Devicecurrent_heater = float(device.states['master_heater_timeON_timer'])
                self.heater_timer = t.time()  ## reset current timer in case running.
                append_states = []
                key = "master_heater_timeON_timer"
                value = 0
                append_states.append({'key': key, 'value': value})
                todaydeltastring = device.states['master_heater_timeON']
                key = "master_heater_timeON_yesterday"
                value = str(todaydeltastring)
                append_states.append({'key': key, 'value': value})
                key = "master_heater_timeON"
                timedelta = datetime.timedelta(seconds=0)
                stringtimedelta = human_readable.precise_delta(timedelta, minimum_unit="minutes")
                value = str(stringtimedelta)
                append_states.append({'key': key, 'value': value})
                device.updateStatesOnServer(append_states)
## ACtions

    def actionReturnPumps(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Pumps')
        myArray = []
        x = 0
        for pump in self.myspa.facade.pumps:
            myArray.append( (x,  "Pump : "+str(x+1)) )
            x= x +1
        return myArray

    def actionReturnWatercare(self, filter, valuesDict,typeId, targetId):
        self.logger.debug(u'Generate Watercare Modes')
        myArray = []
        for pump in self.myspa.facade.water_care.modes:
            myArray.append( (pump,  "WaterCare Mode : "+str(pump)) )
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
        global commandQue
        self.logger.debug("pluginAction "+str(pluginAction))
        #asyncio.run(self.myspa.facade.pumps[0].async_set_mode()
        actionPump = int(pluginAction.props.get("actionPump"))
        statePump = str(pluginAction.props.get("statePump") )
        if statePump in self.myspa.facade.pumps[actionPump].modes:
            self.logger.info("Selected Mode pump validated by spa.  Setting Now.")
            commandQue.put_nowait(self.myspa.facade.pumps[actionPump].async_set_mode(statePump))
        else:
            self.logger.info(f"Selected Mode {statePump}, not available for this pump.  Describes only these modes being available. {self.myspa.facade.pumps[actionPump].modes}")

    def sendWatercareAction(self, pluginAction, device):
        global commandQue
        self.logger.debug("pluginAction "+str(pluginAction))
        actionWatercare = pluginAction.props.get("actionWater")
        if actionWatercare in self.myspa.facade.water_care.modes:
            self.logger.info("Selected Mode Watercare validated by spa.  Setting Now.")
            commandQue.put_nowait(self.myspa.self.facade.water_care.async_set_mode(actionWatercare))
        else:
            self.logger.info(f"Selected Mode {actionWatercare}, not available for this Spa.  Describes only these modes being available: {self.myspa.facade.water_care.modes}")

    def sendBlowerOn(self, pluginAction, device):
        global commandQue
        self.logger.debug("send Blower On Action "+str(pluginAction))
        actionBlower = int(pluginAction.props.get("actionBlower"))
        commandQue.put_nowait(self.myspa.facade.blowers[actionBlower].async_turn_on())


    def sendBlowerOff(self, pluginAction, device):
        global commandQue
        self.logger.debug("send Blower Off Action "+str(pluginAction))
        actionBlower = int(pluginAction.props.get("actionBlower"))
        commandQue.put_nowait(self.myspa.facade.blowers[actionBlower].async_turn_off())

        #asyncio.run(self.myspa.facade.blowers[actionBlower].async_turn_off())

    def sendLightOn(self, pluginAction, device):
        global commandQue
        self.logger.debug("send Light On Action " + str(pluginAction))
        actionLight = int(pluginAction.props.get("actionLight"))
        commandQue.put_nowait( self.myspa.facade.lights[actionLight].async_turn_on() )

    def sendLightOff(self, pluginAction, device):
        global commandQue
        self.logger.debug("send Light Off Action " + str(pluginAction))
        actionLight = int(pluginAction.props.get("actionLight"))
        commandQue.put_nowait( self.myspa.facade.lights[actionLight].async_turn_off() )

    def sendEcoOff(self, pluginAction, device):
        global commandQue
        self.logger.debug("send Eco Off Action " + str(pluginAction))
        asyncio.run(self.myspa.spaAction("eco", "Economy Mode", "OFF"))
        commandQue.put_nowait( self.myspa.facade.eco_mode.async_turn_on() )

    def sendEcoOn(self, pluginAction, device):
        global commandQue
        self.logger.debug("send Eco On Action " + str(pluginAction))
        commandQue.put_nowait( self.myspa.facade.eco_mode.async_turn_on() )

    def increaseTemp(self, pluginAction, device):
        global commandQue
        self.logger.debug("send increase temp Action " + str(pluginAction))
        commandQue.put_nowait(self.myspa.facade.water_heater.async_set_target_temperature(self.myspa.facade.water_heater.target_temperature + 0.5) )
       # commandQue.put_nowait(self.myspa.increase_temp())

    def decreaseTemp(self, pluginAction, device):
        global commandQue
        self.logger.debug("send decrease temp Action " + str(pluginAction))
        commandQue.put_nowait(self.myspa.facade.water_heater.async_set_target_temperature(self.myspa.facade.water_heater.target_temperature - 0.5))

    def setTemp(self, pluginAction, device):
        global commandQue
        self.logger.debug("send decrease temp Action " + str(pluginAction))
        actionTemp = float(pluginAction.props.get("actionTemp"))
        commandQue.put_nowait(self.myspa.facade.water_heater.async_set_target_temperature(actionTemp))

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
