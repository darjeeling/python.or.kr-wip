from pydantic import BaseModel, Field
from pydantic_ai import Agent
from datetime import date, datetime, time, timedelta

from django.core.files.base import ContentFile

class TranslatedResult(BaseModel):
    title: str = Field(description="The title of the translated article")
    slug: str = Field(
        description="The URL slug. Do not include the language code. Make it similar to the original URL."
    )
    description: str = Field(
        description="The description of the translated article. Don't mention that it's translated."
    )
    author: str = Field(description="The author of the translated article")
    tags: list[str] = Field(
        description="List of Python-related tags inferred from the document."
    )
    written_date: date = Field(description="The written date of the translated article")
    content: str = Field(description="The content of the translated article")

def translate_rssitem(rss_item_id: int):
    from .models import LLMService, LLMUsage, TranslatedContent, RSSItem
    """
    Translate an RSS item to Korean using AI and save as TranslatedContent.
    
    Args:
        rss_item: RSSItem instance to translate
        
    Returns:
        TranslatedContent: The created translated content instance
    """
    rss_item = RSSItem.objects.get(id=rss_item_id)
    
    # Get LLM provider and model
    provider, model = LLMService.get_llm_provider_model()
    if not provider or not model:
        raise ValueError("No available LLM service found")
    
    model_name = f"{provider}:{model}"
    
    # Read the crawled content from the file
    if not rss_item.crawled_content:
        raise ValueError("RSS item has no crawled content")
    
    with rss_item.crawled_content.open('r') as f:
        content = f.read()
    
    # Create AI agent for translation
    agent = Agent(
        model_name, 
        output_type=TranslatedResult, 
        system_prompt="Translate the following markdown article in full to korean"
    )
    
    # Run translation
    try:
        result = agent.run_sync(content)
    except Exception as e:
        # Set RSS item status to failed and save error message
        rss_item.crawling_status = 'failed'
        rss_item.translate_error_message = str(e)
        rss_item.save(update_fields=['crawling_status', 'translate_error_message'])
        raise
    
    # Create TranslatedContent instance
    translated_content = TranslatedContent(
        title=result.output.title,
        slug=result.output.slug,
        description=result.output.description,
        author=result.output.author,
        tags=result.output.tags,
        written_date=result.output.written_date,
        model_name=model_name,
        source_rss_item=rss_item,
        source_url=rss_item.link
    )
    
    # save to get instance id
    translated_content.save()
    # Save the translated content to a file
    content_file = ContentFile(result.output.content, name=f"{rss_item.id}-translated.md")
    translated_content.content.save(f"{rss_item.id}-translated.md", content_file)
    # save again to update the content field
    translated_content.save()
    
    # Create LLM usage record
    usage = result.usage()
    LLMUsage.objects.create(
        model_name=model_name,
        input_tokens=usage.request_tokens,
        output_tokens=usage.response_tokens,
        total_tokens=usage.total_tokens
    )
    
    return translated_content

class PyCondersSource(BaseModel):
    title: str = Field(description="The title of curated article title")
    summary: str = Field(
        description="summary of curated article"
    )
    curated_source_url: str = Field(description="url of curated source")
    content_source_type: str = Field(description="type of curated contents in ‘sponsor’,’course’,’release’,’news’,’article’,’others’,’project’,’tutorial’,’event’ ")
    author: str = Field(description="author of curated article")

class PyCondersWeeklyResult(BaseModel):
    issue_number: str = Field(description="number of issue")
    published_date: date = Field(description="The published date of the weekly article")
    issues: list[PyCondersSource] = Field(description="issues of the newletters")


system_prompt = "You are an AI assistant specialized in extracting core curated content from a given weekly newsletter URL and clearly separating each content item."

system_prompt = "You are an AI assistant specialized in extacting core curated content from a given weekly newsletter html and clearly separating each content item."

system_prompt = "You are an AI assistant specialized in extracting core curated content from a given weekly newsletter markdown and clearly separating each content item."
agent = Agent("google-gla:gemini-2.5-flash-preview-04-17",
                system_prompt=system_prompt,
               output_type=PyCondersWeeklyResult)