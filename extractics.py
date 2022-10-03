"""Extract Open Timetables information to an ICS / iCalendar file from a list of module codes"""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2022 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2022-10-03'  # ISO 8601 (YYYY-MM-DD)

import argparse
import asyncio
import datetime
import json
import os

import aiohttp
import icalendar

# you can update these values if needed, but they should work for all Swansea University courses
BASE_URL = 'https://opentimetables.swan.ac.uk/'
BASE_UUID = '525fe79b-73c3-4b5c-8186-83c652b3adcc'
AUTHORISATION_HEADER = 'basic kR1n1RXYhF'

OUTPUT_FILE = f"{os.path.dirname(os.path.realpath(__file__))}/timetable.ics"

REQUEST_HEADERS = {
    'Content-Type': 'application/json; charset=utf-8',
    'Authorization': AUTHORISATION_HEADER
}


class OpenTimetablesICS:
    def __init__(self, period):
        self.event_template = self.load_event_template(period)

    @staticmethod
    def load_event_template(period='year'):
        print('Loading event period template', period)
        with open(f"{os.path.dirname(os.path.realpath(__file__))}/templates/{period}.json") as f:
            return json.load(f)

    @staticmethod
    async def get_identifiers(session, module_codes):
        module_identifiers = {}

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
                        print('\tWarning: found more than one page of results; additional pages will be skipped')

            if not success:
                print(f"\tWarning: module {module_code} not found at {BASE_URL}; skipping")

        return module_identifiers

    @staticmethod
    async def get_timetable(session, event_template, identifier):
        event_template['CategoryIdentities'] = [identifier]
        timetable = None
        async with session.post(f"{BASE_URL}broker/api/categoryTypes/{BASE_UUID}/categories/events/filter",
                                headers=REQUEST_HEADERS, json=event_template) as request:
            if request.status == 200:
                timetable = await request.json()
        return timetable

    async def generate_ical(self, module_codes, output_file):
        calendar = icalendar.Calendar()
        calendar.add('x-wr-calname', f"Lectures for modules {', '.join(module_codes)}")
        calendar.add('last-modified', datetime.datetime.now())

        session = aiohttp.ClientSession()
        module_identifiers = await self.get_identifiers(session, module_codes)
        print('Downloading timetables for', len(module_identifiers), 'modules')

        for name, identifier in module_identifiers.items():
            timetable = await self.get_timetable(session, self.event_template.copy(), identifier)
            if not timetable:
                print(f"\tWarning: timetable for module {name} not found at {BASE_URL}; skipping")
                continue

            event_count = 0
            for opentimetables_event in timetable[0]['CategoryEvents']:
                event = icalendar.Event()
                event.add('summary', opentimetables_event['Name'])
                event.add('dtstart', datetime.datetime.fromisoformat(opentimetables_event['StartDateTime']))
                event.add('dtend', datetime.datetime.fromisoformat(opentimetables_event['EndDateTime']))

                description = f"Module name: {name}\nEvent type: {opentimetables_event['EventType']}"
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

        print('Saving activities to', output_file)
        with open(output_file, 'wb') as f:
            f.write(calendar.to_ical())

        await session.close()


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-m', '--modules', nargs='+', help='[Required] A list of module codes separated by spaces',
                            required=True)
    arg_parser.add_argument('-p', '--period', default='year', help='The time period to include in the output. Valid '
                                                                   'options are `year`, `s1` (i.e., Semester 1) or '
                                                                   '`s2` (Semester 2). Default: `year`')
    arg_parser.add_argument('-o', '--output-file', default=OUTPUT_FILE, help=f"The full path to an ICS file to save "
                                                                             f"output. Default: `{OUTPUT_FILE}` in the "
                                                                             f"same directory as this script")
    arg_parser.add_argument('--version', action='version', version=__version__)
    args = arg_parser.parse_args()

    timetable_parser = OpenTimetablesICS(args.period)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(timetable_parser.generate_ical(args.modules, args.output_file))
