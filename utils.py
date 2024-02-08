from langchain.retrievers import ContextualCompressionRetriever, CohereRagRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain_community.embeddings import CohereEmbeddings
from langchain_community.chat_models import ChatCohere
from langchain.docstore.document import Document
from langchain.schema import HumanMessage
from langchain.prompts import PromptTemplate

import cohere
import weaviate

import requests
import json
from typing import List


# Cohere Instantiation
api_key_cohere = "xxxxxx"
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
api_key_weaviate = "xxxxxxxxxx"
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
    class_name: str = 'SECSavvyNOWClean',
    top_n: int = 20,
    max_distance: float = 999.0
) -> List[Document]:
    """
    Retrieve top documents from Weaviate based on the provided query and company names.

    Args:
        query (str): The query string used for retrieving relevant documents.
        company_names (list of str): List of company names to filter the documents.
        class_name (str, optional): Name of the class in Weaviate. Defaults to 'SECSavvyNOWClean'.
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
        "{source_documents}"
        f"{persona_requests.get(user_persona, 'Please generate a detailed analysis based on the information extracted from the reports.')}"
    )

    # Creating Prompt object
    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["source_documents"]
    )

    return PROMPT




def is_document_relevant(document, user_query, cohere_model):
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
    prompt = f"Reply with YES or NO only. Is the document at least partially relevant to the query: '{user_query}'? Document content: {document_content}. \n"
    
    # Generate response using the Cohere model
    messages = [HumanMessage(content=prompt)]
    response = cohere_model(messages)

    # Determine relevancy based on response
    return "yes" in response.content.lower()



def is_document_relevant_extractive_summary(document, user_query, cohere_model):
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
    prompt = f"""Does the Document_Content partially answer the User_Query? \n 
                 If Yes, Provide only the extractive summary of the relevant part of the document. Do not add any additional explanation. \n
                 If No, return the word 'IRRELEVANT' and nothing else. \n\n
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
    

def rag(user_query, user_persona='Individual Investor', company_names=['UNITEDHEALTH GROUP INC']):
    """
    Retrieve an answer and citations related to the given user query using Cohere's RAG model.

    Args:
        user_query (str): The user query for which the answer is sought.

    Returns:
        tuple: A tuple containing the answer text and a list of citations.

    Notes:
        This function assumes that the necessary variables like api_key_cohere and client_weaviate
        are already defined and accessible within the scope.

    """
    # Retrieve top relevant documents
    input_docs = retrieve_top_documents(user_query, company_names=company_names)

    # Filter relevant documents using the light model
    relevant_docs = []
    for doc in input_docs:
        if is_document_relevant(doc, user_query, cohere_chat_model_light):
            relevant_docs.append(doc)

    # # Generate the Prompt based on 
    rag_prompt = generate_rag_prompt_template(user_persona=user_persona, 
                                              user_query=user_query,
                                              company_names=company_names)
    
    # Create the Cohere RAG retriever using the chat model 
    rag = CohereRagRetriever(llm=cohere_chat_model, rag_prompt=rag_prompt)
    docs = rag.get_relevant_documents(user_query, 
                                      source_documents=relevant_docs)
    
    # Extract answer and citations
    answer = docs[-1].page_content
    citations = docs[-1].metadata.get('citations', [])
    
    return answer, citations
