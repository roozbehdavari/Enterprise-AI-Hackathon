from langchain.retrievers import ContextualCompressionRetriever, CohereRagRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain_community.embeddings import CohereEmbeddings
from langchain_community.chat_models import ChatCohere
from langchain.docstore.document import Document
import cohere
import weaviate
import streamlit as st
from streamlit_pills import pills

from utils import retrieve_top_documents
from utils import rag, rag_with_webSearch

import requests
import json
import os
import numpy as np
import pandas as pd
import extra

import warnings
warnings.filterwarnings("ignore")

# Instantiate Cohere
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


# Instantiate Weaviate
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

def prefill_prompts(action, choice, company):
    
    if action == None:
        return
    
    # list of companies
    if type(choice) == list:
        choice = ", ".join(choice)
        
    prompts = {
        'Summarize': 'Summarize the following section',
        'Questions': 'Answer the following question',
        'Compare': 'Compare these companies',
    }
        
    # grammar fix 
    if action == 'Compare':
        prefill = f'{prompts[action]} with {company}: {str(choice)}'
    else:
        prefill = f'{prompts[action]} for {company}: {str(choice)}'

    js = f"""
        <script>
            function insertText(dummy_var_to_force_repeat_execution) {{
                var chatInput = parent.document.querySelector('textarea[data-testid="stChatInput"]');
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                nativeInputValueSetter.call(chatInput, "{prefill}");
                var event = new Event('input', {{ bubbles: true}});
                chatInput.dispatchEvent(event);
            }}
            insertText({len(st.session_state.messages)});
        </script>
        """
    st.components.v1.html(js, height=0)

## --- ##

# Set Streamlit config
st.set_page_config(layout="wide")
if "messages" not in st.session_state:
    st.session_state.messages = []

# custom_css = """
#     <style>
#         section.stSidebar .stButton button {
#                 background-color: #298319;
#                 border-color: #DBE1E7;
#                 color: #368B28;
#                 height: 48px;
#         }
#         .stButton button:first-child {
#             background-color: #F9F9FD;
#             border-color: #DBE1E7;
#             color: #368B28;
#             height: 48px;
#         }
#         .stButton button:hover {
#             background-color: #F5F4F2;
#             border-color: #DBE1E7;
#             color: #368B28;
#         }
#         head, body, h1, h2, h3, h4, h5, h6, p, span, div {
#             font-family: 'Lato', sans-serif;
#         }
#         p {
#             font-size: 18px;
#         }
#     </style>
# """
#368B28 theme primary color
custom_css = """
    <style>
        .st-emotion-cache-bgrkbf {
            background-color: #F9F9FD;
            border-color: #DBE1E7;
            color: #368B28;
            height: 48px;
        }
        .st-emotion-cache-bgrkbf:hover {
            background-color: #F5F4F2;
            border-color: #DBE1E7;
            color: #368B28;
            height: 48px;
        }
        .st-emotion-cache-lxjuph {
            background-color: #298319;
            border-color: #3A3F51;
            color: #FFFFFF;
        }
        .st-emotion-cache-lxjuph:hover {
            background-color: #5DB14E;
            border-color: #3A3F51;
            color: #FFFFFF;
        }
        .pill {
            font-size: 14px;
        }
        .st-emotion-cache-16idsys p {
            font-size: 16px;
        }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

#000000 choose a persona, company, feature 20px
#1F1F1F BLACK
#298319 dark green

st.markdown("<h2 style='text-align: center; color: black;'>SECSavvyNow</h2>", unsafe_allow_html=True)

with st.sidebar:
    columns = st.columns([0.1, 0.9])
    with columns[0]:
        st.image('sparkle_purple.svg')
    with columns[1]:
        st.write('SECSavvyNow by ServiceNow')
    persona = pills('Choose a persona.', ['Sales Representative', 'Investor', 'Financial Analyst'], index=1)
    company = st.selectbox('Choose a company to analyze.', extra.companies, index=extra.companies.index('ServiceNow, Inc.'))
    feature = pills('Choose a feature.', ['Questions', 'Summarize', 'Compare'], index=0)
    if feature == 'Compare':
        choice = st.multiselect(label='Choose two companies to compare the above company to.', options=[item for item in extra.companies if item != company], max_selections=2)

    clear_chat = st.button('➕ New Topic', type='primary', help='Restart the chat.')
    
if clear_chat:
    st.session_state.messages = []

if feature == 'Summarize':
    st.markdown("<h5 style='text-align: center; color: gray;'>Choose the section you want to summarize.</h5>", unsafe_allow_html=True)

    # choice = pills(label='Summarize Options', options=extra.summary_sections, label_visibility='collapsed', index=None)
    buttons = []
    columns = st.columns(2)
    for index, i in enumerate(extra.summary_sections):
        col_num = 0  if index < len(extra.summary_sections)//2 else 1
        with columns[col_num]:
            button = st.button(i, use_container_width=True, type='primary')
            buttons.append(button)
    choice = None if True not in buttons else extra.summary_sections[buttons.index(True)]
elif feature == 'Questions':
    st.markdown("<h5 style='text-align: center; color: gray;'>Choose the question you want to explore.</h5>", unsafe_allow_html=True)
    if persona == 'Sales Representative':
        # choice = st.radio(label='Question Options', options=extra.sales_questions, label_visibility='collapsed', index=None)
        buttons = []
        columns = st.columns(2)
        for index, i in enumerate(extra.sales_questions):
            col_num = 0  if index < len(extra.sales_questions)//2 else 1
            with columns[col_num]:
                button = st.button(i, use_container_width=True, type='primary')
                buttons.append(button)
        choice = None if True not in buttons else extra.sales_questions[buttons.index(True)]
    elif persona == 'Investor':
        # choice = st.radio(label='Question Options', options=extra.investor_questions, label_visibility='collapsed', index=None)
        buttons = []
        columns = st.columns(2)
        for index, i in enumerate(extra.investor_questions):
            col_num = 0  if index < len(extra.investor_questions)//2 else 1
            with columns[col_num]:
                button = st.button(i, use_container_width=True, type='primary')
                buttons.append(button)
        choice = None if True not in buttons else extra.investor_questions[buttons.index(True)]
    else:
        # choice = st.radio(label='Question Options', options=extra.fin_questions, label_visibility='collapsed', index=None)
        buttons = []
        columns = st.columns(2)
        for index, i in enumerate(extra.fin_questions):
            col_num = 0  if index < len(extra.fin_questions)//2 else 1
            with columns[col_num]:
                button = st.button(i, use_container_width=True, type='primary')
                buttons.append(button)
        choice = None if True not in buttons else extra.fin_questions[buttons.index(True)]

# Load history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if choice is not None:
    prefill_prompts(feature, choice, company)

# Chat interface
if prompt_msg := st.chat_input("Ask a follow-up question..."):
    st.session_state.messages.append({"role": "user", "content": prompt_msg})
    with st.chat_message("user"):
        st.markdown(prompt_msg)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Fetching the answer..."):
            answer, citations, search_type = rag_with_webSearch(user_query=prompt_msg, 
                                                                user_persona=persona, 
                                                                company_names=[company])
            print(citations, search_type)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        #message_placeholder.markdown(answer)
        message_placeholder.markdown(f"Answer: {answer}\n\r Citation:{citations}\n\r Search Type:{search_type}")
        # st.write(df)st.table(df)
