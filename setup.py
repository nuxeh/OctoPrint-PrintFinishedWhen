from setuptools import setup

setup(
    name="OctoPrint-PrintFinishedWhen",
    version="0.1.8",
    description="Sends periodic messages showing how long ago a print finished",
    long_description="A lightweight OctoPrint plugin that periodically "
                     "notifies you how long ago a print finished, with LCD M117 support.",
    author="Ed Cragg",
    url="https://github.com/nuxeh/OctoPrint-PrintFinishedWhen",
    license="ISC",
    packages=["octoprint_print_finished_when"],
    include_package_data=True,
    entry_points={
        "octoprint.plugin": [
            "print_finished_when = octoprint_print_finished_when"
        ]
    },
    zip_safe=False,
)

