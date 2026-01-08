$(function () {
    console.log("Print Finished When: JavaScript loading...");

    function PrintFinishedWhenViewModel(parameters) {
        var self = this;

        console.log("Print Finished When: ViewModel constructor called");
        console.log("Print Finished When: Parameters:", parameters);

        self.settings = parameters[0];

        console.log("Print Finished When: Settings:", self.settings);

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            console.log("Print Finished When: Plugin message received:", plugin, data);

            if (plugin !== "print_finished_when") {
                console.log("Print Finished When: Ignoring message from other plugin");
                return;
            }

            if (data.text) {
                console.log("Print Finished When: Showing notification:", data.text);
                new PNotify({
                    title: "Print Finished",
                    text: data.text,
                    type: "info",
                    hide: true
                });
            }
        };

        self.testNotification = function () {
            console.log("=== Print Finished When: Test notification button clicked ===");
            console.log("Print Finished When: Calling simpleApiCommand...");

            OctoPrint.simpleApiCommand(
                "print_finished_when",
                "test_notification"
            ).done(function(response) {
                console.log("Print Finished When: API call SUCCESS:", response);
            }).fail(function(xhr, status, error) {
                console.error("Print Finished When: API call FAILED");
                console.error("Print Finished When: Status:", status);
                console.error("Print Finished When: Error:", error);
                console.error("Print Finished When: Response:", xhr.responseText);
            });
        };

        console.log("Print Finished When: ViewModel initialized successfully");
    }

    console.log("Print Finished When: Registering viewmodel...");

    OCTOPRINT_VIEWMODELS.push({
        construct: PrintFinishedWhenViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_print_finished_when"]
    });

    console.log("Print Finished When: Viewmodel registered");
});
