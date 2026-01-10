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
            message_template_under_60s="Finished {seconds} s ago",
            message_template_under_60m="Finished {minutes} m ago",
            message_template_over_60m="Finished {hours} h ago",
            message_template_over_24h="Finished {days} d ago",
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
            "Template (<60m)",
            self._settings.get(["message_template_under_60m"])
        )
        self.log.kv(
            "Template (>=60m)",
            self._settings.get(["message_template_over_60m"])
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
        elapsed_seconds = int(
            now - self._print_finished_at - self._paused_duration
        )

        start_delay = self._settings.get_int(["start_delay_seconds"])
        if elapsed_seconds < start_delay:
            self.log.info("Waiting to start")
            self.log.kv("delay", f"{start_delay}")
            self.log.kv("elapsed", f"{elapsed_seconds}")
            return

        # floored divisions
        minutes = elapsed_seconds // 60
        hours = minutes // 60
        days = hours // 24

        mod_m = minutes - (hours * 60)
        mod_s = seconds - (hours * 60 * 60) # TODO
        mod_h = hours # TODO
        hms = f"{hours}h{mod_m}s{mod_s}"
        dhms = f"{days}d{mod_h}h{mod_m}m{mod_s}s"

        if elapsed_seconds < 60:
            template = self._settings.get(["message_template_under_60s"])
        elif minutes < 60:
            template = self._settings.get(["message_template_under_60m"])
        else:
            template = self._settings.get(["message_template_over_60m"])

        self.log.kv("Template tier",
            "under 60s" if elapsed_seconds < 60 else
            "under 60m" if minutes < 60 else
            "over 60m" if minutes >= 60 else
            "over 24h" if hours > 24
        )

        try:
            message = template.format(
                seconds=elapsed_seconds,
                minutes=minutes,
                hours=hours,
                hms=hms,
                dhms=dhms,
                mod_d=mod_d,
                mod_h=mod_h,
                mod_m=mod_m,
                mod_s=mod_s
            )
        except Exception as e:
            self.log.error(f"Template formatting error: {e}")
            return

        self.log.kv("Message", message)

        try:
            self._printer.commands([f"M117 {message}"])
        except Exception as e:
            self.log.error(f"M117 send failed: {e}")

    def get_template_configs(self):
        return [dict(type="settings", autoescape=True, custom_bindings=False)]

    def is_template_autoescaped(self):
        return True

__plugin_name__ = "Print Finished When"
__plugin_author__ = "Ed Cragg"
__plugin_description__ = "Periodically displays how long ago a print finished on the printer LCD"
__plugin_version__ = "0.2.4"
__plugin_license__ = "ISC"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_icon__ = "clock-o"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintFinishedWhenPlugin()

