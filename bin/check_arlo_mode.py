"""Checks arlo modes and sends an email if the system is not in the appropriate mode."""

from argparse import ArgumentParser
from collections import namedtuple
from configparser import RawConfigParser
from datetime import datetime, timedelta
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from logging import basicConfig, getLogger, DEBUG, INFO
from smtplib import SMTP

from pyarlo import PyArlo

logger = getLogger(__name__)

__fmt_12 = '%I:%M %p'
__fmt_24 = '%H:%m'


ScheduleEntry = namedtuple("ScheduleEntry", field_names=['mode', 'start', 'end'])  # pylint: disable=invalid-name


def parse_args():
    """Parse command line arguments"""
    parser = ArgumentParser(description='Arlo mode monitor')

    parser.add_argument('config', help='Configuration file', type=str, default="./twitter.cfg")

    parser.add_argument('-g', '--gen', help='Generate basic configuration file', type=str)
    parser.add_argument('-v', '--verbose', help='Verbose logs', default=False, action='store_true')

    return parser.parse_args()


def main():
    """Simple runnable main function"""
    logging_config = dict(level=INFO,
                          format='[%(asctime)s - %(filename)s:%(lineno)d - %(funcName)s - %(levelname)s] %(message)s')
    basicConfig(**logging_config)

    args = parse_args()

    if args.verbose:
        getLogger('').setLevel(DEBUG)

    config = RawConfigParser()
    config.read(args.config)

    username = config.get('arlo', 'username')
    password = config.get('arlo', 'password')

    arlo = PyArlo(username, password)
    schedule = build_schedule(config)
    smtp_manager = make_smtp_manager(config)

    recipients = config.get('email', 'recipients')

    if ',' in recipients:
        recipients = [r for r in map(str.strip, recipients.split(','))]
    else:
        recipients = [recipients]

    # assuming all base stations are on the same schedule.
    for station in arlo.base_stations:
        logger.info('Checking base station: %s', station.device_id)
        station_mode = station.mode

        found_entry = find_entry(schedule)
        check_station_mode(smtp_manager, found_entry, station_mode, smtp_manager.username, recipients)


def build_schedule(config):
    """Build schedule list of times from config file."""
    schedule_basename = 'schedule'

    entries = config.get(schedule_basename, 'entries').strip()
    clock_type = config.getint(schedule_basename, 'clock')

    if ',' in entries:
        entries = map(str.strip, entries.split(','))
    else:
        entries = [entries]

    selected_fmt = __fmt_12

    if clock_type == 24:
        selected_fmt = __fmt_24

    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    schedule = []

    for entry in entries:
        section_name = schedule_basename + '_' + entry

        mode = config.get(section_name, 'mode')
        start = datetime.strptime(config.get(section_name, 'start'), selected_fmt)
        end = datetime.strptime(config.get(section_name, 'end'), selected_fmt)

        start = start.replace(year=now.year, month=now.month, day=now.day, second=0, microsecond=0)
        end = end.replace(year=now.year, month=now.month, day=now.day, second=0, microsecond=0)

        # if end is start of day timestamp, assume end is actually end of day.
        if end == start_of_day:
            end = end + timedelta(days=1)

        logger.debug("%s - %s -> %s", mode, start, end)

        schedule_entry = ScheduleEntry(mode=mode,
                                       start=start,
                                       end=end)

        schedule.append(schedule_entry)

    return schedule


def find_entry(schedule):
    """Finds the current entry in the schedule."""
    now = datetime.now()
    found_entry = None
    for entry in schedule:
        # print(entry.start.strftime(_fmt_12), entry.end.strftime(_fmt_12))
        if entry.start <= now < entry.end:
            found_entry = entry

    # print('found', found_entry.start.strftime(_fmt_12), found_entry.end.strftime(_fmt_12))
    if found_entry is None:
        raise RuntimeError('Entry not found.')
    return found_entry


def check_station_mode(smtp_manager, found_entry, station_mode, originator, notification_recipients):
    """Checks the station mode against the one found in the schedule."""
    logger.info("Expect Arlo to be in mode %s, its in %s", found_entry.mode, station_mode)
    if found_entry.mode.lower() == station_mode.lower():
        logger.info('Arlo is in the expected mode.')
    else:
        logger.info('Arlo is not in the expected mode.  Notifying someone.')

        content = 'Arlo in {0} should be {1}'.format(station_mode, found_entry.mode)

        with smtp_manager as smtp:
            msg = MIMEText(content, 'plain')
            msg['From'] = originator
            msg['To'] = ", ".join(notification_recipients)
            msg['Subject'] = content

            logger.info("sending messages to %s", notification_recipients )

            smtp.sendmail(msg['From'], notification_recipients, msg.as_string())
            logger.info('Notification sent')


def make_smtp_manager(config):
    """Create a SMTP context manager."""
    username = config.get("email", "smtp_username")
    password = config.get("email", "smtp_password")
    server = config.get("email", "smtp_server")
    port = config.getint("email", "smtp_port")

    return SMTPManager(username, password, server, port)


class SMTPManager(object):
    """SMTP context manager."""

    def __init__(self, username: str, password: str, server: str, port: int):
        self._server = server
        self._port = port
        self._username = username
        self._password = password
        self._connection = None

        logger.debug("Created SMTP Sender.")

    @property
    def username(self):
        """Retrieve the username that will be used to log into the smtp server"""
        return self._username

    @property
    def server(self):
        """The SMTP server"""
        return self._server

    @property
    def port(self):
        """THe SMTP port"""
        return self._port

    def __enter__(self):
        """Connect to the server, prepare to send."""
        logger.debug("Connecting to SMTP server")
        self._connection = SMTP(self._server, self._port)
        logger.debug("Connected to SMTP server")

        self._connection.ehlo()
        self._connection.starttls()
        self._connection.ehlo()
        self._connection.login(self._username, self._password)
        logger.debug("Logged into SMTP server")
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from the server."""
        logger.debug("Disconnecting from SMTP server")
        self._connection.quit()
        self._connection = None

    def send(self, message: MIMEBase):
        """Send the message using the server."""
        if self._connection is None:
            raise RuntimeError('Not connected to smtp server')

        self._connection.sendmail(message['From'], [message['To']], message.as_string())

    def __str__(self):
        """String representation"""
        return "{0}(username={1._username}, server={1._server}, port={1._port})".format(self.__class__.__name__, self)


if __name__ == '__main__':
    main()
