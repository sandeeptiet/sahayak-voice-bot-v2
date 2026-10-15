import json
import boto3
from botocore.config import Config

client = boto3.Session(profile_name="default").client(
    "bedrock-runtime",
    region_name="ap-south-1",
    config=Config(retries={"total_max_attempts": 1}),
)
response = client.invoke_model(
    modelId="amazon.titan-embed-text-v2:0",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "inputText": "Wi-Fi is connected but websites do not open.",
        "dimensions": 1024,
        "normalize": True,
    }),
)
result = json.loads(response["body"].read())
print("Embedding dimensions:", len(result["embedding"]))
print("Input tokens:", result["inputTextTokenCount"])