"""Cosine similarity checker to ensure generated pages stay below 40% identical.

Google's March 2026 updates aggressively target templated/duplicate content.
This module verifies that each pair of generated pages has sufficiently unique content,
ensuring the site survives spam classifiers.
"""

import logging
import os
import random
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

MAX_ALLOWED_SIMILARITY = 0.40


class SimilarityChecker:
    """Verify inter-page similarity stays below the threshold."""

    def __init__(self, max_similarity: float = MAX_ALLOWED_SIMILARITY):
        self.max_similarity = max_similarity
        # Use character n-grams to better capture numerical differences
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=8000,
            ngram_range=(1, 3),
            analyzer="word",
            min_df=1,
            max_df=0.85,
            sublinear_tf=True,
        )

    def check_pages(self, output_dir: str, sample_size: int = 100) -> dict:
        """Check cosine similarity across generated HTML pages.

        Args:
            output_dir: Directory containing generated HTML files.
            sample_size: Max number of pages to sample for comparison.

        Returns:
            Dict with results: passed, avg_similarity, max_similarity, violations.
        """
        html_files = list(Path(output_dir).rglob("*.html"))
        if len(html_files) < 2:
            return {
                "passed": True,
                "total_pages": len(html_files),
                "avg_similarity": 0.0,
                "max_similarity": 0.0,
                "violations": [],
                "sample_size": len(html_files),
            }

        if len(html_files) > sample_size:
            html_files = random.sample(html_files, sample_size)

        page_texts: list[str] = []
        page_paths: list[str] = []

        for fpath in html_files:
            text = self._extract_text(fpath)
            if text:
                page_texts.append(text)
                page_paths.append(str(fpath))

        if len(page_texts) < 2:
            return {
                "passed": True,
                "total_pages": len(page_texts),
                "avg_similarity": 0.0,
                "max_similarity": 0.0,
                "violations": [],
                "sample_size": len(page_texts),
            }

        tfidf_matrix = self.vectorizer.fit_transform(page_texts)
        sim_matrix = cosine_similarity(tfidf_matrix)

        violations: list[dict] = []
        total_sim = 0.0
        pair_count = 0
        max_sim = 0.0

        for i in range(len(page_texts)):
            for j in range(i + 1, len(page_texts)):
                sim = sim_matrix[i][j]
                total_sim += sim
                pair_count += 1
                max_sim = max(max_sim, sim)

                if sim > self.max_similarity:
                    violations.append({
                        "page_a": os.path.basename(page_paths[i]),
                        "page_b": os.path.basename(page_paths[j]),
                        "similarity": round(float(sim), 4),
                    })

        avg_sim = total_sim / pair_count if pair_count > 0 else 0.0

        result = {
            "passed": len(violations) == 0,
            "total_pages": len(page_texts),
            "sample_size": len(page_texts),
            "pairs_checked": pair_count,
            "avg_similarity": round(avg_sim, 4),
            "max_similarity": round(float(max_sim), 4),
            "threshold": self.max_similarity,
            "violations": violations[:20],
            "total_violations": len(violations),
        }

        if violations:
            logger.warning(
                "SIMILARITY CHECK FAILED: %d pairs exceed %.0f%% threshold (max=%.2f%%)",
                len(violations),
                self.max_similarity * 100,
                max_sim * 100,
            )
        else:
            logger.info(
                "Similarity check passed: avg=%.2f%%, max=%.2f%% (threshold=%.0f%%)",
                avg_sim * 100,
                max_sim * 100,
                self.max_similarity * 100,
            )

        return result

    @staticmethod
    def _extract_text(filepath: Path) -> str | None:
        """Extract visible text content from an HTML file, excluding boilerplate."""
        try:
            import re

            from bs4 import BeautifulSoup

            html = filepath.read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "lxml")

            # Remove all boilerplate elements
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()

            # Remove JSON-LD structured data
            for tag in soup.select("script[type='application/ld+json']"):
                tag.decompose()

            # Focus on main content only
            main = soup.select_one("main")
            if main:
                # Remove breadcrumb nav
                for bc in main.select("nav"):
                    bc.decompose()
                text = main.get_text(separator=" ", strip=True)
            else:
                text = soup.get_text(separator=" ", strip=True)

            # Remove common template phrases that appear on every page
            boilerplate_phrases = [
                r"View Auction",
                r"View this auction on .+ for full manifest details",
                r"Interested in this lot",
                r"Need financing for bulk purchases",
                r"Business financing available",
                r"Explore Business Financing",
                r"Find Active Listings",
                r"Search current eBay",
                r"Migrating to Cloud",
                r"Compare Cloud Options",
                r"Data sourced from public auction platforms",
                r"Updated:",
                r"SurplusIndex",
                r"Dashboard",
                r"Pallets",
                r"Hardware",
                r"ITAD Blue Book",
            ]
            for phrase in boilerplate_phrases:
                text = re.sub(phrase, "", text, flags=re.IGNORECASE)

            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()

            return text if len(text) > 50 else None
        except Exception as e:
            logger.warning("Failed to extract text from %s: %s", filepath, e)
            return None
