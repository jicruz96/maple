import json
from pathlib import Path
from firebase_functions.firestore_fn import (
    Event,
    DocumentSnapshot,
)
from llm_functions import get_summary_api_function, get_tags_api_function_v2
from typing import TypedDict, NewType
from collections import deque

Category = NewType("Category", str)


with (
    Path(__file__).resolve().parents[1] / "shared" / "topics_by_category.json"
).open() as f:
    TOPICS_BY_CATEGORY: dict[Category, list[str]] = json.load(f)


# This allows us to type the return of `get_topics`
class TopicAndCategory(TypedDict):
    # We use the name `tag` in Python, but `topic` in the database
    topic: str
    # Topic can be mapped directly to a category
    category: Category


# Using a 'deque' because appending to lists in Python is slow
def get_categories_from_topics(
    topics: list[str], topic_to_category: dict[str, Category]
) -> deque[TopicAndCategory]:
    to_return: deque[TopicAndCategory] = deque()
    for topic in topics:
        if topic_to_category.get(topic):
            to_return.append(
                TopicAndCategory(topic=topic, category=topic_to_category[topic])
            )
    return to_return


# When a bill is created for a given session, we want to populate both the
# summary and the tags for that bill. This is an idempotent function.
def run_trigger(event: Event[DocumentSnapshot | None]) -> None:
    bill_id = event.params["bill_id"]
    inserted_data = event.data
    if inserted_data is None:
        print(f"bill with id `{bill_id}` has no event data")
        return

    inserted_content = inserted_data.to_dict()
    if inserted_content is None:
        print(f"bill with id `{bill_id}` has no inserted content")
        return

    # If the summary is already populated, only run the tags code
    summary = inserted_content.get("summary")
    if summary is None:
        document_text = inserted_content.get("contents", {}).get("DocumentText")
        document_title = inserted_content.get("contents", {}).get("Title")
        if document_text is None or document_title is None:
            print(f"bill with id `{bill_id}` unable to fetch document text or title")
            return

        summary = get_summary_api_function(bill_id, document_title, document_text)

        if summary["status"] in [-1, -2]:
            print(
                f"failed to generate summary for bill with id `{bill_id}`, got {summary['status']}"
            )
            return

        # Set and insert the summary for the categorization step
        summary = summary["summary"]
        inserted_data.reference.update({"summary": summary})
        print(f"Successfully updated summary for bill with id `{bill_id}`")

    # If the topics are already populated, we are done
    topics = inserted_content.get("topics")
    if topics is not None:
        print(f"bill with id `{bill_id}` has topics")
        return

    tags = get_tags_api_function_v2(bill_id, document_title, summary)

    if tags["status"] != 1:
        print(
            f"failed to generate tags for bill with id `{bill_id}`, got {tags['status']}"
        )
        return
    topics_and_categories = get_categories_from_topics(
        tags["tags"], category_by_topic()
    )
    inserted_data.reference.update({"topics": list(topics_and_categories)})
    print(f"Successfully updated topics for bill with id `{bill_id}`")
    return


# Invert 'TOPICS_BY_CATEGORY' into a dictionary from topics to categories
def category_by_topic() -> dict[str, Category]:
    to_return = {}
    for category, topics in TOPICS_BY_CATEGORY.items():
        for topic in topics:
            to_return[topic] = category
    return to_return
