$(function () {
    function PrintFinishedWhenViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "print_finished_when") return;

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

    self.testNotification = function () {
        console.log("Test notification button clicked");
        OctoPrint.simpleApiCommand(
            "print_finished_when",
            "test_notification"
        );
    };

    OCTOPRINT_VIEWMODELS.push({
        construct: PrintFinishedWhenViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_print_finished_when"]
    });
});

