from store import add_document, search_documents

add_document(
    "dsa_stack",
    "A stack is a linear data structure that follows the LIFO principle."
)

add_document(
    "dsa_queue",
    "A queue is a linear data structure that follows the FIFO principle."
)

results = search_documents("What data structure uses LIFO?")

for result in results:
    print(result)