import httpx
import llm
from pydantic import BaseModel

import os



class Result(BaseModel):
    categories: list[str]


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def fetch_content_from_url(url: str) -> str:
    """
    Fetches the content from the given URL.

    Args:
        url (str): The URL to fetch content from.

    Returns:
        str: The content fetched from the URL.
    """
    llm_friendly_jina_ai_url = f"https://r.jina.ai/{url}"
    response = httpx.get(llm_friendly_jina_ai_url)
    return response.text


def parse_contents(contents: str):
    headers, markdown_body = contents.split("Markdown Content:", 1)
    header = {}
    for header_line in headers.splitlines():
        if header_line.strip() != "":
            header_name, header_value = header_line.split(":", 1)
            header[header_name.strip()] = header_value.strip()
    # most case
    # Title, URL Source
    return header, markdown_body


def get_summary_from_url(url: str):
    contents = fetch_content_from_url(url)
    model = llm.get_model("gemini-2.5-pro-exp-03-25")
    model.key = GEMINI_API_KEY
    response = model.prompt(
        contents,
        system="""make readable title and summary in korean as markdown format,
                summary should be list of minimum 3, maximum 5 items""",
    )
    # header, markdown_body = parse_contents(contents)
    return response.text()


def translate_to_korean(content: str):
    english_text = content
    model = llm.get_model("gemini-2.5-pro-exp-03-25")
    model.key = GEMINI_API_KEY
    response = model.prompt(
        f"Please translate the following English text accurately to Korean.\n\n{english_text}",
        system="Your are a helpful assistant that translates English text to Korean.",
    )

    return response.text()


def categorize_summary(summary: str, categories: list[str]):
    category_list_str = [f"'{category}'" for category in categories]
    model = llm.get_model("gemini-2.5-pro-exp-03-25")
    model.key = GEMINI_API_KEY
    response = model.prompt(
        f"Please categories the following article summary:\n\n{summary}",
        system=f"""
- You are a helpful assistant that categorizes technical articles based on their summary. 
- Assign one or more relevant categories from the following list: {category_list_str}. 
- Respond with ONLY the category names, separated by commas (e.g., 'Web Development, Large Language Models'). 
- If none fit well, respond with 'Other'.
        """,
    )

    return response.text()
