import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import sys
import os

# Add parent directory to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import generate_response

class TestLLMClient(unittest.TestCase):

    @patch('src.llm_client.urllib.request.urlopen')
    def test_generate_response_success(self, mock_urlopen):
        # Setup mock
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"response": "Hello, I am JARVIS."}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute
        result = generate_response("Who are you?")
        
        # Assert
        self.assertEqual(result, "Hello, I am JARVIS.")
        mock_urlopen.assert_called_once()

    @patch('src.llm_client.urllib.request.urlopen')
    def test_generate_response_connection_error(self, mock_urlopen):
        # Setup mock to raise URLError
        mock_urlopen.side_effect = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
        
        # Execute
        result = generate_response("Hello")
        
        # Assert
        self.assertIn("Error: Could not connect to Ollama", result)

if __name__ == "__main__":
    unittest.main()
