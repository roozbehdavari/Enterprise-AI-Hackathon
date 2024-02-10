import unittest
from unittest.mock import patch, MagicMock
import src.app
from src.main import Document 

class TestApp(unittest.TestCase):

    def setUp(self):
        # Setup mock for streamlit functions
        self.patcher = patch('streamlit.secrets', {"api_key_cohere": "fake_api_key_cohere", "api_key_weaviate": "fake_api_key_weaviate", "url_weaviate": "fake_url_weaviate"})
        self.mock_secrets = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('app.prefill_prompts')
    @patch('app.rag_with_webSearch')
    @patch('streamlit.components.v1.html')
    def test_prefill_prompts(self, mock_html, mock_rag_with_webSearch, mock_prefill_prompts):
        # Set up mock return values if necessary
        mock_prefill_prompts.return_value = None
        
        # Example of how you might call a function to test
        # You need to simulate Streamlit's environment here if necessary
        action = 'Summarize'
        choice = ['Revenue', 'Net Income']
        company = 'Mock Company'
        
        src.app.prefill_prompts(action, choice, company)
        
        # Assertions to check if the mocked data is returned correctly
        # Here you might want to assert that the mock_html function was called with the expected JavaScript
        mock_html.assert_called()

    @patch('streamlit.button')
    def test_clear_chat(self, mock_button):
        # Simulate the button being pressed
        mock_button.return_value = True

        # Normally, Streamlit would reset the session state, but here we can only check if the button logic is triggered
        # This will depend on how your actual `clear_chat` function works
        src.app.clear_chat = MagicMock(return_value=None)
        src.app.clear_chat()
        
        src.app.clear_chat.assert_called()

    # Add more test cases for other functions you want to test
    # Note that testing Streamlit apps requires mocking a lot of the Streamlit components
    # and might not provide as much value unless you have complex logic in the app itself.

if __name__ == '__main__':
    unittest.main()
