# test_openai.py
import os
from openai import OpenAI

# Set API key
os.environ["OPENAI_API_KEY"] = "your-api-key"

# Create client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Test a simple API call
models = client.models.list()
print(f"Available models: {len(models.data)}")