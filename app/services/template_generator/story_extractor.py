#!/usr/bin/env python3
import os
import sys
import json
import time
import asyncio
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from app.repository.template_repository import TemplateRepository
from app.schemas.schemas import TemplateStatusEnum

# Add the project root to the Python path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.repository import chapter_repository
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Book, Chapter
from app.services.ai_service import get_openai_client
from app.utils.model_settings import ModelSettings
from app.utils.constants import SettingKeys
from app.repository.base_repository import BaseRepository
from app.repository.character_arcs_repository import CharacterArcsRepository
# Import prompt templates
from prompts.story_extractor_prompts import (
    CHAPTER_SUMMARY_SYSTEM_PROMPT,
    CHAPTER_SUMMARY_USER_PROMPT_TEMPLATE,
    CHARACTER_ARC_EXTRACTION_SYSTEM_PROMPT,
    CHARACTER_ARC_EXTRACTION_USER_PROMPT_TEMPLATE,
    PLOT_BEAT_ANALYSIS_SYSTEM_PROMPT,
    PLOT_BEAT_ANALYSIS_USER_PROMPT_TEMPLATE
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StoryExtractor:
    def __init__(self, book_id: int, db: Session, template_id: int):
        """Initialize the analyzer with a book ID and database session"""
        self.book_id = book_id
        self.db = db
        self.book = None
        self.chapters = []
        self.chapter_summaries = []
        self.characters = []
        self.client = get_openai_client()
        self.template_id = template_id
        self.template_repo = TemplateRepository(self.db)
        self.model_settings = None

    async def initialize(self):
        """Load book and chapters from database"""
        # Load book data
        self.book = self.db.query(Book).filter(Book.id == self.book_id).first()
        if not self.book:
            raise ValueError(f"Book with ID {self.book_id} not found")
        
        # Initialize model settings
        self.model_settings = ModelSettings(self.db)
        logger.info("Initialized model settings")
        
        # Load chapters in order
        self.chapters = self.db.query(Chapter).filter(
            Chapter.book_id == self.book_id
        ).order_by(Chapter.chapter_no).all()
        
        # Double-check sorting to ensure chapters are in proper order
        self.chapters.sort(key=lambda chapter: chapter.chapter_no)
        
        if not self.chapters:
            raise ValueError(f"No chapters found for book with ID {self.book_id}")
        
        logger.info(f"Loaded book: {self.book.title}")
        logger.info(f"Found {len(self.chapters)} chapters")
            
        return self.book, self.chapters
        
    # Method removed and replaced with direct ModelSettings usage
    
    async def summarize_chapter(self, chapter: Chapter) -> Dict[str, Any]:
        """Summarize a single chapter while preserving key metadata and story elements"""
        # If a summary already exists in the database, use it directly
        if chapter.source_text:
            summary_text = chapter.source_text
            result = {
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "chapter_number": chapter.chapter_no,
                "original_length": len(chapter.content),
                "summary_length": len(summary_text),
                "summary": summary_text,
                "compression_ratio": len(summary_text) / (len(chapter.content) or 1),
                "timestamp": int(time.time())
            }
            logger.info(f"Summary loaded from source_text")
            return result
        
        
        logger.info(f"Summarizing Chapter {chapter.chapter_no}: {chapter.title}")
        
        # Get model and temperature from settings
        model, temperature = self.model_settings.chapter_summary_for_template()

        system_prompt = CHAPTER_SUMMARY_SYSTEM_PROMPT
        user_prompt = CHAPTER_SUMMARY_USER_PROMPT_TEMPLATE.format(
            chapter_title=chapter.title,
            chapter_number=chapter.chapter_no,
            chapter_content=chapter.content
        )
        
        import asyncio
        try:
            def blocking_openai_call():
                return self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                )
            response = await asyncio.to_thread(blocking_openai_call)
            summary_text = response.choices[0].message.content
            
            # Create summary with metadata (for tracking in memory)
            result = {
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "chapter_number": chapter.chapter_no,
                "original_length": len(chapter.content),
                "summary_length": len(summary_text),
                "summary": summary_text,
                "compression_ratio": len(summary_text) / (len(chapter.content) or 1),  # Avoid division by zero
                "timestamp": int(time.time())
            }

            # Save the summary to the database
            chapter.source_text = summary_text
            chapter_repo = chapter_repository.ChapterRepository(self.db)
            chapter_repo.update(chapter)
            logger.info(f"Summary saved to database")
            
            return result
        except Exception as e:
            error_message = f"Error summarizing chapter {chapter.id}: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return {
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "chapter_number": chapter.chapter_no,
                "error": True
            }
    
    async def summarize_all_chapters(self) -> List[Dict[str, Any]]:
        """Summarize all chapters in the book"""
        import time as _time
        self.template_repo.update_summary_status(self.template_id, TemplateStatusEnum.IN_PROGRESS)
        chapters_to_process = self.chapters
        logger.info(f"Summarizing all {len(chapters_to_process)} chapters")

        # Use a semaphore to limit concurrency
        import asyncio
        semaphore = asyncio.Semaphore(15)  # Limit to 15 concurrent tasks

        async def limited_summarize(chapter):
            async with semaphore:
                logger.info(f"[START] Summarizing chapter {chapter.chapter_no}: {chapter.title}")
                start_time = _time.time()
                result = await self.summarize_chapter(chapter)
                elapsed = _time.time() - start_time
                logger.info(f"[DONE] Chapter {chapter.chapter_no}: {chapter.title} summarized in {elapsed:.2f}s")
                return result

        logger.info("[BATCH] Starting concurrent summarization of chapters...")
        batch_start = _time.time()
        tasks = [limited_summarize(chapter) for chapter in chapters_to_process]
        results = await asyncio.gather(*tasks)
        batch_elapsed = _time.time() - batch_start
        logger.info(f"[BATCH] All chapter summaries complete in {batch_elapsed:.2f}s")
        self.template_repo.update_summary_status(self.template_id, TemplateStatusEnum.COMPLETED)
        return results
    
    # The extract_characters_from_summaries method has been removed as it's now part of extract_character_arcs
    
    async def analyze_plot_beats_batch(self, chapter_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze plot beats from multiple chapter summaries at once"""
        if not chapter_batch:
            logger.error("No chapters provided for batch plot analysis")
            return {"error": "No chapters provided"}
        
        # Get the range of chapters in this batch
        start_chapter = chapter_batch[0]["chapter_no"]
        end_chapter = chapter_batch[-1]["chapter_no"]
        logger.info(f"Analyzing plot beats for chapters {start_chapter} to {end_chapter}")
        
        # Combine the chapter summaries
        combined_summaries = ""
        for chapter in chapter_batch:
            combined_summaries += f"\n\nCHAPTER {chapter['chapter_no']}: {chapter['title']}\n{chapter['summary']}"
        
        system_prompt = PLOT_BEAT_ANALYSIS_SYSTEM_PROMPT
        user_prompt = PLOT_BEAT_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            combined_summaries=combined_summaries
        )
        
        try:
            # Get model and temperature from settings
            model, temperature = self.model_settings.extracting_plot_beats()
            logger.info(f"Making API call to analyze plot beats for chapters {start_chapter}-{end_chapter} using {model}")
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
            )
            
            plot_analysis = response.choices[0].message.content

            # Save each plot beat to the database using PlotBeatRepository
            from app.repository.plot_beat_repository import PlotBeatRepository
            plot_beat_repo = PlotBeatRepository(self.db)
            plot_beat_repo.create(
                content=plot_analysis,
                type="EXTRACTED",
                source_id=self.book_id,
            )
            
            # Create a result dict with metadata
            result = {
                "start_chapter": start_chapter,
                "end_chapter": end_chapter,
                "chapters": [ch["chapter_no"] for ch in chapter_batch],
                "plot_analysis": plot_analysis,
                "timestamp": int(time.time())
            }
            
            return result
            
        except Exception as e:
            error_message = f"Error analyzing plot beats for chapters {start_chapter}-{end_chapter}: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return {    
                "start_chapter": start_chapter,
                "end_chapter": end_chapter,
                "error": error_message
            }
    
    async def analyze_all_plot_beats(self) -> List[Dict[str, Any]]:
        """Analyze all chapter summaries for plot beats using multi-chapter batches, using the database only."""
        logger.info("Analyzing plot beats from all chapter summaries")

        # Check for existing plot beats in the database
        from app.repository.plot_beat_repository import PlotBeatRepository
        plot_beat_repo = PlotBeatRepository(self.db)
        existing_plot_beats = plot_beat_repo.get_by_source_id_and_type(self.book_id, "EXTRACTED")
        if existing_plot_beats:
            self.template_repo.update_plot_beats_status(self.template_id, TemplateStatusEnum.COMPLETED)
            logger.info(f"Found {len(existing_plot_beats)} plot beats in the database for book_id {self.book_id}")
            return [
                {
                    "content": pb.content,
                    "type": pb.type,
                    "source_id": pb.source_id,
                    "id": pb.id
                }
                for pb in existing_plot_beats
            ]
        # If not found, generate plot beats
        logger.info("No plot beats found in the database, generating new plot beats")
        # Load all chapter summaries from the database (source_text)
        self.template_repo.update_plot_beats_status(self.template_id, TemplateStatusEnum.IN_PROGRESS)
        summaries = []
        for chapter in self.chapters:
            if chapter.source_text:
                summaries.append({
                    "chapter_no": chapter.chapter_no,
                    "title": chapter.title,
                    "summary": chapter.source_text
                })
            else:
                logger.warning(f"No summary (source_text) found for chapter {chapter.chapter_no}")

        if not summaries:
            logger.error("No chapter summaries found for plot beat analysis")
            return [{"error": "No summaries available"}]

        logger.info(f"Loaded {len(summaries)} chapter summaries for plot beat analysis")

        # Process in larger batches (10 chapters at a time for narrative continuity)
        BATCH_SIZE = 10
        all_results = []
        batch_count = (len(summaries) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"Processing {len(summaries)} chapters in {batch_count} multi-chapter batches")

        for i in range(0, len(summaries), BATCH_SIZE):
            batch = summaries[i:i+BATCH_SIZE]
            start_ch = batch[0]['chapter_no']
            end_ch = batch[-1]['chapter_no']
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{batch_count} (chapters {start_ch}-{end_ch})")

            # Analyze this batch of chapters together
            batch_result = await self.analyze_plot_beats_batch(batch)
            all_results.append(batch_result)

            # Brief pause between batches to avoid rate limits
            if i + BATCH_SIZE < len(summaries):
                await asyncio.sleep(2)
        self.template_repo.update_plot_beats_status(self.template_id, TemplateStatusEnum.COMPLETED)
        return all_results
    
    async def extract_character_arcs(self) -> Dict[str, Any]:
        """Extract character identities and their growth arcs in a single analysis pipeline"""
        logger.info("Extracting character arcs from chapter summaries")
        # Step 1: Try to load character arcs from the database first
        character_arcs_repo = CharacterArcsRepository(self.db)
        db_character_arcs = character_arcs_repo.get_by_type_and_source_id('EXTRACTED', self.book_id)
        if db_character_arcs:
            logger.info(f"Found {len(db_character_arcs)} character arcs in the database for book_id {self.book_id}")
            return db_character_arcs
        
        self.template_repo.update_character_arc_status(self.template_id, TemplateStatusEnum.IN_PROGRESS)
        # Fallback: Load all chapter summaries from the chapters table (source_text column)
        summaries = []
        chapter_repo = chapter_repository.ChapterRepository(self.db)
        chapters = chapter_repo.get_by_book_id(self.book_id)
        chapters = [ch for ch in chapters if ch.source_text]
        chapters.sort(key=lambda ch: ch.chapter_no)
        for ch in chapters:
            summaries.append({
                "chapter_no": ch.chapter_no,
                "title": ch.title,
                "summary": ch.source_text
            })
        
        if not summaries:
            logger.error("No chapter summaries found for character arc extraction")
            return {"error": "No summaries available"}
        
        logger.info(f"Loaded {len(summaries)} chapter summaries for character arc extraction")
        
        # Sort summaries by chapter number
        summaries.sort(key=lambda x: x["chapter_no"])
        
        # Step 2: Combine summaries
        combined_summary = ""
        for summary in summaries:
            combined_summary += f"\n\nCHAPTER {summary['chapter_no']}: {summary['title']}\n{summary['summary']}"
        
        # Step 3: Create prompts for character arc extraction
        system_prompt = CHARACTER_ARC_EXTRACTION_SYSTEM_PROMPT
        user_prompt = CHARACTER_ARC_EXTRACTION_USER_PROMPT_TEMPLATE.format(
            book_title=self.book.title,
            book_author=getattr(self.book, 'author', 'Unknown'),
            combined_summary=combined_summary
        )
        
        try:
            # Get model and temperature from settings
            model, temperature = self.model_settings.extracting_character_arcs()
            logger.info(f"Making API call to extract character arcs using {model}")
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
            )
            
            character_markdown_content = response.choices[0].message.content
            print(f"character_markdown_content: {character_markdown_content}")
            # Extract individual character files using regex pattern
            import re
            # Updated pattern to capture everything between FILE_START and FILE_END for each character
            pattern = r"CHARACTER:\s*([^\n]+)\s*\nFILE_START\n([\s\S]*?)FILE_END"
            matches = re.findall(pattern, character_markdown_content)

            # Save individual character arc in database
            character_arcs_repo = CharacterArcsRepository(self.db)
            character_arcs = []
            role_pattern = r"## Role\n([^\n]+)"
            for name, content in matches:
                # Extract the role using a second regex
                role_match = re.search(role_pattern, content)
                role = role_match.group(1).strip() if role_match else ""
                character_arc = character_arcs_repo.create(content=content.strip(), type='EXTRACTED', source_id=self.book_id, name=name.strip(), role=role)
                character_arcs.append(character_arc)
            self.template_repo.update_character_arc_status(self.template_id, TemplateStatusEnum.COMPLETED)
            return character_arcs

        except Exception as e:
            error_message = f"Error extracting character arcs: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            self.template_repo.update_character_arc_status(self.template_id, TemplateStatusEnum.FAILED)
            return {"error": error_message}

    async def run_analysis(self) -> Dict[str, Any]:
        """Run the full analysis pipeline"""
        logger.info(f"Starting analysis for book ID: {self.book_id}")

        await self.summarize_all_chapters()
        
        await self.extract_character_arcs()
        
        await self.analyze_all_plot_beats()
        
        logger.info("Analysis completed")
