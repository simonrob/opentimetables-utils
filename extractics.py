"""Extract Open Timetables information to an ICS / iCalendar file from a list of module codes"""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2022 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2022-10-04'  # ISO 8601 (YYYY-MM-DD)

import argparse
import asyncio
import base64
import datetime
import io
import json
import os
import re
import sys
import urllib.parse
import webbrowser

import aiohttp
import icalendar

# you can update these values if needed, but they should work for all Swansea University courses
BASE_URL = 'https://opentimetables.swan.ac.uk/'
BASE_UUID = '525fe79b-73c3-4b5c-8186-83c652b3adcc'
AUTHORISATION_HEADER = 'basic kR1n1RXYhF'

BASE_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
OUTPUT_FILE = f"{BASE_DIRECTORY}/timetable.ics"
CACHE_FILE = f"{BASE_DIRECTORY}/module-cache.json"

REQUEST_HEADERS = {
    'Content-Type': 'application/json; charset=utf-8',
    'Authorization': AUTHORISATION_HEADER
}

E_START = '\u001b[31m'
E_END = '\u001b[0m'


class OpenTimetablesICS:
    def __init__(self, period):
        self.event_template = self.load_event_template(period)

    @staticmethod
    def load_event_template(period='year'):
        """Timetable queries use a JSON template to specify the event period we are interested in"""
        print(f"Loading event period template `{period}`")

        period_name = 'week' if period == 'next' else period  # week templates share the same root
        period_file = f"{BASE_DIRECTORY}/templates/{period_name}.json"

        if not os.path.exists(period_file):
            print(f"\t{E_START}Error: time period template `{period}` not found; exiting{E_END}")
            sys.exit(1)

        with open(period_file) as f:
            period_template = json.load(f)

        if period_name == 'week' or period_name == 'today':
            today = datetime.date.today()
            start_date = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(
                days=7 if period == 'next' else 0)
            formatted_start_date = start_date.isoformat() + 'T00:00:00.000Z'
            period_template['ViewOptions']['Weeks'][0]['FirstDayInWeek'] = formatted_start_date
            if period_name == 'today':
                current_day = today.weekday() + 1  # Monday is day 1 in Open Timetables; 0 in Python
                period_template['ViewOptions']['Days'][0]['DayOfWeek'] = current_day
                print(f"\tInitialised template to {formatted_start_date} (day {current_day})")
            else:
                print(f"\tInitialised template to {formatted_start_date} (one week)")
        else:
            # TODO: dynamic year and semester templates by calculating week dates? (currently needs annual updates)
            pass

        return period_template

    @staticmethod
    async def get_modules(session, page):
        """Get a single page of the module name/identity list"""
        request_template = [{"Identity": "a6b2d3ea-c138-436d-9a43-d09a995f7269", "Values": ["null"]}]
        modules = None
        async with session.post(f"{BASE_URL}broker/api/CategoryTypes/{BASE_UUID}/Categories/Filter?pageNumber={page}",
                                headers=REQUEST_HEADERS, json=request_template) as request:
            if request.status == 200:
                modules = await request.json()
        return modules

    @staticmethod
    async def cache_modules():
        """Request all pages of the module name/identity list (via get_modules()) and save to CACHE_FILE"""
        async with aiohttp.ClientSession() as session:
            first_page = await OpenTimetablesICS.get_modules(session, 1)
            if not first_page:
                print(f"\t{E_START}Warning: unable to load module list to cache; skipping task{E_END}")
            cache = first_page['Results']

            print('\tCaching module page 1', end='')
            for page in range(1, first_page['TotalPages'] + 1):
                print(f", {page}", end='', flush=True)
                page_results = await OpenTimetablesICS.get_modules(session, page)
                if page_results:
                    cache.extend(page_results['Results'])
                else:
                    print(f"\n\t{E_START}Warning: failed to load and cache page {page} of module list{E_END}")

            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=4)
            print('\n\tCaching complete with', len(cache), 'results; expected:', first_page['Count'])

    @staticmethod
    async def get_identifiers(session, module_codes):
        """Each module has an identifier that can be retrieved through a search-type interface (or our cache)"""
        module_identifiers = {}

        if os.path.exists(CACHE_FILE):
            print('Loading module identifiers from cache file', CACHE_FILE)
            with open(CACHE_FILE) as cached_identifiers:
                cache = json.load(cached_identifiers)
            for module_code in module_codes:
                for module in cache:
                    if module_code in module['Name']:
                        # note: we don't break here to keep the same match behaviour as the online filter
                        module_identifiers[module['Name']] = module['Identity']
                        print('\tAdding module result', module['Name'], ':', module['Identity'])
            return module_identifiers

        for module_code in module_codes:
            print(f"Searching for `{module_code}`:")
            success = False
            async with session.post(
                    # note: this search does not have to be module codes; keywords also work but are far less reliable
                    f"{BASE_URL}broker/api/CategoryTypes/{BASE_UUID}/Categories/Filter?query={module_code}",
                    headers=REQUEST_HEADERS) as request:

                if request.status == 200:
                    data = await request.json()
                    if data['Results']:
                        success = True
                        for result in data['Results']:
                            name = result['Name']
                            identity = result['Identity']
                            print('\tAdding module result', name, ':', identity)
                            module_identifiers[name] = identity
                    if data['TotalPages'] > 1:
                        print(f"\t{E_START}Warning: found more than one page of results; additional pages will be",
                              f"skipped{E_END}")

            if not success:
                print(f"\t{E_START}Warning: module {module_code} not found at {BASE_URL}; skipping{E_END}")

        return module_identifiers

    @staticmethod
    async def get_timetable(session, event_template, identifier):
        """Retrieve the actual timetable information using a period template and module identifier"""
        event_template['CategoryIdentities'] = [identifier]
        timetable = None
        async with session.post(f"{BASE_URL}broker/api/categoryTypes/{BASE_UUID}/categories/events/filter",
                                headers=REQUEST_HEADERS, json=event_template) as request:
            if request.status == 200:
                timetable = await request.json()
        return timetable

    async def generate_ical(self, module_codes, output_file):
        """Request timetables for the given list of module_codes, and save to output_file (or `view` in a browser)"""
        calendar_title = f"Lectures for modules {', '.join(module_codes)}"
        calendar = icalendar.Calendar()
        calendar.add('version', '2.0')
        calendar.add('prodid', 'https://github.com/simonrob/opentimetables-utils')
        calendar.add('method', 'PUBLISH')
        calendar.add('last-modified', datetime.datetime.now())
        calendar.add('x-wr-calname', calendar_title)

        async with aiohttp.ClientSession() as session:
            module_identifiers = await OpenTimetablesICS.get_identifiers(session, module_codes)
            print('Downloading timetables for', len(module_identifiers), 'matching modules')

            for name, identifier in module_identifiers.items():
                timetable = await OpenTimetablesICS.get_timetable(session, self.event_template.copy(), identifier)
                if not timetable:
                    print(f"\t{E_START}Warning: timetable for module {name} not found at {BASE_URL}; skipping{E_END}")
                    continue

                event_count = 0
                for opentimetables_event in timetable[0]['CategoryEvents']:
                    event = icalendar.Event()
                    event.add('summary', name)
                    event.add('dtstart', datetime.datetime.fromisoformat(opentimetables_event['StartDateTime']))
                    event.add('dtend', datetime.datetime.fromisoformat(opentimetables_event['EndDateTime']))
                    event.add('uid', opentimetables_event['EventIdentity'])

                    description = f"Module code(s): {opentimetables_event['Name']}"
                    description += f"\nModule name: {name}\nEvent type: {opentimetables_event['EventType']}"
                    if opentimetables_event['Location']:
                        event.add('location', opentimetables_event['Location'])
                        description += f"\nLocation: {opentimetables_event['Location']}"
                    for event_property in opentimetables_event['ExtraProperties']:
                        if event_property['DisplayName'] == 'Photo':
                            description += f"\nVenue photo: {event_property['Value']}"
                    event.add('description', description)

                    calendar.add_component(event)
                    event_count += 1

                print('\tAdded', event_count, 'scheduled activities for', name)

            if output_file == 'view':
                print('Opening ICS viewer with timetable output')
                ical_bytes = io.BytesIO(calendar.to_ical()).getvalue()
                encoded_ics = urllib.parse.quote(base64.b64encode(ical_bytes))
                encoded_title = urllib.parse.quote(calendar_title)
                webbrowser.open(f"https://simonrob.github.io/online-ics-feed-viewer/#file={encoded_ics}"
                                f"&title={encoded_title}&hideinput=true&view=agendaWeek")
            else:
                print('Saving activities to', output_file)
                with open(output_file, 'wb') as f:
                    f.write(calendar.to_ical())


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-m', '--modules', nargs='+', help='[Required] A list of module codes separated by spaces, '
                                                               'or the magic value `paste` to be prompted to paste a '
                                                               'list from, e.g., a module selection table',
                            required=True)
    arg_parser.add_argument('-p', '--period', default='year', help='The time period to include in the output. Valid '
                                                                   'options are `year`, `s1` (i.e., Semester 1), `s2` '
                                                                   '(Semester 2), `today`, `week` (current week) or '
                                                                   '`next` (next week). Default: `year` (i.e., all'
                                                                   'known events')
    arg_parser.add_argument('-o', '--output-file', default=OUTPUT_FILE, help=f"The full path to an ICS file to save "
                                                                             f"output, or the magic value `view` to "
                                                                             f"open the ICS output in an online viewer "
                                                                             f". Default: `{OUTPUT_FILE}` in the same "
                                                                             f"directory as this script")
    arg_parser.add_argument('-c', '--cache-modules', action='store_true', help=f"Downloads and caches (for future use) "
                                                                               f"the full list of available modules "
                                                                               f"and identifiers into {CACHE_FILE}")
    arg_parser.add_argument('--version', action='version', version=__version__)
    args = arg_parser.parse_args()

    loop = asyncio.get_event_loop()
    timetable_parser = OpenTimetablesICS(args.period)

    if args.cache_modules:
        if os.path.exists(CACHE_FILE):
            print(f"Found existing cache file; skipping cache building (delete {CACHE_FILE} and re-run to regenerate)")
        else:
            try:
                loop.run_until_complete(timetable_parser.cache_modules())
            except aiohttp.ClientConnectorError:
                print(f"\t{E_START}Error caching module information - is there an internet connection?{E_END}")
                sys.exit(1)

    if args.modules == ['paste']:
        print('Please paste a list of module codes then press enter: ')
        pasted_modules = []
        while True:
            line = input()
            if line:
                # try to match the various displays of module selections
                match = re.match(r'^(?P<prefix>\w+\t)?(?P<code>[A-Z]+-?[A-Z]?\d+[A-Z]?)\t(?(prefix)\w|/)', line)
                if match:
                    matched_code = match.group('code')
                    if matched_code not in pasted_modules:
                        pasted_modules.append(matched_code)
            else:
                break
        if pasted_modules:
            args.modules = sorted(pasted_modules)
        else:
            print(f"\t{E_START}Error: unable to detect any module codes in pasted input; exiting{E_END}")
            sys.exit(1)

    print(f"Generating timetables for modules {args.modules}")

    try:
        loop.run_until_complete(timetable_parser.generate_ical(args.modules, args.output_file))
    except aiohttp.ClientConnectorError:
        print(f"\t{E_START}Error retrieving timetable information - is there an internet connection?{E_END}")
