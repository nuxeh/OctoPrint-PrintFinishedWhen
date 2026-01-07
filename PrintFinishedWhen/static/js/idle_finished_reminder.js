$(function () {
    function IdleFinishedReminderViewModel(parameters) {
        var self = this;

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "idle_finished_reminder") return;

            if (data.text) {
                new PNotify({
                    title: "Print Finished",
                    text: data.text,
                    type: "info",
                    hide: true
                });
            }
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: IdleFinishedReminderViewModel,
        dependencies: [],
        elements: []
    });
});

