from langchain.retrievers import ContextualCompressionRetriever, CohereRagRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain_community.embeddings import CohereEmbeddings
from langchain_community.chat_models import ChatCohere
from langchain.docstore.document import Document
import cohere
import weaviate
import streamlit as st
from streamlit_pills import pills

from main import retrieve_top_documents
from main import rag, rag_with_webSearch
import constants

import requests
import json
import os
import numpy as np
import pandas as pd
import random

import warnings
warnings.filterwarnings("ignore")

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
        st.image('img/sparkle_purple.svg')
    with columns[1]:
        st.write('SECSavvyNow by ServiceNow')
    persona = pills('Choose a persona.', ['Sales Representative', 'Investor', 'Financial Analyst'], index=1)
    company = st.selectbox('Choose a company to analyze.', constants.companies, index=constants.companies.index('ServiceNow, Inc.'))
    feature = pills('Choose a feature.', ['Questions', 'Summarize', 'Compare'], index=0)
    
    if feature == 'Compare':
        choice = st.multiselect(label='Select up to two companies to compare the above company to.', options=[item for item in constants.companies if item != company], max_selections=2)

    clear_chat = st.button('➕ New Topic', type='primary', help='Restart the chat.')    
if clear_chat:
    st.session_state.messages = []

if feature == 'Summarize':
    st.markdown("<h5 style='text-align: center; color: gray;'>Choose the section you want to summarize.</h5>", unsafe_allow_html=True)

    buttons = []
    columns = st.columns(2)
    for index, i in enumerate(constants.summary_sections):
        col_num = 0  if index < len(constants.summary_sections)//2 else 1
        with columns[col_num]:
            button = st.button(i, use_container_width=True, type='primary')
            buttons.append(button)
    choice = None if True not in buttons else constants.summary_sections[buttons.index(True)]
elif feature == 'Questions':
    st.markdown("<h5 style='text-align: center; color: gray;'>Choose the question you want to explore.</h5>", unsafe_allow_html=True)
    if persona == 'Sales Representative':
        buttons = []
        columns = st.columns(2)
        for index, i in enumerate(constants.sales_questions):
            col_num = 0  if index < len(constants.sales_questions)//2 else 1
            with columns[col_num]:
                button = st.button(i, use_container_width=True, type='primary')
                buttons.append(button)
        choice = None if True not in buttons else constants.sales_questions[buttons.index(True)]
    elif persona == 'Investor':
        buttons = []
        columns = st.columns(2)
        for index, i in enumerate(constants.investor_questions):
            col_num = 0  if index < len(constants.investor_questions)//2 else 1
            with columns[col_num]:
                button = st.button(i, use_container_width=True, type='primary')
                buttons.append(button)
        choice = None if True not in buttons else constants.investor_questions[buttons.index(True)]
    else:
        buttons = []
        columns = st.columns(2)
        for index, i in enumerate(constants.fin_questions):
            col_num = 0  if index < len(constants.fin_questions)//2 else 1
            with columns[col_num]:
                button = st.button(i, use_container_width=True, type='primary')
                buttons.append(button)
        choice = None if True not in buttons else constants.fin_questions[buttons.index(True)]

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
        with st.spinner(f'Generating the Answer: ...'):
            if feature == 'Compare':
                company_list = choice + [company]
            else:
                company_list = [company]
            answer, citations, search_type = rag_with_webSearch(user_query=prompt_msg, 
                                                                user_persona=persona, 
                                                                company_names=company_list)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        message_placeholder.markdown(f"Answer: {answer}\n\r Citation:\n\r{search_type}: {citations}")
