from setuptools import setup

setup(
    name="OctoPrint-PrintFinishedWhen",
    version="0.1.0",
    description="Repeats a reminder/messages to LCD showing how long ago a print finished",
    author="Ed Cragg",
    license="AGPLv3",
    packages=["octoprint_idle_finished_reminder"],
    include_package_data=True,
    entry_points={
        "octoprint.plugin": [
            "idle_finished_reminder = octoprint_idle_finished_reminder"
        ]
    },
)

