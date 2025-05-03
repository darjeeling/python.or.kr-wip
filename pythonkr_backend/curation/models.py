from django.db import models
from django.utils.text import slugify
from .utils import get_summary_from_url, translate_to_korean, categorize_summary 
import readtime
import os


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="The name of the category (e.g., 'Web Development', 'LLM').")
    slug = models.SlugField(max_length=100, unique=True, help_text="A URL-friendly slug for the category.", blank=True) # Optional but good practice

    def save(self, *args, **kwargs):
        # Auto-generate slug if blank (optional)
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories" # Nicer plural name in admin
        ordering = ['name'] # Optional: Order categories alphabetically


class Article(models.Model):
    url = models.URLField(unique=True, max_length=2048, help_text="The unique URL of the article.")
    title = models.CharField(max_length=512, blank=True, help_text="Article title (can be fetched automatically or entered manually).")
    summary = models.TextField(blank=True, help_text="AI-generated summary of the article.")
    summary_ko = models.TextField(blank=True, help_text="Korean translation of the summary (via OpenAI).")
    reading_time_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Estimated reading time in minutes (based on full article content)."
    )
    categories = models.ManyToManyField(
        Category,
        blank=True, # An article might have no categories initially or after processing
        related_name='articles', # How Category model refers back to Articles
        help_text="Select one or more categories for this article."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or self.url
        
    def calculate_reading_time(self, full_text: str):
        """
        Calculates reading time based on the provided text.
        """
        if full_text:
            try:
                result = readtime.of_text(full_text)
                self.reading_time_minutes = result.minutes
            except Exception as e:
                print(f"Error calculating reading time for article {self.id}: {e}")
                self.reading_time_minutes = None # Set to None on calculation error
        else:
            self.reading_time_minutes = None

    def fetch_and_summarize(self) -> str:
        """
        Fetches content, calculates reading time on full text, generates summary,
        translates summary, and saves all results.
        """
        if not self.url:
            return "Error: No URL provided."

        try:
            summary_text = get_summary_from_url(self.url)

            self.calculate_reading_time(summary_text) # Call updated method

            if not summary_text:
                self.summary = ""
                self.summary_ko = ""
                self.save(update_fields=['title', 'summary', 'summary_ko', 'reading_time_minutes', 'updated_at'])
                return "Error extracting summary. Other details saved."

            self.summary = summary_text # Set summary

            categorization_status = "Categorization skipped (no summary)."
            if self.summary: # Only categorize if summary was successful
                 categorization_status = self.assign_categories() # Call the revised method
                 print(f"Categorization status for article {self.id}: {categorization_status}")

            translation_status = self.translate_summary_to_korean() # Call translation
            print(f"Translation status for article {self.id}: {translation_status}")
            translation_failed = "Error" in translation_status

            self.save(update_fields=[
                'title',
                'summary',
                'summary_ko',
                'reading_time_minutes',
                'updated_at'
            ])

            translation_failed = "Error" in translation_status # Re-evaluate this variable if needed

            final_message = "Fetch, Read Time, Summary completed."
            final_message += " Translation failed." if translation_failed else " Translation completed."
            final_message += f" {categorization_status}" # Include categorization status message
            return final_message

        except ImportError as e:
            return f"Error with required libraries: {str(e)}"
        except Exception as e:
             print(f"Unexpected error during fetch/summarize/translate for {self.id}: {e}")
             return f"Unexpected error processing article: {str(e)}"
            
    def translate_summary_to_korean(self):
        """
        Translates the summary to Korean using the OpenAI API via Langchain.
        """
        if not self.summary:
            self.summary_ko = ""
            return "No summary to translate."

        try:
            translated_text = translate_to_korean(self.summary)

            self.summary_ko = translated_text.strip() if translated_text else ""
            self.save(update_fields=['summary_ko', 'updated_at'])
            return "Summary translated successfully using OpenAI."

        except Exception as e:
            print(f"Error translating article {self.id} using OpenAI: {e}")
            self.summary_ko = "" # Clear on error
            self.save(update_fields=['summary_ko', 'updated_at'])
            return f"Error during OpenAI translation: {str(e)[:150]}"
            
    def assign_categories(self):
        """Assigns multiple categories based on the summary using an LLM."""
        if not self.summary:
            self.categories.clear() # Clear existing categories if no summary
            return "Error: No summary available to categorize."

        try:
            defined_category_names = [
                'Web Development', 'MLOps', 'Large Language Models',
                'Data Science', 'AI General', 'Software Engineering', 'Other'
            ]
            category_objects = []
            created_names = []
            for name in defined_category_names:
                cat, created = Category.objects.get_or_create(name=name)
                category_objects.append(cat)
                if created:
                  created_names.append(name)
                  cat.save()

            if created_names:
                print(f"Ensured categories exist. Created new: {created_names}")

            response_text = categorize_summary(self.summary, defined_category_names).replace("'", "").replace('"', "")
            assigned_category_names = [name.strip() for name in response_text.split(',') if name.strip()]

            valid_categories = Category.objects.filter(name__in=assigned_category_names).filter(name__in=defined_category_names)
            valid_category_names = list(valid_categories.values_list('name', flat=True))

            print(f"LLM suggested: {assigned_category_names}, Validated & Found: {valid_category_names}")

            self.categories.clear() # Remove old associations first
            if valid_categories:
                self.categories.add(*valid_categories) # Add the new set using the splat operator
                return f"Article categories set to: {', '.join(valid_category_names)}."
            elif 'Other' in assigned_category_names:
                 other_cat = Category.objects.filter(name='Other').first()
                 if other_cat:
                     self.categories.add(other_cat)
                     return "Article category set to: Other."

            return "Warning: No valid categories assigned based on LLM response."

        except Exception as e:
            print(f"Error categorizing article {self.id}: {e}")
            return f"Error during categorization: {str(e)[:150]}"
