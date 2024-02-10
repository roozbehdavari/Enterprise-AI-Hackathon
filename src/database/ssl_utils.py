# https://stackoverflow.com/questions/15445981/how-do-i-disable-the-security-certificate-check-in-python-requests
import warnings
import contextlib

import requests
from urllib3.exceptions import InsecureRequestWarning

import json
from os.path import join, split

old_merge_environment_settings = requests.Session.merge_environment_settings

@contextlib.contextmanager
def no_ssl_verification():
    opened_adapters = set()

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        # Verification happens only once per connection so we need to close
        # all the opened adapters once we're done. Otherwise, the effects of
        # verify=False persist beyond the end of this context manager.
        opened_adapters.add(self.get_adapter(url))

        settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
        settings['verify'] = False

        return settings

    requests.Session.merge_environment_settings = merge_environment_settings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            yield
    finally:
        requests.Session.merge_environment_settings = old_merge_environment_settings

        for adapter in opened_adapters:
            try:
                adapter.close()
            except:
                pass

def export(path, outfile, filing):
	full_filename = join(path, outfile)
	with open(full_filename, "w") as f:
		json.dump(filing, f, indent=4)


def get_path(full_filename):
	head_tail = split(full_filename)
	return head_tail[0]

def read_filelist(filename):
	with open(filename) as f:
		files = [line.rstrip() for line in f]

	return files
            