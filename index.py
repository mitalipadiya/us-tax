import requests
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv
import os
import tiktoken
import json
import pandas as pd
import time


load_dotenv()

api_key = os.getenv("COMPANY_OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

page_size = '10'
token = 'Token c2450095ea9280c658de7aaa6788117302940843'
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

def append_data_summarization(data, processedData, max_tokens):
    summary = ""
    summaryRequest= '''\n  I have detailed case data and I need a structured summary. Please include the following information based on the case data in max 1500 tokens
1. Name of petitioners / taxpayers
2. Name of Judge
3. Type of issue (income tax; excise tax; anything else ['whistleblower])
4. Type of taxpayer (individual; corporation)
5. Year the case was decided (year of decision)
6. Number of years for which the taxpayer is appealing (e.g., 2005 and 2006; therefore 2 years)
7. Gender of judge (male/female)
8. Gender of appellant/taxpayer (male/female)
9. Outcome/settlement to the taxpayer (Win [100% successful], Lose, Partially successful [neither win 100% nor lose])
10. Outcome reason (Brief description of outcome)
11. coowners of petitioner with their roles'''
    summary +="\nI have some initial data summarized from a previous page which includes information like:\n"
    summary += "\n[" + processedData + "]\nPlease ensure that your summary addresses each of these points clearly and accurately based on the case data I provide. The outcome and the reason for the outcome are particularly important, so please give detailed attention to these aspects."

    lines = data.split('\n')
    current_chunk = summary
    while lines:
        next_line = lines[0]  # Peek at the first line
        if num_tokens_from_string(current_chunk + next_line + '\n') <= max_tokens:
            current_chunk += next_line + '\n'
            lines.pop(0)  # Remove the line that was just added
        else:
            break  # Stop adding lines if the token limit is exceeded

    # The remaining data after removing processed lines
    remaining_data = '\n'.join(lines)
    return current_chunk + summaryRequest, remaining_data

def json_request_append(data):
    jsonRequest= '''\n Create a JSON object with the following details, ensuring each key and corresponding value is properly formatted within double quotes. The JSON should include these keys:

'petitioners_taxpayers': [Name of petitioners or taxpayers],
'judge': [Name of Judge],
'issue': [Type of issue, e.g., income tax, excise tax, whistleblower],
'type_of_taxpayer': [Type of taxpayer, e.g., individual, corporation],
'year_of_decision': [Year the case was decided],
'number_of_years_appealed': [Number of years for which the taxpayer is appealing],
'gender_of_judge': [Gender of the judge, e.g., male, female],
'gender_of_appellant_taxpayer': [Gender of the appellant/taxpayer],
'outcome': [Outcome for the taxpayer, e.g., Win, Lose, Partially successful],
'outcome_reason': [Outcome reason in brief]
'coowners': [Co-owners of the petitioner and their roles, if any].

Replace the bracketed sections with the specific information for each key. If no information avaialable replace with double quotes but return proper json format'''

    data += jsonRequest
    return data

def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(string))
    return num_tokens

def chunk_data(data, max_tokens):
    """
    Splits the data into chunks, each with a token count less than or equal to max_tokens.
    """
    chunks = []
    current_chunk = ""
    for line in data.split('\n'):
        # Check the token count of the current chunk + new line
        if num_tokens_from_string(current_chunk + line + '\n') <= max_tokens:
            current_chunk += line + '\n'
        else:
            if current_chunk:  # Add the current chunk if it's not empty
                chunks.append(current_chunk)
            current_chunk = line + '\n'  # Start a new chunk

    if current_chunk:  # Add the last chunk if it's not empty
        chunks.append(current_chunk)
    return chunks


def process_completion(completion):
    try:
        generated_content = completion.choices[0].message.content
        print("Output ==>", generated_content)
        if not generated_content:
            print("No content received in completion response.")
            return {"response": []}
        # generated_data = json.loads(generated_content)
        return generated_content
    except json.JSONDecodeError as e:
        print(f"Error parsing generated content: {e}")
        print("Raw content:", generated_content)  # Temporarily print raw content for debugging
        return {"response": generated_content}

def process_completion_json(completion):
    try:
        generated_content = completion.choices[0].message.content
        print("Output ==>", generated_content)
        if not generated_content:
            print("No content received in completion response.")
            return {"response": []}
        generated_data = json.loads(generated_content)
        return generated_data
    except json.JSONDecodeError as e:
        print(f"Error parsing generated content: {e}")
        print("Raw content:", generated_content)  # Temporarily print raw content for debugging
        return {"response": generated_content}

def write_to_excel(case_data_list):
    # Define the Excel file path
    excel_file_path = "generated_data_output.xlsx"

    # Check if the Excel file exists
    try:
        # Read the existing Excel file
        existing_df = pd.read_excel(excel_file_path)
    except FileNotFoundError:
        # If the file does not exist, create an empty DataFrame with the same columns
        existing_df = pd.DataFrame(columns=case_data_list[0].keys())

    # Create a DataFrame from the case_data_list
    new_df = pd.DataFrame(case_data_list)

    # Concatenate the new data with the existing data
    final_df = pd.concat([existing_df, new_df], ignore_index=True)

    # Save the updated DataFrame to the Excel file
    final_df.to_excel(excel_file_path, index=False)
    return []

cnt = 0
# currentPage = 'https://api.case.law/v1/cases/?page_size=' + page_size + '&decision_date_min=1900-01-01&decision_date_max=2020-12-31&court=tc&cursor=eyJwIjogWzAuMCwgMjMzODg5N119&ordering=relevance'

currentPage = 'https://api.case.law/v1/cases/?court=tc&cursor=eyJwIjogWzAuMCwgMTIxMTM1MDJdfQ%3D%3D&decision_date_max=2020-12-31&decision_date_min=1900-01-01&ordering=relevance&page_size=10'

while cnt <= 100:
    cnt = cnt + 1
    paginatedTests = requests.get(
        currentPage,
        headers={'Authorization': token})
    paginatedData = paginatedTests.json()

    prevPg = paginatedData['previous']
    nextPg = paginatedData['next']
    allTests = paginatedData['results']
    # Create a list to store the caseData
    case_data_list = []

    request_count = 0
    # mitali_cnt = 0
    for i, test in enumerate(allTests):
        # mitali_cnt = mitali_cnt + 1
        generated_data = {}
        # cnt = cnt + 1
        testUrl = test['url']
        response = requests.get(testUrl + '?full_case=true', headers={'Authorization': token})
        caseData = ""
        if cnt <= 100:
            fullCaseJson = response.json()
            opinionType = ""
            caseData += "Parties: " + fullCaseJson['name'] + "\n"
            caseData += "Decision date: " + fullCaseJson['decision_date'] + "\n"
            opinions = fullCaseJson['casebody']['data']['opinions']
            frontendUrl = fullCaseJson['frontend_url']
            
            print (len(opinions))
            if len(opinions) == 1:
                if opinions[0]['author']:
                    caseData += "Author: " + opinions[0]['author'] + "\n"
                else:
                    caseData += "Author: " + "" + "\n"
                opinionType = opinions[0]['type']
                caseData += "Opinion: " + opinions[0]['text']

                jsonRequestData = json_request_append(caseData)
                tokens = num_tokens_from_string(jsonRequestData)
                # # Calculate token length without making an API call
                # tokens = token_count(caseData)

                # Check if the token count exceeds the maximum limit
                print(tokens)
                aggregated_data = []
                if  tokens > 4090:
                    updated_case_data = caseData
                    processed_data = ""
                    case_data_chunks, updated_case_data = append_data_summarization(updated_case_data,"", 3800)
                    
                    while(num_tokens_from_string(updated_case_data) != 0):
                        print(num_tokens_from_string(case_data_chunks))
                        # print("Input ==>", case_data_chunks)
                        completion = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                            {"role": "user", "content": case_data_chunks}
                            ])

                        request_count += 1
                
                        # Process each completion
                        processed_data = process_completion(completion)
                        case_data_chunks, updated_case_data = append_data_summarization(updated_case_data,processed_data, 3800)

                        # Check if the request count is a multiple of 3
                        if request_count % 3 == 0:
                            time.sleep(60)  # Delay for 1 minute

                    jsonRequestData = json_request_append(processed_data)
                    if request_count % 3 == 0:
                        time.sleep(60) 
                    completion = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                        {"role": "user", "content": jsonRequestData}
                        ])
                    request_count += 1
                    generated_data = process_completion_json(completion)
                    print("JSON output ==>", generated_data)

                    generated_data["URL"] = testUrl + "?full_case=true"
                    generated_data["Frontend URL"] = frontendUrl
                    generated_data["Opinion Type"] = opinionType
                    generated_data["prevPg"] = prevPg
                    generated_data["nextPg"] = nextPg
                    generated_data["current"] = currentPage
                    
                    case_data_list.append(generated_data)
                    case_data_list = write_to_excel(case_data_list)
                    # print("Length of case_data_list:", len(case_data_list))
                    # print(f"Token count ({tokens}) exceeds the maximum limit. Skipping this case.")
                    # continue

                # Append caseData to the list
                # case_data_list.append(caseData)
                else:
                    # Check if the request count is a multiple of 3
                    if request_count % 3 == 0:
                        time.sleep(60)  # Delay for 1 minute
                    completion = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "user", "content": jsonRequestData}
                        ])

                    request_count += 1

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
                        generated_data["prevPg"] = prevPg
                        generated_data["nextPg"] = nextPg
                        generated_data["current"] = currentPage
                        case_data_list.append(generated_data)
                        case_data_list = write_to_excel(case_data_list)
                    except json.JSONDecodeError as e:
                        generated_data = {}
                        generated_data["response"] = generated_content
                        generated_data["URL"] = testUrl + "?full_case=true"
                        generated_data["Frontend URL"] = frontendUrl
                        generated_data["Opinion Type"] = opinionType
                        generated_data["prevPg"] = prevPg
                        generated_data["nextPg"] = nextPg
                        generated_data["current"] = currentPage
                        case_data_list.append(generated_data)
                        case_data_list = write_to_excel(case_data_list)
                        print(f"Error parsing generated content: {e}")
                        continue

                # Append generated data to the list
                # case_data_list.append(generated_data)
                # print("Length of case_data_list:", len(case_data_list))

            else:
                generated_data["URL"] = testUrl + "?full_case=true"
                generated_data["Frontend URL"] = frontendUrl
                generated_data["No. of Opinions"] = len(opinions)
                generated_data["petitioners_taxpayers"] = fullCaseJson['name']
                generated_data["prevPg"] = prevPg
                generated_data["nextPg"] = nextPg
                generated_data["current"] = currentPage
                case_data_list.append(generated_data)
                case_data_list = write_to_excel(case_data_list)
                # print(caseData)
    currentPage = nextPg
    # Define the Excel file path
    excel_file_path = "generated_data_output.xlsx"

    # Check if the Excel file exists
    try:
        # Read the existing Excel file
        existing_df = pd.read_excel(excel_file_path)
    except FileNotFoundError:
        # If the file does not exist, create an empty DataFrame with the same columns
        existing_df = pd.DataFrame(columns=case_data_list[0].keys())

    # Create a DataFrame from the case_data_list
    new_df = pd.DataFrame(case_data_list)

    # Concatenate the new data with the existing data
    final_df = pd.concat([existing_df, new_df], ignore_index=True)

    # Save the updated DataFrame to the Excel file
    final_df.to_excel(excel_file_path, index=False)
