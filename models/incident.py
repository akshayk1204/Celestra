from typing import List, Optional
from pydantic import BaseModel

class Incident(BaseModel):
    title: str
    source: str
    display_name: str
    source_url: str
    link: str
    date: str
    raw_content: str
    categories: List[str]
    organizations: List[str] = []  # New field
    scrape_content: bool = False  # New field