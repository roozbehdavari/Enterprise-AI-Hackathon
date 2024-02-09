# ##################################################################### 
# Reads a list of extracted SEC filings. 
# Chunks into pages based on aggregating sentences.
# Uses GPT Chat to generate per-page summaries and extract key points.   
# Exports back to text for additional processing.
# 
# #####################################################################

# import libraries
import copy
from datetime import datetime
from itertools import chain
import json
from nltk.tokenize import regexp_tokenize, wordpunct_tokenize, blankline_tokenize
from openai import AzureOpenAI
import os
import pathlib
import re
import requests
import spacy
from spacy.lang.en import English
import sys
import time
import warnings


# import local tools
utils = os.path.join(pathlib.Path(__file__).parent.parent.resolve(),"utils")
sys.path.insert(1, utils)
from file_utils import *


# global setup
nlp = spacy.load('en_core_web_sm')

secrets = {}
secrets_file = 'hackathon_secrets'
with open(secrets_file) as f:
	secrets = json.load(f)
exit()


# GPT summarization
def call_chatGpt(prompt, context):
	endpoint = "https://openai-emerging.openai.azure.com"    
	
	client = AzureOpenAI(
		api_key = secrets["OPEN_API_KEY"],
		api_version="2023-03-15-preview",
		azure_endpoint=endpoint
	)
	
	response = client.chat.completions.create(
		model = "gpt-35-turbo",
		messages=[
			{"role":"system", "content":"{}".format(prompt)},
			{"role":"user", "content": "{}".format(context)}
		])
	
	return response

def segment_text(text):
	pages = [[]]
	page_total_words = 0

	sentences = nlp(text)

	for sentence in sentences.sents:
		page_total_words += len(sentence.text.split(" "))

		if page_total_words > 2000:
			pages.append([])
			page_total_words = len(sentence.text.split(" "))

		pages[len(pages)-1].append(sentence.text)

	return pages


def truncate_words(text, cap):
	split_text = text.split(" ")
	size = len(split_text)
	if size > cap:

	   print("truncating text to {} words from {}".format(cap, size))
	   return " ".join(split_text[0:cap]) 
	else:
		print("page len was OK at {} words".format(size))
		return text

def summarize_text(text):
	prompt = "Summarize the following 10-K report section in no more than 250 words:"
	response = call_chatGpt(prompt, text)
	return response.choices[0].message.content


def get_page_summaries(pages):
	page_summaries = []

	for chunks in pages:
		long_summary = truncate_words(" ".join(chunks), 2000)
		page_summary = summarize_text(long_summary)
		page_summaries.append(page_summary)

	return page_summaries

def extract_key_points(text):
	prompt = "Extract the 5 most important segments from this financal report. Limit each segment to 100 words. "
	response = call_chatGpt(prompt, text)
	content = response.choices[0].message.content
	return content

def process_key_points(pages):
	key_points = []

	for chunks in pages:
		long_summary = truncate_words(" ".join(chunks), 2000)
		response = extract_key_points(long_summary)
		if response is not None:
			split_response = response.split("\n")
			points = [p for p in split_response if len(p.strip()) > 0]
			key_points.append(points)
			return key_points
		else:
			print("Failed to generate key points")
			return ''


def print_time():
	now = datetime.now()
	current_time = now.strftime("%H:%M:%S")
	print("Current Time =", current_time)


def process(text):
	response = {
		"pages": [],
		"chunks": [],
		"sectionSummary": "",
		"pageSummaries": []
	}
	
	# if the section contains only data, skip for now.
	if len(text) < 100:
		response["pages"] = [ text ]
		response["chunks"] = [ text ]
		response["sectionSummary"] = [ text ]
		response["keyPoints"] = []
		return response
		
	pages = segment_text(text)
	chunks = list(chain.from_iterable(pages))
	summaries = get_page_summaries(pages)
	section_summary = summarize_text(truncate_words(" ".join(summaries), 5500))
	key_points = process_key_points(pages)

	response["chunks"] = chunks
	response["pages"] = [ " ".join(chunk) for chunk in pages]
	response["pageSummaries"] = summaries
	response["sectionSummary"] = section_summary
	response["keyPoints"] = key_points
	return response



# ########################################################################
# Takes a path rather than walking a directory for simple parallelization.
# Usage: 
# > python3 ./chunk/chunk.py path_to_filelist
# ########################################################################
if __name__ == "__main__":
	for arg in sys.argv:
		print(arg)

	files = read_filelist(arg)
	in_path = get_path(arg)
	out_path = in_path.replace("data", "output")	
	for file in files:
		print_time()
		filing = load_filing(in_path, file)
		for f in filing:
			for section in f["sections"]:
				response = process(section["raw"])
				section["chunks"] = response["chunks"]        
				section["pages"] = response["pages"]
				section["pageSummaries"] = response["pageSummaries"]
				section["sectionSummary"] = response["sectionSummary"]
				section["keyPoints"] = response["keyPoints"]
				print("finished section {}".format(section["SectionType"]))

		export(out_path, file, filing)
		print("finished filing {}".format(file))



