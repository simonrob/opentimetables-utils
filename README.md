| Note: With the release of the updated Open Timetables service (now renamed to [My Timetable](https://mytimetable.swan.ac.uk/timetables)) that allows linking to specific activities and locations, and a personalised timetable view, this repository is no-longer required in most cases. |
|-|

---

# Open Timetables Utilities
[Open Timetables](http://opentimetables-help.azurewebsites.net/1.0/Content/Home.htm) allows institutions to easily provide public-facing timetables for all programmes.
But it can be very difficult to extract data from its timetable display, and time-consuming to repeatedly adjust its interface to request schedule details.
This repository contains utilities to help make this task easier.

You can [run the `Extract ICS data` script online](https://simonrob.github.io/opentimetables-utils/) if needed (via Gitpod; account required).


## Disclaimer
Double-check any outputs provided by these tools against the Open Timetables display to ensure accuracy.
You are responsible for checking that results are correct.


## Installation
After cloning or [downloading](https://github.com/simonrob/opentimetables-utils/archive/refs/heads/main.zip) this repository, start by installing requirements:

```shell
python -m pip install -r requirements.txt
```

Python 3.7 or later is required.


## Tools
### Extract ICS data (extractics.py)
Generate an ICS (iCalendar) file from Open Timetables for a given list of module codes:

```shell
python extractics.py -m CSCM69 CSCM45 CSPM40
```

Alternatively, use an online viewer to show the timetable for, say, next week:

```shell
python extractics.py -m CSCM69 -p next -o view
```

Or use `paste` mode to (attempt to) automatically extract codes from a table of module selections:

```shell
python extractics.py -m paste -o view
```

The `--cache` option is a one-time (per module catalogue update) operation to download and locally save module data, making it quicker to try broader queries. For example to show all Computer Science second-year modules this week:
```shell
python extractics.py --cache --modules CS-2 -p week -o view
```

You can configure the script's behaviour via the following optional arguments:
- `-m` or `--modules`: A list of module codes separated by spaces. Use the magic value `paste` and the script will prompt you to paste a list then do (very basic) automatic module code matching from, e.g., a module selection table.
- `-p` or `--period`: The time period to include in the output. Valid options are `year`, `s1` (i.e., Semester 1), `s2` (Semester 2), `today`, `week` (current week) or `next` (next week). Default: `year` (i.e., all known events).
- `-o` or `--output-file`: The full path to an ICS file to save output, or the magic value `view` to open the ICS output in an [online viewer](https://simonrob.github.io/online-ics-feed-viewer/).
Default: `timetable.ics` in the same directory as the script.
- `-c` or `--cache-modules`: Downloads and caches (for future use) the full list of available modules and identifiers into a local file, which speeds up future timetable requests.
A cache file is automatically used if present; this option is only needed to trigger the initial cache generation, which will take some time.

The environment variables `OT_MODULES`, `OT_PERIOD` and `OT_OUTPUT` can be used to pass the `-m`, `-p` and `-o` options, respectively.
This configuration method is provided to support running the script [online](https://simonrob.github.io/opentimetables-utils/).


## Limitations and caveats
Module code searching is actually a string match on the module/course title (as codes are not provided anywhere else).
So, including a module that shares a prefix with others will include all matches.
Avoid this if needed by also appending the occurrence string (e.g., `CSCM69_A`).

It would be relatively little extra effort to expand capabilities to cover both programme-specific module collections (which are somewhat error-prone) and venue timetables, but these actions are just about manageable in Open Timetables, so not currently implemented.
If you would benefit from these features, please feel free to [open an issue](https://github.com/simonrob/opentimetables-utils/issues) (or submit a pull request).

Calendar applications often import events from local ICS files rather than treating them as an updatable stream.
Events exported using this repository's tools are given persistent unique IDs, which should allow re-importing if schedules change.
However, if your timetabled events are likely to change and your calendar viewer does not easily support re-importing, you may find it beneficial to set up the script to fetch events on a regular basis and store the resulting ICS file on a web server (or, e.g., Dropbox) that you can subscribe to.

The default configuration in this repository is for Swansea University timetables and modules, but this can be configured by editing script global variables.
Use a browser's developer tools to inspect and retrieve the correct configuration for your institution.

## License
[Apache 2.0](LICENSE)
