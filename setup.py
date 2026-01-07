from setuptools import setup

setup(
    name="OctoPrint-PrintFinishedWhen",
    version="0.1.0",
    description="Repeats a reminder/messages to LCD showing how long ago a print finished",
    author="Ed Cragg",
    license="AGPLv3",
    packages=["octoprint_print_finished_when"],
    include_package_data=True,
    entry_points={
        "octoprint.plugin": [
            "print_finished_when = octoprint_print_finished_when"
        ]
    },
)

