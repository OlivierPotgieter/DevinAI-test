import os
from typing import List, Tuple

from dotenv import load_dotenv
import requests
import argparse

from logger_utils import log_call
from llm_service import get_service
from email_utils import condense_repetitive_messages

load_dotenv()

SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
llm = get_service()


def fetch_recent_emails(
    query: str = "newer_than:1d",
    labels: List[str] | None = None,
    max_results: int = 10,
) -> Tuple[str, int]:
    url = f"{SERVER_URL}/call_tool"
    args: dict[str, object] = {"query": query, "max_results": max_results}
    if labels:
        args["label_ids"] = labels
    payload = {"name": "list_recent_emails", "arguments": args}
    resp = requests.post(url, json=payload, timeout=30)
    log_call("list_recent_emails", payload, resp.text)
    resp.raise_for_status()
    data = resp.json()
    return data.get("text", ""), int(data.get("count", 0))


def ask_mail_insights(question: str, email_text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that answers questions about the users"
                " recent emails based only on the snippets provided."
            ),
        },
        {"role": "user", "content": f"Emails:\n{email_text}\n\nQuestion: {question}"},
    ]
    answer = llm.chat(messages)
    log_call("llm_chat", {"question": question}, answer)
    return answer


def summarize_with_chunking(question: str, email_text: str, chunk_tokens: int = 3000) -> str:
    words = email_text.split()
    if len(words) <= chunk_tokens:
        return ask_mail_insights(question, email_text)

    partial_summaries: list[str] = []
    for i in range(0, len(words), chunk_tokens):
        chunk = " ".join(words[i : i + chunk_tokens])
        part = ask_mail_insights(question, chunk)
        partial_summaries.append(part)

    combined = "\n".join(partial_summaries)
    return ask_mail_insights(f"Provide a final summary answering: {question}", combined)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Gmail messages")
    parser.add_argument("--query", default="newer_than:1d")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--labels", default="")
    parser.add_argument(
        "--keep-repetitive",
        action="store_true",
        help="Do not collapse repeated subjects",
    )
    parser.add_argument("question", nargs="?", default="Summarize these emails.")
    args = parser.parse_args()

    label_ids = [l for l in args.labels.split(",") if l]
    emails_text, count = fetch_recent_emails(args.query, label_ids, args.max_results)
    if not args.keep_repetitive:
        emails_text = condense_repetitive_messages(emails_text)
    if not emails_text:
        print("No recent emails returned from MCP server.")
        return
    print(f"Found {count} emails matching query.")
    token_estimate = len(emails_text.split())
    print(f"Fetched about {token_estimate} tokens from Gmail snippets.")
    answer = summarize_with_chunking(args.question, emails_text)
    print("\nAnswer:\n")
    print(answer)


if __name__ == "__main__":
    main()
