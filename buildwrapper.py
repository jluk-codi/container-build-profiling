from __future__ import print_function
import json
import subprocess
import build_analyzer2
import os

env = os.environ.copy()
env['DOCKER_BUILDKIT'] = '1'
image = 'testbuild:atag'
#out = subprocess.check_output(['bash', '-c', 'time -p docker build -t {} .'.format(image)], shell=False, stderr=subprocess.STDOUT, env=env)
p = subprocess.Popen(['bash', '-c', 'time -p docker build --no-cache -t {} .'.format(image)], shell=False, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env)
out ,_ = p.communicate()
print(out)
obj = build_analyzer2.parse_build_log_from_string(out)
#print(obj)
print('Building image', image)
print('Layers by duration:')
for i, step in sorted(enumerate(obj['steps']), key=lambda x: x[1]['duration'], reverse=True):
    print('{:3}.'.format(i+1),step['duration'], step['command'])
out = subprocess.check_output(['bash', '-c', 'dive {} -j dive.json'.format(image)], shell=False, stderr=subprocess.STDOUT, env=env)
with open('dive.json', 'r') as infile:
    dive = json.load(infile)
eff = dive['image']['efficiencyScore']
wasted = dive['image']['inefficientBytes']
print()
print('Storage efficiency:', eff*100, '%')
print('Wasted:', wasted / (1024*1024), 'MB')
