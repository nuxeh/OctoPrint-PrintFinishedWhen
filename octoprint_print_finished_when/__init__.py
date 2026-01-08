import time
import logging
from logging.handlers import RotatingFileHandler
import os
from octoprint.plugin import (
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin,
    SimpleApiPlugin,
    AssetPlugin
)
from octoprint.events import Events
from octoprint.util import RepeatedTimer
from octoprint.server import admin_permission
from flask import jsonify


class PluginLogger:
    """Wrapper for cleaner logging throughout the plugin"""

    def __init__(self, logger):
        self._logger = logger

    def section(self, title):
        """Log a major section header"""
        self._logger.info(f"=== {title} ===")

    def subsection(self, title):
        """Log a subsection header"""
        self._logger.info(f"--- {title} ---")

    def event(self, message):
        """Log an event"""
        self._logger.info(f">> {message} <<")

    def highlight(self, message):
        """Log something important"""
        self._logger.info(f"*** {message} ***")

    def info(self, message):
        """Standard info message"""
        self._logger.info(f" {message}")

    def debug(self, message):
        """Debug message"""
        self._logger.debug(f" {message}")

    def warning(self, message):
        """Warning message"""
        self._logger.warning(f" {message}")

    def error(self, message):
        """Error message"""
        self._logger.error(f" {message}")

    def kv(self, key, value):
        """Log a key-value pair"""
        self._logger.info(f" {key}: {value}")


class PrintFinishedWhenPlugin(
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin,
    SimpleApiPlugin,
    AssetPlugin,
):
    def __init__(self):
        self._print_finished_at = None
        self._messages_active = False
        self._timer = None
        self._paused_at = None
        self._paused_duration = 0
        self.log = None  # Will be initialized in initialize()

    def initialize(self):
        """Called after plugin is initialized"""
        # Set up logging to ~/.octoprint/logs/plugin_print_finished_when.log
        logging_path = os.path.join(
            self._settings.getBaseFolder("logs"),
            "plugin_print_finished_when.log"
        )

        file_handler = RotatingFileHandler(
            logging_path,
            maxBytes=5*1024*1024,
            backupCount=3
        )

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)

        self._logger.addHandler(file_handler)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = True

        # Initialize our logging wrapper
        self.log = PluginLogger(self._logger)

        # Log initialization
        self.log.section("Print Finished When Plugin Initialized")
        self.log.kv("Log file", logging_path)
        self.print_settings()

    ## --- Settings ---

    def get_settings_defaults(self):
        return dict(
            enabled=True,
            interval_minutes=1,
            start_delay_minutes=5,
            message_template="Print finished {minutes} minute(s) ago",
            send_lcd=True,
            send_popup=False
        )

    def print_settings(self):
        self.log.kv("Enabled", self._settings.get_boolean(['enabled']))
        self.log.kv("Interval", f"{self._settings.get_int(['interval_minutes'])} minutes")
        self.log.kv("Start delay", f"{self._settings.get_int(['start_delay_minutes'])} minutes")
        self.log.kv("Send LCD", self._settings.get_boolean(['send_lcd']))
        self.log.kv("Send popup", self._settings.get_boolean(['send_popup']))

    def on_settings_save(self, data):
        if self.log:
            self.log.info("on_settings_save called")

        """Called when settings are saved"""
        SettingsPlugin.on_settings_save(self, data)

        if self.log:
            self.log.section("Settings Saved")
            self.print_settings()

            # If there's an active timer, restart it with new interval
            if self._timer and self._print_finished_at:
                self.log.info("Restarting timer with new settings")
                self._timer.cancel()
                interval = self._settings.get_int(["interval_minutes"]) * 60
                self.log.kv("New interval", f"{interval}s")
                self._timer = RepeatedTimer(interval, self._send_message, run_first=False)
                self._timer.start()
                self.log.info("Timer restarted")

    def get_assets(self):
        return {
            "js": ["js/print_finished_when.js"]
        }

    def is_template_autoescape(self):
        return True

    ## --- Events ---

    def on_event(self, event, payload):
        if not self.log:
            return

        self.log.section(f"Event: {event}")
        self.log.kv("Payload", payload)

        if event == Events.PRINT_DONE:
            self.log.event("PrintDone detected")
            self._on_print_done()

        elif event == Events.PRINT_PAUSED:
            self.log.event("PrintPaused detected")
            self._on_print_paused()

        elif event == Events.PRINT_RESUMED:
            self.log.event("PrintResumed detected")
            self._on_print_resumed()

        elif event in (
            Events.PRINT_STARTED,
            Events.PRINT_CANCELLED,
            Events.PRINT_FAILED
        ):
            self.log.event(f"{event} detected - resetting state")
            self._reset_state()

    def _on_print_paused(self):
        if self._paused_at is None:
            self._paused_at = time.time()
            self.log.info(f"Print paused at {self._paused_at}")
        else:
            self.log.warning("Pause event but already paused")

    def _on_print_resumed(self):
        if self._paused_at is not None:
            paused_for = time.time() - self._paused_at
            self._paused_duration += paused_for
            self._paused_at = None
            self.log.info(f"Resumed after {int(paused_for)}s (total: {int(self._paused_duration)}s)")
        else:
            self.log.warning("Resume event but not currently paused")

    def _on_print_done(self):
        self.log.subsection("Print Done Handler")

        enabled = self._settings.get_boolean(["enabled"])
        self.log.kv("Plugin enabled", enabled)

        if not enabled:
            self.log.info("Plugin disabled, skipping")
            return

        self._print_finished_at = time.time()
        self._paused_at = None
        self._paused_duration = 0
        self._messages_active = False

        self.log.kv("Print finished at", self._print_finished_at)

        self._stop_timer()

        interval = self._settings.get_int(["interval_minutes"]) * 60
        self.log.kv("Timer interval", f"{interval}s")

        self._timer = RepeatedTimer(interval, self._send_message, run_first=False)
        self._timer.start()

        self.log.highlight("Timer started")

    ## --- Timer ---

    def _stop_timer(self):
        self.log.subsection("Stop Timer")

        if self._timer:
            self.log.info("Cancelling timer")
            self._timer.cancel()
            self._timer = None
        else:
            self.log.info("No timer to cancel")

        # Don't clear _print_finished_at here - it's needed for the next timer!
        # Only clear when we truly want to reset everything
        self._messages_active = False

    def _reset_state(self):
        """Fully reset plugin state when starting/cancelling/failing a print"""
        self.log.subsection("Reset State")
        self._stop_timer()
        self._print_finished_at = None
        self._paused_at = None
        self._paused_duration = 0
        self.log.info("State reset complete")

    ## --- Messaging ---

    def _send_message(self):
        self.log.section("Send Message")

        if not self._printer:
            self.log.error("No printer object!")
            return

        is_printing = self._printer.is_printing()
        self.log.kv("Printer is printing", is_printing)

        if is_printing:
            self.log.info("Printer busy, stopping timer")
            self._stop_timer()
            return

        if not self._print_finished_at:
            self.log.warning("No print_finished_at time")
            return

        now = time.time()
        effective_elapsed = now - self._print_finished_at - self._paused_duration
        elapsed_minutes = int(effective_elapsed / 60)
        start_delay = self._settings.get_int(["start_delay_minutes"])

        self.log.kv("Elapsed minutes", elapsed_minutes)
        self.log.kv("Start delay", start_delay)

        if elapsed_minutes < start_delay:
            self.log.info(f"Waiting... ({elapsed_minutes} < {start_delay})")
            return

        if not self._messages_active:
            self._messages_active = True
            self.log.highlight(f"ACTIVATED after {start_delay} minutes")

        template = self._settings.get(["message_template"])
        message = template.format(minutes=elapsed_minutes)

        self.log.kv("Message", f"'{message}'")

        send_lcd = self._settings.get_boolean(["send_lcd"])
        send_popup = self._settings.get_boolean(["send_popup"])

        if send_lcd:
            gcode_cmd = f"M117 {message}"
            self.log.info(f"Sending: {gcode_cmd}")
            try:
                self._printer.commands([gcode_cmd])
                self.log.info("LCD command sent")
            except Exception as e:
                self.log.error(f"LCD error: {e}")

        if send_popup:
            self.log.info("Sending popup")
            try:
                self._plugin_manager.send_plugin_message(
                    self._identifier,
                    dict(text=message)
                )
                self.log.info("Popup sent")
            except Exception as e:
                self.log.error(f"Popup error: {e}")

    ## --- API ---

    def get_api_commands(self):
        return {"test_notification": []}

    def on_api_command(self, command, data):
        self.log.section(f"API Command: {command}")
        self.log.kv("Data", data)

        if command == "test_notification":
            if not admin_permission.can():
                self.log.warning("Insufficient permissions")
                return jsonify(error="Insufficient permissions"), 403

            self._send_test_message()
            return jsonify(success=True)

    def _send_test_message(self):
        self.log.subsection("Test Message")

        message = "Test: Print Finished When message"

        if not self._printer:
            self.log.error("No printer object!")
            return

        send_lcd = self._settings.get_boolean(["send_lcd"])
        send_popup = self._settings.get_boolean(["send_popup"])

        self.log.kv("Message", f"'{message}'")
        self.log.kv("Send LCD", send_lcd)
        self.log.kv("Send popup", send_popup)

        if send_lcd:
            gcode_cmd = f"M117 {message}"
            self.log.info(f"Sending: {gcode_cmd}")
            try:
                self._printer.commands([gcode_cmd])
                self.log.info("Test LCD sent")
            except Exception as e:
                self.log.error(f"Test LCD error: {e}")

        if send_popup:
            self.log.info("Sending test popup")
            try:
                self._plugin_manager.send_plugin_message(
                    self._identifier,
                    dict(text=message)
                )
                self.log.info("Test popup sent")
            except Exception as e:
                self.log.error(f"Test popup error: {e}")

    ## --- UI ---

    def get_template_configs(self):
        return [
            dict(type="settings", autoescape=True)
        ]

__plugin_name__ = "Print Finished When"
__plugin_author__ = "Ed Cragg"
__plugin_description__ = (
    "Sends periodic messages showing how long ago a print finished"
)
__plugin_version__ = "0.1.15"
__plugin_license__ = "ISC"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_icon__ = "clock-o"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintFinishedWhenPlugin()
