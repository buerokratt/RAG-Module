OUT_OF_SCOPE_MESSAGE = (
    "I apologize, but I’m unable to provide a complete response because the available "
    "context does not sufficiently cover your request. Please try rephrasing or providing more details."
)

TECHNICAL_ISSUE_MESSAGE = (
    "2. Technical issue with response generation\n"
    "I apologize, but I’m currently unable to generate a response due to a temporary technical issue. "
    "Please try again in a moment."
)

UNKNOWN_SOURCE = "Unknown source"

INPUT_GUARDRAIL_VIOLATION_MESSAGE = "I apologize, but I'm unable to assist with that request as it violates our usage policies."

OUTPUT_GUARDRAIL_VIOLATION_MESSAGE = "I apologize, but I'm unable to provide a response as it may violate our usage policies."

GUARDRAILS_BLOCKED_PHRASES = [
    "i'm sorry, i can't respond to that",
    "i cannot respond to that",
    "i cannot help with that",
    "this is against policy",
]

# Streaming configuration
STREAMING_ALLOWED_ENVS = {"production"}
TEST_DEPLOYMENT_ENVIRONMENT = "testing"
