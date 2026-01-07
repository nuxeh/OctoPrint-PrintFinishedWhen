# octoprint_idle_finished_reminder/__init__.py

import time
from octoprint.plugin import (
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin
)
from octoprint.events import Events
from octoprint.util import RepeatedTimer


class IdleFinishedReminderPlugin(
    SettingsPlugin,
    EventHandlerPlugin,
    TemplatePlugin
):
    def __init__(self):
        self._print_finished_at = None
        self._timer = None

    ## --- Settings ---

    def get_settings_defaults(self):
        return dict(
            enabled=True,
            interval_minutes=1,
            message_template="Print finished {minutes} minute(s) ago",
            send_lcd=True,
            send_popup=False
        )

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

    ## --- Messaging ---

    def _send_message(self):
        if self._printer.is_printing():
            self._stop_timer()
            return

        if not self._print_finished_at:
            return

        minutes = int((time.time() - self._print_finished_at) / 60)
        template = self._settings.get(["message_template"])
        message = template.format(minutes=minutes)

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
            dict(type="settings", custom_bindings=True)
        ]


__plugin_name__ = "Idle Finished Reminder"
__plugin_pythoncompat__ = ">=3.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = IdleFinishedReminderPlugin()

