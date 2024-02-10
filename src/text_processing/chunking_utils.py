import json
from os import listdir
from os.path import isfile, join, split
import sys

def divide_list(l, n):      
    # looping till length l 
    for i in range(0, len(l), n):  
        yield l[i:i + n] 

def walk_dir(dir):
	onlyfiles = [f for f in listdir(dir) if isfile(join(dir, f))]
	x = list(divide_list(onlyfiles, 10)) 

	for idx,l in enumerate(x):
		listname = join(dir, "file_list_{}.txt".format(idx))
		with open(listname, "w") as f:
			for line in l:
				f.write(f"{line}\n")	


def read_filelist(filename):
	with open(filename) as f:
		files = [line.rstrip() for line in f]

	return files


def load_filing(path, infile):
	full_filename =join(path, infile)
	with open(full_filename) as f:
	    data = json.load(f)
	return data


def export(path, outfile, filing):
	full_filename = join(path, outfile)
	with open(full_filename, "w") as f:
		json.dump(filing, f, indent=4)


def get_path(full_filename):
	head_tail = split(full_filename)
	return head_tail[0]

if __name__ == "__main__":
	for arg in sys.argv:
	    print(arg)

	walk_dir(arg)