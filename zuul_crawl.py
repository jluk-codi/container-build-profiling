import os
import sys
import glob
import requests
import argparse
import build_analyzer
import elk_poster
import yaml
import json
from lxml import html


class Sourcer():
    def __init__(self, review, patchset):
        self.review = review
        self.patchset = patchset

    def review_path(self):
        suffix = str(self.review)[-2:]
        return "{}/{}/{}".format(suffix, self.review, self.patchset)
    
    def read_file(self, path):
        with open(path, 'r') as infile:
            return infile.read()

    def crawl(self):
        results = []
        upload_count = 0
        jobs = self.get_jobs()
        for job in jobs:
            builds = self.get_builds(job)
            for b in builds:
                logs = self.get_logs(job, b)
                inventory_yaml = self.fetch_inventory(job, b)
                inventory = yaml.load(inventory_yaml)['all']['vars']
                job = inventory['zuul']['job']
                branch = inventory['zuul']['branch']
                build = inventory['zuul']['build'][:5]
                openstack_version = inventory['openstack_version']
                for l in logs:
                    log = self.fetch_log(l)
                    parsed = build_analyzer.parse_build_log_from_string(log)
                    parsed['job'] = job
                    parsed['branch'] = branch
                    parsed['openstack_version'] = openstack_version
                    parsed['build'] = build
                    results.append(parsed)
                    #upload_count += 1
                    #print('Uploading', upload_count)
                    #elk_poster.post(parsed)
        return results


class LocalSourcer(Sourcer):
    def __init__(self, review, patchset, path):
        super(LocalSourcer, self).__init__(review, patchset)
        self.path = path
        self.start_path = self.path + '/' + self.review_path()

    def list_dirs(self, path):
        try:
            return next(os.walk(path))[1]
        except StopIteration as si:
            print('ERROR: Directory', path, 'missing, exiting...')
            sys.exit(1)

    def get_jobs(self):
        return self.list_dirs(self.start_path)

    def get_builds(self, job):
        return self.list_dirs(self.start_path + '/' + job)

    def get_logs(self, job, build):
        return glob.glob(self.start_path + '/' + job + '/' + build + '/container-builder-logs/*.log')

    def fetch_inventory(self, job, build):
        return self.read_file(self.start_path + '/' + job + '/' + build + '/inventory.yaml')

    def fetch_log(self, log):
        return self.read_file(log)
        

def get_links(url):
    print('dlding', url)
    response = requests.get(url)
    if response.status_code == 404:  # break once the page is not found
        print(404)
    tree = html.fromstring(response.text)
    links = []
    for video_link in tree.xpath('//a'):
        title = video_link.text
        link = video_link.attrib['href']
        links.append((title, link, url + link))
    return links


def get_jobs(review, patchset):
    suffix = str(review)[-2:]
    url = "http://logs.tungsten.io/{}/{}/{}/check/".format(suffix, review, patchset)
    jobs = get_links(url)
    #print('jobs', jobs)
    jobs = [l for l in jobs if 'build-containers' in l[0]]
    print('jobs', jobs)
    return jobs


def get_builds(url):
    jobs = get_links(url)
    #print('jobs', jobs)
    links = [l for l in get_links(url) if l[0] == l[1]]
    #print('builds', links)
    return links


def get_logs(url):
    url = url + 'container-builder-logs/'
    jobs = get_links(url)
    #print('jobs', jobs)
    links = [l for l in get_links(url) if l[1].endswith('.log')]
    #print('builds', links)
    return links


def ensure_dir(path):
    try:
        os.makedirs(path)
    except FileExistsError as fee:
        pass

def download_if_missing(url, path):
    if not os.path.isfile(path):
        print('Downloading')
        ensure_dir(os.path.dirname(path))
        with open(path, 'w') as out:
            req = requests.get(url)
            out.write(req.text)
            return req.text
    else:
        print('Reading from file')
        with open(path, 'r') as infile:
            return infile.read()


def get_last_segments(string, n, delimiter=' '):
    string_strip = string.strip(delimiter)
    segments = string_strip.split(delimiter)
    if len(segments) >= n:
        return delimiter.join(segments[-n:])
    else:
        return string


def crawl_review(review, patchset):
    jobs = get_jobs(review, patchset)
    for job in jobs:
        builds = get_builds(job[2])
        for b in builds:
            logs = get_logs(b[2])
            path = get_last_segments(b[2], 1, '/')
            inventory_yaml = download_if_missing(b[2] + '/zuul-info/inventory.yaml', path + '/inventory.yaml')
            inventory = yaml.load(inventory_yaml)['all']['vars']
            job = inventory['zuul']['job']
            branch = inventory['zuul']['branch']
            openstack_version = inventory['openstack_version']
            for l in logs:
                url = l[2]
                path = get_last_segments(url, 3, '/')
                print('Will save', url, 'to', path)
                log = download_if_missing(url, path)
                #print(log) 
                parsed = build_analyzer.parse_build_log_from_string(log)
                parsed['job'] = job
                parsed['branch'] = branch
                #print(json.dumps(parsed, indent=4))
                print(openstack_version, parsed['name'], parsed['tag'], parsed['total']) 

    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', type=int)
    parser.add_argument('--patchset', type=int)
    args = parser.parse_args()
    ls = LocalSourcer(args.review, args.patchset, '.')
    results = ls.crawl()
    elk_poster.bulk_post(results)
    #for r in results:
    #    print(r['openstack_version'], r['name'], r['tag'], r['total']) 

    #crawl_review(args.review, args.patchset)

if __name__ == '__main__':
    main()
