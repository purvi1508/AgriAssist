def build_farmer_profile_prompt(input_text: str, parser) -> str:
    """
    Builds a structured prompt for extracting a farmer's profile in JSON format.

    Args:
        input_text (str): The raw text input containing farmer information.
        parser: A parser object that includes a get_format_instructions() method.

    Returns:
        str: A formatted prompt string.
    """
    prompt = f"""
    Extract a structured JSON of the farmer's profile and personalization preferences from the following text. 
    Only include information mentioned or clearly inferable. Leave missing values as `null` or empty lists where appropriate.

    {input_text}

    {parser.get_format_instructions()}
    """
    return prompt

def farmer_intent_planner_prompt(
    input_text: str,
    age: int,
    state: str,
    category: str,
    crop: str,
    income: int,
    land_size_acres: float,
    parser
) -> str:
    profile_str = f"""Farmer Profile:
- State: {state}
- Age: {age}
- Category: {category}
- Crop: {crop}
- Income: ₹{income}
- Land Size: {land_size_acres} acres"""

    format_instructions = parser.get_format_instructions()

    prompt = f"""
You are a smart assistant that helps farmers understand government schemes.

Given the farmer's profile and a query, extract:
1. The farmer's **intent**, including any specific **problem or need** they mention (intent)
2. The relevant scheme topic (scheme_topic)
- If the farmer asks about a specific location (e.g. state or district), include it in the scheme_topic.
{profile_str}

Farmer Query: "{input_text}"

Respond in this JSON format:
{format_instructions}
"""

    return prompt
def relevance_checker_prompt(response_text, profile, parser):
    return f"""
You are a government scheme advisor assistant for Indian farmers.

Given:
• Recommendation: "{response_text}"
• Farmer Profile: {profile}

Evaluate if this scheme recommendation is truly relevant for the farmer based on:
- Location (state/district)
- Financial status (land ownership, land size, income)
- Crop type
- Eligibility criteria (SC/ST/OBC/general etc.)

Respond with your judgment and reasoning.

{parser.get_format_instructions()}
""".strip()


def final_response_prompt(query, response_text, is_relevant, reason, parser):
    return f"""
You are a helpful AI assistant for farmers.

The farmer asked: "{query}"

Here is a government scheme recommendation:
"{response_text}"

Assessment of relevance: {"Yes" if is_relevant else "No"}
Reason: {reason}

Now write a final response for the farmer. If the recommendation is not relevant, suggest general advice or encourage visiting the nearest Krishi Vigyan Kendra or agriculture office.

{parser.get_format_instructions()}
""".strip()
