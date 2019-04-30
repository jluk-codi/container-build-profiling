import sys
import json
import traceback
import argparse
import requests


elk_host = '1.2.3.4'
url = 'http://{}:9200'.format(elk_host)
index = 'builds'
index_url = url + '/' + index
index_pattern_url = 'http://{}:5601/api/saved_objects/index-pattern/{}'.format(elk_host, index)


def copy_keys(d1, d2, key_list):
    for key in key_list:
        d2[key] = d1[key]


def transform(obj):
    results = []
    for i, step in enumerate(obj['steps']):
        obj2 = {
            'layer': i+1
        }
        common_keys = ['name', 'total', 'branch', 'openstack_version', 'build']
        step_keys = ['command', 'duration']
        copy_keys(obj, obj2, common_keys)
        copy_keys(step, obj2, step_keys)
        results.append(obj2)
        print(json.dumps(obj2, indent=4))
    return results


def bulk_post(objs, index_url=index_url):
    print('Posting', len(objs), 'in bulk to', index_url)
    data = ''
    action_line = '{ "index":{} }\n'
    for obj in objs:
        for layer in transform(obj):
            data += action_line
            data += json.dumps(layer) + '\n'
    resp = requests.post(index_url + '/layer/_bulk', data=data, headers={'Content-Type': 'application/x-ndjson'})
    print(resp.text)


def post(obj, index_url=index_url):
    try:
        for obj2 in transform(obj):
            requests.post(index_url + '/layer', json=obj2)
    except Exception as e:
        print('Exception during processing', buildfile, e)
        traceback.print_exc(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true')
    parser.add_argument('buildfile', nargs='*')
    args = parser.parse_args()
    if args.clean:
        requests.delete(index_url) 
        ipd = requests.delete(index_pattern_url, headers={'kbn-xsrf': 'reporting'}) 
        print(ipd.text)
        sys.exit(0)
    for buildfile in args.buildfile:
        try:
            print('Sending', buildfile)
            with open(buildfile, 'r') as infile:
                payload = infile.read()
                obj = json.loads(payload)
                for i, step in enumerate(obj['steps']):
                    obj2 = {'image_name': obj['name'], 'command': step['command'], 'duration': step['duration'], 'layer': i+1, 'total': obj['total']}
                    requests.post(index_url + '/layer', json=obj2)
        except Exception as e:
            print('Exception during processing', buildfile, e)
            traceback.print_exc(e)


if __name__ == '__main__':
    main()
