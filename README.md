# Enterprise-AI-Hackathon
Generative AI for Business Use Cases w. Cohere &amp; NYSE

# SECSavvyNow - Advanced Financial Insights and Analysis Platform
SECSavvyNow is an innovative platform designed to revolutionize the way analysts, investors, and business professionals access and analyze financial information. Utilizing state-of-the-art language models and retrieval technologies, SECSavvyNow offers a comprehensive suite of tools for extracting, comparing, and summarizing key financial metrics and insights from vast repositories of corporate filings and documents.

## Objective:

SECSavvyNow aims to democratize access to complex financial information, making it easier for professionals to conduct in-depth analyses, perform competitive intelligence, and make informed decisions without the need for extensive manual research. By automating the extraction and analysis of critical financial data, SECSavvyNow not only saves time but also uncovers insights that might otherwise remain hidden in the vast amount of corporate filings and financial reports.

## Core Features:

Contextual Information Retrieval: Leverages the Contextual Compression Retriever and CohereRag Retriever to fetch relevant documents from a custom document store powered by Weaviate, an AI-first database. This enables users to query specific financial metrics or topics and receive the most pertinent information based on their query context.

Dynamic Query Generation: Utilizes Cohere's powerful NLP models to dynamically generate new queries or refine existing ones based on user inputs and ongoing conversations. This adaptive query mechanism ensures that the information retrieval process remains highly focused and efficient.

Advanced Document Summarization: Employs CohereRerank and custom summarization techniques to distill lengthy financial documents into concise summaries, highlighting critical data points such as revenue, net income, EPS, and market cap among others.

Financial Comparisons: Features a specialized query generation system that constructs comparative analyses of selected companies based on a wide array of financial metrics. This allows users to easily compare performance, strategy, and market positioning across different entities.

Interactive Chat Interface: Powered by ChatCohere, the platform offers an interactive, conversational interface that guides users through their information discovery journey, providing personalized insights and responses.

Relevancy Checks and Extractive Summaries: Incorporates a rigorous document relevancy evaluation framework, ensuring that only the most relevant documents are presented to the user. For documents deemed relevant, the platform can generate extractive summaries, focusing on the parts of the documents that directly answer the user's queries.

## Technology Stack:

Cohere's NLP Models: At the heart of SECSavvyNow are Cohere's advanced language models, which power the platform's chat models, embeddings, and document summarization capabilities.

Weaviate Vector Database: Utilized for its AI-first approach to data storage and retrieval, enabling semantic search capabilities that are critical for the platform's efficient document fetching mechanism.

Modern Web Technologies: Incorporates technologies such as Streamlit for the web interface, ensuring a smooth and accessible user experience.
