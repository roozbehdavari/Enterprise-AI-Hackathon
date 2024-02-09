import json
import openai
import re
from sec_api import ExtractorApi

extractorApi = ExtractorApi(
    '')


# Function to generate a section
def generate_section(section_type, section_heading, section_text):
  return {
      "SectionType": section_type,
      "SectionHeading": section_heading,
      "sectionSummary": "",
      "raw": section_text,
      "chunks": []
  }


# Function to generate a company entry with multiple sections
def generate_company_entry(company_name,
                           filing_url,
                           quarter,
                           filing,
                           num_sections=2):
  sections = []
  section_info = [
      ('part1item1', 'Part 1: Financial Statements'),
      ('part1item2',
       "Part 1: Management’s Discussion and Analysis of Financial Condition and Results of Operations"
       ),
      ('part1item3',
       'Part 1: Quantitative and Qualitative Disclosures About Market Risk'),
      ('part1item4', 'Part 1: Controls and Procedures'),
      ('part2item1', 'Part 2: Legal Proceedings'),
      ('part2item1a', 'Part 2: Risk Factors'),
      ('part2item2',
       'Part 2: Unregistered Sales of Equity Securities and Use of Proceeds'),
      ('part2item3', 'Part 2: Defaults Upon Senior Securities'),
      ('part2item4', 'Part 2: Mine Safety Disclosures'),
      ('part2item5', 'Part 2: Other Information'),
      ('part2item6', 'Part 2: Exhibits')
  ]

  for section_id, section_heading in section_info:
    section_text = extractorApi.get_section(filing_url, section_id, "text")
    cleaned_section = re.sub(r"\n|&#[0-9]+;", "", section_text)
    sections.append(
        generate_section(section_id, section_heading, cleaned_section))

  return {
      "companyName": company_name,
      "filingUrl": filing_url,
      "Quarter": quarter,
      "Filing": filing,
      "sections": sections
  }


file_path = "filing_urls_10Q_fortune100.json"  # Replace with the actual path to your file

# Read the JSON data from the file
with open(file_path, 'r') as file:
  json_data = json.load(file)

# Loop through each entry in the JSON data
for entry in json_data:
  company_name = entry.get("companyName", "N/A")
  ticker = entry.get("ticker", "N/A")
  filing_details_link = entry.get("linkToFilingDetails", "N/A")
  form_type = entry.get("formType", "N/A")
  filed_at = entry.get("filedAt", "N/A")

  # Generate JSON data with user-input company name and filing URL
  company_entry = generate_company_entry(company_name, filing_details_link,
                                         filed_at, form_type)

  # Convert the dictionary to a JSON-formatted string
  json_data = json.dumps([company_entry], indent=2)

  # Print the result
  #print(json_data)
  # Specify the file path
  file_path = "fortune100_10Q_2023/" + ticker + "_" + filed_at + "_" + form_type + ".json"

  # Write data to the JSON file
  with open(file_path, 'w') as json_file:
    json_file.write(json_data)

  print(f"Data has been written to {file_path}.")
print("All data generation complete")
