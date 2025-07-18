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
