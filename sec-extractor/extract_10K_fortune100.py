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
      ("1", "Business"),
      ("1A", "Risk Factors"),
      ("1B", "Unresolved Staff Comments"),
      ("2", "Properties"),
      ("3", "Legal Proceedings"),
      ("4", "Mine Safety Disclosures"),
      ("5",
       "Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities"
       ),
      ("6", "Selected Financial Data"),
      ("7",
       "Management's Discussion and Analysis of Financial Condition and Results of Operations"
       ),
      ("7A", "Quantitative and Qualitative Disclosures About Market Risk"),
      ("8", "Financial Statements and Supplementary Data"),
      ("9",
       "Changes in and Disagreements With Accountants on Accounting and Financial Disclosure"
       ),
      ("9A", "Controls and Procedures"),
      ("9B", "Other Information"),
      ("10", "Directors, Executive Officers and Corporate Governance"),
      ("11", "Executive Compensation"),
      ("12",
       "Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters"
       ),
      ("13",
       "Certain Relationships and Related Transactions, and Director Independence"
       ),
      ("14", "Principal Accountant Fees and Services"),
      ("15", "Exhibits, Financial Statement Schedules"),
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


file_path = "../data/filing_urls_10K_fortune100.json"  # Replace with the actual path to your file

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
  file_path = "../data/fortune100_10K_2023/" + ticker + "_" + filed_at + "_" + form_type + ".json"

  # Write data to the JSON file
  with open(file_path, 'w') as json_file:
    json_file.write(json_data)

  print(f"Data has been written to {file_path}.")
print("All data generation complete")
