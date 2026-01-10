from setuptools import setup

setup(
    name="OctoPrint-PrintFinishedWhen",
    version="0.2.3",
    description="Displays how long ago a print finished on the printer LCD",
    long_description=(
        "A minimal OctoPrint plugin that periodically sends M117 messages "
        "to the printer LCD showing how long ago a print finished."
    ),
    long_description_content_type="text/plain",
    author="Ed Cragg",
    url="https://github.com/nuxeh/OctoPrint-PrintFinishedWhen",
    license="ISC",
    python_requires=">=3.7,<4",
    packages=["octoprint_print_finished_when"],
    include_package_data=True,
    entry_points={
        "octoprint.plugin": [
            "print_finished_when = octoprint_print_finished_when"
        ]
    },
    zip_safe=False,
)

