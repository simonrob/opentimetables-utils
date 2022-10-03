# Open Timetables Utilities
Open Timetables allows institutions to easily provide public-facing timetables for all programmes. But it can be very difficult to extract data from its timetable display, and time-consuming to repeatedly adjust its interface to request schedule details. This repository contains utilities to help make this easier.

## Disclaimer
Double-check any outputs provided by these tools against the Open Timetables display to ensure accuracy. You are responsible for checking that results are correct.


## Installation
After cloning or [downloading](https://github.com/simonrob/opentimetables-utils/archive/refs/heads/main.zip) this repository, start by installing requirements:

```shell
python -m pip install -r requirements.txt
```

## Tools
### extractics.py
Generate an ICS (iCalendar) file from Open Timetables for a given list of module codes:

```shell
python extractics.py -m CSCM69 CSCM45 CSPM40
```

You can configure the script's behaviour via the following optional arguments:
- `-m` or `--modules`: A list of module codes separated by spaces.
- `-p` or `--period`: The time period to include in the output. Valid options are `year`, `s1` (i.e., Semester 1) or `s2` (Semester 2). Default: `year`.
- `-o` or `--output-file`: The full path to an ICS file to save output. Default: `timetable.ics` in the same directory as the script.


## Limitations and caveats
Module code searching is actually a string match on the module/course title (as codes are not provided anywhere else). So, including a module that shares a prefix with others will include all matches. Avoid this if needed by also appending the occurrence string (e.g., `CSCM69_A`).


## License
[Apache 2.0](LICENSE)
