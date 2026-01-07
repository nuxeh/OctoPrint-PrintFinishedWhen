# octoprint_print_finished_when/__init__.py

import time
from octoprint.plugin import (
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin
)
from octoprint.events import Events
from octoprint.util import RepeatedTimer

class PrintFinishedWhenPlugin(
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin,
):
    def __init__(self):
        self._print_finished_at = None
        self._messages_active = False
        self._timer = None

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

    def get_assets(self):
        return {
            "js": ["js/print_finished_when.js"]
        }

    def is_template_autoescape(self):
        return True

    ## --- Events ---

    def on_event(self, event, payload):
        if event == Events.PRINT_DONE:
            self._on_print_done()

        elif event in (
            Events.PRINT_STARTED,
            Events.PRINT_CANCELLED,
            Events.PRINT_FAILED
        ):
            self._stop_timer()

    def _on_print_done(self):
        if not self._settings.get_boolean(["enabled"]):
            return

        self._print_finished_at = time.time()
        self._messages_active = False
        self._start_timer()

    ## --- Timer ---

    def _start_timer(self):
        if self._timer:
            return

        interval = self._settings.get_int(["interval_minutes"]) * 60

        self._timer = RepeatedTimer(
            interval,
            self._send_message,
            run_first=False
        )
        self._timer.start()

    def _stop_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._print_finished_at = None
        self._messages_active = False

    ## --- Messaging ---

    def _send_message(self):
        if self._printer.is_printing():
            self._stop_timer()
            return

        if not self._print_finished_at:
            return

        elapsed_minutes = int((time.time() - self._print_finished_at) / 60)

        start_delay = self._settings.get_int(["start_delay_minutes"])

        # Not time yet, do nothing
        if elapsed_minutes < start_delay:
            return

        # Activate messages
        if not self._messages_active:
            self._messages_active = True
            self._send_message()
            self._logger.info(
                f"Print Finished When started after {start_delay} minutes"
            )

        template = self._settings.get(["message_template"])
        message = template.format(minutes=elapsed_minutes)

        if self._settings.get_boolean(["send_lcd"]):
            self._printer.commands([f"M117 {message}"])

        if self._settings.get_boolean(["send_popup"]):
            self._plugin_manager.send_plugin_message(
                self._identifier,
                dict(text=message)
            )

    ## --- UI ---

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True, autoescape=True)
        ]

__plugin_name__ = "Print Finished When"
__plugin_author__ = "Ed Cragg"
__plugin_description__ = (
    "Sends periodic messages showing how long ago a print finished"
)
__plugin_version__ = "0.1.0"
__plugin_license__ = "ISC"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_icon__ = "clock-o"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintFinishedWhenPlugin()

