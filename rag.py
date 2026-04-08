import os
import requests
import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import re
from bs4 import BeautifulSoup
import sqlite3
import hashlib
from datetime import datetime, timedelta

# Lightweight imports - no heavy ML libraries
try:
    import feedparser  # For RSS feeds
    import numpy as np
except ImportError:
    print("Please install: pip install feedparser beautifulsoup4 requests numpy")
    exit(1)

@dataclass
class Document:
    content: str
    url: str
    title: str
    timestamp: datetime
    chunk_id: str
    source_type: str  # New: track source type
    authority_score: float = 0.0  # New: source quality score

class EnhancedWebSearcher:
    """Advanced web searcher with premium sources"""
    
    def __init__(self, config: Dict[str, str] = None):
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Define high-quality source domains
        self.premium_domains = {
            # Academic & Research
            'arxiv.org': 0.95,
            'pubmed.ncbi.nlm.nih.gov': 0.95,
            'scholar.google.com': 0.90,
            'researchgate.net': 0.85,
            'ieee.org': 0.90,
            'acm.org': 0.90,
            
            # News & Media
            'reuters.com': 0.90,
            'bbc.com': 0.85,
            'bloomberg.com': 0.90,
            'wsj.com': 0.85,
            'ft.com': 0.85,
            'economist.com': 0.85,
            
            # Tech & Industry
            'techcrunch.com': 0.75,
            'arstechnica.com': 0.80,
            'wired.com': 0.75,
            'mit.edu': 0.95,
            'stanford.edu': 0.95,
            
            # Government & Official
            '.gov': 0.95,
            '.edu': 0.90,
            'who.int': 0.95,
            'cdc.gov': 0.95,
            'nih.gov': 0.95,
        }
    
    def search_arxiv(self, query: str) -> List[Dict[str, Any]]:
        """Search academic papers on arXiv"""
        try:
            url = "http://export.arxiv.org/api/query"
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': 5,
                'sortBy': 'relevance'
            }
            
            response = self.session.get(url, params=params)
            
            # Parse XML response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            results = []
            entries = root.findall('{http://www.w3.org/2005/Atom}entry')
            
            for entry in entries:
                title = entry.find('{http://www.w3.org/2005/Atom}title').text
                summary = entry.find('{http://www.w3.org/2005/Atom}summary').text
                link = entry.find('{http://www.w3.org/2005/Atom}id').text
                
                results.append({
                    'title': f"arXiv: {title.strip()}",
                    'url': link,
                    'content': summary.strip(),
                    'source_type': 'academic',
                    'authority_score': 0.95
                })
            
            return results
        except Exception as e:
            print(f"arXiv search error: {e}")
            return []
    
    def search_reddit_api(self, query: str) -> List[Dict[str, Any]]:
        """Search Reddit for current discussions"""
        try:
            url = f"https://www.reddit.com/search.json"
            params = {
                'q': query,
                'sort': 'relevance',
                'limit': 10,
                't': 'month'  # Past month
            }
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            results = []
            for post in data.get('data', {}).get('children', []):
                post_data = post.get('data', {})
                if post_data.get('selftext') and len(post_data.get('selftext', '')) > 100:
                    results.append({
                        'title': f"Reddit: {post_data.get('title', '')}",
                        'url': f"https://reddit.com{post_data.get('permalink', '')}",
                        'content': post_data.get('selftext', ''),
                        'source_type': 'discussion',
                        'authority_score': 0.60
                    })
            
            return results
        except Exception as e:
            print(f"Reddit search error: {e}")
            return []
    
    def search_rss_feeds(self, query: str) -> List[Dict[str, Any]]:
        """Search curated RSS feeds for recent content"""
        feeds = [
            'https://rss.cnn.com/rss/edition.rss',
            'https://feeds.bloomberg.com/technology/news.rss',
            'http://feeds.reuters.com/reuters/technologyNews',
            'https://www.wired.com/feed/rss',
            'https://techcrunch.com/feed/',
        ]
        
        results = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:3]:  # Limit per feed
                    if query.lower() in entry.title.lower() or query.lower() in entry.summary.lower():
                        results.append({
                            'title': entry.title,
                            'url': entry.link,
                            'content': entry.summary,
                            'source_type': 'news_feed',
                            'authority_score': self._get_authority_score(entry.link)
                        })
            except Exception as e:
                continue
        
        return results
    
    def search_scholarly_google(self, query: str) -> List[Dict[str, Any]]:
        """Search Google Scholar (basic scraping)"""
        try:
            url = "https://scholar.google.com/scholar"
            params = {'q': query, 'num': 5}
            
            response = self.session.get(url, params=params)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            results = []
            for result in soup.find_all('div', class_='gs_r gs_or gs_scl')[:5]:
                title_elem = result.find('h3', class_='gs_rt')
                snippet_elem = result.find('div', class_='gs_rs')
                
                if title_elem and snippet_elem:
                    title = title_elem.get_text()
                    snippet = snippet_elem.get_text()
                    link = title_elem.find('a')
                    url = link.get('href') if link else ''
                    
                    results.append({
                        'title': f"Scholar: {title}",
                        'url': url,
                        'content': snippet,
                        'source_type': 'academic',
                        'authority_score': 0.90
                    })
            
            return results
        except Exception as e:
            print(f"Google Scholar error: {e}")
            return []
    
    def search_specialized_apis(self, query: str, domain: str = None) -> List[Dict[str, Any]]:
        """Search domain-specific APIs"""
        results = []
        
        # PubMed for medical/health queries
        if not domain or domain == 'medical':
            results.extend(self._search_pubmed(query))
        
        # SEC EDGAR for financial/business queries  
        if not domain or domain == 'financial':
            results.extend(self._search_sec_edgar(query))
        
        # USPTO for patent searches
        if not domain or domain == 'patent':
            results.extend(self._search_patents(query))
        
        return results
    
    def _search_pubmed(self, query: str) -> List[Dict[str, Any]]:
        """Search PubMed for medical research"""
        try:
            # Search for PMIDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmax': 5,
                'retmode': 'json'
            }
            
            search_response = self.session.get(search_url, params=search_params)
            search_data = search_response.json()
            
            pmids = search_data.get('esearchresult', {}).get('idlist', [])
            
            if not pmids:
                return []
            
            # Fetch abstracts
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }
            
            fetch_response = self.session.get(fetch_url, params=fetch_params)
            
            results = []
            # Parse XML and extract abstracts (simplified)
            if 'Abstract' in fetch_response.text:
                # This is a simplified parser - you'd want more robust XML parsing
                results.append({
                    'title': f"PubMed Research: {query}",
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/?term={query.replace(' ', '+')}",
                    'content': "Recent medical research abstracts found...",
                    'source_type': 'medical_research',
                    'authority_score': 0.95
                })
            
            return results
        except Exception as e:
            print(f"PubMed search error: {e}")
            return []
    
    def _search_sec_edgar(self, query: str) -> List[Dict[str, Any]]:
        """Search SEC EDGAR for financial filings"""
        try:
            # This is a simplified example - real implementation would use SEC API
            url = f"https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'action': 'getcompany',
                'CIK': query,
                'type': '10-K',
                'dateb': '',
                'owner': 'exclude',
                'count': 5
            }
            
            # Note: SEC has specific requirements for API access
            # This is just a placeholder for the concept
            
            return [{
                'title': f"SEC Filing: {query}",
                'url': f"https://www.sec.gov/edgar/search/?q={query}",
                'content': "Financial filing information...",
                'source_type': 'financial_filing',
                'authority_score': 0.95
            }]
        except Exception as e:
            return []
    
    def _search_patents(self, query: str) -> List[Dict[str, Any]]:
        """Search patent databases"""
        try:
            # Use Google Patents or USPTO API
            url = f"https://patents.google.com/"
            # This would need proper implementation
            
            return [{
                'title': f"Patents: {query}",
                'url': f"https://patents.google.com/?q={query}",
                'content': "Patent information and technical specifications...",
                'source_type': 'patent',
                'authority_score': 0.85
            }]
        except Exception as e:
            return []
    
    def _get_authority_score(self, url: str) -> float:
        """Calculate authority score based on domain"""
        for domain, score in self.premium_domains.items():
            if domain in url:
                return score
        
        # Default scoring based on TLD
        if '.edu' in url:
            return 0.90
        elif '.gov' in url:
            return 0.95
        elif '.org' in url:
            return 0.75
        else:
            return 0.60
    
    def extract_content(self, url: str) -> Optional[Dict[str, str]]:
        """Enhanced content extraction with source scoring"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside", "advertisement"]):
                script.decompose()
            
            # Get title
            title = soup.find('title')
            title = title.get_text().strip() if title else urlparse(url).netloc
            
            # Enhanced content extraction based on source type
            content_selectors = [
                'article', 
                'main', 
                '.content', 
                '#content', 
                '.post', 
                '.article',
                '.entry-content',
                '.post-content',
                '.article-body',
                '.story-body',
                '[role="main"]'
            ]
            
            content = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text()
                    break
            
            if not content:
                content = soup.get_text()
            
            # Clean content
            content = re.sub(r'\n\s*\n', '\n\n', content)
            content = re.sub(r' +', ' ', content)
            content = content.strip()
            
            # Quality filtering - reject low-quality content
            if len(content) < 100:
                return None
            
            # Check for common spam indicators
            spam_indicators = ['click here', 'buy now', 'limited time', 'act now']
            if any(indicator in content.lower() for indicator in spam_indicators):
                return None
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'authority_score': self._get_authority_score(url)
            }
            
        except Exception as e:
            print(f"Content extraction error for {url}: {e}")
            return None


class TextProcessor:
    """Process and chunk text documents"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str, url: str, title: str) -> List[Document]:
        """Split text into overlapping chunks"""
        chunks = []
        
        # Simple sentence-based chunking
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = []
        current_size = 0
        chunk_id = 0
        
        for sentence in sentences:
            sentence_len = len(sentence)
            
            if current_size + sentence_len > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                doc = Document(
                    content=chunk_text,
                    url=url,
                    title=title,
                    timestamp=datetime.now(),
                    chunk_id=f"{url}_{chunk_id}",
                    source_type='unknown',
                    authority_score=0.0
                )
                chunks.append(doc)
                
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap // 10)
                current_chunk = current_chunk[overlap_start:] + [sentence]
                current_size = sum(len(s) for s in current_chunk)
                chunk_id += 1
            else:
                current_chunk.append(sentence)
                current_size += sentence_len
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            doc = Document(
                content=chunk_text,
                url=url,
                title=title,
                timestamp=datetime.now(),
                chunk_id=f"{url}_{chunk_id}",
                source_type='unknown',
                authority_score=0.0
            )
            chunks.append(doc)
        
        return chunks


class FreeVectorStore:
    """Simple keyword-based vector store (no ML required)"""
    
    def __init__(self):
        self.documents: List[Document] = []
    
    def _score_document(self, query: str, doc: Document) -> float:
        """Simple keyword matching score"""
        query_words = set(query.lower().split())
        content_words = doc.content.lower()
        title_words = doc.title.lower()
        
        # Score based on word matches in content and title
        content_score = sum(1 for w in query_words if w in content_words) / max(len(query_words), 1)
        title_score = sum(2 for w in query_words if w in title_words) / max(len(query_words) * 2, 1)
        
        return content_score + title_score + doc.authority_score * 0.1
    
    def add_documents(self, documents: List[Document]) -> int:
        """Add documents to the store"""
        self.documents.extend(documents)
        return len(documents)
    
    def search(self, query: str, k: int = 5) -> List[Document]:
        """Search for relevant documents using keyword matching"""
        if not self.documents:
            return []
        
        # Score all documents
        scored = [(self._score_document(query, doc), doc) for doc in self.documents]
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return top k
        return [doc for score, doc in scored[:k] if score > 0]
    
    def clear(self):
        """Clear all documents"""
        self.documents = []


class FreeLLMClient:
    """Simple text-based response generator (no ML required)"""
    
    def generate_response(self, question: str, documents: List[Document]) -> str:
        """Generate a response based on retrieved documents"""
        if not documents:
            return "I couldn't find any relevant information to answer your question."
        
        # Build context from documents
        context_parts = []
        for i, doc in enumerate(documents[:3], 1):
            # Extract relevant sentences containing query keywords
            query_words = set(question.lower().split())
            sentences = re.split(r'(?<=[.!?])\s+', doc.content)
            relevant = [s for s in sentences if any(w in s.lower() for w in query_words)]
            
            if relevant:
                excerpt = ' '.join(relevant[:3])
            else:
                excerpt = doc.content[:300]
            
            context_parts.append(f"[Source {i}] {doc.title}:\n{excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        return f"Based on {len(documents)} sources found:\n\n{context}\n\n---\nTo get a generated answer, install: pip install transformers torch"


class EnhancedRAGSystem:
    """Enhanced RAG system with premium sources"""
    
    def __init__(self, config: Dict[str, str] = None):
        """
        Initialize with API keys:
        config = {
            'news_api_key': 'your_newsapi_key',
            'github_token': 'your_github_token',
            'serper_api_key': 'your_serper_key',  # For Google search
        }
        """
        self.config = config or {}
        self.searcher = EnhancedWebSearcher(config)
        self.processor = TextProcessor()
        self.vector_store = FreeVectorStore()
        self.llm = FreeLLMClient()
    
    def search_comprehensive(self, query: str, source_types: List[str] = None) -> int:
        """
        Comprehensive search across multiple premium sources
        
        source_types: ['academic', 'reddit', 'rss', 'scholar', 'medical', 'financial']
        """
        if source_types is None:
            source_types = ['academic', 'reddit', 'rss', 'scholar']
        
        print(f"Searching premium sources for: {query}")
        all_results = []
        
        # Search each source type
        for source_type in source_types:
            print(f"  Searching {source_type}...")
            
            if source_type == 'academic':
                results = self.searcher.search_arxiv(query)
            elif source_type == 'reddit':
                results = self.searcher.search_reddit_api(query)
            elif source_type == 'rss':
                results = self.searcher.search_rss_feeds(query)
            elif source_type == 'scholar':
                results = self.searcher.search_scholarly_google(query)
            elif source_type == 'medical':
                results = self.searcher.search_specialized_apis(query, 'medical')
            elif source_type == 'financial':
                results = self.searcher.search_specialized_apis(query, 'financial')
            else:
                continue
            
            all_results.extend(results)
            time.sleep(1)  # Rate limiting
        
        # Sort by authority score
        all_results.sort(key=lambda x: x.get('authority_score', 0), reverse=True)
        
        print(f"Found {len(all_results)} high-quality results")
        
        # Process and index
        documents = []
        for result in all_results[:15]:  # Limit to top results
            if result.get('content') and len(result['content']) > 100:
                chunks = self.processor.chunk_text(
                    result['content'],
                    result['url'],
                    result['title']
                )
                
                # Add source metadata to chunks
                for chunk in chunks:
                    chunk.source_type = result['source_type']
                    chunk.authority_score = result['authority_score']
                
                documents.extend(chunks)
        
        # Add to vector store
        added_count = self.vector_store.add_documents(documents)
        print(f"Added {added_count} premium document chunks")
        
        return added_count
    
    def query_enhanced(self, question: str, preferred_sources: List[str] = None) -> Dict[str, Any]:
        """Enhanced query with source preferences"""
        start_time = time.time()
        
        # Search existing knowledge
        relevant_docs = self.vector_store.search(question, 5)
        
        # Filter by preferred sources if specified
        if preferred_sources:
            relevant_docs = [
                doc for doc in relevant_docs 
                if hasattr(doc, 'source_type') and doc.source_type in preferred_sources
            ]
        
        # Search premium sources if needed
        if len(relevant_docs) < 3:
            print("Searching premium sources for better information...")
            self.search_comprehensive(question, preferred_sources)
            relevant_docs = self.vector_store.search(question, 5)
        
        # Generate enhanced response
        answer = self.llm.generate_response(question, relevant_docs)
        
        # Prepare enhanced source info
        sources = []
        seen_urls = set()
        for doc in relevant_docs:
            if doc.url not in seen_urls:
                source_info = {
                    "title": doc.title,
                    "url": doc.url,
                    "timestamp": doc.timestamp.isoformat(),
                    "authority_score": getattr(doc, 'authority_score', 0.0),
                    "source_type": getattr(doc, 'source_type', 'unknown')
                }
                sources.append(source_info)
                seen_urls.add(doc.url)
        
        # Sort sources by authority
        sources.sort(key=lambda x: x['authority_score'], reverse=True)
        
        return {
            "answer": answer,
            "sources": sources,
            "source_breakdown": self._get_source_breakdown(sources),
            "avg_authority_score": np.mean([s['authority_score'] for s in sources]) if sources else 0,
            "processing_time": time.time() - start_time
        }
    
    def _get_source_breakdown(self, sources: List[Dict]) -> Dict[str, int]:
        """Get breakdown of source types"""
        breakdown = {}
        for source in sources:
            source_type = source.get('source_type', 'unknown')
            breakdown[source_type] = breakdown.get(source_type, 0) + 1
        return breakdown

def main():
    """Enhanced main function with free sources only"""
    print("=" * 70)
    print("ENHANCED RAG SYSTEM WITH FREE SOURCES")
    print("=" * 70)
    
    # No API keys needed - using free sources only
    config = {}
    
    print("Using free sources only (no API keys required)")
    
    # Initialize enhanced system
    rag_system = EnhancedRAGSystem(config)
    
    print("\nAvailable source types:")
    print("  academic, reddit, rss, scholar, medical, financial")
    print("\nCommands:")
    print("  'sources: academic,rss' - specify source types")
    print("  'quit' - exit")
    print("=" * 70)
    
    preferred_sources = None
    
    while True:
        query = input("\nEnter your question: ").strip()
        
        if query.lower() == 'quit':
            break
        elif query.startswith('sources:'):
            preferred_sources = [s.strip() for s in query[8:].split(',')]
            print(f"Preferred sources set to: {preferred_sources}")
            continue
        elif not query:
            continue
        
        try:
            result = rag_system.query_enhanced(query, preferred_sources)
            
            print(f"\n{'='*60}")
            print("ENHANCED ANSWER:")
            print(result['answer'])
            
            print(f"\n{'='*60}")
            print("PREMIUM SOURCES:")
            for i, source in enumerate(result['sources'], 1):
                authority = "★" * int(source['authority_score'] * 5)
                print(f"{i}. [{source['source_type'].upper()}] {authority}")
                print(f"   {source['title']}")
                print(f"   {source['url']}")
                print(f"   Authority: {source['authority_score']:.2f}")
            
            print(f"\nSource Breakdown: {result['source_breakdown']}")
            print(f"Average Authority Score: {result['avg_authority_score']:.2f}")
            print(f"Processing time: {result['processing_time']:.2f}s")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
