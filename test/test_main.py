import unittest
from unittest.mock import patch, Mock
from src.main import (
    retrieve_top_documents, 
    generate_comparison_new_queries, 
    generate_comparison_template_queries, 
    match_company_to_generated_query
)

class TestMainFunctions(unittest.TestCase):

    def setUp(self):
        # Mocking the API keys and secrets for the services
        self.mock_api_key_cohere = 'mock_api_key_cohere'
        self.mock_api_key_weaviate = 'mock_api_key_weaviate'
        self.mock_url_weaviate = 'mock_url_weaviate'
        
        # Setup mock responses
        self.mock_weaviate_response = {
            'data': {
                'Get': {
                    'SECSavvyNOW': [
                        {
                            'companyName': 'Mock Company',
                            'filingUrl': 'http://example.com',
                            'sectionSummary': 'Mock Summary',
                            'sectionPage': 'Mock Page Content',
                            'chunk': 'Mock Chunk'
                        }
                    ]
                }
            }
        }

    def test_retrieve_top_documents(self, mock_get):
        # Mock the get call to Weaviate and set a return value
        mock_get.return_value = self.mock_weaviate_response
        
        # Call the function with test data
        documents = retrieve_top_documents(
            query='revenue',
            company_names=['Mock Company'],
            class_name='SECSavvyNOW',
            top_n=1,
            max_distance=1.0
        )
        
        # Assertions to check if the mocked data is returned correctly
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata['source'], 'http://example.com')
        self.assertEqual(documents[0].page_content, 'Mock Page Content')

    @patch('main.client_cohere.chat')
    def test_generate_comparison_new_queries(self, mock_chat):
        # Mock the chat call to Cohere and set a return value
        mock_chat.return_value = {'search_queries': [{'text': 'Mock Query 1'}, {'text': 'Mock Query 2'}]}
        
        # Call the function with test data
        new_queries = generate_comparison_new_queries(user_query='revenue')
        
        # Assertions to check if the mocked data is returned correctly
        self.assertIn('Mock Query 1', new_queries)
        self.assertIn('Mock Query 2', new_queries)

    def test_generate_comparison_template_queries(self):
        # Call the function with test data
        company_names = ['Mock Company A', 'Mock Company B']
        queries = generate_comparison_template_queries(company_names=company_names)
        
        # Assertions to check if the template is generated correctly
        self.assertEqual(len(queries), 2)
        self.assertTrue(any(d['company_name'] == 'Mock Company A' for d in queries))
        self.assertTrue(any(d['company_name'] == 'Mock Company B' for d in queries))

    def test_match_company_to_generated_query(self):
        # Call the function with test data
        company_names = ['Mock Company A', 'Mock Company B']
        queries = ['Mock Company A revenue', 'Mock Company B revenue']
        matched = match_company_to_generated_query(company_names, queries)
        
        # Assertions to check if the companies are matched correctly
        self.assertEqual(len(matched), 2)
        self.assertTrue(any(d['company_name'] == 'Mock Company A' for d in matched))
        self.assertTrue(any(d['company_name'] == 'Mock Company B' for d in matched))

    # You can add more test cases for other functions

if __name__ == '__main__':
    unittest.main()
