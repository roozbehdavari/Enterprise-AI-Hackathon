# ##################################################################################### 
# Reads a list of processed SEC filings. 
# Pushes to Weaviate Vector DB. Records are approximately 1 sentence plus metadata.
# 
# #####################################################################################

# import libraries
from datetime import datetime
import cohere
import json
import os
import path
import requests
import sys
from typing import List, Dict, Any
import weaviate
from weaviate.exceptions import SchemaValidationException

# Update path, then import local tools
utils = os.path.join(pathlib.Path(__file__).parent.parent.resolve(),"utils")
sys.path.insert(1, utils)

from file_utils import *
from ssl_utils import *

# global setup
secrets = {}
secrets_file = './hackathon_secrets'
with open(secrets_file) as f:
	secrets = json.load(f)

def init():
	api_key = secrets["COHERE_API_KEY"]
	co = cohere.Client(api_key)

	auth_config = weaviate.AuthApiKey(api_key=secrets["WEAVIATE_API_KEY"])

	client = weaviate.Client(
		url=secrets["WEAVIATE_URL"],  # URL of your Weaviate instance
		auth_client_secret=auth_config,  # (Optional) If the Weaviate instance requires authentication
		timeout_config=(5, 15),  # (Optional) Set connection timeout & read timeout time in seconds
		additional_headers={  # (Optional) Any additional headers; e.g. keys for API inference services
		"X-Cohere-Api-Key": api_key,   # Replace with your Cohere key
			})

	return {
		"cohere": co,
		"weaviate": client
	}

def prettyprint(json_obj):
	print(json.dumps(json_obj, indent=4))


def print_time():
	now = datetime.now()
	current_time = now.strftime("%H:%M:%S")
	print("Current Time =", current_time)	

def check_import(client, class_name, filing_type):
	response = client.query \
		.get(class_name, ["companyName", "filing", "sectionHeading", "chunk"]) \
		.with_where({
			"path": ["filing"],
			"operator": "Equal",
			"valueText": filing_type}) \
		.do()
	prettyprint(response)

def cleanup(client, class_name, company_name):
	client.batch.delete_objects(
	    class_name=class_name,
	    where={
	        "path": ["companyName"],
	        "operator": "Like",
	        "valueText": company_name
	    },
	)	

def create_WEAVIATE_class(client: 'weaviate.client.Client', 
						  class_name: str, 
						  input_dtype: str = "text") -> bool:
	"""
	Create a class in Weaviate schema.

	Args:
		client: The Weaviate client instance.
		class_name: The name of the class to create.
		input_dtype: The data type for the input properties.

	Returns:
		bool: True if successful, False otherwise.
	"""
	try:
		client.schema.delete_class(class_name)
	except (RequestError, SchemaValidationException) as e:
		print(f"Error deleting class '{class_name}': {e}")
		return False
	
	class_obj = {
		"class": class_name,
		"vectorizer": "text2vec-cohere",  
		"moduleConfig": {
			"text2vec-cohere": {
				"vectorizeClassName": False,
				"input_type": "search_document"
			},
			"reranker-cohere": {
				"model": "rerank-english-v2.0",  
			}
		},
		"properties": [{
			"moduleConfig": { 
				"text2vec-cohere": { 
					"companyName": False,
					"filingUrl": False,
					"source": False,
					"quarter": False,
					"filing": False,
					"SectionHeading": False,
					"sectionSummary": False,
					"sectionPage": False,
					"chunk": True
				}
			},
			"dataType": [
				input_dtype  # Set the input data type
			],
			"name": "name"
		}],
		"generative-cohere": {}
	}

	try:
		client.schema.create_class(class_obj)
		return True
	except (SchemaValidationException) as e:
		print(f"Error creating class '{class_name}': {e}")
		return False


def process_and_expand_json_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
	"""
	Process and expand JSON data into a list of dictionaries.

	Args:
		data (dict): The JSON data to process and expand.

	Returns:
		list: A list of dictionaries representing the expanded data.
	"""
	expanded_data = []
	
	# Extracting top-level details
	companyName = data.get('companyName')
	filingUrl = data.get('filingUrl')
	quarter = data.get('Quarter')  # Using lowercase key as 'Quarter' is inconsistent
	filing = data.get('Filing')
	sections = data.get('sections', [])  # Handling case where 'sections' key might be missing
	
	for section in sections:
		# Extracting section-level details
		sectionraw = section.get('raw')
		sectionType = section.get('SectionType')
		sectionHeading = section.get('SectionHeading')
		sectionSummary = section.get('sectionSummary')
		pages = section.get('pages', [])
		chunks = section.get('chunks', [])
		pageSummaries = section.get('pageSummaries', [])
		keyPoints = section.get('keyPoints', [])
		
		# Constructing source URL
		source = f'{filingUrl} || Section: {sectionHeading}' if filingUrl and sectionHeading else None
		
		# Adding Chunk details to expanded_data
		for chunk in chunks:
			matching_page = next((page for page in pages if chunk in page), None)
			if matching_page:
				expanded_data.append({
					'companyName': companyName,
					'filingUrl': filingUrl,
					'quarter': quarter,
					'filing': filing,
					'sectionPage': matching_page,
					'sectionType': sectionType,
					'sectionHeading': sectionHeading,
					'sectionSummary': sectionSummary,
					'chunk': chunk,
					'source': source
				})
		
		# Adding LLM-Summarized Pages as CHUNKS
		for page, pageSummary in zip(pages, pageSummaries):
			expanded_data.append({
				'companyName': companyName,
				'filingUrl': filingUrl,
				'quarter': quarter,
				'filing': filing,
				'sectionPage': page,
				'sectionType': sectionType,
				'sectionHeading': sectionHeading,
				'sectionSummary': sectionSummary,
				'chunk': pageSummary,
				'source': source
			})

		# Adding LLM-Generated Pages KeyPoints as CHUNKS
		for page, keyPoint in zip(pages, keyPoints):
			for point in keyPoint:
				expanded_data.append({
					'companyName': companyName,
					'filingUrl': filingUrl,
					'quarter': quarter,
					'filing': filing,
					'sectionPage': page,
					'sectionType': sectionType,
					'sectionHeading': sectionHeading,
					'sectionSummary': sectionSummary,
					'chunk': point,
					'source': source
				})

	return expanded_data

def import_data_to_WEAVIATE(client: 'weaviate.client.Client', 
							data_folder: str, 
							filenames: List[str],
							class_name: str,
							batch_size: int=50,
							min_chunk_charactre: int=20) -> None:
	"""
	Import data from JSON files in a list to Weaviate.

	Args:
		client: The Weaviate client instance.
		data_folder: The path to the folder containing JSON files.
		class_name: The name of the class in Weaviate.

	Returns:
		None
	"""
	for file in filenames:
		file_path = os.path.join(data_folder, file)
	 	# Loading JSONs
		with open(file_path, 'rb') as fp:
			data = json.load(fp)[0]
		company_name = data["companyName"]
		print_time()
		print(f"Company Name: {company_name}")
		# Constructing the Expanded JSONs to be Pushed to Weaviate
		expanded_data = process_and_expand_json_data(data)

		# Splitting expanded data into batches
		batches = [expanded_data[i:i+batch_size] for i in range(0, len(expanded_data), batch_size)]

		with client.batch as batch:  # Initialize a batch process
			for i, d in enumerate(expanded_data, start=1):  # Batch import data
				if i % 500 == 0:
					print(f"Importing record: {i}")
				# Filtering Out Junk Chunks (too short!)
				if len(d["chunk"]) >= min_chunk_charactre:
					properties = {
						"companyName": d['companyName'],
						"filingUrl": d['filingUrl'],
						"source": d['source'],
						"quarter": d['quarter'],
						"filing": d['filing'],
						"sectionHeading": str(d["sectionHeading"]),
						"sectionSummary": str(d["sectionSummary"]),
						"sectionPage": str(d["sectionPage"]),
						"chunk": str(d["chunk"])
					}
					batch.add_data_object(
						data_object=properties,
						class_name=class_name
					)

# ########################################################################
# Takes a path rather than walking a directory for simple parallelization.
# Usage: 
# > python3 ./push/weaviate.py path_to_filelist
# ########################################################################
if __name__ == "__main__":
	for arg in sys.argv:
		print(arg)

	filenames = read_filelist(arg)
	in_path = get_path(arg)

	with no_ssl_verification():
		clients = init()	
		class_name="SECSavvyNOW"

		import_data_to_WEAVIATE(client=clients["weaviate"], data_folder=in_path, filenames=filenames, class_name=class_name)

		# Sample usage of other calls
		# filing_type="10-Q"
		# company_name = "Apple Inc."
		# create_WEAVIATE_class(clients["weaviate"], class_name)
    	# some_objects = clients["weaviate"].data_object.get()
		# print(json.dumps(some_objects, indent=4))
		# cleanup(clients["weaviate"], class_name, company_name)
		# check_import(clients["weaviate"], class_name, filing_type)
