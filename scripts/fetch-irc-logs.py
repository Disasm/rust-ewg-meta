#!/usr/bin/env python3

import urllib.request
from datetime import datetime, timedelta
import re
import sys


def fetch_url(url):
    with urllib.request.urlopen(url) as response:
        data = response.read()
        return data.decode("utf-8")


def get_last_meeting_date():
    for i in range(1, 8):
        date = datetime.now() - timedelta(days=i)
        if date.weekday() == 1:  # Tuesday
            return date.date()


def main():
    # Deduce last meeting date
    date = get_last_meeting_date()
    #date = datetime.strptime("2019-03-19", "%Y-%m-%d")
    print("Last meeting date", date.strftime("%Y-%m-%d"))

    # Fetch meeting logs
    url = "https://mozilla.logbot.info/rust-embedded/%s/raw" % date.strftime("%Y%m%d")
    logs_data = fetch_url(url)

    leaders = ["japaric", "jamesmunns", "therealprof"]
    starts = ["let's start this meeting", "lets get this started", "let's get started"]
    ends = ["thanks everyone for attending", "and see you next week", "thanks to everyone for attending", "see you all next week"]

    rec = False
    meeting_lines = []
    for line in logs_data.split("\n"):
        if len(line) == 0:
            continue
        is_leader = any(["<"+nick+">" in line for nick in leaders])
        is_start = any([s.lower() in line.lower() for s in starts])
        is_end = any([s.lower() in line.lower() for s in ends])
        if is_leader and is_start:
            rec = True

        if rec:
            m = re.search(r'([0-9:]+) (<[^>]+>) (.*)', line)
            m2 = re.search(r'([0-9:]+) (\* [^ ]+) (.*)', line)
            if not m and m2:
                m = m2
            if m:
                time_str = m.group(1)
                tm = datetime.strptime(time_str, "%I:%M:%S")
                hour = (tm.hour + 12 + 1) % 24  # log timestamps are in 12-hour format and UTC+0 timezone, use CET instead
                full_dt = datetime(year=date.year, month=date.month, day=date.day, hour=hour, minute=tm.minute, second=tm.second)
                time_str = full_dt.strftime("%Y-%m-%d %H:%M:%S")
                nick = m.group(2)
                message = m.group(3)
                formatted_line = "%s\t%s\t%s" % (time_str, nick, message)
                meeting_lines.append(formatted_line)
            else:
                print("Unexpected line: '%s'" % line)

        if is_leader and is_end:
            rec = False
            break

    if rec:
        print("Can't find meeting ending!")
        sys.exit(1)

    filename = "%s.irc.log" % date.strftime("%Y-%m-%d")
    f = open(filename, 'wt')
    f.write("\n".join(meeting_lines))
    f.close()


if __name__ == "__main__":
    main()
