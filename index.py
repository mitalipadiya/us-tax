import requests
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv
import os
import tiktoken
import json
import pandas as pd


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

page_size = '10'
token = 'Token c2450095ea9280c658de7aaa6788117302940843'
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

paginatedTests = requests.get(
    'https://api.case.law/v1/cases/?page_size=' + page_size + '&decision_date_min=1900-01-01&decision_date_max=2020-12-31&court=tc&cursor=eyJwIjogWzAuMCwgMjMzODg5N119&ordering=relevance',
    headers={'Authorization': token})
paginatedData = paginatedTests.json()

prevPg = paginatedData['previous']
nextPg = paginatedData['next']
allTests = paginatedData['results']
# Create a list to store the caseData
case_data_list = []
cnt = 0

def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(string))
    return num_tokens

for i, test in enumerate(allTests):
    generated_data = {}
    cnt = cnt + 1
    testUrl = test['url']
    response = requests.get(testUrl + '?full_case=true', headers={'Authorization': token})
    caseData = ""
    if i == 1:
        fullCaseJson = response.json()
        opinionType = ""
        caseData += "Parties: " + fullCaseJson['name'] + "\n"
        caseData += "Decision date: " + fullCaseJson['decision_date'] + "\n"
        opinions = fullCaseJson['casebody']['data']['opinions']
        frontendUrl = fullCaseJson['frontend_url']
        
        print (len(opinions))
        if len(opinions) == 1:
            caseData += "Author: " + opinions[0]['author'] + "\n"
            opinionType = opinions[0]['type']
            caseData += "Opinion: " + opinions[0]['text']

            caseData += '''\n need this data in json format
1. Name of petitioners / taxpayers
2. Name of Judge
3. Type of issue (income tax; excise tax; anything else ['whistleblower])
4. Type of taxpayer (individual; corporation)
5. Year the case was decided (year of decision)
6. Number of years for which the taxpayer is appealing (e.g., 2005 and 2006; therefore 2 years)
7. Gender of judge (male/female)
8. Gender of appellant/taxpayer (male/female)
9. Outcome (settlement) to the taxpayer [Win (100% successful), Lose, Partially successful (neither win 100% nor lose)] with description - reason
10. coowners of petitioner with their roles'''

            # # Calculate token length without making an API call
            # tokens = token_count(caseData)

            # Check if the token count exceeds the maximum limit
            tokens = num_tokens_from_string(caseData)
            if  tokens > 4096:
                generated_data["URL"] = testUrl + "?full_case=true"
                generated_data["Frontend URL"] = frontendUrl
                generated_data["No. of tokens"] = tokens
                case_data_list.append(generated_data)
                print("Length of case_data_list:", len(case_data_list))
                print(f"Token count ({tokens}) exceeds the maximum limit. Skipping this case.")
                continue

            # Append caseData to the list
            # case_data_list.append(caseData)

            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": caseData}
                ])

            # Extract the generated content from the completion response
            generated_content = completion.choices[0].message.content

            # Print the generated content (for verification)
            # print(generated_content)

            # Parse the generated content as JSON
            try:
                generated_data = json.loads(generated_content)
                generated_data["URL"] = testUrl + "?full_case=true"
                generated_data["Frontend URL"] = frontendUrl
                generated_data["Opinion Type"] = opinionType
            except json.JSONDecodeError as e:
                print(f"Error parsing generated content: {e}")
                continue

            # Append generated data to the list
            case_data_list.append(generated_data)
            print("Length of case_data_list:", len(case_data_list))

        else:
            generated_data["URL"] = testUrl + "?full_case=true"
            generated_data["Frontend URL"] = frontendUrl
            generated_data["No. of Opinions"] = len(opinions)
            generated_data["Parties"] = fullCaseJson['name']
            case_data_list.append(generated_data)
            # print(caseData)

# Create a DataFrame from the case_data_list
df = pd.DataFrame(case_data_list)

# Save the DataFrame to an Excel file
df.to_excel("generated_data_output.xlsx", index=False)
