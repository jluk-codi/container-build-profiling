import sys
import re
import json
import yaml
import argparse
import traceback


def parse_command(line):
    line_regex = '^#\d+ +name: .*$'
    if re.match(line_regex, line):
        cmd = ' '.join(line.split()[3:])[:-1]
    else:
        cmd = None
    return cmd


def parse_duration(line):
    line_regex = '^#\d+ +duration: +((?P<minutes>\d+(\.\d+)?)m)?((?P<seconds>\d+(\.\d+)?)s)?((?P<milliseconds>\d+.(\d+)?)ms)?[^s]'
    line_regex = '^#\d+ +duration: +((?P<minutes>\d+(\.\d+)?)m)?((?P<seconds>\d+(\.\d+)?)s)?((?P<milliseconds>\d+.(\d+)?)ms)?$'
    match = re.match(line_regex, line)
    seconds = 0.0
    if match:
        matches = match.groupdict()
        seconds += float(matches.get('minutes', 0) or 0) * 60
        seconds += float(matches.get('seconds', 0) or 0)
    return int(round(seconds))


def parse_image_name(line):
    line_regex = '^#\d+ +naming to .*$'
    if re.match(line_regex, line):
        name = line.split()[3]
    else:
        name = None
    return name


def split_image_url(url):
    parts = url.split('/')
    host = None
    if len(parts) > 1:
        host = parts[0]
        del parts[0]
    name, tag = parts[-1].split(':')
    return { 'host': host, 'name': name, 'tag': tag } 


def parse_build_log(path='./build_log'):
    log = None
    with open(path, 'r') as build_log_file:
        log = build_log_file.read()
    return parse_build_log_from_string(log)


def parse_build_log_from_string(log):
    lines = None
    name = None
    lastline = '#0 duration: 0s'
    current_stepnum = 0
    buildstep = False
    # [{'command': 'RUN abc', 'duration': 300}] (seconds)
    result = []
    steps = {}
    lines = log.splitlines()
    for l in lines:
        if len(l.strip()) == 0:
            buildstep = False
            result.append({'command': None})
            continue
        if l[0] == '#':
            stepnum = int(l[1:].split()[0])
            if stepnum not in steps:
                steps[stepnum] = {'buildstep': False, 'command': None}
            step = steps[stepnum]
            if stepnum > current_stepnum:
                current_stepnum = stepnum
            if re.match('^#\d+ +\[\d+/\d+\] +', l):
                step['buildstep'] = True
            if step['buildstep']:
                cmd = parse_command(l)
                if cmd is not None:
                    result[-1]['command'] = cmd
                    step['command'] = cmd
            duration = parse_duration(l)
            if duration is not None:
                result[-1]['duration'] = duration
                step['duration'] = duration
            name = name or parse_image_name(l)
        elif l.startswith('real '):
            total = int(round(float(l.split()[1])))
            break
    # filtering only true Dockerfile command entries
    steps = {n: v for n,v in steps.items() if v['command'] is not None}
    # total time in seconds
    result = [steps[n] for n in sorted(steps.keys())]
    result = { 'total': total, 'steps': result }
    result.update(split_image_url(name))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('logfile', nargs='+')
    args = parser.parse_args()
    for logfile in args.logfile:
        try:
            print('Analyzing', logfile)
            result = parse_build_log(path=logfile)
            output = json.dumps(result, indent=4)
            #with open(result['name'] + '.json', 'w') as outfile:
            #    outfile.write(output)
        except Exception as e:
            print('Exception during processing', logfile, e)
            traceback.print_exc(e)

if __name__ == '__main__':
    main()
