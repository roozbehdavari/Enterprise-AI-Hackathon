from langchain.retrievers import ContextualCompressionRetriever, CohereRagRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain_community.embeddings import CohereEmbeddings
from langchain_community.chat_models import ChatCohere
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.docstore.document import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

import cohere
import weaviate

import requests
import json
import re
from typing import List, Tuple, Optional, Dict


# Cohere Instantiation
api_key_cohere = "h5s3funzwf1JpxgZknyFoEap69EsEBdfRxT45W0r"
client_cohere = cohere.Client(api_key_cohere)

# Create Cohere's chat model and embeddings objects
cohere_chat_model = ChatCohere(cohere_api_key=api_key_cohere, 
                               model="command-nightly", 
                               temperature=0, 
                               echo=True)
cohere_chat_model_light = ChatCohere(cohere_api_key=api_key_cohere, 
                                     model="command-light", 
                                     temperature=0, 
                                     echo=True)
cohere_embeddings = CohereEmbeddings(cohere_api_key=api_key_cohere, 
                                     model="embed-english-v3.0")


# Weaviate Instantiation
api_key_weaviate = "XdEHRl1epRJQGFMdTCbgLybatoNC25iSw8mA"
auth_config = weaviate.AuthApiKey(api_key=api_key_weaviate)

client_weaviate = weaviate.Client(
  url="https://now-cohere-hackathon-z2e1dbnn.weaviate.network", 
  auth_client_secret=auth_config,  
  timeout_config=(5, 15), 
  additional_headers={  
    "X-Cohere-Api-Key": api_key_cohere,   
  }
)


def retrieve_top_documents(
                            query: str,
                            company_names: List[str],
                            class_name: str = 'SECSavvyNOW',
                            top_n: int = 20,
                            max_distance: float = 999.0
                        ) -> List[Document]:
    """
    Retrieve top documents from Weaviate based on the provided query and company names.

    Args:
        query (str): The query string used for retrieving relevant documents.
        company_names (list of str): List of company names to filter the documents.
        class_name (str, optional): Name of the class in Weaviate. Defaults to 'SECSavvyNOW'.
        top_n (int, optional): Number of top documents to retrieve. Defaults to 20.
        max_distance (float, optional): Maximum distance for near text search. Defaults to 999.0.

    Returns:
        list of Document: List of top documents retrieved from Weaviate.
    """
    response = (
        client_weaviate.query
        .get(class_name, ["companyName", "filingUrl", "sectionSummary", "sectionPage", "chunk"])
        .with_near_text({"concepts": [query], "distance": max_distance})
        .with_where({"path": ["companyName"], "operator": "ContainsAny", "valueText": company_names})
        .with_limit(top_n)
        .do()
    )

    # Set to store unique sectionPage contents
    unique_contents = set()

    documents = []
    if 'data' in response and 'Get' in response['data'] and class_name in response['data']['Get']:
        for item in response['data']['Get'][class_name]:
            page_content = item.get("sectionPage", "")
            # Check if the content is already encountered, skip if so
            if page_content in unique_contents:
                continue
            filing_url = item.get("filingUrl", "")
            documents.append(Document(page_content=page_content, metadata={"source": filing_url}))
            # Add the content to the set of unique contents
            unique_contents.add(page_content)

    return documents


def generate_comparison_new_queries(user_query: str) -> List[str]:
    """
    Generates new queries based on the user's initial query using Cohere's chat API.
    
    Args:
        user_query (str): The initial query provided by the user.
    
    Returns:
        list: A list of new queries generated based on the user's initial query.
    """
    # Assuming 'client_cohere' is already initialized Cohere client
    try:
        new_queries_results = client_cohere.chat(message=user_query,
                                                 search_queries_only=True
                                                )
        new_queries = [x['text'] for x in new_queries_results.search_queries]
    except Exception as e:
        # Handle potential errors from the API call or processing
        print(f"An error occurred: {e}")
        new_queries = [user_query]  # Return the initial query
    
    return new_queries


def generate_comparison_template_queries(company_names: List[str], metrics: List[str] = None) -> List[Dict[str, str]]:
    """
    Generates template queries for extracting specified metrics for a list of companies,
    returning a list of dictionaries with company names and their corresponding queries.
    
    Args:
        company_names (List[str]): A list of company names.
        metrics (List[str]): Optional. A list of metrics to include in the query. Defaults to a predefined list.
    
    Returns:
        List[Dict[str, str]]: A list of dictionaries, each containing a 'company_name' key with the company name
                              and a 'query' key with the formatted query for that company.
    """
    # Default metrics if none are provided
    if metrics is None:
        metrics = [
            "Revenue", 
            "Net Income", 
            "Earnings Per Share (EPS)",
            "Total Assets",
            "Liabilities",
            "Equity",
            "Operating Cash Flow",
            "Capital Expenditures",
            "R&D Expenses",
            "Debt to Equity Ratio",
            "Market Cap"
        ]

    # Creating the query string for metrics
    metrics_string = '", "'.join(metrics)

    # Generating queries with list comprehension
    queries = [
        {
            "company_name": company,
            "query": f"Extract the following metrics for {company}: \"{metrics_string}\"."
        } for company in company_names
    ]

    return queries


def match_company_to_generated_query(company_names: List[str], queries: List[str]) -> List[Dict[str, str]]:
    """
    Matches each company name to its most relevant query based on partial matches,
    using regular expressions for flexible matching. Returns a list of dictionaries
    with each dictionary containing a company name and its matched query.
    
    Args:
        company_names (List[str]): A list of company names.
        queries (List[str]): A list of queries.
    
    Returns:
        List[Dict[str, str]]: A list of dictionaries, where each dictionary has 'company_name'
                              and 'query' keys representing matched pairs.
    """
    matched_pairs = []

    for company_name in company_names:
        # Remove common suffixes and split by spaces and non-word characters for flexible matching
        pattern_parts = re.split(r'\s+|,|\.', company_name)
        pattern = r'.*'.join(re.escape(part) for part in pattern_parts if part.lower() not in ['inc', 'com', 'corp', 'group', ''])
        
        # Compile regex pattern to match case-insensitively
        regex_pattern = re.compile(pattern, re.IGNORECASE)

        for query in queries:
            # If the regex pattern matches the query, add as a dictionary to matched_pairs
            if regex_pattern.search(query):
                matched_pairs.append({'company_name': company_name, 'query': query})
                break  # Assuming one company name matches to one query uniquely

    return matched_pairs


def generate_user_query(chat_history: str, 
                        model: ChatCohere = cohere_chat_model_light
                    ) -> str:
    """
    Generates a new user query based on the provided chat history using the specified Cohere model.

    Args:
        chat_history (str): Chat history exchanged between the user and the AI assistant.
        model (ChatCohere, optional): The Cohere model instance to use for generating the user query. 
            Defaults to cohere_chat_model_light.

    Returns:
        str: The generated user query.
    """
    # Define the template for generating the new user query
    template = """You are an intelligent assistant for generating the most concise and accurate user query based on the chat history.  
    Use the following pieces of context to generate the new user query. 
    Use two sentences maximum and keep the answer concise.
    User Query should be in a form of a question.
    Chat History: {chat_history} 
    User Query:
    """

    # Create a prompt template from the template string
    prompt = ChatPromptTemplate.from_template(template)

    # Define the processing chain
    rag_chain = (
        {"chat_history": RunnablePassthrough()}
        | prompt
        | model
        | StrOutputParser()
    )

    # Invoke the processing chain to generate the user query
    generated_query = rag_chain.invoke(chat_history)

    return generated_query


def generate_rag_prompt_template(
                                user_persona: str,
                                user_query: str,
                                company_names: List[str]
                            ) -> str:
    """
    Generates a prompt template for the RAG (Retrieval-Augmented Generation) process.

    Args:
        user_persona: The persona of the user (e.g., Individual Investor, Financial Analyst, Sales Representative).
        user_query: The user's query or question.
        company_names: List of company names being analyzed.

    Returns:
        The generated RAG prompt template.
    """
    # Define persona-specific requests and descriptions
    persona_requests = {
        "Individual Investor": "Please generate insights and key trends from the reports to assist with investment decision-making.",
        "Financial Analyst": "Please provide in-depth analysis and financial metrics extracted from the reports to facilitate detailed financial modeling.",
        "Sales Representative": "Please identify competitor strategies, market trends, and other insights from the reports to inform sales strategies and market positioning."
    }
    persona_descriptions = {
        "Individual Investor": "Seeking insights from financial reports to inform investment decisions.",
        "Financial Analyst": "Conducting in-depth analysis of financial data to provide insights and recommendations.",
        "Sales Representative": "Researching competitor strategies and market trends to inform sales strategies and market positioning."
    }

    # Constructing the prompt template
    prompt_template = (
        f"User Persona: {user_persona} - {persona_descriptions.get(user_persona, 'No description available.')}\n"
        f"User Query: {user_query}\n"
        f"Context: Analyzing 10-K and 10-Q reports of companies: {', '.join(company_names)}.\n"
        "source_documents: \n"
        "{context}"
        f"{persona_requests.get(user_persona, ' Please generate a detailed analysis based on the information extracted from the reports.')}"
    )

    # Creating Prompt object
    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context"]
    )

    return PROMPT


def is_document_relevant(document: Document, 
                         user_query: str, 
                         cohere_model: ChatCohere = cohere_chat_model_light
                        ) -> bool:
    """
    Check the relevancy of a document to the user query using the specified Cohere model.

    Args:
        document (Document): The document to check for relevancy.
        user_query (str): The user query.
        cohere_model (ChatCohere): The Cohere model instance to use for relevancy checking.

    Returns:
        bool: True if the document is relevant, False otherwise.
    """
    
    # Get the document content
    document_content = document.page_content

    # Generate the prompt using the document content and user query
    prompt = f"""Reply with YES or NO only. 
                 Is the document at least partially relevant to the query: 
                 '{user_query}'? Document content: {document_content}. \n"""
    
    # Generate response using the Cohere model
    messages = [HumanMessage(content=prompt)]
    response = cohere_model(messages)

    # Determine relevancy based on response
    return "yes" in response.content.lower()
    

def is_document_relevant_extractive_summary(document: Document, 
                                            user_query: str, 
                                            cohere_model: ChatCohere = cohere_chat_model_light
                                           ) -> bool:
    """
    Check the relevancy of a document to the user query using the specified Cohere model.

    Args:
        document (Document): The document to check for relevancy.
        user_query (str): The user query.
        cohere_model (ChatCohere): The Cohere model instance to use for relevancy checking.

    Returns:
        Document or None: If the document is relevant, return the extractive summary of the relevant part
        of the document. Otherwise, return None.
    """
    
    # Get the document content
    document_content = document.page_content

    # Generate the prompt using the document content and user query
    prompt = f"""If Document_Content partially answer the User_Query create the extractive summary of the relevant part of the document. \n
                 Do not add any additional explanation. \n
                 Otherwise, return return "irrelevant" \n\n
                 User_Query: '{user_query}' \n 
                 Document_Content: {document_content}."""

    # Generate response using the Cohere model
    messages = [HumanMessage(content=prompt)]
    response = cohere_model(messages)

    # Determine relevancy based on response
    if "irrelevant" in response.content.lower():
        return None
    else:
        return Document(page_content=response.content, metadata={"source": document.metadata['source']})


def rag(user_query: str, 
        chat_history: str = None, 
        user_persona: str = 'Individual Investor', 
        company_names: List[str] = ['UNITEDHEALTH GROUP INC']
        ) -> Tuple[str, List[str]]:
    """
    Retrieve an answer and citations related to the given user query using Cohere's RAG model.

    Args:
        user_query (str): The user query for which the answer is sought.
        chat_history (str): The chat history containing the conversation context.
        user_persona (str, optional): The persona of the user (e.g., Individual Investor, Financial Analyst, Sales Representative). Defaults to 'Individual Investor'.
        company_names (list of str, optional): List of company names being analyzed. Defaults to ['UNITEDHEALTH GROUP INC'].

    Returns:
        tuple: A tuple containing the answer text and a list of citations.
    """

    # If chat_history is not empty, refine the user query
    if chat_history:
        # Append the user query to the chat history
        combined_history = f"{chat_history}\n{user_query}"
        user_query = generate_user_query(combined_history)

    # Retrieve top relevant documents
    input_docs = retrieve_top_documents(user_query, company_names=company_names)
    
    # Filter relevant documents using the light model
    relevant_docs = []
    for doc in input_docs:
        doc_relevancy_summary = is_document_relevant_extractive_summary(doc, user_query)
        if doc_relevancy_summary:
            relevant_docs.append(doc_relevancy_summary)
    
    # Generate the RAG prompt template
    rag_prompt = generate_rag_prompt_template(user_persona=user_persona, user_query=user_query, company_names=company_names)
    
    # Generate the Response
    chain = create_stuff_documents_chain(llm=cohere_chat_model_light, prompt=rag_prompt)
    answer = chain.invoke({"context": relevant_docs})
    sources = list(set([x.metadata['source'] for x in relevant_docs]))
    search_type = "Grounded Search"
    
    return answer, sources, search_type


def rag_with_webSearch(user_query: str, 
                       chat_history: str = None, 
                       user_persona: str = 'Individual Investor', 
                       company_names: List[str] = ['UNITEDHEALTH GROUP INC']
                       ) -> Tuple[str, List[str]]:
    """
    Retrieve an answer and citations related to the given user query using Cohere's RAG model.
    Web Search is used a fallback search mechanism. 

    Args:
        user_query (str): The user query for which the answer is sought.
        chat_history (str): The chat history containing the conversation context.
        user_persona (str, optional): The persona of the user (e.g., Individual Investor, Financial Analyst, Sales Representative). Defaults to 'Individual Investor'.
        company_names (list of str, optional): List of company names being analyzed. Defaults to ['UNITEDHEALTH GROUP INC'].

    Returns:
        tuple: A tuple containing the answer text and a list of citations.
    """

    # If chat_history is not empty, refine the user query
    if chat_history:
        # Append the user query to the chat history
        combined_history = f"{chat_history}\n{user_query}"
        user_query = generate_user_query(combined_history)

    # Retrieve top relevant documents
    if len(company_names) > 1:
        # Creating company specific query
        user_queries = generate_comparison_template_queries(company_names)
        input_docs = []
        for pair in user_queries:
            company_name = pair['company_name']
            company_query = pair['query']
            query_docs = retrieve_top_documents(company_query, company_names=[company_name], top_n=10)
            input_docs += query_docs
    else:
        input_docs = retrieve_top_documents(user_query, company_names=company_names)
    
    # Check if input_docs is empty
    if not input_docs:
        # Fall back to web search with user_persona and company_names included in the query
        search_query = f"{user_query} related to user persona of {user_persona} and companies {' '.join(company_names)}"
        rag_retriever = CohereRagRetriever(llm=cohere_chat_model, connectors=[{"id": "web-search"}])
        docs = rag_retriever.get_relevant_documents(search_query)
        # Extract answer and citations
        answer = docs[-1].page_content
        sources = 'Web Search'
        search_type = 'Connector'
    else:
        # Filter relevant documents using the light model
        relevant_docs = []
        for doc in input_docs:
            doc_relevancy_summary = is_document_relevant_extractive_summary(doc, user_query)
            if doc_relevancy_summary:
                relevant_docs.append(doc_relevancy_summary)
        # Check if relevant_docs is empty
        if not relevant_docs:
            # Fall back to web search with user_persona and company_names included in the query
            search_query = f"{user_query} related to user persona of {user_persona} and companies {' '.join(company_names)}"
            rag_retriever = CohereRagRetriever(llm=cohere_chat_model, connectors=[{"id": "web-search"}])
            docs = rag_retriever.get_relevant_documents(search_query)
            # Extract answer and citations
            answer = docs[-1].page_content
            sources = 'Web Search'
            search_type = 'Connector'
        else:
            # Generate the RAG prompt template
            rag_prompt = generate_rag_prompt_template(user_persona=user_persona, user_query=user_query, company_names=company_names)
            # Generate the Response
            chain = create_stuff_documents_chain(llm=cohere_chat_model_light, prompt=rag_prompt)
            answer = chain.invoke({"context": relevant_docs})
            sources = list(set([x.metadata['source'] for x in relevant_docs]))
            search_type = "Grounded Search"
    
    # Check if docs is empty
    if not answer:
        return "No relevant information found. Please try again later.", [], ''

    return answer, sources, search_type


# def rag_with_webSearch(user_query: str, 
#                        chat_history: str = None, 
#                        user_persona: str = 'Individual Investor', 
#                        company_names: List[str] = ['UNITEDHEALTH GROUP INC']
#                        ) -> Tuple[str, List[str]]:
#     """
#     Retrieve an answer and citations related to the given user query using Cohere's RAG model.
#     Web Search is used a fallback search mechanism. 

#     Args:
#         user_query (str): The user query for which the answer is sought.
#         chat_history (str): The chat history containing the conversation context.
#         user_persona (str, optional): The persona of the user (e.g., Individual Investor, Financial Analyst, Sales Representative). Defaults to 'Individual Investor'.
#         company_names (list of str, optional): List of company names being analyzed. Defaults to ['UNITEDHEALTH GROUP INC'].

#     Returns:
#         tuple: A tuple containing the answer text and a list of citations.
#     """

#     # If chat_history is not empty, refine the user query
#     if chat_history:
#         # Append the user query to the chat history
#         combined_history = f"{chat_history}\n{user_query}"
#         user_query = generate_user_query(combined_history)

#     # Retrieve top relevant documents
#     if len(company_names) > 1:
#         # Creating company specific query
#         user_queries = generate_comparison_new_queries(user_query)
#         # Match the query and the company name
#         matched_pairs = match_company_to_generated_query(queries=user_queries, company_names=company_names)
#         input_docs = []
#         for pair in matched_pairs:
#             company_name = pair['company_name']
#             company_query = pair['query']
#             query_docs = retrieve_top_documents(company_query, company_names=[company_name], top_n=10)
#             input_docs += query_docs
#     else:
#         input_docs = retrieve_top_documents(user_query, company_names=company_names)
    
#     # Check if input_docs is empty
#     if not input_docs:
#         # Fall back to web search with user_persona and company_names included in the query
#         search_query = f"{user_query} related to user persona of {user_persona} and companies {' '.join(company_names)}"
#         rag_retriever = CohereRagRetriever(llm=cohere_chat_model, connectors=[{"id": "web-search"}])
#         docs = rag_retriever.get_relevant_documents(search_query)
#         # Extract answer and citations
#         answer = docs[-1].page_content
#         sources = 'Web Search'
#         search_type = 'Connector'
#     else:
#         # Filter relevant documents using the light model
#         relevant_docs = []
#         for doc in input_docs:
#             doc_relevancy_summary = is_document_relevant_extractive_summary(doc, user_query)
#             if doc_relevancy_summary:
#                 relevant_docs.append(doc_relevancy_summary)
#         # Check if relevant_docs is empty
#         if not relevant_docs:
#             # Fall back to web search with user_persona and company_names included in the query
#             search_query = f"{user_query} related to user persona of {user_persona} and companies {' '.join(company_names)}"
#             rag_retriever = CohereRagRetriever(llm=cohere_chat_model, connectors=[{"id": "web-search"}])
#             docs = rag_retriever.get_relevant_documents(search_query)
#             # Extract answer and citations
#             answer = docs[-1].page_content
#             sources = 'Web Search'
#             search_type = 'Connector'
#         else:
#             # Generate the RAG prompt template
#             rag_prompt = generate_rag_prompt_template(user_persona=user_persona, user_query=user_query, company_names=company_names)
#             # Generate the Response
#             chain = create_stuff_documents_chain(llm=cohere_chat_model_light, prompt=rag_prompt)
#             answer = chain.invoke({"context": relevant_docs})
#             sources = list(set([x.metadata['source'] for x in relevant_docs]))
#             search_type = "Grounded Search"
    
#     # Check if docs is empty
#     if not answer:
#         return "No relevant information found. Please try again later.", [], ''

#     return answer, sources, search_type
    
