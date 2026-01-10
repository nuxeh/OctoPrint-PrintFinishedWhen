import time
import logging
import os
from logging.handlers import RotatingFileHandler

from octoprint.plugin import (
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin,
)
from octoprint.events import Events
from octoprint.util import RepeatedTimer

class NullLogger:
    """ Null logger class used before the plugin is initialised
    Using this avoids checking that the logger has been initialised, each time
    the logger is called, as apparently plugins can be called before
    initialisation.
    """
    def section(self, *_, **__): pass
    def subsection(self, *_, **__): pass
    def event(self, *_, **__): pass
    def highlight(self, *_, **__): pass
    def info(self, *_, **__): pass
    def warning(self, *_, **__): pass
    def error(self, *_, **__): pass
    def kv(self, *_, **__): pass

class PluginLogger:
    def __init__(self, logger):
        self._logger = logger

    def section(self, title):
        self._logger.info(f"=== {title} ===")

    def subsection(self, title):
        self._logger.info(f"--- {title} ---")

    def event(self, message):
        self._logger.info(f">> {message} <<")

    def highlight(self, message):
        self._logger.info(f"*** {message} ***")

    def info(self, message):
        self._logger.info(f"{message}")

    def debug(self, message):
        self._logger.debug(f"{message}")

    def warning(self, message):
        self._logger.warning(f"{message}")

    def error(self, message):
        self._logger.error(f"{message}")

    def kv(self, key, value):
        self._logger.info(f"[{key}] {value}")


class PrintFinishedWhenPlugin(
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin,
):
    def __init__(self):
        self._print_finished_at = None
        self._paused_at = None
        self._paused_duration = 0
        self._timer = None
        self.log = NullLogger()

    def initialize(self):
        logging_path = os.path.join(
            self._settings.getBaseFolder("logs"),
            "plugin_print_finished_when.log"
        )

        file_handler = RotatingFileHandler(
            logging_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3
        )

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)

        self._logger.addHandler(file_handler)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        self.log = PluginLogger(self._logger)

        self.log.section("Print Finished When Plugin initialised")
        self.log.kv("Log file", logging_path)
        self.log_settings()

    def get_settings_version(self):
        return 1

    def get_settings_defaults(self):
        return dict(
            enabled=True,
            interval_seconds=60,
            start_delay_seconds=300,
            message_template_under_60s="Finished {seconds}s ago",
            message_template_under_60m="Finished {ms} ago",
            message_template_over_60m="Finished {hm} ago",
            message_template_over_24h="Finished {dhm} ago",
        )

    def on_settings_save(self, data):
        SettingsPlugin.on_settings_save(self, data)

        self.log.section("Settings Saved")
        self.log.info(f"Data: {data}")

        for key, value in data.items():
            self.log.kv(key, value)

        self._apply_settings()

    def log_settings(self):
        self.log.kv(
            "Enabled", self._settings.get_boolean(["enabled"]))
        self.log.kv(
            "Interval",
            f"{self._settings.get_int(['interval_seconds'])} seconds"
        )
        self.log.kv(
            "Start delay",
            f"{self._settings.get_int(['start_delay_seconds'])} seconds"
        )
        self.log.kv(
            "Template (<60s)",
            self._settings.get(["message_template_under_60s"])
        )
        self.log.kv(
            "Template (<60m)",
            self._settings.get(["message_template_under_60m"])
        )
        self.log.kv(
            "Template (>=60m)",
            self._settings.get(["message_template_over_60m"])
        )
        self.log.kv(
            "Template (>=24h)",
            self._settings.get(["message_template_over_24h"])
        )

    def _apply_settings(self):
        """
        Apply settings to the running plugin.
        Safe to call at any lifecycle stage.
        """
        if not self._settings.get_boolean(["enabled"]):
            self._stop_timer()
            return

        if self._timer and self._print_finished_at:
            interval = self._settings.get_int(["interval_seconds"])
            self._stop_timer()
            self._timer = RepeatedTimer(interval, self._send_message, run_first=False)
            self._timer.start()
            self.log.highlight(f"Timer restarted with interval {interval}s")

        self.log_settings()

    def on_event(self, event, payload):
        trigger_events = {
            Events.PRINT_DONE,
            Events.PRINT_PAUSED,
            Events.PRINT_RESUMED,
            Events.PRINT_STARTED,
            Events.PRINT_CANCELLED,
            Events.PRINT_FAILED,
            Events.SETTINGS_UPDATED,
        }

        if event in trigger_events:
            self.log.section(f"Event: {event}")
        else:
            self.log.debug(f"Event: {event}")

        if event == Events.PRINT_DONE:
            self.log.event("Print finished")
            self._on_print_done()
        elif event == Events.PRINT_PAUSED:
            self.log.event("Print paused")
            self._on_print_paused()
        elif event == Events.PRINT_RESUMED:
            self.log.event("Print resumed")
            self._on_print_resumed()

        elif event == Events.PRINT_STARTED:
            self.log.event("Print started")
        elif event == Events.PRINT_CANCELLED:
            self.log.event("Print cancelled")
        elif event == Events.PRINT_FAILED:
            self.log.event("Print failed")

        elif event == Events.SETTINGS_UPDATED:
            self.log.event("Settings updated")

        reset_events = {
            Events.PRINT_STARTED,
            Events.PRINT_CANCELLED,
            Events.PRINT_FAILED,
        }

        if event in reset_events:
            self._reset_state()

    def _on_print_done(self):
        if not self._settings.get_boolean(["enabled"]):
            self.log.info("Plugin disabled, ignoring print completion")
            return

        self._print_finished_at = time.time()
        self._paused_at = None
        self._paused_duration = 0

        self._stop_timer()

        interval = self._settings.get_int(["interval_seconds"])
        self.log.kv("Timer interval", f"{interval}s")

        self._timer = RepeatedTimer(interval, self._send_message, run_first=False)
        self._timer.start()
        self.log.highlight("Timer started")

    def _on_print_paused(self):
        if self._paused_at is None:
            self._paused_at = time.time()
        else:
            self.log.warning("Pause event received while already paused")

    def _on_print_resumed(self):
        if self._paused_at is not None:
            paused_for = time.time() - self._paused_at
            self._paused_duration += paused_for
            self._paused_at = None
            self.log.info(f"Resumed after {int(paused_for)}s pause")
        else:
            self.log.warning("Resume event received while not paused")

    def _stop_timer(self):
        if self._timer:
            self.log.highlight("Stopping timer")
            self._timer.cancel()
            self._timer = None

    def _reset_state(self):
        self._stop_timer()
        self._print_finished_at = None
        self._paused_at = None
        self._paused_duration = 0
        self.log.info("State reset")

    def _calculate_template_data(self, seconds_elapsed):
        """ Calculate values for substitutions, and define their keys

        Any new local variables defined in this function (and associated
        values) will be used in message string substitutions.

        Defining anything new here will be propagated automatically, to be used
        in the message formatting code, and to the settings UI. No other
        changes are required. Pretty neat, eh.
        """
        seconds = seconds_elapsed
        minutes, mod_s = divmod(seconds, 60)
        hours, mod_m = divmod(minutes, 60)
        days, mod_h = divmod(hours, 24)

        # Create strings
        ms = f"{minutes}m{mod_s}s"
        hm = f"{hours}h{mod_m:02}m"
        hms = f"{hours}h{mod_m:02}m{mod_s:02}s"
        dhm = f"{days}d{mod_h:02}h{mod_m:02}m"
        dhms = f"{days}d{mod_h:02}h{mod_m:02}m{mod_s:02}s"

        # get all variables defined in this function as a dict
        data = locals().copy()

        # prune those which are not wanted for substitutions
        data.pop("self", None)
        data.pop("seconds_elapsed", None)

        return data

    def _send_message(self):
        self.log.section("Send Message")

        if not self._printer:
            self.log.error("Printer not available")
            self._stop_timer()
            return

        if self._printer.is_printing():
            self.log.info("Printer active, stopping timer")
            self._stop_timer()
            return

        if not self._print_finished_at:
            self.log.warning("No completion timestamp")
            return

        now = time.time()
        seconds = int(
            now - self._print_finished_at - self._paused_duration
        )

        start_delay = self._settings.get_int(["start_delay_seconds"])
        if seconds < start_delay:
            self.log.info("Waiting to start")
            self.log.kv("delay", f"{start_delay}")
            self.log.kv("elapsed", f"{seconds}")
            return

        template_data = self._calculate_template_data(seconds)

        # log (verbose)
        for key, value in template_data.items():
            self.log.kv(key, value)

        s = template_data["seconds"]
        m = template_data["minutes"]
        h = template_data["hours"]

        if s < 60:
            tier,t = "under 60s", "message_template_under_60s"
        elif m < 60:
            tier,t = "under 60m", "message_template_under_60m"
        elif h < 24:
            tier,t = "over 60m", "message_template_over_60m"
        else:
            tier,t = "over 24h", "message_template_over_24h"

        self.log.kv("Template tier", tier)
        template = self._settings.get([t])

        try:
            message = template.format(**template_data)
        except Exception as e:
            self.log.error(f"Template formatting error: {e}")
            return

        self.log.kv("Message", message)

        try:
            self._printer.commands([f"M117 {message}"])
        except Exception as e:
            self.log.error(f"M117 send failed: {e}")

    def get_template_vars(self):
        # get the template data directly, with sample calculation
        # return the keys for display on settings page
        sample_data = self._calculate_template_data(3600)
        return dict(placeholders=sorted(sample_data.keys()))

    def get_template_configs(self):
        return [dict(type="settings", autoescape=True, custom_bindings=False)]

    def is_template_autoescaped(self):
        return True

__plugin_name__ = "Print Finished When"
__plugin_author__ = "Ed Cragg"
__plugin_description__ = "Periodically displays how long ago a print finished on the printer LCD"
__plugin_version__ = "0.2.5"
__plugin_license__ = "ISC"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_icon__ = "clock-o"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintFinishedWhenPlugin()

