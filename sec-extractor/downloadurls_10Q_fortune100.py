from sec_api import QueryApi
import json

queryApi = QueryApi(
    api_key="")

base_query = {
    "query": {
        "query_string": {
            "query": "PLACEHOLDER",  # this will be set during runtime 
            "time_zone": "America/New_York"
        }
    },
    "from": "0",
    "size": "200",  # dont change this
    # sort returned filings by the filedAt key/value
    "sort": [{
        "filedAt": {
            "order": "desc"
        }
    }]
}
# open the file we use to store the filing URLs
log_file = open("filing_urls_10Q_fortune100.json", "a")
year = "2023"

ticker_symbols = [
    "NOW", "WMT", "AMZN", "AAPL", "CVS", "UNH", "XOM", "BRK.B", "GOOGL", "MCK",
    "ABC", "COST", "CI", "T", "MSFT", "CAH", "CVX", "HD", "WBA", "MPC", "ANTM",
    "KR", "F", "VZ", "JPM", "GM", "CNC", "FB", "CMCSA", "PSX", "VLO", "DELL",
    "TGT", "FNMA", "UPS", "LOW", "BAC", "JNJ", "ADM", "FDX", "HUM", "WFC",
    "PFE", "C", "PEP", "INTC", "PG", "GE", "IBM", "MET", "PRU", "ACI", "DIS",
    "ET", "LMT", "FMCC", "GS", "RTX", "HPQ", "BA", "MS", "HCA", "ABBV", "DOW",
    "TSLA", "ALL", "AIG", "BBY", "CHTR", "SYY", "MRK", "CAT", "CSCO", "TJX",
    "COP", "PGR", "TSN", "BMY", "NKE", "DE", "AXP", "ABT", "SNEX", "PAGP",
    "EPD", "ORCL", "TMO", "KO", "GD", "NUE", "EXC"
]
for ticker in ticker_symbols:
  print("Starting download for " + ticker + " for year " + year)

  # a single search universe is represented as a month of the given year

  # get 10-Q and 10-Q/A filings filed in year and month
  # resulting query example: "formType:\"10-Q\" AND filedAt:[2021-01-01 TO 2021-01-31]"
  universe_query = \
                "ticker: " + ticker +" AND formType:\"10-Q\" " + \
                "AND NOT formType:\"NT 10-K\" " + "AND NOT formType:\"10-K/A\" " + \
                "AND filedAt:[2023-01-01 TO 2023-12-31]"

  base_query["query"]["query_string"]["query"] = universe_query

  response = queryApi.get_filings(base_query)

  # no more filings in search universe
  if len(response["filings"]) == 0:
    continue

  # Generate a simplified response containing companyName and linkToFilingDetails using lambda
  simplified_response = list(
      map(
          lambda entry: {
              'companyName': entry['companyName'],
              'ticker': entry['ticker'],
              'linkToFilingDetails': entry['linkToFilingDetails'],
              'formType': entry['formType'],
              'filedAt': entry['filedAt']
          },
          filter(lambda entry: entry['formType'] == '10-Q',
                 response["filings"])))

  # Print the simplified response
  log_file.write(json.dumps(simplified_response, indent=2))

log_file.close()

print("All URLs downloaded")
